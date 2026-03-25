# Step 11 — Role-Based Router + 3 Sub-Agents

## What this component does

Two things:
1. **Role Detection**: Figures out WHO is calling (CEO, Ops Manager, Analyst) from what they say or their phone number
2. **Role Router**: Sends them to the right specialist sub-agent with a role-specific prompt

## Why multi-agent > single agent with role switching

Think of it like a hospital:
- You *could* have one doctor see everyone
- But a cardiologist, dermatologist, and surgeon each give better answers in their domain
- The **router is the receptionist** — figures out which specialist you need

### The context pollution problem

With a single agent and a role flag:
```
System prompt for CEO includes: "also, here are hourly trend tools,
city comparison tools, distribution analysis tools..."
```
The CEO agent sees tool descriptions it'll never use. This means:
- More tokens (= more cost)
- More confusion (LLM might call the wrong tool)
- Prompt is diluted with irrelevant instructions

With sub-agents:
```
CEO agent sees: get_ceo_summary, get_orders, get_revenue (3 tools)
Analyst sees: all 10 tools (that's what they need)
```
Each agent has a **tight, focused context**.

## How it connects to the rest

```
Bolna webhook → ARQ worker → State Machine advances
                                    ↓
                            ROLE_DETECTION state
                                    ↓
                            detect_role(text, caller_id)
                                    ↓
                            machine.role = "ceo"
                                    ↓
                            ANOMALY_SCAN state
                                    ↓
                            scan_all_anomalies()
                                    ↓
                            BRIEFING state
                                    ↓
                            route_to_agent(role="ceo", ...)
                                    ↓
                            run_orchestrator() with CEO prompt
                                    ↓
                            GPT-4o ReAct loop → response
                                    ↓
                            WebSocket → Dashboard
```

## Production reality (Swiggy connection)

- **Swiggy Databricks**: "distinct agents for each disposition type" — Order Status agent, Refund agent, Complaint agent each had separate prompts and tools
- **Hermes V3**: "charter-based compartmentalization" — each agent had a "charter" defining its scope, boundaries, and allowed actions
- **Production role detection**: Multi-factor (caller ID → known number DB, IVR menu selection, NLP classification). We simplified to keyword matching.

---

## Role Detection: 3 Strategies

| Priority | Strategy | How it works | Confidence |
|----------|----------|-------------|------------|
| 1 | DB lookup | Match caller's phone number → managers table | High |
| 2 | Keyword match | Scan text for role signals ("CEO", "operations", "data breakdown") | Medium |
| 3 | Default | If nothing matches → CEO (shortest, safest response) | Low |

### Why default to CEO?

CEO gets the SHORTEST response (~75 words). If we don't know who someone is, giving them a brief summary is safer than dumping an analyst-level data wall on them.

### Keyword signals (examples)

```
CEO:     "ceo", "executive", "big picture", "how's the business"
Ops:     "operations", "delays", "delivery", "what's broken", "city"
Analyst: "data", "breakdown", "hourly", "trend", "deep dive"
```

---

## The Full Pipeline (now live in webhook_worker.py)

The `_handle_user_spoke()` function is no longer a stub. It now runs:

```
Turn 1: User speaks
  1. State machine auto-advances (GREETING → ROLE_DETECTION)
  2. detect_role() analyzes text + caller_id
  3. State advances (ROLE_DETECTION → ANOMALY_SCAN)
  4. scan_all_anomalies() checks all metrics
  5. State advances (ANOMALY_SCAN → BRIEFING)
  6. route_to_agent() → orchestrator ReAct loop
  7. LLM calls tools, generates response
  8. WebSocket broadcasts to dashboard
  9. DB updated with state + role
```

---

## Test Results

### Role detection accuracy:
```
"I am the CEO, give me a quick update"     → ceo (medium confidence)
"I manage operations for Mumbai and Delhi"  → ops_manager (low confidence)
"I need a detailed data breakdown"          → analyst (high confidence)
"Hello, how are you?"                       → ceo (default, low confidence)
"Check the delivery delays in Bangalore"    → ops_manager (medium confidence)
```

### Full pipeline simulation:
```
State flow: GREETING → ROLE_DETECTION → ANOMALY_SCAN → BRIEFING
Role: CEO (detected via keywords)
Anomalies: 4 found (Mumbai orders, Delhi cancellations, Mumbai revenue, Wok Express)
Agent: GPT-4o called get_ceo_summary, 1 tool call
Response: Mentioned all anomalies, ~75 words, conversational tone
Tokens: 2,244 | Latency: 7.5s
```

---

## What breaks if we remove it

| If you remove... | What breaks |
|-----------------|-------------|
| Role detection | Everyone gets the same prompt. CEO gets analyst-level dump. |
| Router | No role-specific context scoping. All tools visible to all roles. |
| Keyword signals | Can't detect role from speech. Must ask explicitly every time. |
| DB lookup | Known callers have to re-identify every call. Bad UX. |
| Default to CEO | Unknown callers get no response or an error. |
| State machine integration | Pipeline doesn't know when to scan, when to brief, when to route. |

## Where we simplified vs production

| Us | Production |
|---|---|
| Keyword matching for role | NLP classification model fine-tuned on support data |
| 3 roles | Dozens (regional manager, restaurant partner, delivery partner) |
| Same orchestrator, different prompts | Separate agent deployments with different tool sets |
| Default to CEO | Ask user to identify, then remember via caller ID |
| In-memory state machines | Redis-backed state with TTL and crash recovery |

---

## Interview questions

### "Why did you use multi-agent instead of one agent with a role flag?"
**Answer**: "Context scoping. Each role needs different data, different tools, and different response styles. A CEO asking for a 30-second update shouldn't have the orchestrator considering hourly trend tools that only an analyst would use. Separate agents mean focused prompts, lower token costs, and better response quality. This mirrors Swiggy's approach — their Databricks article describes distinct agents per disposition type, each with their own prompt and tool set."

### "How does role detection work?"
**Answer**: "Three-tier strategy. First, we check if the caller's phone number matches a known manager in our database — that's the highest confidence. If not, we do keyword matching on their first utterance — words like 'CEO', 'operations', 'data breakdown' signal different roles. If nothing matches, we default to CEO because it produces the shortest, safest response. In production, you'd add NLP classification as a middle tier."

### "What happens if the role is detected wrong?"
**Answer**: "The response will be mismatched in tone and detail level — a CEO getting an analyst dump, or an analyst getting a brief summary. But it's not catastrophic — the data is still correct. The user can say 'give me more detail' and the drill-down state handles it. In production, you'd add a confirmation step: 'I've identified you as a CEO. Is that correct?' This is one of the simplifications we made."

### "Why didn't you use the OpenAI Agents SDK?"
**Answer**: "I built the orchestrator and role router manually because I wanted to understand the ReAct loop internals — how tool calls work, how the conversation loops, how to handle max iterations. But in production, I'd consider OpenAI's Agents SDK which handles the loop, tool execution, and agent handoffs out of the box. The architecture stays the same — a triage agent detects the role and hands off to a specialist. The SDK just reduces boilerplate. It also provides guardrails (input/output validation) and built-in tracing for debugging multi-agent flows."

### OpenAI Agents SDK — what we'd gain

We built the ReAct loop and role routing manually to demonstrate understanding of the internals. In production, we'd evaluate the OpenAI Agents SDK which provides:
- **Built-in ReAct loops** — no manual `for iteration in range(max_iterations)` needed
- **Agent handoffs** — `Handoff(target=ceo_agent)` instead of our router's if/else
- **`@function_tool` decorator** — auto-converts Python functions to tool schemas (we manually wrote 10 tool definitions)
- **Guardrails** — input/output validation per agent
- **Tracing** — built-in debugging for multi-agent flows

The architecture is identical: Triage Agent → detects role → hands off to CEO/Ops/Analyst Agent → tools → response. The SDK reduces boilerplate but the design pattern is the same.

### User checkpoint
You should be able to explain:
- What multi-agent architecture means (separate agents per role with scoped contexts)
- Why context scoping matters (focused prompts, lower cost, better quality)
- How the router decides which agent to use (detection → routing)
- How this connects to Swiggy's charter-based compartmentalization
