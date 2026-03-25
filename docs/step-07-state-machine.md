# Step 7 — Conversation State Machine

## What this component does
Controls the flow of every conversation. Each call moves through defined stages. The state machine knows where the call is, what can happen next, and prevents invalid jumps.

## Why a state machine beats if/else

```python
# if/else approach (breaks at scale):
if greeted and not role_detected:
    detect_role()
elif role_detected and not briefed:
    if anomaly_scanned:
        brief()
    else:
        scan_anomalies()
# ...this gets worse with every new feature

# State machine approach (clean):
machine.transition(State.DRILL_DOWN)  # either works or raises error
```

Benefits:
- **Predictable**: you always know where you are and where you can go
- **Debuggable**: full history of transitions with timestamps and reasons
- **Extensible**: adding a new state = add one entry to TRANSITIONS dict
- **Safe**: invalid jumps are caught immediately, not discovered in production

## The 7 States

```
GREETING → ROLE_DETECTION → ANOMALY_SCAN → BRIEFING
                                              ↓
                                         DRILL_DOWN ←→ FOLLOW_UP
                                              ↓              ↓
                                           CLOSING ←─────────┘
```

| State | What happens here | Who triggers exit |
|-------|------------------|-------------------|
| GREETING | Agent says hello, waits for user | User's first utterance |
| ROLE_DETECTION | Detects CEO/Ops/Analyst from what user says | Claude classifies the role |
| ANOMALY_SCAN | Auto-scans data for anomalies (no user input needed) | Scan completes automatically |
| BRIEFING | Delivers the personalized briefing based on role | User responds |
| DRILL_DOWN | User asks for more detail ("show me Mumbai breakdown") | User asks another question or says done |
| FOLLOW_UP | User asks related but different question | User asks more or says done |
| CLOSING | Wrap up — generate summary, send WhatsApp | Terminal state |

## Allowed Transitions

```
GREETING        → ROLE_DETECTION, CLOSING
ROLE_DETECTION  → ANOMALY_SCAN, CLOSING
ANOMALY_SCAN    → BRIEFING
BRIEFING        → DRILL_DOWN, FOLLOW_UP, CLOSING
DRILL_DOWN      → DRILL_DOWN, FOLLOW_UP, CLOSING  (can loop)
FOLLOW_UP       → DRILL_DOWN, FOLLOW_UP, CLOSING  (can loop)
CLOSING         → (nothing — terminal)
```

Key design choices:
- DRILL_DOWN can loop to itself (user asks "more detail" multiple times)
- Any non-terminal state can go to CLOSING (user can hang up anytime)
- ANOMALY_SCAN can only go to BRIEFING (it's automatic, no branching)

## How it connects to the rest
- Worker (Step 4) creates a state machine on `call_started`
- On each `user_spoke`, worker calls `auto_advance()` to determine next state
- Orchestrator (Step 10) uses `get_context()` to know what the conversation has covered
- Dashboard shows current state per call in the call history table

## Production reality (Swiggy connection)
Swiggy's Databricks article: moved from "hardcoded logic where each intent required manual branching" to "node-based graph execution where different intent handlers are modeled as graph branches." That's exactly what a state machine is — graph-based execution with defined nodes and edges.

Their agentic transition solved: "stateful conversations — enabled persistent memory, allowing the agent to maintain context across multiple turns." Our state machine tracks the full conversation context.

---

## Key Concepts

### auto_advance() — Smart State Detection
Instead of asking the user "what do you want to do?", the machine reads their message and figures out the right state:

```python
# User says "show me more details" → DRILL_DOWN
# User says "thanks, bye" → CLOSING
# User says "what about cancellations?" → FOLLOW_UP
```

It uses signal words to detect intent. This will get smarter when integrated with Claude (Step 10).

### get_context() — State as Input to Claude
The orchestrator needs to know where we are in the conversation. `get_context()` returns everything:

```python
{
    "current_state": "BRIEFING",
    "allowed_transitions": ["DRILL_DOWN", "FOLLOW_UP", "CLOSING"],
    "role": "ops_manager",
    "turn_count": 3,
    "history": [...]
}
```

This context goes into the Claude prompt so the AI knows not to repeat the greeting or re-detect the role.

### State History — Full Audit Trail
Every transition is logged with timestamp and reason. This is critical for:
- Debugging ("why did the agent skip the briefing?")
- Dashboard visualization (show conversation flow)
- Post-call analysis (how many turns in drill-down?)

---

## Test Results

```
Simulated full conversation:
  GREETING → ROLE_DETECTION (user greeted)
  ROLE_DETECTION → ANOMALY_SCAN (role detected as ops_manager)
  ANOMALY_SCAN → BRIEFING (anomaly scan complete)
  BRIEFING → DRILL_DOWN (user wants drill-down)
  DRILL_DOWN → DRILL_DOWN (follow-up question about another topic)
  DRILL_DOWN → CLOSING (user said thanks)

Invalid transition caught:
  "Cannot go from GREETING to BRIEFING. Allowed: ['ROLE_DETECTION', 'CLOSING']"
```

---

## What breaks if we remove it

| If you remove... | What breaks |
|-----------------|-------------|
| State machine entirely | No conversation flow control. Agent might greet twice, skip anomaly scan, or brief before detecting role. |
| ANOMALY_SCAN state | Agent jumps straight to briefing without checking for problems. Misses the proactive alerting feature. |
| Transition validation | Agent can jump to any state — GREETING → CLOSING skips everything. Bugs become silent. |
| State history | Can't debug conversation flow. Dashboard can't show what happened. |
| auto_advance() | Worker must manually decide every transition. Logic leaks into the worker. |

## Where we simplified vs production

| Us | Production |
|---|---|
| In-memory state (dict of machines) | Persistent state in DB or Redis (survives server restart) |
| Signal word detection for auto_advance | Claude-powered intent classification |
| 7 states | Potentially dozens (billing, complaints, menu, scheduling...) |
| Linear-ish flow | Complex branching with parallel states |
| No timeout handling | Auto-close after 5 min silence, auto-escalate after too many turns |

---

## Interview questions

### "Why did you use a state machine for conversations?"
**Answer**: "A state machine gives me predictable, debuggable conversation flow. Every call has defined stages — greeting, role detection, anomaly scan, briefing, drill-down, follow-up, closing. The machine enforces valid transitions so the agent can't accidentally greet twice or skip the anomaly scan. It also provides a full audit trail of every transition with timestamps and reasons. Swiggy moved from hardcoded branching to graph-based execution for the same reason — maintainability and extensibility."

### "How does the state machine interact with the AI?"
**Answer**: "The state machine provides context to Claude via get_context(). Claude knows: 'we're in BRIEFING state, the user is a CEO, we've covered 3 turns, and the allowed next states are DRILL_DOWN, FOLLOW_UP, or CLOSING.' This prevents the AI from going off-track. The AI generates the response content, but the state machine controls the conversation structure. Separation of concerns — the AI handles what to say, the state machine handles when to say it."
