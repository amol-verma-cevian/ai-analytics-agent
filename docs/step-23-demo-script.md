# Step 23 — Demo Script

## How to Demo This Project (5-minute walkthrough)

### Setup (30 seconds)
```bash
cd backend
python3 -m uvicorn app.main:app --port 8000 &
cd ../frontend
npm run dev
```
Open http://localhost:5173

### Demo Flow

#### 1. Dashboard Overview (30 seconds)
"This is a real-time AI analytics dashboard. It monitors business metrics — orders, revenue, cancellations across 6 cities. The top cards show today's snapshot. Everything updates live via WebSocket."

Point out: 4 metric cards, anomaly feed (showing real detected anomalies), evaluation scores chart.

#### 2. Chat with the Agent (2 minutes)
Click **"New Session"** in the Chat panel.

**Message 1**: "Hi, I'm the CEO"
- Show: Role detection happened automatically
- Show: State machine advanced from GREETING → ROLE_DETECTION → BRIEFING
- Show: Agent called data tools and gave a concise briefing (~75 words)
- Show: Metadata bar (role: ceo, state: BRIEFING, sentiment, latency)

**Message 2**: "What about Mumbai specifically?"
- Show: Drill-down — agent used city-specific tools
- Show: Multiple tool calls visible in the metadata
- Show: LiveCallFeed panel updating in real-time

**Message 3**: "This data seems wrong, connect me to a real person"
- Show: Escalation triggered (explicit phrase detection)
- Show: EscalationPanel updated
- Show: Response changes to a handoff message

Click **"End Session"**.

#### 3. Evaluation Pipeline (1 minute)
"Every response is automatically scored on 5 dimensions:
- Accuracy, Factual Correctness, Stability, Response Style, Conversational Coherence
- Each scored 1-3 by a separate LLM call
- This is the same pattern Swiggy uses for their voice agents"

Point to: EvalScores bar chart showing dimension averages.

#### 4. A/B Testing (30 seconds)
"Each role has v1 and v2 prompts. CEO v1 is 75 words, v2 is 50 words. The system randomly assigns versions and tracks which scores higher. After 5+ samples, it declares a winner."

Point to: ABTestResults grouped bar chart.

#### 5. Architecture Deep Dive (30 seconds)
"Under the hood:
- **State machine** with 7 states manages conversation flow
- **RAG pipeline** with ChromaDB for business glossary
- **Anomaly detection** runs before every briefing (proactive AI)
- **Sentiment detection** is two-tier: keywords first, LLM for ambiguous
- **Voice input** supported via OpenAI Whisper API
- Everything is async — FastAPI + Redis queue for production scale"

---

## Quick Interview Answers

**Q: Why not use a single prompt for all roles?**
A: Context scoping. A CEO doesn't need city-level hourly data. An analyst does. Different roles = different tool access + different response styles. This is the same multi-agent architecture Swiggy uses.

**Q: Why evaluate with a separate LLM call?**
A: Self-evaluation is biased. A separate evaluation call with scoring criteria gives objective metrics. This is how Swiggy's Hermes V3 does it — MLflow logs + 7-dimension scoring.

**Q: Why rule-based sentiment before LLM?**
A: Cost optimization. ~70% of sentiments are obvious ("this is useless" = frustrated). Only ambiguous cases go to the LLM. Rules are free, LLM calls cost money.

**Q: Why a state machine instead of just prompting?**
A: Predictability. Without it, the agent might jump from greeting to deep analysis. The state machine ensures: greeting → role detection → anomaly scan → briefing → drill-down → closing. Each state has allowed transitions.

**Q: How would you scale this to production?**
A: PostgreSQL instead of SQLite, Redis for queue, Kubernetes for horizontal scaling, CloudFlare for CDN, Pinecone/Qdrant instead of ChromaDB, proper auth with JWT tokens.

**Q: Why did you build this as a personal project vs using Bolna's SDK?**
A: I wanted to understand every layer — state management, tool orchestration, evaluation — not just wrap an API. Building from scratch shows I can architect AI systems, not just configure them.
