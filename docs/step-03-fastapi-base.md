# Step 3 — FastAPI Base

## What this component does
The HTTP server — the entry point for everything. Bolna hits `/webhook`, the dashboard hits `/metrics/*` and `/calls`, Railway hits `/health` to know we're alive.

## Why FastAPI over Flask
| Feature | FastAPI | Flask |
|---------|---------|-------|
| Async support | Native `async/await` | Requires extra setup (Quart) |
| Auto API docs | Built-in at `/docs` (Swagger) | Needs Flask-RESTx extension |
| Request validation | Pydantic models auto-validate | Manual or Flask-Marshmallow |
| WebSocket | Built-in | Needs Flask-SocketIO |
| Type hints | First-class citizen | Optional add-on |

For voice AI, **async is non-negotiable**. Our webhook needs to enqueue jobs and return in <100ms. Flask's synchronous default would block the entire server while waiting for Claude API calls.

## How it connects to the rest
- Routes call services (thin layer — no business logic in routes)
- `main.py` lifespan event initializes the database on startup
- WebSocket endpoint (Step 5) will be added to `main.py`
- The webhook route (Step 4) will push to Redis instead of returning directly

## Production reality (Swiggy connection)
Swiggy's Databricks article describes "seamless end-to-end integration of Agent with all systems." Their CRM integration uses structured action-trigger patterns. Our routes are the trigger layer — each endpoint is a trigger point that kicks off a pipeline.

---

## Endpoints

### Health
| Method | Path | Purpose |
|--------|------|---------|
| GET | `/health` | Uptime check — returns DB status. Railway/load balancers hit this. |

### Webhook
| Method | Path | Purpose |
|--------|------|---------|
| POST | `/webhook/` | Receives Bolna events (call_started, user_spoke, call_ended, silence_detected) |

### Metrics
| Method | Path | Purpose |
|--------|------|---------|
| GET | `/metrics/orders` | Order data — filterable by `?date=` and `?city=` |
| GET | `/metrics/revenue` | Revenue data — same filters |
| GET | `/metrics/cancellations` | Cancellation data — same filters |
| GET | `/metrics/cities` | City metadata |
| GET | `/metrics/restaurants` | Restaurant data — filter by city, min_complaints |
| GET | `/metrics/hourly` | Hourly trends — filter by date, city |
| GET | `/metrics/week-comparison` | This week vs last week |
| GET | `/metrics/ceo-summary` | Top 3 metrics for CEO briefing |

### Calls
| Method | Path | Purpose |
|--------|------|---------|
| GET | `/calls/` | Call history — filter by role, limit |
| GET | `/calls/{call_id}` | Single call + its evaluation scores |

### Evaluations
| Method | Path | Purpose |
|--------|------|---------|
| GET | `/evaluations/` | Recent evaluation scores |
| GET | `/evaluations/ab-results` | A/B test results per role per version |
| GET | `/evaluations/anomalies` | Detected anomalies list |

---

## Key Files

### `config.py` — Settings
- All environment variables in one place
- Threshold values for anomaly detection (customizable without code changes)
- CORS origins for frontend dev server
- **Never hardcode secrets** — all sensitive values come from `os.getenv()`

### `main.py` — App Setup
- `lifespan` context manager — runs on startup/shutdown
  - On startup: initializes DB, seeds if empty
  - On shutdown: cleanup
- CORS middleware — allows React frontend to call backend (different ports)
- Router registration — each route file is mounted at its prefix

### `data_service.py` — Query Layer
- Every database query lives here — not in routes
- **Why?** Multiple consumers need the same data: routes, agents, anomaly detection
- Functions return `list[dict]` — easy to serialize to JSON
- `get_top_metrics_for_ceo()` is a specialized query — pre-aggregated for the CEO agent

### Route files — Thin HTTP layer
- Routes only do: parse request -> call service -> return response
- No business logic in routes — that lives in services
- All use FastAPI's `APIRouter()` for modular mounting

---

## Test Results (verified working)

```
GET /health
  → {"status": "healthy", "database": "connected", "version": "1.0.0"}

GET /metrics/ceo-summary
  → {"date": "2026-03-19", "total_orders": 47353, "total_revenue": 16925750.72, "cancellation_rate": 4.67}

POST /webhook/ {"call_id": "test-123", "event": "call_started"}
  → {"status": "accepted", "message": "Event 'call_started' for call test-123 received"}

GET /metrics/orders?date=2026-03-19&city=Mumbai
  → [{"total_orders": 9000, "delivered": 8503, ...}]  (the anomaly! down from ~12000)
```

---

## What breaks if we remove it

| If you remove... | What breaks |
|-----------------|-------------|
| `/health` endpoint | Railway can't check if server is alive, deploys blind |
| `/webhook` route | Bolna has nowhere to send call events. No calls work. |
| CORS middleware | Frontend gets blocked by browser. Dashboard shows nothing. |
| `data_service.py` | Routes would have raw SQL inline — duplication, bugs, untestable |
| Lifespan event | Database doesn't initialize on fresh deploy. Everything 500s. |

## Where we simplified vs production

| Us | Production |
|---|---|
| Single uvicorn process | Gunicorn with multiple workers + nginx reverse proxy |
| SQLite queries in data_service | ORM (SQLAlchemy) or query builder with connection pooling |
| No authentication on endpoints | API keys, OAuth, rate limiting |
| No request logging middleware | Structured logging (JSON) with correlation IDs |
| Auto-docs always on | Docs disabled in production, enabled in staging |

---

## Interview questions

### "Why are your routes so thin?"
**Answer**: "Routes should only handle HTTP concerns — parsing requests and formatting responses. Business logic lives in services, AI reasoning lives in agents. This separation means I can test services independently, swap the HTTP framework without touching logic, and multiple consumers (routes, workers, scheduled jobs) can reuse the same service functions."

### "Why did you choose FastAPI?"
**Answer**: "Three reasons: native async support (critical for voice AI where webhook latency matters), automatic Pydantic validation (catches malformed Bolna payloads before they hit my code), and built-in WebSocket support for the real-time dashboard. Flask could work, but I'd need 3-4 extensions to match what FastAPI gives me out of the box."

### "How does your API design handle scale?"
**Answer**: "The webhook endpoint is designed to be stateless — it just validates and enqueues. The actual processing happens in ARQ workers. This means I can scale the web server and workers independently. Swiggy's Databricks article describes the same pattern: their Model Serving layer handles variable traffic with autoscaling, while the agent processing happens asynchronously."
