"""
Prompt Registry — JSON-based prompt versioning (MLflow-lite).

Instead of hardcoding prompts in ab_test_service, this provides:
1. JSON file with all prompt versions per role
2. Version history tracking
3. "Promote to production" — set the active version
4. Dashboard API to view and manage versions

Why a registry?
- Swiggy uses MLflow Prompt Registry to version prompts
- We build a lightweight equivalent using JSON + SQLite
- Prompts are config, not code — they should be versionable independently
"""

import json
import logging
from datetime import datetime
from pathlib import Path

from app.models.database import get_connection

logger = logging.getLogger(__name__)

# Prompt definitions file
PROMPTS_FILE = Path(__file__).parent.parent / "prompts.json"

# Default prompts (written to file if it doesn't exist)
DEFAULT_PROMPTS = {
    "ceo": {
        "active_version": "v1",
        "versions": {
            "v1": {
                "style_note": "Keep it under 30 seconds. Lead with anomalies.",
                "word_limit": 75,
                "created_at": "2024-01-01",
                "description": "Concise executive briefing with anomaly-first approach",
            },
            "v2": {
                "style_note": "Keep it under 20 seconds. Numbers only, no narrative.",
                "word_limit": 50,
                "created_at": "2024-01-15",
                "description": "Ultra-brief numbers-only format for quick updates",
            },
        },
    },
    "ops_manager": {
        "active_version": "v1",
        "versions": {
            "v1": {
                "style_note": "City-by-city breakdown with operational flags.",
                "word_limit": 225,
                "created_at": "2024-01-01",
                "description": "Full operational breakdown across all cities",
            },
            "v2": {
                "style_note": "Only mention cities with issues. Skip healthy cities.",
                "word_limit": 150,
                "created_at": "2024-01-15",
                "description": "Exception-based reporting — only flag problems",
            },
        },
    },
    "analyst": {
        "active_version": "v1",
        "versions": {
            "v1": {
                "style_note": "Full data breakdown. Include hourly trends.",
                "word_limit": None,
                "created_at": "2024-01-01",
                "description": "Complete data analysis with hourly granularity",
            },
            "v2": {
                "style_note": "Structured output: metric → value → change → insight.",
                "word_limit": None,
                "created_at": "2024-01-15",
                "description": "Structured tabular format for easy parsing",
            },
        },
    },
}


def _load_prompts() -> dict:
    """Load prompts from JSON file, creating it if needed."""
    if not PROMPTS_FILE.exists():
        _save_prompts(DEFAULT_PROMPTS)
    return json.loads(PROMPTS_FILE.read_text())


def _save_prompts(data: dict):
    """Save prompts to JSON file."""
    PROMPTS_FILE.write_text(json.dumps(data, indent=2))


def get_all_prompts() -> dict:
    """Get all prompt versions for all roles."""
    return _load_prompts()


def get_prompt(role: str, version: str = None) -> dict:
    """
    Get a specific prompt version, or the active version if not specified.

    Args:
        role: "ceo", "ops_manager", or "analyst"
        version: "v1", "v2", etc. If None, uses active_version.

    Returns:
        The prompt config dict
    """
    prompts = _load_prompts()
    role_data = prompts.get(role, prompts.get("ceo"))

    if version is None:
        version = role_data.get("active_version", "v1")

    return role_data["versions"].get(version, role_data["versions"]["v1"])


def promote_version(role: str, version: str) -> dict:
    """
    Promote a version to active (production) for a role.

    This is the "deploy" action — makes a tested version the default.

    Args:
        role: the role to update
        version: the version to promote

    Returns:
        Updated role config
    """
    prompts = _load_prompts()

    if role not in prompts:
        return {"error": f"Unknown role: {role}"}

    if version not in prompts[role]["versions"]:
        return {"error": f"Unknown version: {version}"}

    old_version = prompts[role]["active_version"]
    prompts[role]["active_version"] = version
    _save_prompts(prompts)

    # Log the promotion
    _log_promotion(role, old_version, version)

    logger.info(f"[registry] Promoted {role}/{version} to active (was {old_version})")
    return {
        "role": role,
        "promoted": version,
        "previous": old_version,
    }


def add_version(role: str, version_id: str, config: dict) -> dict:
    """
    Add a new prompt version for a role.

    Args:
        role: the role
        version_id: e.g., "v3"
        config: must include "style_note" and optionally "word_limit", "description"

    Returns:
        The new version config
    """
    prompts = _load_prompts()

    if role not in prompts:
        return {"error": f"Unknown role: {role}"}

    config["created_at"] = datetime.now().strftime("%Y-%m-%d")
    prompts[role]["versions"][version_id] = config
    _save_prompts(prompts)

    logger.info(f"[registry] Added {role}/{version_id}")
    return {"role": role, "version": version_id, "config": config}


def _log_promotion(role: str, old_version: str, new_version: str):
    """Log version promotion to DB for audit trail."""
    try:
        conn = get_connection()
        conn.execute(
            """INSERT INTO prompt_history (role, old_version, new_version, promoted_at)
               VALUES (?, ?, ?, ?)""",
            (role, old_version, new_version, datetime.now().isoformat()),
        )
        conn.commit()
        conn.close()
    except Exception:
        pass  # table might not exist yet, that's ok


def get_promotion_history(role: str = None) -> list:
    """Get version promotion history."""
    try:
        conn = get_connection()
        if role:
            rows = conn.execute(
                "SELECT * FROM prompt_history WHERE role = ? ORDER BY promoted_at DESC",
                (role,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM prompt_history ORDER BY promoted_at DESC"
            ).fetchall()
        conn.close()
        return [dict(r) for r in rows]
    except Exception:
        return []
