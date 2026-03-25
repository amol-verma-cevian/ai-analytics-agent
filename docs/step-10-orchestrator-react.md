# Step 10 — Orchestrator Agent (Claude ReAct Loop)

## What is ReAct?

ReAct = **Rea**soning + **Act**ing. Instead of one question → one answer, the AI loops:

```
THINK → ACT (call tool) → OBSERVE result → THINK again → ACT again → ... → RESPOND
```

### Example

```
User: "How's Mumbai doing?"

Iteration 1:
  THINK: "User wants Mumbai data. Let me check orders first."
  ACT:   get_orders(city="Mumbai")  →  9,000 orders (down from 12,107)

Iteration 2:
  THINK: "Orders dropped 25%. Let me check revenue too."
  ACT:   get_revenue(city="Mumbai")  →  revenue down 27.2%

Iteration 3:
  THINK: "Both dropped. I have enough data to respond."
  RESPOND: "Mumbai had a tough day yesterday — orders fell about 25%
            from around twelve thousand to nine thousand..."
```

The AI **decided** what tools to call. We didn't hardcode "always query orders then revenue." Claude figured out the right sequence based on the question.

### Why is this better than hardcoded logic?

```python
# Hardcoded approach (fragile):
if role == "ceo":
    orders = get_orders()
    revenue = get_revenue()
    return f"Orders: {orders}, Revenue: {revenue}"
# What if CEO asks about restaurants? This breaks.

# ReAct approach (flexible):
# Claude reads the question and decides which tools to call.
# "How's Mumbai?" → calls get_orders + get_revenue
# "Any restaurant issues?" → calls get_restaurants
# "Compare this week to last" → calls get_week_comparison
# Same orchestrator handles ALL questions.
```

## How it connects to the rest
- Worker (Step 4) calls `run_orchestrator()` during the BRIEFING/DRILL_DOWN/FOLLOW_UP states
- Orchestrator receives: user text, role, anomalies, state context
- Calls any of 10 tools to fetch data
- Returns: response text, tool calls log, token count, latency

## Production reality (Swiggy connection)
- Hermes V3: "Agent layer that decides what actions to take — whether to clarify, rewrite, fetch metadata, or execute"
- Databricks article: tested ReAct, Chain-of-Thought, and Meta prompting. "ReAct enhanced decision-making in interactive flows"
- Swiggy also found: "Chain-of-Thought improved step-by-step reasoning but increased response length"

---

## Architecture

```
┌──────────────────────────────────────────────────────┐
│                    ORCHESTRATOR                       │
│                                                      │
│  System Prompt:                                      │
│  ┌────────────────────────────────────────────┐      │
│  │ Role: "You are a voice briefing agent"     │      │
│  │ User role: CEO / Ops / Analyst             │      │
│  │ Anomalies: "ALERT: 4 issues detected..."   │      │
│  │ Freshness: "Data is 4 minutes old"          │      │
│  │ State: BRIEFING, turn 1                     │      │
│  └────────────────────────────────────────────┘      │
│                                                      │
│  User: "How are the numbers today?"                  │
│                    ↓                                  │
│  ReAct Loop:                                         │
│    Claude THINKS → calls get_ceo_summary()           │
│    Claude THINKS → calls get_orders(city="Mumbai")   │
│    Claude THINKS → enough data, RESPONDS             │
│                    ↓                                  │
│  Response: "Good morning. Before the briefing,       │
│   I'm seeing a significant drop in Mumbai..."        │
└──────────────────────────────────────────────────────┘
```

## 10 Available Tools

| Tool | What it does | When Claude uses it |
|------|-------------|-------------------|
| `get_orders` | Order data by date/city | Almost every briefing |
| `get_revenue` | Revenue data by date/city | CEO and analyst queries |
| `get_cancellations` | Cancellation data by date/city | When anomaly flagged or user asks |
| `get_restaurants` | Restaurant performance + complaints | Ops manager queries |
| `get_hourly_trends` | Hourly patterns (lunch/dinner peaks) | Analyst deep dives |
| `get_week_comparison` | This week vs last week | Trend questions |
| `get_ceo_summary` | Top 3 numbers (orders, revenue, cancel rate) | CEO briefings |
| `get_city_info` | City metadata (restaurants, partners) | Context for city comparisons |
| `search_glossary` | Business term definitions (AOV, CSAT...) | When user mentions jargon |
| `search_past_queries` | Find similar past Q&As | To reuse proven approaches |

## Role-Specific System Prompts

| Role | Tone | Length | Focus |
|------|------|--------|-------|
| CEO | Confident, executive | ~75 words (30 sec) | Top 3 metrics, risks, strategic |
| Ops Manager | Direct, operational | ~225 words (90 sec) | City breakdowns, delays, flags |
| Analyst | Precise, data-heavy | Unlimited | Full breakdown, hourly trends |

## Key Design Decisions

### Why max 8 iterations?
Safety limit. If Claude keeps calling tools endlessly (e.g., "let me also check hourly trends for each city..."), we stop at 8 and return what we have. In practice, most responses need 2-4 tool calls.

### Why voice-specific prompt rules?
This response becomes speech. So:
- "About forty-seven thousand" not "47,353"
- No bullet points, no markdown
- Natural speaking rhythm
- Lead with the most important insight

### Why include anomalies in the system prompt?
So Claude **leads with problems**. The system prompt says "if anomalies were detected, mention them prominently at the start." This makes the agent proactive.

---

## Test Results (dry-run, no API key needed)

```
Tool execution:
  CEO Summary: orders=47,353, revenue=16,925,751
  Mumbai orders: 9,000
  High-complaint restaurants: 1
  Glossary search for AOV: correct match (score: 0.195)

System prompt:
  Length: 1,842 chars
  Contains role guidance: YES
  Contains anomalies: YES
  Contains freshness: YES
  Contains conversation state: YES
```

### Multi-LLM Support

The orchestrator supports **both OpenAI and Anthropic**. Set `LLM_PROVIDER` env var:
- `openai` (default) — uses GPT-4o function calling
- `anthropic` — uses Claude tool use

The tool definitions are maintained in OpenAI format and auto-converted to Anthropic format. Same ReAct loop logic, different API calls.

To test with OpenAI:
```bash
export OPENAI_API_KEY="your-key-here"
PYTHONPATH=backend python3 -c "
import asyncio
from app.agents.orchestrator import run_orchestrator
result = asyncio.run(run_orchestrator(
    user_text='How are the numbers today?',
    role='ceo',
    anomalies=[],
    state_context={'current_state': 'BRIEFING', 'turn_count': 1}
))
print(result['response'])
"
```

### Live test results (GPT-4o, March 2026):
```
Briefing test ("How are the numbers today?"):
  Tool calls: 1 (get_ceo_summary)
  Response: Conversational, mentioned anomalies, ~75 words
  Tokens: 2,056 | Latency: 17s

Drill-down test ("Tell me more about Mumbai"):
  Tool calls: 3 (get_orders, get_revenue, get_cancellations — all for Mumbai)
  Response: City-level breakdown with trends
  Tokens: 5,273 | Latency: 21s
```

---

## What breaks if we remove it

| If you remove... | What breaks |
|-----------------|-------------|
| ReAct loop | One-shot response with no data. Claude guesses instead of checking. |
| Tool definitions | Claude can't fetch any data. Responses are hallucinated. |
| Role-specific prompts | CEO gets analyst-level detail dump. Analyst gets CEO-level summary. |
| Anomaly injection in prompt | Agent doesn't lead with problems. Becomes reactive. |
| Voice formatting rules | Response has markdown and exact numbers — sounds robotic when spoken. |
| Max iterations safety | Runaway loop. Infinite API calls. Budget blown. |

## Where we simplified vs production

| Us | Production |
|---|---|
| Single Claude call per iteration | Streaming responses for lower perceived latency |
| 10 tools | Dozens (check inventory, contact restaurant, check promotions) |
| Role passed as string | Role confirmed via multi-step verification |
| System prompt as string template | Prompt from MLflow Prompt Registry with versioning |
| No conversation memory across calls | Persistent memory of past briefings per manager |

---

## Interview questions

### "What is ReAct and why did you use it?"
**Answer**: "ReAct stands for Reasoning and Acting. Instead of one prompt producing one response, the AI loops — it thinks about what data it needs, calls a tool to fetch it, observes the result, and decides if it needs more. I used it because our agent needs different data for different questions. 'How's Mumbai?' needs order data, but 'Any restaurant issues?' needs complaint data. With ReAct, Claude decides the right tool sequence on its own. Swiggy tested ReAct, Chain-of-Thought, and Meta prompting — ReAct won for interactive flows because it handles dynamic, multi-step queries better."

### "How does the orchestrator know what data to fetch?"
**Answer**: "I define 10 tools with descriptions — get_orders, get_revenue, search_glossary, etc. Claude reads the user's question and the tool descriptions, then decides which tools to call and in what order. It's like giving a smart intern access to 10 databases and telling them 'answer this question.' They figure out which databases to check. The key is good tool descriptions — they're the 'menu' Claude reads from."

### "What happens if Claude calls the wrong tool?"
**Answer**: "The ReAct loop is self-correcting. If Claude calls get_orders but gets data that doesn't answer the question, it will recognize that in the next THINK step and call a different tool. The max iterations limit (8) prevents infinite loops, and the final response is based on whatever data was actually retrieved — so even partial data produces a useful response."
