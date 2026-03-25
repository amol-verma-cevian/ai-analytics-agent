# Steps 14 & 15 — Evaluation Agent + A/B Prompt Testing

## Step 14: Evaluation Agent (7 Dimensions)

### What it does
After every agent response, a **separate LLM call** scores the response across 7 dimensions. This is quality control — measurable, not vibes.

### The 7 dimensions

| # | Dimension | Scale | What it catches |
|---|-----------|-------|-----------------|
| 1 | Accuracy | 1-3 | Did agent answer the right question? |
| 2 | Factual Correctness | 1-3 | Are numbers correct vs tool data? |
| 3 | Stability | 1-3 | Would same question get same answer? |
| 4 | Response Style | 1-3 | Is tone/length right for the role? |
| 5 | Conversational Coherence | 1-3 | Does it fit the conversation state? |
| 6 | Cost | tokens | How expensive was this response? |
| 7 | Latency | ms | How long did the user wait? |

Dimensions 1-5 are **LLM-scored**. Dimensions 6-7 are **measured directly**.

### Why a separate LLM call?
You don't ask the student to grade their own exam. The evaluation agent has different instructions (objective scoring, not response generation). This keeps evaluation independent.

### Swiggy connection
- **Databricks article**: These exact 7 dimensions. They used MLflow to track scores and detect degradation over time.
- The evaluation is also the **input to the fallback system** — avg score below 1.5 triggers human escalation (Step 13).

### Test Results
```
CEO briefing scored by GPT-4o:
  Accuracy:       2/3  (user asked "numbers", agent jumped to alerts)
  Factual:        3/3  (numbers matched tool data exactly)
  Stability:      3/3  (consistent, repeatable)
  Style:          3/3  (CEO-appropriate, concise)
  Coherence:      2/3  (slightly mismatched the broad "numbers" query)
  AVG:            2.6/3
  Tokens:         2,244
  Latency:        7,500ms

The evaluator correctly identified subtle issues (accuracy vs coherence)
while giving high marks for factual correctness and style.
```

---

## Step 15: A/B Prompt Testing

### What it does
Each role has v1 and v2 prompts. On each call, randomly assign one, track scores, surface the winner.

### How it works
```
Call comes in → assign random v1 or v2
             → agent uses that prompt version
             → evaluation scores tagged with version
             → dashboard shows which version wins
             → "Promote to production" = make winner the default
```

### Prompt versions

| Role | v1 | v2 |
|------|----|----|
| CEO | "Lead with anomalies, ~75 words" | "Numbers only, ~50 words" |
| Ops | "City-by-city breakdown, ~225 words" | "Only problem cities, ~150 words" |
| Analyst | "Full breakdown with hourly" | "Structured: metric→value→change→insight" |

### Statistical validity
We require **5+ samples per version** before declaring a winner. This prevents "v2 got one 3/3 score so it wins!" premature conclusions. In production, you'd use statistical significance tests (chi-squared or Thompson sampling).

### Swiggy connection
- **Databricks article**: "MLflow Prompt Registry with versioning" — same pattern, but they used MLflow to store/retrieve prompt versions and track experiments.

---

## How they connect to the pipeline

```
User speaks → Agent generates response
                    ↓
          assign_prompt_version() → "v2"
                    ↓
          route_to_agent(prompt_version="v2")
                    ↓
          Agent responds (using v2 prompt style)
                    ↓
          evaluate_response() → {accuracy: 3, factual: 3, ...}
                    ↓
          record_ab_result(role="ceo", version="v2", score=2.8)
                    ↓
          check_escalation(eval_score=2.8) → no escalation
                    ↓
          WebSocket → dashboard shows scores + A/B results
```

---

## What breaks if we remove it

| If you remove... | What breaks |
|---|---|
| Evaluation agent | No quality measurement. Flying blind. |
| 7 dimensions | One score hides problems (high accuracy but wrong tone). |
| Separate LLM call | Agent grades itself — always says "I did great." |
| A/B testing | Can't objectively improve prompts. Subjective "feels better." |
| Minimum sample requirement | Premature winner declaration from 1-2 data points. |
| DB storage | No historical trend. Can't detect prompt degradation over time. |

## Where we simplified vs production

| Us | Production |
|---|---|
| Same LLM evaluates | Separate evaluation model (cheaper, calibrated) |
| 50/50 random split | Multi-armed bandit or Thompson sampling |
| 5-sample minimum | Statistical significance testing (p < 0.05) |
| 2 versions per role | Dozens of versions tested simultaneously |
| JSON prompt config | MLflow Prompt Registry with versioning + rollback |
| Score stored in SQLite | MLflow experiment tracking with dashboards |

---

## Interview questions

### "How do you evaluate your agent's responses?"
**Answer**: "Seven dimensions, borrowed from Swiggy's Databricks article: Accuracy, Factual Correctness, Stability, Response Style, Conversational Coherence — all scored 1-3 by a separate evaluation LLM call — plus Cost (tokens) and Latency (ms) measured directly. The key is using a separate evaluation agent, not asking the same agent to grade itself. The average score feeds into the fallback system — below 1.5 triggers human escalation."

### "How does your A/B testing work?"
**Answer**: "Each call gets randomly assigned v1 or v2 of the prompt for that role. The evaluation scores are tagged with the version. After enough samples — at least 5 per version — we can declare a winner. The dashboard shows the comparison. In production, you'd use MLflow Prompt Registry and Thompson sampling instead of random assignment, but the principle is the same: measure, don't guess."

### "What if the evaluation LLM disagrees with a human reviewer?"
**Answer**: "That's expected — and it's why you need both. The LLM evaluation catches obvious issues at scale (wrong numbers, wrong tone). Human review catches subtle issues (the response was technically correct but missed the implied question). In production, you'd periodically sample evaluations for human review and use the disagreement rate to calibrate the evaluation prompt. Swiggy did this with their human-in-the-loop system."

### User checkpoint (from project requirements)
You should be able to explain:
- What the 7 evaluation dimensions are and why each matters
- Why evaluation uses a separate LLM call (not self-grading)
- How A/B testing objectively improves prompts
- How evaluation feeds into the fallback system
- Connection to Swiggy's MLflow evaluation pipeline
