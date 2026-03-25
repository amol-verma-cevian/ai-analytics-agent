# AI Analytics Briefing Agent

An intelligent multi-agent system that provides personalized business analytics briefings based on user roles. Built with FastAPI, React, and OpenAI GPT-4o.

## What It Does

A user (CEO, Operations Manager, or Data Analyst) starts a conversation. The system:

1. **Detects their role** automatically from natural language
2. **Scans for anomalies** proactively before briefing (order drops, cancellation spikes, complaint thresholds)
3. **Routes to a role-specific agent** with tailored tools and response style
4. **Generates a data-grounded briefing** using function calling (ReAct loop with 10 tools)
5. **Evaluates response quality** on 5 dimensions via a separate LLM call
6. **Tracks sentiment** using two-tier detection (rule-based + LLM)
7. **Escalates to human** when needed (4 trigger types)
8. **A/B tests prompt versions** to data-drive improvements

All of this runs in real-time with a live dashboard showing metrics, anomalies, evaluations, and sentiment.

## Architecture

```
User (Text / Voice via Whisper)
          │
          ▼
   ┌─────────────┐        ┌──────────────────┐
   │   FastAPI    │◄──────►│  React Dashboard │
   │  19 endpoints│  WS    │  9 live panels   │
   └──────┬──────┘        └──────────────────┘
          │
   ┌──────▼──────┐
   │ State Machine│  7 states: GREETING → ROLE_DETECTION →
   │ (FSM)       │  ANOMALY_SCAN → BRIEFING → DRILL_DOWN →
   └──────┬──────┘  FOLLOW_UP → CLOSING
          │
   ┌──────▼──────┐
   │ Role Router  │  Detects: CEO / Ops Manager / Analyst
   └──────┬──────┘  Method: DB lookup → keyword match → default
          │
   ┌──────▼──────┐
   │ Anomaly Scan │  Checks: order drops, cancellation spikes,
   └──────┬──────┘  complaint thresholds, data freshness
          │
   ┌──────▼──────┐
   │ ReAct Agent  │  GPT-4o + 10 tools (orders, revenue,
   │ Orchestrator │  cities, restaurants, anomalies, etc.)
   └──────┬──────┘  Role-specific context scoping
          │
   ┌──────▼──────┐
   │ Evaluation   │  5 dimensions (1-3 scale each):
   │ Pipeline     │  accuracy, factual correctness, stability,
   └──────┬──────┘  response style, conversational coherence
          │
   ┌──────▼──────┐
   │  Sentiment   │  Tier 1: Rule-based keywords (free, <1ms)
   │  Detection   │  Tier 2: LLM classification (ambiguous cases)
   └──────┬──────┘
          │
   ┌──────▼──────┐
   │  Escalation  │  Triggers: explicit request, frustrated user,
   │  Engine      │  low AI confidence, too many turns
   └─────────────┘
```

## Tech Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| **Backend** | FastAPI (async Python) | API server, WebSocket, 19 endpoints |
| **LLM** | OpenAI GPT-4o | Function calling, ReAct orchestration |
| **Voice** | OpenAI Whisper | Speech-to-text transcription |
| **Vector DB** | ChromaDB | RAG — business glossary + query history |
| **Queue** | Redis + ARQ | Async job processing (production) |
| **Database** | SQLite | 12 tables, business + system data |
| **Frontend** | React + Vite | SPA with real-time updates |
| **Styling** | TailwindCSS | Utility-first dark theme |
| **Charts** | Recharts | Evaluation scores, A/B test results |
| **Real-time** | WebSocket | Live dashboard updates |

## Key Features

### Multi-Agent Role Routing
Different roles get different experiences:
- **CEO**: Concise 75-word briefing, anomaly-first, high-level metrics
- **Ops Manager**: City-by-city breakdown, operational flags, delivery times
- **Data Analyst**: Full data access, hourly trends, no word limits

### ReAct Orchestrator (10 Tools)
The agent decides what data to fetch based on the conversation:
- `get_orders_summary` — order volume by city/date
- `get_revenue_summary` — revenue and AOV breakdown
- `get_cancellations` — cancellation rates and reasons
- `get_city_info` — city metadata and capacity
- `get_restaurant_performance` — individual restaurant metrics
- `get_hourly_trends` — intraday order patterns
- `get_week_comparison` — week-over-week changes
- `get_ceo_summary` — aggregated executive snapshot
- `get_anomalies` — detected anomalies with severity
- `search_glossary` — RAG lookup for business terms

### Proactive Anomaly Detection
Runs **before** every briefing — the agent finds problems, not just answers questions:
- Order volume drops > 20% (city-level)
- Cancellation rate spikes > 30%
- Restaurant complaint threshold exceeded
- Data staleness warnings

### 5-Dimension Evaluation Pipeline
Every agent response is scored by a **separate** LLM call (avoids self-evaluation bias):
- Accuracy (did it use the right data?)
- Factual Correctness (are the numbers right?)
- Stability (consistent across similar queries?)
- Response Style (matches role expectations?)
- Conversational Coherence (flows naturally?)

### A/B Prompt Testing
- Each role has v1 and v2 prompt configurations
- Random 50/50 assignment per session
- Evaluation scores tracked per version
- Winner declared after 5+ samples
- JSON-based prompt registry for version management

### Escalation Engine (4 Triggers)
| Trigger | Detection | Severity |
|---------|-----------|----------|
| Explicit | "connect me to a human" | High |
| Sentiment | Frustrated user detected | High |
| Confidence | Avg eval score < 1.5/3 | Medium |
| Turn Count | > 8 turns without resolution | Low |

## Quick Start

### Prerequisites
- Python 3.9+
- Node.js 18+
- OpenAI API key

### Setup

```bash
# Clone
git clone https://github.com/amol-verma-cevian/ai-analytics-agent.git
cd ai-analytics-agent

# Backend
cd backend
pip install -r requirements.txt
export OPENAI_API_KEY="your-key-here"
python -m uvicorn app.main:app --port 8000

# Frontend (new terminal)
cd frontend
npm install
npm run dev
```

Open **http://localhost:5173**

### Try It
1. Click **"New Session"** in the Chat panel
2. Type: `I am the CEO`
3. Type: `What about Mumbai specifically?`
4. Type: `connect me to a real person` (triggers escalation)

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Health check |
| POST | `/webhook/` | Conversation event intake |
| GET | `/metrics/orders` | Order data |
| GET | `/metrics/revenue` | Revenue data |
| GET | `/metrics/cancellations` | Cancellation data |
| GET | `/metrics/cities` | City metadata |
| GET | `/metrics/restaurants` | Restaurant performance |
| GET | `/metrics/hourly` | Hourly trends |
| GET | `/metrics/week-comparison` | Week-over-week comparison |
| GET | `/metrics/ceo-summary` | Aggregated executive summary |
| GET | `/calls/` | Session history |
| GET | `/evaluations/` | Evaluation scores |
| GET | `/evaluations/ab-results` | A/B test results |
| GET | `/evaluations/anomalies` | Detected anomalies |
| GET | `/evaluations/escalations` | Escalation events |
| GET | `/evaluations/prompts` | Prompt registry |
| POST | `/chat/start` | Start chat session |
| POST | `/chat/message` | Send message |
| POST | `/chat/end` | End chat session |
| POST | `/voice/transcribe` | Whisper voice-to-text |

## Project Structure

```
├── backend/
│   ├── app/
│   │   ├── agents/           # LLM orchestration layer
│   │   │   ├── orchestrator.py   # ReAct loop + 10 tools
│   │   │   ├── role_router.py    # Role detection + routing
│   │   │   ├── sentiment.py      # Two-tier sentiment detection
│   │   │   └── evaluation.py     # 5-dimension scoring
│   │   ├── models/           # Database + schemas
│   │   │   ├── database.py       # SQLite (12 tables)
│   │   │   ├── schemas.py        # Pydantic models
│   │   │   └── seed_data.py      # Mock business data
│   │   ├── routes/           # API endpoints
│   │   ├── services/         # Business logic
│   │   │   ├── anomaly_service.py    # Proactive anomaly detection
│   │   │   ├── fallback_service.py   # Escalation engine
│   │   │   ├── ab_test_service.py    # A/B prompt testing
│   │   │   ├── prompt_registry.py    # Version management
│   │   │   └── data_service.py       # Data access layer
│   │   ├── rag/              # ChromaDB vector search
│   │   ├── state/            # Conversation state machine
│   │   └── workers/          # Async job processing
│   └── requirements.txt
├── frontend/
│   └── src/
│       ├── components/       # 10 React components
│       ├── hooks/            # WebSocket hook
│       └── services/         # API client
├── tests/
│   └── test_integration.py   # 22 passing tests
├── Dockerfile
└── README.md
```

## Design Decisions

| Decision | Rationale |
|----------|-----------|
| Separate agent per role | Context scoping — CEO needs 75 words, analyst needs everything |
| State machine over free-form | Predictable flow, prevents skipping anomaly scan |
| Two-tier sentiment | 70% caught by free rules, LLM only for ambiguous cases |
| Independent evaluation LLM call | Self-evaluation is biased; separate call is objective |
| A/B testing with registry | "Make prompt better" is subjective; scores are data |
| Proactive anomaly detection | Push AI > Pull AI — system finds issues before user asks |
| Text-first + voice optional | Demos anywhere; voice is Whisper add-on, not requirement |

## Docker

```bash
docker build -t ai-analytics-agent .
docker run -p 8000:8000 -e OPENAI_API_KEY=sk-your-key ai-analytics-agent
```

## Integration Tests

```bash
# Start backend first, then:
python tests/test_integration.py

# Result: 22 passed, 0 failed
```

## License

MIT
