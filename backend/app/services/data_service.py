"""
Data service — all SQLite queries live here.

Why a separate service? Routes should be thin (just HTTP parsing).
Multiple consumers need the same data: routes, agents, anomaly detection.
Centralizing queries here means one place to optimize, one place to fix bugs.
"""

from datetime import date, timedelta
from typing import Optional

from app.models.database import get_connection


def get_orders_summary(target_date: Optional[str] = None, city: Optional[str] = None) -> list[dict]:
    """Get order data, optionally filtered by date and city."""
    conn = get_connection()
    query = "SELECT * FROM orders WHERE 1=1"
    params = []

    if target_date:
        query += " AND date = ?"
        params.append(target_date)
    if city:
        query += " AND city = ?"
        params.append(city)

    query += " ORDER BY date DESC, city"
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_revenue_summary(target_date: Optional[str] = None, city: Optional[str] = None) -> list[dict]:
    """Get revenue data, optionally filtered."""
    conn = get_connection()
    query = "SELECT * FROM revenue WHERE 1=1"
    params = []

    if target_date:
        query += " AND date = ?"
        params.append(target_date)
    if city:
        query += " AND city = ?"
        params.append(city)

    query += " ORDER BY date DESC, city"
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_cancellations_summary(target_date: Optional[str] = None, city: Optional[str] = None) -> list[dict]:
    """Get cancellation data, optionally filtered."""
    conn = get_connection()
    query = "SELECT * FROM cancellations WHERE 1=1"
    params = []

    if target_date:
        query += " AND date = ?"
        params.append(target_date)
    if city:
        query += " AND city = ?"
        params.append(city)

    query += " ORDER BY date DESC, city"
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_city_info(city: Optional[str] = None) -> list[dict]:
    """Get city metadata."""
    conn = get_connection()
    if city:
        rows = conn.execute("SELECT * FROM cities WHERE name = ?", (city,)).fetchall()
    else:
        rows = conn.execute("SELECT * FROM cities ORDER BY name").fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_restaurants(city: Optional[str] = None, min_complaints: Optional[int] = None) -> list[dict]:
    """Get restaurant data, optionally filtered."""
    conn = get_connection()
    query = "SELECT * FROM restaurants WHERE is_active = 1"
    params = []

    if city:
        query += " AND city = ?"
        params.append(city)
    if min_complaints is not None:
        query += " AND complaints_last_7d >= ?"
        params.append(min_complaints)

    query += " ORDER BY avg_rating DESC"
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_hourly_trends(target_date: Optional[str] = None, city: Optional[str] = None) -> list[dict]:
    """Get hourly order/revenue trends."""
    conn = get_connection()
    if not target_date:
        target_date = date.today().isoformat()

    query = "SELECT * FROM hourly_trends WHERE date = ?"
    params = [target_date]

    if city:
        query += " AND city = ?"
        params.append(city)

    query += " ORDER BY hour"
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_managers(role: Optional[str] = None) -> list[dict]:
    """Get registered managers, optionally filtered by role."""
    conn = get_connection()
    if role:
        rows = conn.execute(
            "SELECT * FROM managers WHERE role = ? AND is_active = 1", (role,)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM managers WHERE is_active = 1"
        ).fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_week_comparison(city: Optional[str] = None) -> dict:
    """Compare this week vs last week — total orders, revenue, cancellations."""
    conn = get_connection()
    today = date.today()
    this_week_start = (today - timedelta(days=today.weekday())).isoformat()
    last_week_start = (today - timedelta(days=today.weekday() + 7)).isoformat()
    last_week_end = (today - timedelta(days=today.weekday() + 1)).isoformat()

    base_query = "SELECT SUM(total_orders) as orders, COUNT(DISTINCT date) as days FROM orders WHERE date >= ? AND date < ?"
    params_this = [this_week_start, today.isoformat()]
    params_last = [last_week_start, last_week_end]

    if city:
        base_query += " AND city = ?"
        params_this.append(city)
        params_last.append(city)

    this_week = dict(conn.execute(base_query, params_this).fetchone())
    last_week = dict(conn.execute(base_query, params_last).fetchone())

    conn.close()

    this_orders = this_week["orders"] or 0
    last_orders = last_week["orders"] or 1  # avoid division by zero
    change_pct = round(((this_orders - last_orders) / last_orders) * 100, 1)

    return {
        "this_week_orders": this_orders,
        "last_week_orders": last_orders,
        "change_pct": change_pct,
    }


def get_top_metrics_for_ceo() -> dict:
    """CEO gets top 3 metrics: total orders, total revenue, cancellation rate — yesterday."""
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    conn = get_connection()

    orders = conn.execute(
        "SELECT SUM(total_orders) as total FROM orders WHERE date = ?", (yesterday,)
    ).fetchone()
    revenue = conn.execute(
        "SELECT SUM(gross_revenue) as total FROM revenue WHERE date = ?", (yesterday,)
    ).fetchone()
    cancellations = conn.execute(
        "SELECT SUM(total_cancellations) as total FROM cancellations WHERE date = ?", (yesterday,)
    ).fetchone()

    conn.close()

    total_orders = orders["total"] or 0
    total_cancel = cancellations["total"] or 0
    cancel_rate = round((total_cancel / total_orders * 100), 2) if total_orders else 0

    return {
        "date": yesterday,
        "total_orders": total_orders,
        "total_revenue": round(revenue["total"] or 0, 2),
        "cancellation_rate": cancel_rate,
    }
