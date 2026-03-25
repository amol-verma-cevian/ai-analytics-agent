# Steps 8 & 9 — Anomaly Detection + Data Freshness

## What these components do

**Step 8 — Anomaly Detection**: Scans all business metrics BEFORE every briefing, looking for problems. The agent leads with "I found 2 issues" instead of waiting for the user to ask.

**Step 9 — Data Freshness**: Tracks when each metric was last updated. The agent says "this data is 4 minutes old" so the user knows how current it is.

## Why this changes the product fundamentally

This is the difference between **reactive AI** and **proactive AI**:

```
REACTIVE (basic chatbot):
User: "How are numbers today?"
Agent: "Orders are 47,000. Revenue is 16.9M."
User: "Is anything wrong?"
Agent: "Actually yes, Mumbai dropped 25%..."

PROACTIVE (what we build):
User: "How are numbers today?"
Agent: "Before the briefing — I'm seeing two alerts:
        1. Mumbai orders dropped 25% yesterday
        2. Delhi cancellations spiked 35%
        Now here's the full picture..."
```

The CEO doesn't have to know what to ask. The agent tells them what matters.

## How they connect to the rest
- Worker calls `scan_all_anomalies()` during ANOMALY_SCAN state (before briefing)
- Worker calls `format_freshness_for_agent()` to include in the Claude prompt
- Anomalies are stored in DB → displayed on dashboard Panel 5 (Anomaly Feed)
- Anomalies are broadcast via WebSocket → dashboard updates live
- Orchestrator (Step 10) includes anomaly text and freshness text in the prompt

## Production reality (Swiggy connection)
- Swiggy's Hermes V3 scans data before query execution and flags inconsistencies
- Their Databricks article mentions "real-time evaluation of Agent's output" — same proactive pattern
- Data freshness is critical in enterprise: Swiggy tracks "data freshness for each metric" so analysts know if numbers are real-time or delayed

---

## Anomaly Checks (4 types)

| Check | What it detects | Comparison | Threshold |
|-------|----------------|------------|-----------|
| Order drops | City orders fell sharply | Yesterday vs day before | > 20% drop |
| Cancellation spikes | City cancellations surged | Yesterday vs 7-day average | > 30% spike |
| Revenue dips | City revenue below normal | Yesterday vs 7-day average | > 15% dip |
| Restaurant complaints | Restaurant has too many issues | 7-day complaint count | > 8 complaints |

### Why different comparison methods?

- **Orders vs previous day**: A sudden overnight drop is more actionable than a gradual trend. CEO needs to know "Mumbai broke overnight."
- **Cancellations vs 7-day avg**: Cancellations are noisy day-to-day. Weekly average is more reliable for detecting true spikes.
- **Revenue vs 7-day avg**: Same reasoning as cancellations — daily revenue fluctuates with promotions, weather, etc.
- **Complaints as absolute count**: A threshold breach is a threshold breach — doesn't matter what the average was.

### Severity Classification

```
deviation < threshold[0]  → low
threshold[0] to [1]       → medium
threshold[1] to [2]       → high
deviation > threshold[2]  → critical
```

For order drops: 20-30% = medium, 30-50% = high, 50%+ = critical

---

## Test Results

```
Full anomaly scan detected 4 issues:

  [MEDIUM]  Orders in Mumbai dropped 25.7% (12,107 → 9,000)
  [MEDIUM]  Cancellations in Delhi spiked 34.8% above 7-day avg (420 → 567)
  [HIGH]    Revenue in Mumbai dropped 27.2% below weekly average
  [MEDIUM]  Wok Express (Delhi) has 12 complaints in 7 days (threshold: 8)
```

Note: Revenue dip in Mumbai (27.2%) is a **correlated anomaly** — it follows from the order drop. This is realistic. In real data, anomalies cluster.

### Agent-formatted output (what Claude receives):

```
ALERT: 4 anomalie(s) detected:

  1. [MEDIUM!] Orders in Mumbai dropped 25.7% (12,107 → 9,000)
  2. [MEDIUM!] Cancellations in Delhi spiked 34.8% above 7-day avg
  3. [HIGH!!] Revenue in Mumbai dropped 27.2% below weekly average
  4. [MEDIUM!] Wok Express (Delhi) has 12 complaints in 7 days
```

### Data freshness output:
```
Data freshness warning: data is 242 minutes old.
Stale metrics: orders, revenue, cancellations, hourly_trends, restaurant_ratings
```

(Stale because we seeded data hours ago. In production, this would be "4 minutes old".)

---

## What breaks if we remove it

| If you remove... | What breaks |
|-----------------|-------------|
| Anomaly scan | Agent gives flat briefing with no alerts. Misses critical issues. |
| Severity classification | All anomalies look equally important. CEO can't prioritize. |
| `format_anomalies_for_agent()` | Orchestrator doesn't know about anomalies. Agent can't mention them. |
| Freshness tracker | Agent states numbers with no age context. User might act on stale data. |
| `_store_anomalies()` | Dashboard has no anomaly history. Can't show trends in anomaly frequency. |

## Where we simplified vs production

| Us | Production |
|---|---|
| 4 anomaly checks | Dozens (surge pricing triggers, delivery partner shortage, restaurant downtime) |
| Static thresholds in config | ML-based dynamic thresholds that adapt to seasonality |
| Check runs per-call | Background cron checks every 5 minutes, caches results |
| Single severity scale | Multi-dimension severity (impact × urgency × scope) |
| Freshness tracked per table | Freshness tracked per column, per partition, per data source |

---

## Interview questions

### "How does your anomaly detection work?"
**Answer**: "Before every briefing, I run 4 checks: order drops vs previous day, cancellation spikes vs 7-day average, revenue dips vs weekly average, and restaurant complaint thresholds. Each uses a different comparison method — orders use day-over-day because overnight drops need immediate action, while cancellations use 7-day average because they're noisy day-to-day. Detected anomalies are classified by severity, stored in DB, and injected into the Claude prompt so the agent leads with problems."

### "Why is proactive AI better than reactive?"
**Answer**: "A CEO calling for a briefing shouldn't have to know what questions to ask. If Mumbai orders dropped 25% overnight, that's the most important thing — not the overall revenue number. Proactive AI scans for problems first and leads with what matters. Swiggy's evolution from rule-based to agentic AI was partly about this — making the system intelligent enough to surface issues without being asked."

### "How do you handle false positives?"
**Answer**: "Right now, we use static thresholds which can cause false positives — a 21% order drop might just be a slow Monday. In production, you'd use ML-based dynamic thresholds that account for day-of-week, seasonality, and local events. The severity classification helps — a 'medium' anomaly is mentioned but not emphasized, while 'critical' gets top billing. The dashboard also has an 'acknowledged' flag so operators can dismiss false positives."
