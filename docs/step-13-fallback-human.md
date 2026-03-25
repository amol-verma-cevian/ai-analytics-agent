# Step 13 — Fallback to Human Agent

## What this component does

When the AI agent fails — wrong data, confused user, or explicit request — gracefully hand off to a human analyst. The system says "Let me connect you" and fires notifications so a human can take over.

## Why this matters

No AI is 100% reliable. Forcing the user to stay in a broken AI loop is terrible UX. The fallback turns a **bad AI experience** into a **good human experience**.

```
WITHOUT fallback:
  User: "This data is wrong"
  Agent: "Let me try again... here are the orders..." (same wrong data)
  User: "No! This is WRONG!"
  Agent: "I apologize, here are the orders..." (still wrong)
  User: *hangs up, never calls again*

WITH fallback:
  User: "This data is wrong"
  [SENTIMENT: frustrated, high confidence → ESCALATE]
  Agent: "I can see this isn't meeting your needs. Let me connect
         you with one of our analysts who can give you a more
         detailed walkthrough. Transferring you now."
  [Slack notification → analyst picks up → problem resolved]
```

## Production reality (Swiggy connection)

- **Databricks article**: "human-in-the-loop design" — low-confidence responses routed to human reviewers
- **Hermes V3**: escalation paths for queries the agent couldn't resolve
- **Production**: Escalation creates a ticket in Jira/Zendesk, sends Slack alert to on-call team, transfers call via telephony API

---

## 4 Escalation Triggers

| Priority | Trigger | Example | Severity |
|----------|---------|---------|----------|
| 1 | **Explicit** | "Connect me to a human" | High |
| 2 | **Sentiment** | Frustrated with high confidence (from Step 12) | High/Medium |
| 3 | **Confidence** | Agent eval score < 1.5 out of 3 (from Step 14) | Medium |
| 4 | **Turn count** | >6 turns without resolution | Low |

### Why this priority order?

- **Explicit** is highest because the user literally asked — always respect that
- **Sentiment** is next because emotional state matters most in voice AI
- **Confidence** catches cases where the AI is technically wrong (user might not realize)
- **Turn count** is a safety net — if we're still going after 6 turns, something's off

### Handoff messages (role-appropriate)

Each trigger gets a different handoff message because the context is different:

```
Explicit:   "Absolutely, let me connect you with a live analyst right away."
             → Respectful, immediate. User asked, we deliver.

Sentiment:  "I can see this isn't quite meeting your needs. Let me connect
             you with an analyst for a more personalized walkthrough."
             → Acknowledges the problem without being defensive.

Confidence: "I want to make sure you get the most accurate information.
             Let me connect you with a senior analyst to verify these numbers."
             → Frames it positively — "we want accuracy" not "I'm failing."

Turn count: "I appreciate your patience. Let me connect you with a team
             member who can help you further."
             → General, professional.
```

---

## How it connects to the pipeline

```
User speaks → ... → Agent responds → Sentiment detection
                                          ↓
                                    check_escalation()
                                          ↓
                    ┌─────────── should_escalate? ───────────┐
                    │ YES                                     │ NO
                    ↓                                         ↓
            handle_escalation()                      Return normal response
                    ↓
            1. Store in escalations table
            2. Mark call as escalated
            3. Broadcast via WebSocket
            4. Return handoff message
            5. (TODO) Slack/email notification
            6. (TODO) Bolna call transfer
```

---

## Test Results

```
Escalation decisions:
  1. Explicit ("connect me to human"):    escalate=True,  trigger=explicit,   severity=high
  2. Sentiment (frustrated, high conf):   escalate=True,  trigger=sentiment,  severity=high
  3. Low eval score (1.2/3.0):            escalate=True,  trigger=confidence, severity=medium
  4. 7+ turns without resolution:         escalate=True,  trigger=turn_count, severity=low
  5. Normal conversation:                 escalate=False, trigger=none
  6. Low-confidence frustration:          escalate=False  (intentional — don't over-escalate)

DB records:
  - Escalations table: 2 records stored correctly
  - Calls table: both marked escalated=1, state=CLOSING
```

---

## What breaks if we remove it

| If you remove... | What breaks |
|---|---|
| Fallback service entirely | Frustrated users stay trapped in AI loop. Terrible UX. |
| Explicit trigger | User says "connect me to human" and agent ignores them. |
| Sentiment trigger | Agent doesn't notice frustration. Keeps repeating bad answers. |
| Confidence trigger | Low-quality answers go unchecked. User gets wrong data. |
| Turn count trigger | Infinite conversation loops. No safety net. |
| Handoff messages | Abrupt transfer with no explanation. Feels broken. |
| DB logging | No escalation history. Can't track escalation rates on dashboard. |

## Where we simplified vs production

| Us | Production |
|---|---|
| Log to DB + WebSocket | Slack alert + email + Jira ticket + PagerDuty |
| Handoff message only | Actual call transfer via Bolna API to human agent |
| 4 trigger types | Dozens (domain-specific triggers, time-based, cost-based) |
| Static thresholds | ML model predicting escalation probability per utterance |
| Single escalation path | Multiple paths: transfer, callback, email follow-up |

---

## Interview questions

### "How does your fallback to human work?"
**Answer**: "Four triggers in priority order: explicit request ('connect me to a human'), sentiment-based (frustrated user from our sentiment detector), confidence-based (agent's evaluation score below threshold), and turn count (conversation exceeding 6 turns). When triggered, we log the escalation, broadcast to the dashboard, and generate a role-appropriate handoff message. In production, this would also fire Slack notifications and transfer the call via telephony API."

### "Why not just always escalate to be safe?"
**Answer**: "Because the whole point of the AI agent is to handle calls autonomously. If we escalate every slightly ambiguous response, we're just an expensive IVR system. The thresholds are tuned to catch genuine failures while letting the AI handle normal conversations. In production, you'd track escalation rate — Swiggy targets under 10%. Too many escalations means the AI needs improvement. Too few means you might be missing frustrated users."

### "How does this connect to Swiggy's human-in-the-loop?"
**Answer**: "Swiggy's Databricks article describes 'human-in-the-loop design' where low-confidence agent responses are routed to human reviewers. Our implementation is the same pattern: the evaluation agent (Step 14) scores every response, and if the average score drops below the threshold, we escalate. The human reviewer can then verify the data, correct any errors, and the interaction is logged back for model improvement. It's a feedback loop — bad AI responses get caught, corrected, and used to make the AI better."
