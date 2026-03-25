"""
A/B Prompt Testing (Step 15).

Each role has v1 and v2 prompts. On each call, we randomly assign a version,
track evaluation scores per version, and surface the winner on the dashboard.

Why A/B test prompts?
- "Make the prompt better" is subjective
- "v2 scores 2.7/3 vs v1's 2.3/3 across 50 calls" is objective
- Swiggy's Databricks article: "MLflow Prompt Registry with versioning"

How it works:
1. Call comes in → assign random v1 or v2
2. Agent uses that prompt version
3. Evaluation scores are tagged with the version
4. Dashboard shows which version wins per role
5. "Promote to production" = make the winner the default
"""

import random
import logging
from typing import Optional

from app.models.database import get_connection

logger = logging.getLogger(__name__)


# --- Prompt versions per role ---
# In production, these would be stored in MLflow Prompt Registry.
# We keep them in code for simplicity.

PROMPT_VERSIONS = {
    "ceo": {
        "v1": {
            "style_note": "Keep it under 30 seconds. Lead with anomalies.",
            "word_limit": 75,
        },
        "v2": {
            "style_note": "Keep it under 20 seconds. Numbers only, no narrative.",
            "word_limit": 50,
        },
    },
    "ops_manager": {
        "v1": {
            "style_note": "City-by-city breakdown with operational flags.",
            "word_limit": 225,
        },
        "v2": {
            "style_note": "Only mention cities with issues. Skip healthy cities.",
            "word_limit": 150,
        },
    },
    "analyst": {
        "v1": {
            "style_note": "Full data breakdown. Include hourly trends.",
            "word_limit": None,
        },
        "v2": {
            "style_note": "Structured output: metric → value → change → insight.",
            "word_limit": None,
        },
    },
}


def assign_prompt_version(role: str) -> str:
    """
    Randomly assign v1 or v2 for A/B testing.

    50/50 split. In production, you'd use more sophisticated
    strategies: multi-armed bandit, Thompson sampling, etc.
    """
    version = random.choice(["v1", "v2"])
    logger.info(f"[ab_test] Assigned {version} for role {role}")
    return version


def get_prompt_config(role: str, version: str) -> dict:
    """Get the prompt configuration for a role + version combo."""
    role_versions = PROMPT_VERSIONS.get(role, PROMPT_VERSIONS["ceo"])
    return role_versions.get(version, role_versions["v1"])


def record_ab_result(
    role: str,
    prompt_version: str,
    call_id: str,
    avg_score: float,
):
    """Store A/B test result in the database."""
    try:
        conn = get_connection()
        conn.execute(
            """INSERT INTO ab_test_results (role, prompt_version, call_id, avg_score)
               VALUES (?, ?, ?, ?)""",
            (role, prompt_version, call_id, avg_score),
        )
        conn.commit()
        conn.close()
        logger.info(f"[ab_test] Recorded: {role}/{prompt_version} = {avg_score:.2f}")
    except Exception as e:
        logger.error(f"[ab_test] Failed to record: {e}")


def get_ab_results(role: Optional[str] = None) -> dict:
    """
    Get A/B test results — which prompt version is winning per role.

    Returns per-role stats:
    - v1 avg score, count
    - v2 avg score, count
    - winner (or "not enough data")
    """
    conn = get_connection()

    if role:
        rows = conn.execute(
            "SELECT * FROM ab_test_results WHERE role = ? ORDER BY created_at DESC",
            (role,),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM ab_test_results ORDER BY created_at DESC"
        ).fetchall()

    conn.close()

    if not rows:
        return {"status": "no_data", "results": {}}

    # Group by role and version
    results = {}
    for row in rows:
        r = row["role"]
        v = row["prompt_version"]

        if r not in results:
            results[r] = {"v1": {"scores": [], "count": 0}, "v2": {"scores": [], "count": 0}}

        results[r][v]["scores"].append(row["avg_score"])
        results[r][v]["count"] += 1

    # Calculate winners
    summary = {}
    for r, versions in results.items():
        v1_avg = sum(versions["v1"]["scores"]) / len(versions["v1"]["scores"]) if versions["v1"]["scores"] else 0
        v2_avg = sum(versions["v2"]["scores"]) / len(versions["v2"]["scores"]) if versions["v2"]["scores"] else 0

        min_samples = 5  # need at least 5 samples to declare a winner
        if versions["v1"]["count"] >= min_samples and versions["v2"]["count"] >= min_samples:
            winner = "v1" if v1_avg > v2_avg else "v2" if v2_avg > v1_avg else "tie"
        else:
            winner = "not_enough_data"

        summary[r] = {
            "v1": {"avg_score": round(v1_avg, 2), "count": versions["v1"]["count"]},
            "v2": {"avg_score": round(v2_avg, 2), "count": versions["v2"]["count"]},
            "winner": winner,
        }

    return {"status": "ok", "results": summary}
