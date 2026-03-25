"""
Anomaly Detection Service.

Scans business metrics BEFORE every briefing looking for problems:
1. Orders dropped > 20% vs previous day (per city)
2. Cancellations spiked > 30% vs average (per city)
3. Revenue below weekly average (per city)
4. Restaurant complaints above threshold

This is what makes the agent PROACTIVE instead of reactive.
The agent leads with "I found 2 issues" before giving the briefing.

Swiggy connection: Their Hermes V3 scans data before query execution
and flags inconsistencies. Same pattern — check first, alert if needed.
"""

import logging
from datetime import date, timedelta
from typing import Optional

from app.config import settings
from app.models.database import get_connection

logger = logging.getLogger(__name__)


def scan_all_anomalies() -> list[dict]:
    """
    Run all anomaly checks and return detected issues.

    Called by the worker during ANOMALY_SCAN state,
    before every briefing. Results are:
    1. Stored in the anomalies DB table
    2. Broadcast to dashboard via WebSocket
    3. Passed to the orchestrator for the agent to mention
    """
    anomalies = []

    anomalies.extend(check_order_drops())
    anomalies.extend(check_cancellation_spikes())
    anomalies.extend(check_revenue_dips())
    anomalies.extend(check_restaurant_complaints())

    # Store detected anomalies in DB
    if anomalies:
        _store_anomalies(anomalies)

    logger.info(f"[anomaly] Scan complete: {len(anomalies)} anomalies detected")
    return anomalies


def check_order_drops() -> list[dict]:
    """
    Check if any city's orders dropped > threshold vs previous day.

    Why vs previous day (not weekly avg)?
    A sudden drop from yesterday is more actionable than a gradual trend.
    The CEO needs to know "Mumbai broke overnight" not "Mumbai is slightly
    below the 7-day average."
    """
    conn = get_connection()
    today = date.today()
    yesterday = (today - timedelta(days=1)).isoformat()
    day_before = (today - timedelta(days=2)).isoformat()

    yesterday_data = conn.execute(
        "SELECT city, total_orders FROM orders WHERE date = ?", (yesterday,)
    ).fetchall()

    anomalies = []
    for row in yesterday_data:
        city = row["city"]
        yest_orders = row["total_orders"]

        prev = conn.execute(
            "SELECT total_orders FROM orders WHERE date = ? AND city = ?",
            (day_before, city),
        ).fetchone()

        if prev and prev["total_orders"] > 0:
            prev_orders = prev["total_orders"]
            change_pct = ((yest_orders - prev_orders) / prev_orders) * 100

            if change_pct <= -settings.ANOMALY_ORDER_DROP_PCT:
                anomalies.append({
                    "metric": "orders",
                    "city": city,
                    "current_value": yest_orders,
                    "baseline_value": prev_orders,
                    "deviation_pct": round(change_pct, 1),
                    "severity": _classify_severity(abs(change_pct), thresholds=[20, 30, 50]),
                    "message": f"Orders in {city} dropped {abs(round(change_pct, 1))}% "
                               f"({prev_orders:,} → {yest_orders:,})",
                })

    conn.close()
    return anomalies


def check_cancellation_spikes() -> list[dict]:
    """
    Check if any city's cancellations spiked > threshold vs 7-day average.

    Why vs 7-day avg (not previous day)?
    Cancellations are noisier than orders — a single bad day isn't always
    meaningful. A spike vs the weekly average is more reliable.
    """
    conn = get_connection()
    today = date.today()
    yesterday = (today - timedelta(days=1)).isoformat()
    week_ago = (today - timedelta(days=8)).isoformat()

    yesterday_data = conn.execute(
        "SELECT city, total_cancellations FROM cancellations WHERE date = ?",
        (yesterday,),
    ).fetchall()

    anomalies = []
    for row in yesterday_data:
        city = row["city"]
        yest_cancellations = row["total_cancellations"]

        avg_row = conn.execute(
            "SELECT AVG(total_cancellations) as avg_cancel FROM cancellations "
            "WHERE city = ? AND date >= ? AND date < ?",
            (city, week_ago, yesterday),
        ).fetchone()

        if avg_row and avg_row["avg_cancel"] and avg_row["avg_cancel"] > 0:
            avg_cancel = avg_row["avg_cancel"]
            change_pct = ((yest_cancellations - avg_cancel) / avg_cancel) * 100

            if change_pct >= settings.ANOMALY_CANCELLATION_SPIKE_PCT:
                anomalies.append({
                    "metric": "cancellations",
                    "city": city,
                    "current_value": yest_cancellations,
                    "baseline_value": round(avg_cancel, 0),
                    "deviation_pct": round(change_pct, 1),
                    "severity": _classify_severity(change_pct, thresholds=[30, 50, 80]),
                    "message": f"Cancellations in {city} spiked {round(change_pct, 1)}% "
                               f"above 7-day average ({int(avg_cancel)} → {yest_cancellations})",
                })

    conn.close()
    return anomalies


def check_revenue_dips() -> list[dict]:
    """
    Check if any city's revenue is below weekly average by > 15%.

    Revenue dips often follow order drops, but not always.
    A revenue dip without an order drop might mean AOV decreased
    (customers ordering cheaper items).
    """
    conn = get_connection()
    today = date.today()
    yesterday = (today - timedelta(days=1)).isoformat()
    week_ago = (today - timedelta(days=8)).isoformat()

    yesterday_data = conn.execute(
        "SELECT city, gross_revenue FROM revenue WHERE date = ?", (yesterday,)
    ).fetchall()

    anomalies = []
    for row in yesterday_data:
        city = row["city"]
        yest_revenue = row["gross_revenue"]

        avg_row = conn.execute(
            "SELECT AVG(gross_revenue) as avg_rev FROM revenue "
            "WHERE city = ? AND date >= ? AND date < ?",
            (city, week_ago, yesterday),
        ).fetchone()

        if avg_row and avg_row["avg_rev"] and avg_row["avg_rev"] > 0:
            avg_rev = avg_row["avg_rev"]
            change_pct = ((yest_revenue - avg_rev) / avg_rev) * 100

            if change_pct <= -15:
                anomalies.append({
                    "metric": "revenue",
                    "city": city,
                    "current_value": round(yest_revenue, 2),
                    "baseline_value": round(avg_rev, 2),
                    "deviation_pct": round(change_pct, 1),
                    "severity": _classify_severity(abs(change_pct), thresholds=[15, 25, 40]),
                    "message": f"Revenue in {city} dropped {abs(round(change_pct, 1))}% "
                               f"below weekly average",
                })

    conn.close()
    return anomalies


def check_restaurant_complaints() -> list[dict]:
    """
    Check if any restaurant has complaints above threshold in the last 7 days.

    A restaurant with 12 complaints in a week is a red flag — might need
    to be temporarily suspended or investigated.
    """
    conn = get_connection()
    threshold = settings.ANOMALY_COMPLAINT_THRESHOLD

    restaurants = conn.execute(
        "SELECT name, city, complaints_last_7d, avg_rating FROM restaurants "
        "WHERE complaints_last_7d >= ? AND is_active = 1",
        (threshold,),
    ).fetchall()

    anomalies = []
    for row in restaurants:
        severity = "medium" if row["complaints_last_7d"] < 15 else "high"
        anomalies.append({
            "metric": "restaurant_complaints",
            "city": row["city"],
            "current_value": row["complaints_last_7d"],
            "baseline_value": threshold,
            "deviation_pct": round(
                ((row["complaints_last_7d"] - threshold) / threshold) * 100, 1
            ),
            "severity": severity,
            "message": f"{row['name']} ({row['city']}) has {row['complaints_last_7d']} "
                       f"complaints in 7 days (threshold: {threshold}). "
                       f"Rating: {row['avg_rating']}",
        })

    conn.close()
    return anomalies


def _classify_severity(deviation: float, thresholds: list[float]) -> str:
    """
    Classify severity based on deviation percentage.

    thresholds = [low_boundary, high_boundary, critical_boundary]
    Example: [20, 30, 50] means:
      20-30% = medium
      30-50% = high
      50%+   = critical
    """
    if deviation >= thresholds[2]:
        return "critical"
    elif deviation >= thresholds[1]:
        return "high"
    elif deviation >= thresholds[0]:
        return "medium"
    return "low"


def _store_anomalies(anomalies: list[dict]):
    """Persist detected anomalies to DB for dashboard display."""
    conn = get_connection()
    for a in anomalies:
        conn.execute(
            """INSERT INTO anomalies
               (metric, city, current_value, baseline_value, deviation_pct, severity)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (a["metric"], a.get("city"), a["current_value"],
             a["baseline_value"], a["deviation_pct"], a["severity"]),
        )
    conn.commit()
    conn.close()


def format_anomalies_for_agent(anomalies: list[dict]) -> str:
    """
    Format anomalies as text for the Claude prompt.

    The orchestrator includes this in the prompt so the agent
    can lead with the problems before giving the briefing.
    """
    if not anomalies:
        return "No anomalies detected. All metrics are within normal ranges."

    lines = [f"ALERT: {len(anomalies)} anomalie(s) detected:\n"]
    for i, a in enumerate(anomalies, 1):
        severity_icon = {"critical": "!!!", "high": "!!", "medium": "!", "low": ""}.get(a["severity"], "")
        lines.append(f"  {i}. [{a['severity'].upper()}{severity_icon}] {a['message']}")

    return "\n".join(lines)
