"""
Data Freshness Tracker (Step 9).

Tracks when each metric was last updated. The agent tells the user
"this data is 4 minutes old" so they know how current it is.

Why this matters: In enterprise analytics, stale data leads to bad decisions.
If the agent says "orders are 12,000" but the data is 6 hours old,
that number might be meaningless. Transparency builds trust.
"""

from datetime import datetime

from app.models.database import get_connection


def get_freshness_summary() -> dict:
    """
    Get freshness status for all tracked metrics.

    Returns dict with metric name → minutes since last update.
    """
    conn = get_connection()
    rows = conn.execute("SELECT * FROM data_freshness").fetchall()
    conn.close()

    now = datetime.now()
    summary = {}

    for row in rows:
        last_updated = datetime.fromisoformat(row["last_updated"])
        age_minutes = round((now - last_updated).total_seconds() / 60, 1)
        summary[row["metric_name"]] = {
            "last_updated": row["last_updated"],
            "age_minutes": age_minutes,
            "source": row["source"],
            "is_stale": age_minutes > 60,  # stale if older than 1 hour
        }

    return summary


def format_freshness_for_agent() -> str:
    """Format freshness info for the Claude prompt."""
    summary = get_freshness_summary()

    if not summary:
        return "Data freshness: unknown (no tracking data available)"

    max_age = max(m["age_minutes"] for m in summary.values())

    if max_age < 5:
        return f"Data freshness: all metrics updated within the last {int(max_age)} minutes."
    elif max_age < 60:
        return f"Data freshness: most recent update was {int(max_age)} minutes ago."
    else:
        stale = [name for name, m in summary.items() if m["is_stale"]]
        return (f"Data freshness warning: data is {int(max_age)} minutes old. "
                f"Stale metrics: {', '.join(stale)}")


def update_freshness(metric_name: str):
    """Mark a metric as freshly updated (called after data refresh)."""
    conn = get_connection()
    now = datetime.now().isoformat()
    conn.execute(
        "UPDATE data_freshness SET last_updated = ? WHERE metric_name = ?",
        (now, metric_name),
    )
    conn.commit()
    conn.close()
