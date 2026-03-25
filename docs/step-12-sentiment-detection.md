# Step 12 — Sentiment Detection

## What this component does

After every user utterance, classifies their emotional state: **Satisfied**, **Neutral**, or **Frustrated**. If frustrated → raises an escalation flag so the system can adapt (softer tone, offer human handoff).

## Why sentiment matters in voice AI

On a phone call, you can't see the user's face. If a CEO asks the same question 3 times and gets clipped responses, they're frustrated — the agent should recognize this and say "Would you like me to connect you with a live analyst?" instead of repeating the same data.

```
WITHOUT sentiment detection:
  User: "What about Mumbai?"
  Agent: "Mumbai had 9,000 orders..."
  User: "No, I mean what HAPPENED in Mumbai?"
  Agent: "Mumbai had 9,000 orders..."   ← repeating itself, user is angry
  User: "This is useless" → hangs up

WITH sentiment detection:
  User: "What about Mumbai?"
  Agent: "Mumbai had 9,000 orders..."
  User: "No, I mean what HAPPENED in Mumbai?"
  [SENTIMENT: frustrated, repetition detected]
  Agent: "I apologize for the confusion. Let me dig deeper —
         Mumbai orders dropped 25% yesterday compared to the
         day before. Would you like me to investigate the cause,
         or would you prefer I connect you with a live analyst?"
```

## Production reality (Swiggy connection)

- **Databricks article**: "Conversational Coherence" as one of their 7 evaluation dimensions — tracking whether the agent responds appropriately to user mood
- **Hermes V3**: escalation detection to route frustrated users to human support
- **Production systems**: Use dedicated sentiment models (fine-tuned BERT/DistilBERT) instead of LLM calls. Our LLM approach is simpler but works for low-volume.

---

## Two-Tier Architecture

The key design decision: **don't call the LLM for every single utterance**.

### Why two tiers?

```
"Thanks, that's perfect!"      → obviously satisfied (rule catches this)
"This is wrong, connect me"    → obviously frustrated (rule catches this)
"Hmm, I see"                   → ambiguous (need LLM to classify)
```

If we call the LLM every time:
- Cost: ~$0.001 per call × thousands of calls = adds up
- Latency: +1-2 seconds per utterance
- Most utterances are obvious — wasting LLM on "thanks" is pointless

### Tier 1: Rule-based keywords (instant, free)

| Signal type | Keywords |
|---|---|
| Frustration | "wrong", "useless", "connect me to human", "repeat", "already said", "ridiculous" |
| Satisfaction | "great", "thanks", "perfect", "exactly", "helpful", "makes sense" |

If 2+ frustration keywords → frustrated (high confidence)
If 1 frustration + 0 satisfaction → frustrated (medium)
Otherwise → ambiguous, pass to Tier 2

### Tier 1.5: Pattern detection (instant, free)

Two patterns that signal frustration without explicit keywords:

1. **Repetition**: If current utterance has >60% word overlap with recent utterances → user is asking the same thing again
2. **Short clipped responses**: "Fine." "OK." "Sure." after 3+ turns → disengagement

### Tier 2: LLM classification (1-2 seconds, ~100 tokens)

Only for ambiguous cases. Sends a small prompt:

```
Classify the user's emotional state from this phone call utterance.
User said: "I was hoping for something more specific about the trends"
Recent conversation: [previous utterances]

Respond with JSON: {"sentiment": "...", "confidence": "...", "reason": "..."}
```

Uses the same LLM provider as the orchestrator (OpenAI/Anthropic).

---

## Test Results

### Rule-based (Tier 1):
```
"Thanks, that was really helpful and great!"      → satisfied (rule)
"This is wrong and useless, connect me to human"  → frustrated (rule)
"What about Delhi numbers?"                        → ambiguous (→ LLM)
"Can you repeat that? I already said Mumbai"       → frustrated (rule)
"Perfect, exactly what I needed"                   → satisfied (rule)
"OK"                                               → ambiguous (→ LLM)
```

### Full detection:
```
Clear satisfaction: satisfied (rule_based, high)
Clear frustration: frustrated (rule_based, high), should_escalate=True
Repetition pattern: frustrated (pattern, medium), signal=repeated_question
Short clipped "Fine.": frustrated (pattern, low)
Ambiguous → LLM: frustrated (llm, high) — LLM correctly detected subtle frustration
```

---

## How it connects to the pipeline

```
User speaks → State machine → Role detection → Anomaly scan
           → Agent generates response
           → Sentiment detection runs on user's text
                ↓
           sentiment = "frustrated", should_escalate = True
                ↓
           Step 13 (next): trigger fallback to human
                ↓
           WebSocket broadcasts sentiment to dashboard
```

The sentiment result is:
- Stored in the pipeline response
- Broadcast via WebSocket (dashboard can show live sentiment)
- Used by Step 13 for human fallback decisions
- Used by Step 14 for evaluation scoring

---

## What breaks if we remove it

| If you remove... | What breaks |
|---|---|
| Sentiment detection | Agent can't detect frustration. Keeps repeating unhelpful answers. |
| Rule-based tier | Every utterance hits the LLM. 2x cost, 2x latency. |
| Repetition detection | User asking same question 3 times → agent doesn't notice. |
| Short response detection | Disengaged user ("Fine.") → agent keeps talking. |
| LLM tier | Ambiguous cases default to neutral. Misses subtle frustration. |
| Escalation flag | Frustrated user never gets offered human handoff. |

## Where we simplified vs production

| Us | Production |
|---|---|
| Rule-based + LLM classification | Fine-tuned DistilBERT model (~50ms, 99% accuracy) |
| Text-only analysis | Text + audio features (tone, pitch, speech rate) |
| 3 sentiment categories | Granular: angry, confused, impatient, satisfied, delighted |
| Per-utterance | Sliding window of last 3 utterances for trend detection |
| Keyword matching | NLP-based negation handling ("not helpful" vs "helpful") |

---

## Interview questions

### "How does your sentiment detection work?"
**Answer**: "Two-tier system. First, a rule-based keyword check — words like 'wrong', 'useless', 'connect me' signal frustration instantly with zero cost. Second, for ambiguous cases, an LLM classifies the sentiment with conversation history for context. I also detect patterns like repeated questions (60%+ word overlap with recent utterances) and short clipped responses. This hybrid approach handles ~70% of cases with rules and only sends ambiguous cases to the LLM, saving cost and latency."

### "Why not just use the LLM for everything?"
**Answer**: "Cost and latency. 'Thanks, that's perfect' is obviously satisfied — spending a dollar on an LLM call for that is wasteful. The rule-based tier handles obvious cases instantly, and the LLM handles the hard cases where context matters. In production, you'd replace both tiers with a fine-tuned DistilBERT model that does classification in 50ms, but for our scale the hybrid approach works well."

### "How would you add audio-based sentiment?"
**Answer**: "Voice AI has an advantage over text — you can analyze audio features like pitch, speech rate, and volume. A frustrated user speaks faster, louder, with higher pitch. Bolna gives us the transcribed text, but if we had raw audio, we'd run it through a model like wav2vec or Whisper with emotion classification. That would catch cases where the words are neutral but the tone isn't — like a sarcastic 'Great, thanks.'"
