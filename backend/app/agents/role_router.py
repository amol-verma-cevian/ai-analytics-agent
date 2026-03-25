"""
Role Router + Role Detector (Step 11).

Two responsibilities:
1. DETECT: Figure out WHO is calling based on what they say
2. ROUTE: Send them to the right specialist sub-agent

Why separate agents per role instead of one agent with a role flag?
- Context scoping: CEO agent never sees analyst-level tool descriptions
- Prompt focus: each prompt is tuned for one audience
- Cost control: CEO agent uses fewer tools → fewer tokens in system prompt
- Testability: test each role independently

Swiggy connection:
- Databricks article: "distinct agents for each disposition type" with
  separate prompts and tools
- Hermes V3: "charter-based compartmentalization" — each agent has
  a charter defining its scope and boundaries
"""

import json
import logging
from typing import Optional

from app.config import settings

logger = logging.getLogger(__name__)


# --- Role Detection ---

# Keywords that signal which role the caller has
# In production, this would be:
# 1. Caller ID lookup → known manager → role from DB
# 2. If unknown caller → ask "What's your role?"
# 3. NLP classification on their response
# We simplify to keyword matching (but works surprisingly well)

ROLE_SIGNALS = {
    "ceo": [
        "ceo", "chief", "executive", "top line", "big picture",
        "strategic", "board", "investor", "high level", "overview",
        "how are we doing", "how's the business", "quick update",
        "bottom line", "p&l", "profit",
    ],
    "ops_manager": [
        "ops", "operations", "manager", "city", "cities",
        "delays", "delivery", "restaurant", "complaints",
        "fleet", "riders", "drivers", "partner", "ground",
        "what's broken", "issues", "flags", "alerts",
        "zone", "hub", "logistics",
    ],
    "analyst": [
        "analyst", "data", "analysis", "breakdown", "trend",
        "hourly", "compare", "week over week", "correlation",
        "cohort", "segment", "metrics", "dashboard",
        "numbers", "deep dive", "statistical", "distribution",
        "chart", "report", "csv",
    ],
}


def detect_role(text: str, caller_id: Optional[str] = None) -> dict:
    """
    Detect user role from their first utterance.

    Strategy (in priority order):
    1. Look up caller_id in the managers table (known users)
    2. Keyword matching on what they said
    3. Default to "ceo" (safest — shortest response, least data exposure)

    Args:
        text: what the user said (first utterance)
        caller_id: phone number (for DB lookup)

    Returns:
        dict with:
        - role: detected role (ceo, ops_manager, analyst)
        - confidence: how sure we are (high/medium/low)
        - method: how we detected it (db_lookup, keyword_match, default)
    """
    # Strategy 1: DB lookup by caller ID
    if caller_id:
        from app.models.database import get_connection
        conn = get_connection()
        row = conn.execute(
            "SELECT role FROM managers WHERE phone = ? AND is_active = 1",
            (caller_id,),
        ).fetchone()
        conn.close()

        if row:
            logger.info(f"[role_router] Detected role via DB lookup: {row['role']}")
            return {
                "role": row["role"],
                "confidence": "high",
                "method": "db_lookup",
            }

    # Strategy 2: Keyword matching
    text_lower = text.lower()
    scores = {}

    for role, keywords in ROLE_SIGNALS.items():
        score = sum(1 for kw in keywords if kw in text_lower)
        if score > 0:
            scores[role] = score

    if scores:
        best_role = max(scores, key=scores.get)
        best_score = scores[best_role]
        confidence = "high" if best_score >= 3 else "medium" if best_score >= 2 else "low"

        logger.info(
            f"[role_router] Detected role via keywords: {best_role} "
            f"(score: {best_score}, confidence: {confidence})"
        )
        return {
            "role": best_role,
            "confidence": confidence,
            "method": "keyword_match",
            "scores": scores,
        }

    # Strategy 3: Default to CEO (shortest, safest)
    logger.info("[role_router] No role signals found — defaulting to ceo")
    return {
        "role": "ceo",
        "confidence": "low",
        "method": "default",
    }


# --- Role Router ---

async def route_to_agent(
    role: str,
    user_text: str,
    anomalies: list[dict],
    state_context: dict,
    prompt_version: Optional[str] = None,
) -> dict:
    """
    Route the request to the correct role-specific sub-agent.

    Each sub-agent is just run_orchestrator() with a role-specific
    system prompt. The orchestrator already handles role-based prompts —
    this router adds:

    1. Pre-validation of role
    2. Logging for which agent handled the call
    3. Future: tool filtering per role (CEO doesn't need hourly trends)
    4. Future: separate prompt versions per role for A/B testing

    Args:
        role: detected role (ceo, ops_manager, analyst)
        user_text: what the user said
        anomalies: detected anomalies
        state_context: conversation state
        prompt_version: A/B test version

    Returns:
        dict from run_orchestrator + routing metadata
    """
    from app.agents.orchestrator import run_orchestrator

    # Validate role
    valid_roles = ["ceo", "ops_manager", "analyst"]
    if role not in valid_roles:
        logger.warning(f"[role_router] Invalid role '{role}', defaulting to ceo")
        role = "ceo"

    logger.info(f"[role_router] Routing to {role.upper()} agent")

    # Call the orchestrator with the detected role
    result = await run_orchestrator(
        user_text=user_text,
        role=role,
        anomalies=anomalies,
        state_context=state_context,
        prompt_version=prompt_version,
    )

    # Add routing metadata
    result["agent_role"] = role
    return result
