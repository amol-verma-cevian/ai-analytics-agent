import sqlite3
import os
from pathlib import Path

DB_PATH = Path(__file__).parent.parent.parent / "data" / "analytics.db"


def get_connection() -> sqlite3.Connection:
    """Get a SQLite connection with row factory for dict-like access."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")  # better concurrent read performance
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    """Create all tables. Safe to call multiple times (IF NOT EXISTS)."""
    conn = get_connection()
    cursor = conn.cursor()

    # --- Business data tables (mock Swiggy-like metrics) ---

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            city TEXT NOT NULL,
            total_orders INTEGER NOT NULL,
            delivered INTEGER NOT NULL,
            avg_delivery_time_mins REAL NOT NULL,
            created_at TEXT DEFAULT (datetime('now'))
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS revenue (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            city TEXT NOT NULL,
            gross_revenue REAL NOT NULL,
            net_revenue REAL NOT NULL,
            avg_order_value REAL NOT NULL,
            created_at TEXT DEFAULT (datetime('now'))
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS cancellations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            city TEXT NOT NULL,
            total_cancellations INTEGER NOT NULL,
            reason TEXT NOT NULL,
            cancellation_rate REAL NOT NULL,
            created_at TEXT DEFAULT (datetime('now'))
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS cities (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            region TEXT NOT NULL,
            active_restaurants INTEGER NOT NULL,
            active_delivery_partners INTEGER NOT NULL,
            population_tier TEXT NOT NULL
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS restaurants (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            city TEXT NOT NULL,
            cuisine TEXT NOT NULL,
            avg_rating REAL NOT NULL,
            total_orders_lifetime INTEGER NOT NULL,
            complaints_last_7d INTEGER NOT NULL,
            avg_prep_time_mins REAL NOT NULL,
            is_active INTEGER DEFAULT 1
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS hourly_trends (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            hour INTEGER NOT NULL CHECK (hour >= 0 AND hour <= 23),
            city TEXT NOT NULL,
            orders INTEGER NOT NULL,
            revenue REAL NOT NULL,
            avg_delivery_time_mins REAL NOT NULL
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS managers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            role TEXT NOT NULL CHECK (role IN ('ceo', 'ops_manager', 'analyst')),
            email TEXT NOT NULL,
            phone TEXT NOT NULL,
            whatsapp TEXT NOT NULL,
            preferred_briefing_time TEXT DEFAULT '09:00',
            is_active INTEGER DEFAULT 1
        )
    """)

    # --- System tables (call logs, evaluations, anomalies, A/B tests) ---

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS calls (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            call_id TEXT NOT NULL UNIQUE,
            manager_id INTEGER REFERENCES managers(id),
            direction TEXT NOT NULL CHECK (direction IN ('inbound', 'outbound')),
            role_detected TEXT,
            state TEXT DEFAULT 'GREETING',
            transcript TEXT DEFAULT '[]',
            sentiment TEXT DEFAULT 'neutral',
            escalated INTEGER DEFAULT 0,
            prompt_version TEXT,
            total_turns INTEGER DEFAULT 0,
            started_at TEXT DEFAULT (datetime('now')),
            ended_at TEXT,
            summary TEXT,
            whatsapp_sent INTEGER DEFAULT 0
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS evaluations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            call_id TEXT NOT NULL REFERENCES calls(call_id),
            turn_number INTEGER NOT NULL,
            accuracy INTEGER NOT NULL CHECK (accuracy BETWEEN 1 AND 3),
            factual_correctness INTEGER NOT NULL CHECK (factual_correctness BETWEEN 1 AND 3),
            stability INTEGER NOT NULL CHECK (stability BETWEEN 1 AND 3),
            response_style INTEGER NOT NULL CHECK (response_style BETWEEN 1 AND 3),
            conversational_coherence INTEGER NOT NULL CHECK (conversational_coherence BETWEEN 1 AND 3),
            token_count INTEGER NOT NULL,
            latency_ms INTEGER NOT NULL,
            prompt_version TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS anomalies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            detected_at TEXT DEFAULT (datetime('now')),
            metric TEXT NOT NULL,
            city TEXT,
            current_value REAL NOT NULL,
            baseline_value REAL NOT NULL,
            deviation_pct REAL NOT NULL,
            severity TEXT NOT NULL CHECK (severity IN ('low', 'medium', 'high', 'critical')),
            acknowledged INTEGER DEFAULT 0
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS ab_test_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            role TEXT NOT NULL,
            prompt_version TEXT NOT NULL,
            call_id TEXT NOT NULL REFERENCES calls(call_id),
            avg_score REAL NOT NULL,
            created_at TEXT DEFAULT (datetime('now'))
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS escalations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            call_id TEXT NOT NULL REFERENCES calls(call_id),
            trigger TEXT NOT NULL CHECK (trigger IN ('explicit', 'sentiment', 'confidence', 'turn_count')),
            severity TEXT NOT NULL CHECK (severity IN ('low', 'medium', 'high')),
            reason TEXT NOT NULL,
            user_text TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS data_freshness (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            metric_name TEXT NOT NULL UNIQUE,
            last_updated TEXT NOT NULL DEFAULT (datetime('now')),
            source TEXT NOT NULL DEFAULT 'mock'
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS prompt_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            role TEXT NOT NULL,
            old_version TEXT NOT NULL,
            new_version TEXT NOT NULL,
            promoted_at TEXT DEFAULT (datetime('now'))
        )
    """)

    conn.commit()
    conn.close()


if __name__ == "__main__":
    init_db()
    print(f"Database initialized at {DB_PATH}")
