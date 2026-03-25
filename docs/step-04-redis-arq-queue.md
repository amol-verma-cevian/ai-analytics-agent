# Step 4 — Redis + ARQ Job Queue

## What this component does
Decouples the webhook (instant response to Bolna) from the heavy processing (Claude calls, anomaly scans, evaluation). Webhook pushes a job to Redis, returns 200 instantly. A separate ARQ worker picks up the job and does all the work in background.

## Why async matters for voice AI
Bolna expects a response within seconds. Our processing pipeline takes 10-15 seconds (multiple Claude API calls). Without a queue, the webhook times out and the call drops.

```
WITHOUT queue (breaks):
Bolna --> /webhook --> [15 sec of work...] --> Bolna times out

WITH queue (works):
Bolna --> /webhook --> push to Redis --> return 200 (< 100ms)
                              |
                      ARQ worker picks up
                      does 15 sec of work
                      streams result back
```

## How it connects to the rest
- `webhook.py` pushes jobs to Redis queue named `voice_agent`
- `webhook_worker.py` picks up jobs and runs the pipeline
- Later steps fill in the pipeline stubs:
  - Step 7: State machine transitions
  - Step 8: Anomaly scan
  - Step 9: Data freshness check
  - Step 10: Orchestrator ReAct loop
  - Step 11: Role detection + sub-agent routing
  - Step 12: Sentiment detection
  - Step 14: Evaluation scoring
  - Step 15: A/B test recording

## Production reality (Swiggy connection)
Swiggy's Databricks article: "scalable and elastic to handle traffic bursts with low latency at optimal cost." Their Model Serving autoscales from near-zero to hundreds of nodes. Our Redis + ARQ is the same pattern at smaller scale.

---

## How ARQ Works

### The Components

```
┌──────────────┐     ┌─────────┐     ┌──────────────────┐
│ FastAPI Route │ --> │  Redis  │ --> │  ARQ Worker       │
│ (webhook.py) │     │ (queue) │     │ (webhook_worker)  │
│              │     │         │     │                   │
│ Enqueues job │     │ Stores  │     │ Picks up job      │
│ Returns 200  │     │ FIFO    │     │ Runs pipeline     │
│ in < 100ms   │     │         │     │ Updates DB        │
└──────────────┘     └─────────┘     └──────────────────┘
```

### Job Lifecycle

1. Bolna sends POST to `/webhook/`
2. Route creates a job: `redis.enqueue_job("process_webhook", payload)`
3. Redis stores the job in the `voice_agent` queue
4. ARQ worker polls Redis every 500ms
5. Worker picks up job → calls `process_webhook(ctx, payload)`
6. Worker routes to handler based on event type:
   - `call_started` → create DB record, init state
   - `user_spoke` → run full pipeline (orchestrator, evaluation, etc.)
   - `call_ended` → generate summary, send WhatsApp
   - `silence_detected` → prompt user
7. Worker updates DB and dashboard

### Worker Configuration (WorkerSettings)

```python
max_jobs = 10          # 10 concurrent jobs (10 simultaneous calls)
job_timeout = 60       # single job has 60 seconds max
poll_delay = 0.5       # checks Redis every 500ms
queue_name = "voice_agent"  # dedicated queue (not shared)
```

---

## Key Files

### `webhook.py` (modified from Step 3)
- No longer processes inline — just enqueues and returns
- Lazy-initializes Redis pool on first request (avoids startup penalty)
- **Fallback**: if Redis is down, still returns 200 to Bolna (don't let Redis failure cascade to Bolna)

### `webhook_worker.py` (new)
- `process_webhook()` — main entry point, routes by event type
- `_handle_call_started()` — creates call record in DB
- `_handle_user_spoke()` — runs the full processing pipeline (stubs for now)
- `_handle_call_ended()` — finalizes call, triggers summary + WhatsApp
- `_handle_silence()` — returns a gentle prompt
- `WorkerSettings` — ARQ configuration class

---

## Event Handlers

| Event | What the worker does | DB changes |
|-------|---------------------|------------|
| `call_started` | Creates call record | INSERT into `calls` |
| `user_spoke` | Full pipeline → response | UPDATE `calls` (turn count) |
| `call_ended` | Finalize + summary | UPDATE `calls` (ended_at, state) |
| `silence_detected` | Return prompt | None |

---

## Running the Worker

```bash
# Terminal 1: Start the FastAPI server
PYTHONPATH=backend python3 -m uvicorn app.main:app --port 8000

# Terminal 2: Start the ARQ worker
PYTHONPATH=backend python3 -m arq app.workers.webhook_worker.WorkerSettings
```

Both run independently. The server enqueues, the worker processes.

---

## Test Results (verified working)

```
call_started → {'status': 'call_initialized', 'call_id': 'test-789', 'state': 'GREETING'}
user_spoke   → {'status': 'processed', 'response': '[STUB] Received: What are the numbers for today?'}
call_ended   → {'status': 'call_ended', 'call_id': 'test-789'}

DB record after full lifecycle:
  call_id: test-789
  state: CLOSING
  turns: 1
  ended_at: 2026-03-20T18:13:48
```

---

## What breaks if we remove it

| If you remove... | What breaks |
|-----------------|-------------|
| Redis queue | Webhook processes inline → Bolna timeout → call drops |
| Fallback in webhook.py | Redis crash → 500 error → Bolna retries → flood |
| `max_jobs = 10` | Unlimited concurrency → memory exhaustion under load |
| `job_timeout = 60` | Stuck Claude call → worker blocked forever |
| `queue_name = "voice_agent"` | Jobs mix with other apps using same Redis |

## Where we simplified vs production

| Us | Production |
|---|---|
| Redis + ARQ (single worker process) | Kafka / RabbitMQ with auto-scaling consumer groups |
| Single retry on failure | Dead letter queues + circuit breakers + exponential backoff |
| Jobs lost if Redis crashes | Durable message brokers with disk persistence |
| `max_jobs = 10` fixed | Dynamic concurrency based on load |
| No job prioritization | Priority queues (call_started > silence_detected) |

---

## Interview questions

### "Why didn't you just use FastAPI BackgroundTasks?"
**Answer**: "Three reasons. First, if the server crashes mid-processing, the job is lost — Redis persists it. Second, in production with multiple server instances, Redis is shared between them — BackgroundTasks are per-process. Third, ARQ gives me retries, timeouts, and concurrency control out of the box. For a voice AI system where dropped calls mean lost users, reliability of the job pipeline is non-negotiable."

### "Why ARQ over Celery?"
**Answer**: "ARQ is async-native — it uses asyncio, same as FastAPI. Celery uses multiprocessing and has heavier overhead. For our use case (I/O-bound Claude API calls), async is more efficient. ARQ is also simpler to configure — one class vs Celery's broker + backend + beat setup. For a small team or assignment, simplicity wins."

---

## Q&A — Questions I Had During This Step

### Q: "I don't understand ARQ vs Celery — explain simply"

**Restaurant analogy:**

**Celery = hiring one chef per order**

```
Order 1 comes in → hire Chef A → he makes the dish
Order 2 comes in → hire Chef B → he makes the dish
Order 3 comes in → hire Chef C → he makes the dish
```

Each chef takes up space in the kitchen (RAM). Each chef gets their own stove (CPU). 50 orders = 50 chefs. Kitchen gets crowded fast.

Works great when: chefs are actively cooking the whole time (CPU-heavy work like image processing or ML training).

**ARQ = one smart chef who multitasks**

```
Order 1 comes in → Chef puts it in oven, sets timer
Order 2 comes in → while Order 1 bakes, Chef starts prepping Order 2
Order 3 comes in → while 1 bakes and 2 marinates, Chef starts Order 3
Timer rings       → Chef pulls Order 1 out, plates it, goes back to others
```

One chef, one kitchen. He's not standing in front of the oven waiting. He does other things while he waits.

Works great when: most of the time is spent waiting — which is exactly our case.

**Our situation — 95% of the time is waiting:**

```
Send request to Claude API... WAIT 3 seconds... get response
Write to database...          WAIT 5ms...       done
Send to WebSocket...          WAIT 2ms...       done
Send request to Claude API... WAIT 3 seconds... get response (evaluation)
```

We're not doing heavy math. We're sending a message to Claude and sitting around for the answer. So why hire 10 chefs (Celery) when 1 chef who multitasks (ARQ) handles it?

**Why we picked ARQ:**
1. Our work is mostly waiting → one multitasking worker is enough
2. Less setup → 7 lines of config vs 40+ lines
3. Less RAM → 30MB vs 300MB for 10 calls
4. Works with FastAPI → both use the same multitasking system (async/await)

**When would we use Celery instead?**
If we were doing something that keeps the CPU busy the whole time — like resizing 1000 images or training a model. That's like a chef who needs to actively stir the pot for 10 minutes straight. He can't multitask because the work itself never pauses. Then you need multiple chefs (Celery).

### "What happens if Redis goes down?"
**Answer**: "The webhook route has a fallback — it still returns 200 to Bolna so we don't cause a retry flood. The call won't get processed, but it won't crash the system either. In production, you'd add Redis Sentinel or Redis Cluster for high availability, plus a dead letter queue to catch failed jobs."
