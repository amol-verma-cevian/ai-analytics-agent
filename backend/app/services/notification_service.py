"""
Notification Service — generates session summaries.

After a conversation ends, generates a text summary of the session
including key metrics discussed, evaluation scores, and any anomalies found.
"""

import logging
from app.models.database import get_connection

logger = logging.getLogger(__name__)


async def generate_session_summary(call_id: str) -> str:
    """
    Generate a text summary of a completed session.

    Uses call data + evaluation scores to build a concise summary.
    """
    conn = get_connection()

    call = conn.execute(
        "SELECT * FROM calls WHERE call_id = ?", (call_id,)
    ).fetchone()

    evals = conn.execute(
        "SELECT * FROM evaluations WHERE call_id = ? ORDER BY turn_number",
        (call_id,),
    ).fetchall()

    conn.close()

    if not call:
        return "Session summary unavailable."

    role = call["role_detected"] or "unknown"
    turns = call["total_turns"] or 0
    escalated = bool(call["escalated"])

    lines = [
        f"Session Summary — {call_id}",
        f"Role: {role.upper()}",
        f"Turns: {turns}",
        f"Escalated: {'Yes' if escalated else 'No'}",
    ]

    if evals:
        avg_scores = {}
        for e in evals:
            for dim in ["accuracy", "factual_correctness", "stability",
                        "response_style", "conversational_coherence"]:
                if dim not in avg_scores:
                    avg_scores[dim] = []
                avg_scores[dim].append(e[dim])

        overall = sum(
            sum(v) / len(v) for v in avg_scores.values()
        ) / len(avg_scores)
        lines.append(f"Avg Quality: {overall:.1f}/3")

    return "\n".join(lines)
