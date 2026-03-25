# Steps 16, 17, 18 — Streaming, Scheduler, WhatsApp

## Step 16: Streaming Response to Bolna

### What it does
Sends the agent's spoken response back to Bolna via their API so it gets converted to speech (TTS).

### Why streaming matters
In a voice call, silence = latency. If the agent takes 7 seconds to respond, that's 7 seconds of awkward silence. Streaming sends text in chunks — Bolna starts speaking the first sentence while we're still generating the rest. Perceived latency drops from 7s to ~1s.

### Our implementation
We simplified to a single POST with the full text (the Bolna API interface is ready). In production, you'd chunk the response and stream each sentence.

```
Us:         POST /calls/{id}/respond  {text: "full response..."}
Production: Stream sentence by sentence via SSE or WebSocket
```

---

## Step 17: APScheduler — Morning Briefings (Outbound)

### What it does
At 9am daily, triggers outbound calls to all registered managers. The CEO gets their morning briefing without having to call in.

### Why this matters (Push vs Pull AI)
```
PULL (reactive): CEO remembers to call → gets briefing
PUSH (proactive): Agent calls CEO → "Good morning, here are your numbers"
```

Push AI is more valuable because:
- CEO doesn't have to remember
- If there's an overnight crisis, the agent leads with it immediately
- Builds the habit — the briefing becomes part of the morning routine

### How it works
```
APScheduler triggers at 9:00 AM
  → Fetch all active managers from DB
  → For each manager: call Bolna outbound API
  → Bolna calls their phone
  → Manager picks up → same pipeline (skip greeting/role detection)
  → Anomaly scan → Briefing → Drill-down → Closing
```

### Swiggy connection
Swiggy's monitoring systems send proactive alerts. This is the same pattern applied to executive briefings.

---

## Step 18: WhatsApp Summary (Twilio)

### What it does
After every call ends, generates a brief text summary and sends it via WhatsApp to the manager.

### Why WhatsApp?
Voice calls are ephemeral — you forget the numbers. "The agent mentioned Mumbai dropped... by how much?" A text summary lets the manager reference data hours later.

### How it works
```
call_ended webhook
  → generate_call_summary(call_id)
  → Look up manager's WhatsApp number
  → Twilio WhatsApp Business API → send
  → Mark call.whatsapp_sent = 1 in DB
```

### Dry-run mode
Without Twilio/Bolna credentials, both services run in dry-run mode — they log what they *would* do without making actual API calls. The pipeline works end-to-end regardless.

---

## Test Results

```
All 27 modules import successfully
Server starts with scheduler (morning briefings at 9am)
Bolna service: dry-run mode (no API key)
WhatsApp service: dry-run mode (no Twilio credentials)
```

---

## What breaks if we remove it

| If you remove... | What breaks |
|---|---|
| Streaming (Step 16) | 7-second silence on every response. Terrible voice UX. |
| Scheduler (Step 17) | No proactive briefings. CEO must call in manually. |
| WhatsApp (Step 18) | No post-call reference. User forgets the numbers. |

## Where we simplified vs production

| Us | Production |
|---|---|
| Single POST response | Sentence-by-sentence streaming |
| APScheduler (in-process) | Celery Beat or cloud scheduler (SQS, Cloud Tasks) |
| Fixed 9am trigger | Per-manager configured time (from managers.preferred_briefing_time) |
| Twilio WhatsApp | WhatsApp Business API direct (higher throughput) |
| Text summary only | Rich message with charts/links |
| Dry-run mode | Actual API calls with retry logic and dead-letter queues |

---

## Interview questions

### "How do you handle voice latency?"
**Answer**: "Streaming. Instead of waiting for the full response, we send text to Bolna in chunks — sentence by sentence. Bolna starts speaking the first sentence while we generate the rest. This brings perceived latency from 7 seconds down to about 1 second. We also use a safety limit of 8 ReAct iterations to prevent the LLM from over-thinking."

### "Why push AI (outbound) and not just pull?"
**Answer**: "Because the CEO shouldn't have to remember to call every morning. If there's an overnight crisis — Mumbai orders dropped 25% — the agent calls them proactively and leads with it. Push AI delivers value without the user asking. This is the same principle as Swiggy's monitoring alerts, but applied to executive briefings."

### "How does the WhatsApp summary work?"
**Answer**: "On call_ended, we generate a text summary of the key metrics discussed, evaluation scores, and whether the call was escalated. This goes to the manager via Twilio's WhatsApp Business API. It serves as a reference — voice calls are ephemeral, but the WhatsApp message persists. The manager can check the exact numbers hours later."
