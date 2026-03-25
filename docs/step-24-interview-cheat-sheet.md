# Step 24 — Interview Cheat Sheet

## Your Project in One Line
"I built an AI analytics briefing agent that detects user roles, fetches business metrics via function calling, evaluates response quality on 5 dimensions, and A/B tests different prompt strategies — all with a real-time React dashboard."

---

## Architecture at a Glance

```
User (Text/Voice)
     │
     ▼
FastAPI Server ─── WebSocket ──→ React Dashboard
     │
     ▼
State Machine (7 states)
     │
     ▼
Role Detection (CEO/Ops/Analyst)
     │
     ▼
Anomaly Scan (proactive alerts)
     │
     ▼
ReAct Agent Loop (GPT-4o + 10 tools)
     │
     ▼
Sentiment Detection (rule + LLM)
     │
     ▼
Evaluation (5 dimensions, 1-3 scale)
     │
     ▼
A/B Test Recording
     │
     ▼
Escalation Check (4 triggers)
```

---

## Key Design Decisions (Why I Did It This Way)

### 1. Multi-Agent vs Single Agent
**Decision**: Separate context per role, not one fat agent.
**Why**: CEO needs 75 words, analyst needs full data. Single prompt would compromise both.
**Swiggy parallel**: Charter-based compartmentalization in Hermes V3.

### 2. State Machine vs Free-form Chat
**Decision**: 7-state finite state machine (GREETING → ROLE_DETECTION → ANOMALY_SCAN → BRIEFING → DRILL_DOWN → FOLLOW_UP → CLOSING).
**Why**: Predictable conversation flow. Without it, agent might skip anomaly scan or never close the call.
**Production reality**: Every voice bot has a state machine. Dialogflow, Rasa, Lex — all use them.

### 3. Two-Tier Sentiment Detection
**Decision**: Rule-based keywords first, LLM only for ambiguous.
**Why**: 70% of sentiments are obvious. Rules cost $0 and <1ms. LLM costs $0.001 and ~2s.
**Tradeoff**: Might miss subtle sarcasm in rule tier. Acceptable — the LLM catches edge cases.

### 4. Separate Evaluation LLM Call
**Decision**: Don't ask the agent to self-evaluate. Use a separate LLM call with scoring criteria.
**Why**: Self-evaluation is biased — an agent will rate itself high. Independent evaluation is objective.
**Swiggy parallel**: 7-dimension evaluation in Databricks article.

### 5. A/B Testing Prompts
**Decision**: Random 50/50 split, track scores per version, declare winner after 5 samples.
**Why**: "Make the prompt better" is subjective. "v2 scores 2.7/3 vs v1's 2.3/3" is data.
**Production improvement**: Multi-armed bandit (Thompson sampling) instead of fixed 50/50.

### 6. Proactive Anomaly Detection
**Decision**: Scan for anomalies BEFORE the briefing, not when asked.
**Why**: "Mumbai orders dropped 25%" is more valuable than "here are today's numbers."
**This is Push AI vs Pull AI**: The agent finds issues, not just answers questions.

### 7. Function Calling (ReAct Loop)
**Decision**: 10 tools the agent can call (orders, revenue, cities, anomalies, etc.)
**Why**: Agent decides WHAT data to fetch based on the user's question. Not hardcoded queries.
**How it works**: LLM returns `tool_calls` → we execute them → send results back → LLM summarizes.

### 8. Text-First + Voice-Optional
**Decision**: Built a chat API. Voice via Whisper is an add-on, not a requirement.
**Why**: Text-first lets you demo anywhere. Voice adds complexity (TTS, latency, noise). The intelligence layer is the same.

---

## Numbers You Should Know

| Metric | Value |
|--------|-------|
| Backend modules | ~25 Python files |
| API endpoints | 19 |
| Database tables | 11 |
| Agent tools | 10 |
| Eval dimensions | 5 (accuracy, factual, stability, style, coherence) |
| Escalation triggers | 4 (explicit, sentiment, confidence, turn_count) |
| State machine states | 7 |
| Dashboard panels | 9 |
| Prompt versions | 2 per role (v1, v2) |
| Roles supported | 3 (CEO, Ops Manager, Analyst) |
| Agent response time | 3-10 seconds (GPT-4o) |
| Integration tests | 22 passing |

---

## Tech Stack

| Layer | Technology | Why |
|-------|-----------|-----|
| Backend | FastAPI (Python) | Async, WebSocket support, auto docs |
| LLM | OpenAI GPT-4o | Function calling, fast, reliable |
| Voice | OpenAI Whisper | Best speech-to-text accuracy |
| Vector DB | ChromaDB | Simple RAG, no infra needed |
| Queue | Redis + ARQ | Async job processing |
| Database | SQLite | Zero-config, embedded |
| Frontend | React + Vite | Fast builds, HMR |
| Styling | TailwindCSS | Utility-first, no CSS files |
| Charts | Recharts | React-native charts |
| Real-time | WebSocket | Bi-directional live updates |

---

## Common Follow-Up Questions

### "How do you handle hallucination?"
1. Tool-based grounding — agent MUST call tools to get data, can't make up numbers
2. RAG from ChromaDB — business glossary provides ground truth
3. Evaluation scoring catches factual errors (factual_correctness dimension)
4. Data freshness tracking — agent warns when data is stale

### "What if the LLM is slow?"
1. Async architecture — webhook returns 200 immediately, processing happens in background
2. Two-tier sentiment — rule-based catches 70% instantly
3. In production: response streaming (word by word), not wait-for-full-response

### "How would you add a new role?"
1. Add keywords to `ROLE_SIGNALS` dict in `role_router.py`
2. Add prompt versions to `prompts.json`
3. Add tool access rules to `build_system_prompt()` in orchestrator
4. No code changes to the pipeline — it's data-driven

### "How is this different from ChatGPT with custom instructions?"
1. **State machine** — controlled conversation flow
2. **Function calling** — agent queries real business data
3. **Evaluation pipeline** — every response scored objectively
4. **A/B testing** — data-driven prompt improvement
5. **Anomaly detection** — proactive, not reactive
6. **Multi-agent routing** — different behavior per role

### "What's the hardest part you built?"
"The worker pipeline in `webhook_worker.py`. Every message goes through 10 stages in sequence — state machine, role detection, anomaly scan, A/B assignment, agent ReAct loop, sentiment detection, evaluation scoring, A/B recording, escalation check, and WebSocket broadcast. Each step's output feeds the next. Getting this right with async Python and proper error handling was the most complex piece."

---

## Resume Bullet Points

- Built an AI analytics briefing agent with multi-role routing (CEO/Ops/Analyst), 10-tool ReAct orchestration via OpenAI GPT-4o, and 5-dimension evaluation pipeline
- Designed a 7-state conversation state machine with proactive anomaly detection, two-tier sentiment analysis, and automated escalation for 4 trigger types
- Implemented A/B prompt testing framework with JSON-based prompt registry, tracking evaluation scores per version to data-drive prompt improvements
- Built a 9-panel React dashboard with real-time WebSocket updates, Recharts visualizations, and interactive chat interface for the AI agent
- Architected async event pipeline using FastAPI + Redis/ARQ, processing conversations through 10 sequential stages from role detection to evaluation scoring
