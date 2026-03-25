# Steps 20-22 — Prompt Registry, Integration Tests, Deployment

## Step 20: Prompt Registry (MLflow-lite)

### What
JSON-based prompt versioning system with:
- `prompts.json` — all prompt versions per role (CEO, Ops, Analyst)
- Version history tracking in DB (`prompt_history` table)
- "Promote to production" — set active version per role
- REST API for viewing, adding, promoting versions

### API Endpoints
| Method | Path | Description |
|--------|------|-------------|
| GET | `/evaluations/prompts` | All versions for all roles |
| GET | `/evaluations/prompts/{role}` | Active version for a role |
| POST | `/evaluations/prompts/{role}/promote` | Promote version |
| POST | `/evaluations/prompts/{role}/add` | Add new version |
| GET | `/evaluations/prompts-history` | Promotion audit trail |

### How It Works
1. Prompts live in `backend/app/prompts.json` (auto-created from defaults)
2. Each role has an `active_version` (default: "v1") and a `versions` dict
3. A/B testing runs v1 vs v2 randomly
4. When v2 wins → promote it → `active_version` becomes "v2"
5. Promotion is logged to `prompt_history` table (audit trail)

### Why Separate From Code?
- Prompts are **config, not code** — they should change without deploys
- Same principle as MLflow Prompt Registry
- Product team can tweak prompts without touching Python

---

## Step 21: Integration Tests

### What
End-to-end test suite (`tests/test_integration.py`) that verifies:
1. Health & infrastructure (DB connection)
2. All 8 data API endpoints (orders, revenue, cities, etc.)
3. All 6 system endpoints (calls, evals, AB results, etc.)
4. Full chat pipeline (start → message → drill down → end)
5. Prompt registry CRUD
6. Anomaly detection data

### Results
```
22 passed, 0 failed, 1 skipped (Whisper needs audio file)
Completed in 15.0s
```

### How to Run
```bash
# Start backend first
cd backend && python3 -m uvicorn app.main:app &

# Run tests
python3 tests/test_integration.py
```

---

## Step 22: Docker Deployment

### Dockerfile
Single container that:
1. Installs Python 3.11 + Node.js 20
2. `pip install` backend dependencies
3. `npm ci && npm run build` frontend
4. Copies built frontend to `backend/static/`
5. FastAPI serves both API and static files

### Build & Run
```bash
# Build
docker build -t ai-analytics-agent .

# Run
docker run -p 8000:8000 \
  -e OPENAI_API_KEY=sk-your-key \
  -e LLM_PROVIDER=openai \
  ai-analytics-agent
```

### Deploy to Railway/Render
```bash
# Railway
railway init
railway up

# Render
# Add Dockerfile, set env vars in dashboard
```

### Environment Variables
| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `OPENAI_API_KEY` | Yes | - | OpenAI API key |
| `LLM_PROVIDER` | No | `openai` | `openai` or `anthropic` |
| `OPENAI_MODEL` | No | `gpt-4o` | Model for agent |
| `REDIS_URL` | No* | `redis://localhost:6379` | For async queue |
| `PORT` | No | `8000` | Server port |

*Redis is only needed for the webhook/queue flow. Chat API works without Redis.

### Architecture in Production
```
┌──────────────┐
│   Browser     │
│  React SPA    │
└──────┬───────┘
       │ HTTP + WebSocket
┌──────▼───────┐
│   FastAPI     │
│  + Static     │
│   Serving     │
└──────┬───────┘
       │
  ┌────┴────┐
  │ SQLite  │  (or PostgreSQL in production)
  └─────────┘
```
