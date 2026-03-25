# Step 1 — Project Structure

## What this component does
The folder structure is the skeleton of the entire system. It determines how code is organized, how teams navigate it, and how easily new features slot in. A bad structure means spaghetti imports, circular dependencies, and confusion about where things live.

## Why we designed it this way
We use a **layered architecture with domain separation**:
- **Backend** follows FastAPI conventions with clear separation: routes (HTTP layer) -> services (business logic) -> models (data) -> agents (AI layer)
- **Frontend** follows React conventions: components -> pages -> hooks -> services
- Each folder has a single responsibility — you should never wonder "where does this go?"

## How it connects to the rest
Every step in the build plan maps to a specific folder. When we build the webhook handler, it goes in `routes/`. When we build the orchestrator agent, it goes in `agents/`. This predictability is what makes a codebase maintainable.

## Production reality (Swiggy connection)
- Swiggy's Hermes used **charter-based compartmentalization** — separate metadata per business unit
- Our `agents/` folder with role-specific sub-agents (CEO, Ops, Analyst) mirrors this pattern
- Swiggy's Databricks article showed they evolved from monolith -> multi-agent with clear functional separation per disposition
- Our structure supports that from day one

---

## Folder Structure

```
voice-analytics-agent/
|
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py                  # FastAPI app, CORS, lifespan, WebSocket
│   │   ├── config.py                # Environment variables, settings
│   │   │
│   │   ├── routes/
│   │   │   ├── __init__.py
│   │   │   ├── webhook.py           # POST /webhook — Bolna calls this
│   │   │   ├── metrics.py           # GET /metrics/* — dashboard data
│   │   │   ├── health.py            # GET /health — uptime check
│   │   │   ├── evaluation.py        # GET /evaluations — scores, A/B results
│   │   │   └── calls.py             # GET /calls — call history, transcripts
│   │   │
│   │   ├── services/
│   │   │   ├── __init__.py
│   │   │   ├── data_service.py      # SQLite queries — orders, revenue, etc.
│   │   │   ├── anomaly_service.py   # Scans metrics for anomalies pre-briefing
│   │   │   ├── freshness_service.py # Tracks data staleness per metric
│   │   │   ├── sentiment_service.py # Claude call to detect user sentiment
│   │   │   ├── evaluation_service.py# 7-dimension scoring via Claude
│   │   │   ├── whatsapp_service.py  # Twilio WhatsApp/SMS post-call summary
│   │   │   ├── ab_test_service.py   # Prompt version routing + score tracking
│   │   │   └── scheduler_service.py # APScheduler — morning outbound calls
│   │   │
│   │   ├── agents/
│   │   │   ├── __init__.py
│   │   │   ├── orchestrator.py      # ReAct loop — routes to sub-agents
│   │   │   ├── role_router.py       # Detects role -> picks sub-agent
│   │   │   ├── ceo_agent.py         # Top 3 metrics, strategic, 30 sec
│   │   │   ├── ops_agent.py         # Delays, flags, city data, 90 sec
│   │   │   ├── analyst_agent.py     # Full breakdown, unlimited, data-heavy
│   │   │   └── fallback.py          # Confidence check -> escalate to human
│   │   │
│   │   ├── models/
│   │   │   ├── __init__.py
│   │   │   ├── database.py          # SQLite connection + table creation
│   │   │   ├── schemas.py           # Pydantic models for request/response
│   │   │   └── seed_data.py         # Populates mock business data
│   │   │
│   │   ├── rag/
│   │   │   ├── __init__.py
│   │   │   ├── glossary.py          # ChromaDB collection 1 — business terms
│   │   │   └── query_history.py     # ChromaDB collection 2 — past queries
│   │   │
│   │   ├── state/
│   │   │   ├── __init__.py
│   │   │   └── machine.py           # Conversation state machine (7 states)
│   │   │
│   │   ├── prompts/
│   │   │   ├── ceo_v1.txt           # CEO prompt version 1
│   │   │   ├── ceo_v2.txt           # CEO prompt version 2
│   │   │   ├── ops_v1.txt
│   │   │   ├── ops_v2.txt
│   │   │   ├── analyst_v1.txt
│   │   │   ├── analyst_v2.txt
│   │   │   ├── orchestrator.txt     # Main orchestrator system prompt
│   │   │   ├── sentiment.txt        # Sentiment detection prompt
│   │   │   └── evaluation.txt       # 7-dimension evaluation prompt
│   │   │
│   │   └── workers/
│   │       ├── __init__.py
│   │       └── webhook_worker.py    # ARQ worker — processes webhook jobs
│   │
│   ├── requirements.txt
│   ├── .env.example
│   └── Dockerfile
│
├── frontend/
│   ├── public/
│   ├── src/
│   │   ├── App.jsx
│   │   ├── main.jsx
│   │   ├── components/
│   │   │   ├── LiveMetrics.jsx      # Panel 1 — orders, revenue, cancellations
│   │   │   ├── EvalRadar.jsx        # Panel 2 — 7-dim radar + factfulness
│   │   │   ├── CallHistory.jsx      # Panel 3 — call table with scores
│   │   │   ├── ABTestResults.jsx    # Panel 4 — v1 vs v2 per role
│   │   │   ├── AnomalyFeed.jsx      # Panel 5 — live anomaly alerts
│   │   │   ├── CostTracker.jsx      # Panel 6 — tokens, cost per call/day
│   │   │   ├── EscalationQueue.jsx  # Panel 7 — fallback-to-human calls
│   │   │   └── HumanReview.jsx      # Panel 8 — low-score response review
│   │   ├── hooks/
│   │   │   └── useWebSocket.js      # WebSocket connection + live updates
│   │   └── services/
│   │       └── api.js               # Axios calls to backend
│   ├── package.json
│   ├── tailwind.config.js
│   └── vite.config.js
│
├── docs/                            # Build guides (you are here)
│   └── step-01-project-structure.md
│
├── .gitignore
├── .env.example
├── docker-compose.yml               # Backend + Redis + Frontend
└── railway.toml                     # Railway deployment config
```

---

## Folder-by-Folder Breakdown

### `backend/app/routes/`
**What**: HTTP endpoints — the entry points where external systems (Bolna, dashboard) talk to our backend.
**Why separate**: Routes should only handle request/response parsing. No business logic here. This keeps endpoints thin and testable.
**Production reality**: Swiggy's webhook integration with their CRM used structured action-trigger integration. Our `/webhook` endpoint is the equivalent entry point.

### `backend/app/services/`
**What**: All business logic lives here — anomaly detection, sentiment analysis, evaluation scoring, A/B routing, scheduling.
**Why separate**: Services are reusable. The anomaly service is called by both the webhook worker (inbound) and the scheduler (outbound). If logic lived in routes, we'd duplicate it.
**Production reality**: Swiggy's evaluation used MLflow 3.0 judges (built-in + custom). Our `evaluation_service.py` mirrors the same 7 dimensions they used.

### `backend/app/agents/`
**What**: The AI brain — orchestrator (ReAct loop), role router, 3 role-specific sub-agents, fallback handler.
**Why separate from services**: Agents call services (to get data) and call Claude (to reason). They're a higher abstraction layer. Separating them means you can swap the AI model without touching business logic.
**Production reality**: Swiggy's Databricks article explicitly describes multi-agent architecture where "a new agent instance is launched for each distinct disposition to enable clear functional separation." Our 3 sub-agents mirror this exactly.

### `backend/app/models/`
**What**: Database schema, connection management, Pydantic validation models, seed data.
**Why separate**: Data layer should be independent. You should be able to swap SQLite for PostgreSQL by changing only `database.py`.
**Production reality**: Swiggy uses Snowflake + Databricks Delta tables. Our SQLite mirrors the same table structure (orders, revenue, cancellations, cities, restaurants) but without distributed scale.

### `backend/app/rag/`
**What**: ChromaDB vector collections — business glossary (AOV, GMV, CSAT definitions) and query history embeddings.
**Why separate**: RAG is a distinct capability. It could be turned off without breaking the core flow. Keeping it isolated makes that possible.
**Production reality**: Swiggy's Hermes used a Knowledge Base + RAG approach with vector-based few-shot retrieval. Their pipeline: metrics retrieval -> table/column retrieval -> few-shot SQL retrieval -> structured prompt. Our RAG folder handles the retrieval part of this pipeline.

### `backend/app/state/`
**What**: Conversation state machine with 7 states (GREETING -> ROLE_DETECTION -> ANOMALY_SCAN -> BRIEFING -> DRILL_DOWN -> FOLLOW_UP -> CLOSING).
**Why separate**: State management is cross-cutting. The orchestrator uses it, the webhook worker initializes it, the dashboard reads it. It needs its own home.
**Production reality**: Swiggy's Databricks article mentions "holistic state management for multi-turn conversations and failure recovery." Their agentic AI transition specifically solved the stateless problem of plain RAG.

### `backend/app/prompts/`
**What**: All LLM prompts stored as versioned text files. Each role has v1 and v2 for A/B testing.
**Why files, not hardcoded**: Prompts change more often than code. Storing them as files means non-engineers can review them, and version control tracks every change.
**Production reality**: Swiggy uses MLflow's Prompt Registry for systematic version tracking. We use files + DB labels — same concept, simpler implementation. Swiggy explicitly called out that "prompt is an area that needs a lot of iterations."

### `backend/app/workers/`
**What**: ARQ worker that processes webhook jobs from the Redis queue.
**Why separate**: Workers run as separate processes. They consume jobs asynchronously. Keeping them isolated means the web server (FastAPI) stays fast — it just enqueues and returns.
**Production reality**: Swiggy uses scalable job processing with Databricks Model Serving + autoscaling. Our Redis + ARQ is the lightweight equivalent.

### `frontend/src/components/`
**What**: 8 dashboard panels — each a self-contained React component.
**Why one component per panel**: Each panel has its own data source, update frequency, and interaction pattern. Isolation means you can add/remove panels without breaking others.
**Production reality**: Swiggy monitors Conversation Quality Score, Completeness Score, Factfulness Score by Hour, and Resolution Efficiency Score. Our panels 2, 3, 6, 7 directly map to these.

---

## How Folders Map to Build Steps

| Folder | Build Steps | Purpose |
|--------|------------|---------|
| `models/` | Step 2-3 | Database schema, mock data, Pydantic models |
| `routes/` | Step 3 | HTTP endpoints — webhook, metrics, health |
| `workers/` | Step 4 | ARQ async job processing |
| `state/` | Step 7 | Conversation state machine |
| `rag/` | Step 6 | ChromaDB glossary + query history |
| `services/` | Steps 8-9, 12-15, 17-18 | All business logic |
| `agents/` | Steps 10-11, 13 | Orchestrator, role router, sub-agents, fallback |
| `prompts/` | Steps 15, 20 | Versioned prompt files for A/B testing |
| `frontend/` | Step 19 | All 8 dashboard panels |

---

## Simplifications vs Production

| What we do | What production looks like | Why we simplified |
|-----------|--------------------------|-------------------|
| Monorepo (backend + frontend together) | Separate repos with CI/CD pipelines | Easier to develop and deploy for assignment |
| Prompts as `.txt` files | MLflow Prompt Registry with version tracking | Same concept, no MLflow dependency |
| Single SQLite database | Snowflake / Databricks Delta tables | Mirrors same table structure without infra overhead |
| Single FastAPI process + ARQ worker | Kubernetes pods with auto-scaling | Railway handles basic scaling for us |
| ChromaDB (in-process) | Dedicated vector DB cluster (Pinecone, Weaviate) | Good enough for our data volume |

---

## Interview question: "Why did you organize the project this way?"

**Answer**: "I used layered architecture with domain separation. Routes handle HTTP only, services contain business logic, agents handle AI reasoning, and models manage data. This mirrors how Swiggy evolved their system — they started with a monolithic LLM pipeline and moved to multi-agent with clear functional separation per disposition. By structuring folders this way from day one, I avoided the refactor they had to do. Each folder maps to a build step, and each service is independently testable."

---

## Q&A — Questions I Had During This Step

### Q: "I don't know ARQ + queue, why is it being used?"

**The Problem: Bolna has a timeout.**

When Bolna sends a webhook to our server (`POST /webhook`), it expects a response fast — within a few seconds. But our system needs to do all of this for each call:

1. Detect the user's role (Claude API call ~1-2s)
2. Scan for anomalies (database queries)
3. RAG retrieval from ChromaDB
4. Generate briefing via orchestrator (Claude API call ~3-5s)
5. Run sentiment detection (another Claude call)
6. Run 7-dimension evaluation (another Claude call)
7. Log everything to DB
8. Push update to dashboard via WebSocket

That's 10-15 seconds of work. If we do all this inside the webhook endpoint, Bolna's request times out and the call drops.

**The Solution: Queue.**

```
WITHOUT queue (breaks):
Bolna --> /webhook --> [15 sec of work...] --> Bolna times out, call drops

WITH queue (works):
Bolna --> /webhook --> push job to Redis --> return 200 OK (instant)
                                |
                        ARQ worker picks up job
                        does all 15 sec of work in background
                        streams response back to Bolna separately
```

The webhook just says "got it" and returns immediately. The real work happens in the background.

**What is Redis + ARQ specifically?**

- **Redis** = an in-memory key-value store. Think of it as a super-fast to-do list that lives in RAM. Jobs go in, workers pull them out.
- **ARQ** = a Python library that uses Redis as a job queue. Like Celery but lightweight. You define worker functions, ARQ handles putting jobs in, pulling them out, retrying on failure, and running multiple jobs concurrently.

```python
# In webhook route — just enqueue and return
@router.post("/webhook")
async def webhook(payload: WebhookPayload):
    await redis.enqueue_job("process_call", payload.dict())
    return {"status": "accepted"}  # instant response

# In worker — does the heavy lifting
async def process_call(ctx, data):
    role = await detect_role(data)
    anomalies = await scan_anomalies()
    briefing = await generate_briefing(role, anomalies)
    await evaluate_response(briefing)
    await send_to_dashboard(briefing)
```

**Why not just use asyncio / FastAPI BackgroundTasks?**

- If the server crashes, the job is lost — Redis persists it
- If you have multiple server instances (production), Redis is shared between them
- ARQ gives you retries, job status tracking, and concurrency control

**Swiggy connection**: Their Databricks article mentions "thousands of concurrent sessions with sub-second latency." They decoupled request intake from processing — same pattern. Their Model Serving + autoscaling is the production version of our Redis + ARQ.

**Simplification vs production**:

| Us | Production |
|---|---|
| Redis + ARQ (single worker) | Kafka / RabbitMQ / SQS with auto-scaling consumers |
| Jobs in memory + Redis persistence | Durable message brokers with guaranteed delivery |
| Single retry policy | Dead letter queues, circuit breakers, backpressure |

---

### Q: "What is /webhook?"

A **webhook** is a URL you give to an external service and say: "When something happens on your end, send an HTTP request to this URL to notify me."

In our case, **Bolna** is the external service. It handles the actual phone call (speech-to-text, text-to-speech). But Bolna doesn't know what to *say* — that's our job.

**The flow:**

```
1. User calls the Bolna phone number
2. Bolna picks up, converts speech to text
3. Bolna sends that text to YOUR server:
   POST https://your-server.com/webhook
   Body: { "caller_id": "+91...", "text": "What are today's numbers?", "event": "user_spoke" }

4. Your server figures out the response (role detection, data fetch, Claude reasoning)
5. Your server responds back to Bolna with what to say
6. Bolna converts that text to speech and speaks it to the caller
```

**Why is it called a "webhook"?**
It's a hook that fires on the web. Bolna "hooks into" your server. You don't call Bolna — Bolna calls *you*. This is the inversion of control pattern.

**Common webhook events from Bolna:**

| Event | When it fires | What we do |
|-------|--------------|------------|
| `call_started` | User dials in | Initialize state machine at GREETING |
| `user_spoke` | User says something | Process through orchestrator, respond |
| `call_ended` | Call hangs up | Generate summary, send WhatsApp, log scores |
| `silence_detected` | User goes quiet | Prompt them or check sentiment |

**Real-world analogy:**
Think of it like a doorbell. You don't keep checking if someone's at the door (that's polling). Instead, you install a doorbell (webhook) and it rings you when someone arrives. Bolna rings `/webhook` every time something happens on the call.

**Webhook vs normal API endpoint:**

```
Normal API:  YOU call someone else's server to get data
             GET https://weather-api.com/today  -->  { "temp": 32 }

Webhook:     SOMEONE ELSE calls YOUR server to give you data
             Bolna --> POST https://your-server.com/webhook  -->  { "text": "..." }
```

---

## Rewrite Plan (Phase 2 — after the system works)

After the full system is built, rewrite these files yourself for deep understanding and interview confidence:

| File | Why this one matters |
|------|---------------------|
| `orchestrator.py` | The ReAct loop — the brain of the system. Interviewers will ask "walk me through how your agent reasons." |
| `role_router.py` | Multi-agent routing — Swiggy's core pattern. "How do you decide which agent handles a query?" |
| `anomaly_service.py` | Data analysis logic — shows you can work with real metrics, not just LLM wrappers. |
| `evaluation_service.py` | 7-dimension scoring — directly from Swiggy's MLflow evaluation. "How do you measure quality?" |
| `machine.py` | State machine — "How do you manage conversation flow?" This is where you show systems thinking. |
