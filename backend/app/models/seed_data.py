"""
Seed the database with realistic mock business data.

The data is designed so that:
- Yesterday has an anomaly: orders dropped ~25% in Mumbai (triggers anomaly detection)
- Cancellations spiked ~35% in Delhi (triggers anomaly detection)
- One restaurant has 12 complaints in 7 days (triggers complaint threshold)
- Week-on-week comparisons show meaningful trends
- Hourly trends show lunch and dinner peaks
"""

import random
from datetime import datetime, timedelta

from app.models.database import get_connection, init_db

CITIES = ["Mumbai", "Delhi", "Bangalore", "Hyderabad", "Chennai", "Pune"]
CUISINES = ["North Indian", "South Indian", "Chinese", "Italian", "Fast Food", "Biryani", "Street Food"]
CANCELLATION_REASONS = [
    "customer_cancelled", "restaurant_closed", "delivery_delayed",
    "wrong_order", "payment_failed", "out_of_stock"
]

RESTAURANTS = [
    ("Bombay Biryani House", "Mumbai", "Biryani"),
    ("Delhi Darbar", "Delhi", "North Indian"),
    ("Meghana Foods", "Bangalore", "Biryani"),
    ("Paradise Restaurant", "Hyderabad", "Biryani"),
    ("Saravana Bhavan", "Chennai", "South Indian"),
    ("Vaishali", "Pune", "South Indian"),
    ("Pizza Palace", "Mumbai", "Italian"),
    ("Wok Express", "Delhi", "Chinese"),
    ("Burger Barn", "Bangalore", "Fast Food"),
    ("Spice Junction", "Hyderabad", "North Indian"),
    ("Madras Cafe", "Chennai", "South Indian"),
    ("Chatkazz", "Pune", "Street Food"),
    ("Royal Tandoor", "Mumbai", "North Indian"),
    ("Green Leaf", "Delhi", "South Indian"),
    ("Noodle House", "Bangalore", "Chinese"),
]


def seed_all():
    """Populate all tables with mock data."""
    init_db()
    conn = get_connection()
    cursor = conn.cursor()

    # Clear existing data
    for table in ["orders", "revenue", "cancellations", "cities",
                  "restaurants", "hourly_trends", "managers",
                  "data_freshness"]:
        cursor.execute(f"DELETE FROM {table}")

    _seed_cities(cursor)
    _seed_managers(cursor)
    _seed_restaurants(cursor)
    _seed_orders(cursor)
    _seed_revenue(cursor)
    _seed_cancellations(cursor)
    _seed_hourly_trends(cursor)
    _seed_data_freshness(cursor)

    conn.commit()
    conn.close()
    print("Database seeded with mock data.")


def _seed_cities(cursor):
    cities_data = [
        ("Mumbai", "West", 4200, 8500, "tier_1"),
        ("Delhi", "North", 3800, 7200, "tier_1"),
        ("Bangalore", "South", 3500, 6800, "tier_1"),
        ("Hyderabad", "South", 2800, 5100, "tier_1"),
        ("Chennai", "South", 2200, 4300, "tier_1"),
        ("Pune", "West", 1800, 3200, "tier_2"),
    ]
    cursor.executemany(
        "INSERT INTO cities (name, region, active_restaurants, active_delivery_partners, population_tier) VALUES (?, ?, ?, ?, ?)",
        cities_data,
    )


def _seed_managers(cursor):
    managers_data = [
        ("Arjun Mehta", "ceo", "arjun@company.com", "+919876543210", "+919876543210", "09:00"),
        ("Priya Sharma", "ops_manager", "priya@company.com", "+919876543211", "+919876543211", "08:30"),
        ("Rahul Verma", "analyst", "rahul@company.com", "+919876543212", "+919876543212", "09:30"),
    ]
    cursor.executemany(
        "INSERT INTO managers (name, role, email, phone, whatsapp, preferred_briefing_time) VALUES (?, ?, ?, ?, ?, ?)",
        managers_data,
    )


def _seed_restaurants(cursor):
    random.seed(42)
    for name, city, cuisine in RESTAURANTS:
        rating = round(random.uniform(3.2, 4.8), 1)
        lifetime_orders = random.randint(5000, 50000)
        # One restaurant gets high complaints to trigger threshold
        complaints = 12 if name == "Wok Express" else random.randint(0, 5)
        prep_time = round(random.uniform(15, 35), 1)
        cursor.execute(
            "INSERT INTO restaurants (name, city, cuisine, avg_rating, total_orders_lifetime, complaints_last_7d, avg_prep_time_mins) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (name, city, cuisine, rating, lifetime_orders, complaints, prep_time),
        )


def _seed_orders(cursor):
    """Generate 14 days of order data. Yesterday Mumbai drops ~25% to trigger anomaly."""
    random.seed(42)
    today = datetime.now().date()

    base_orders = {
        "Mumbai": 12000, "Delhi": 10500, "Bangalore": 9800,
        "Hyderabad": 7500, "Chennai": 6200, "Pune": 4800,
    }

    for days_ago in range(14, -1, -1):
        date = today - timedelta(days=days_ago)
        date_str = date.isoformat()

        for city in CITIES:
            base = base_orders[city]
            # Normal daily variation: +/- 8%
            variation = random.uniform(0.92, 1.08)
            total = int(base * variation)

            # ANOMALY: yesterday Mumbai orders drop 25%
            if days_ago == 1 and city == "Mumbai":
                total = int(base * 0.75)

            delivered = int(total * random.uniform(0.94, 0.98))
            avg_time = round(random.uniform(28, 42), 1)

            cursor.execute(
                "INSERT INTO orders (date, city, total_orders, delivered, avg_delivery_time_mins) VALUES (?, ?, ?, ?, ?)",
                (date_str, city, total, delivered, avg_time),
            )


def _seed_revenue(cursor):
    """Revenue correlates with orders. Yesterday Mumbai revenue also drops."""
    random.seed(43)
    today = datetime.now().date()

    base_aov = {
        "Mumbai": 380, "Delhi": 340, "Bangalore": 420,
        "Hyderabad": 310, "Chennai": 290, "Pune": 350,
    }

    for days_ago in range(14, -1, -1):
        date = today - timedelta(days=days_ago)
        date_str = date.isoformat()

        for city in CITIES:
            aov = base_aov[city] * random.uniform(0.95, 1.05)
            # Pull order count from same logic
            base_orders = {"Mumbai": 12000, "Delhi": 10500, "Bangalore": 9800,
                           "Hyderabad": 7500, "Chennai": 6200, "Pune": 4800}
            order_count = base_orders[city] * random.uniform(0.92, 1.08)
            if days_ago == 1 and city == "Mumbai":
                order_count = base_orders[city] * 0.75

            gross = round(order_count * aov, 2)
            net = round(gross * random.uniform(0.72, 0.78), 2)  # ~25% commission/costs

            cursor.execute(
                "INSERT INTO revenue (date, city, gross_revenue, net_revenue, avg_order_value) VALUES (?, ?, ?, ?, ?)",
                (date_str, city, gross, net, round(aov, 2)),
            )


def _seed_cancellations(cursor):
    """Cancellation data. Yesterday Delhi spikes ~35% to trigger anomaly."""
    random.seed(44)
    today = datetime.now().date()

    base_cancellations = {
        "Mumbai": 480, "Delhi": 420, "Bangalore": 390,
        "Hyderabad": 300, "Chennai": 250, "Pune": 190,
    }

    for days_ago in range(14, -1, -1):
        date = today - timedelta(days=days_ago)
        date_str = date.isoformat()

        for city in CITIES:
            base = base_cancellations[city]
            total = int(base * random.uniform(0.9, 1.1))

            # ANOMALY: yesterday Delhi cancellations spike 35%
            if days_ago == 1 and city == "Delhi":
                total = int(base * 1.35)

            reason = random.choice(CANCELLATION_REASONS)
            order_base = {"Mumbai": 12000, "Delhi": 10500, "Bangalore": 9800,
                          "Hyderabad": 7500, "Chennai": 6200, "Pune": 4800}
            rate = round((total / order_base[city]) * 100, 2)

            cursor.execute(
                "INSERT INTO cancellations (date, city, total_cancellations, reason, cancellation_rate) VALUES (?, ?, ?, ?, ?)",
                (date_str, city, total, reason, rate),
            )


def _seed_hourly_trends(cursor):
    """Hourly data for today and yesterday. Shows lunch (12-14) and dinner (19-21) peaks."""
    random.seed(45)
    today = datetime.now().date()

    for days_ago in [0, 1]:
        date = today - timedelta(days=days_ago)
        date_str = date.isoformat()

        for city in CITIES:
            base = {"Mumbai": 500, "Delhi": 440, "Bangalore": 410,
                    "Hyderabad": 310, "Chennai": 260, "Pune": 200}[city]

            for hour in range(24):
                # Multiplier based on time of day
                if 12 <= hour <= 14:      # lunch peak
                    multiplier = random.uniform(2.2, 2.8)
                elif 19 <= hour <= 21:    # dinner peak
                    multiplier = random.uniform(2.5, 3.2)
                elif 10 <= hour <= 11:    # late morning ramp
                    multiplier = random.uniform(1.3, 1.6)
                elif 15 <= hour <= 18:    # afternoon
                    multiplier = random.uniform(1.0, 1.4)
                elif 7 <= hour <= 9:      # breakfast
                    multiplier = random.uniform(0.8, 1.1)
                else:                     # late night / early morning
                    multiplier = random.uniform(0.1, 0.4)

                orders = int(base * multiplier)
                aov = random.uniform(280, 420)
                revenue = round(orders * aov, 2)
                delivery_time = round(random.uniform(25, 45), 1)

                cursor.execute(
                    "INSERT INTO hourly_trends (date, hour, city, orders, revenue, avg_delivery_time_mins) VALUES (?, ?, ?, ?, ?, ?)",
                    (date_str, hour, city, orders, revenue, delivery_time),
                )


def _seed_data_freshness(cursor):
    """Track when each metric was last updated."""
    now = datetime.now().isoformat()
    metrics = [
        ("orders", now, "mock"),
        ("revenue", now, "mock"),
        ("cancellations", now, "mock"),
        ("hourly_trends", now, "mock"),
        ("restaurant_ratings", now, "mock"),
    ]
    cursor.executemany(
        "INSERT INTO data_freshness (metric_name, last_updated, source) VALUES (?, ?, ?)",
        metrics,
    )


if __name__ == "__main__":
    seed_all()
