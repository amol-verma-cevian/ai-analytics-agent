"""
Fallback to Human Agent (Step 13).

Decides when to escalate from AI to human support. Three triggers:

1. SENTIMENT: User is frustrated (from Step 12)
2. CONFIDENCE: Agent's evaluation score is too low (from Step 14)
3. EXPLICIT: User directly asks for a human ("connect me to someone")

Why this matters:
No AI is 100% reliable. If the agent gives wrong numbers or can't
understand the question, forcing the user to stay in the AI loop is
terrible UX. The fallback turns a bad AI experience into a good
human experience.

Swiggy connection:
- Databricks article: "human-in-the-loop design" — low-confidence
  responses routed to human reviewers
- Hermes V3: escalation paths when agent couldn't resolve queries
"""

import logging
from datetime import datetime
from typing import Optional

from app.config import settings
from app.models.database import get_connection
from app.services.ws_manager import manager

logger = logging.getLogger(__name__)

# --- Escalation triggers ---

# If user says any of these, escalate immediately
EXPLICIT_ESCALATION_PHRASES = [
    "connect me to a human",
    "talk to a real person",
    "let me speak to someone",
    "transfer me",
    "get me a supervisor",
    "i want a human",
    "real agent",
    "live agent",
    "speak to analyst",
    "connect me to analyst",
]


class EscalationDecision:
    """Result of the escalation check."""

    def __init__(
        self,
        should_escalate: bool,
        reason: str,
        trigger: str,  # "sentiment", "confidence", "explicit", "none"
        severity: str = "medium",  # "low", "medium", "high"
    ):
        self.should_escalate = should_escalate
        self.reason = reason
        self.trigger = trigger
        self.severity = severity

    def to_dict(self) -> dict:
        return {
            "should_escalate": self.should_escalate,
            "reason": self.reason,
            "trigger": self.trigger,
            "severity": self.severity,
        }


def check_escalation(
    user_text: str,
    sentiment_result: Optional[dict] = None,
    eval_score: Optional[float] = None,
    turn_count: int = 0,
) -> EscalationDecision:
    """
    Decide whether to escalate to a human agent.

    Three checks in priority order:
    1. Explicit request — user directly asks for a human
    2. Sentiment — user is frustrated (from Step 12)
    3. Confidence — agent's evaluation score is too low (from Step 14)

    Args:
        user_text: what the user said
        sentiment_result: output from detect_sentiment()
        eval_score: average evaluation score (1-3 scale, from Step 14)
        turn_count: how many turns into the conversation

    Returns:
        EscalationDecision with should_escalate, reason, trigger, severity
    """
    # Check 1: Explicit request for human
    text_lower = user_text.lower()
    for phrase in EXPLICIT_ESCALATION_PHRASES:
        if phrase in text_lower:
            logger.info(f"[fallback] EXPLICIT escalation: user said '{phrase}'")
            return EscalationDecision(
                should_escalate=True,
                reason=f"User explicitly requested human: '{phrase}'",
                trigger="explicit",
                severity="high",
            )

    # Check 2: Sentiment-based escalation
    if sentiment_result and sentiment_result.get("should_escalate"):
        sentiment = sentiment_result.get("sentiment", "unknown")
        confidence = sentiment_result.get("confidence", "low")

        # Only escalate on high/medium confidence frustration
        if confidence in ("high", "medium"):
            logger.info(f"[fallback] SENTIMENT escalation: {sentiment} ({confidence})")
            return EscalationDecision(
                should_escalate=True,
                reason=f"User sentiment: {sentiment} (confidence: {confidence})",
                trigger="sentiment",
                severity="high" if confidence == "high" else "medium",
            )

    # Check 3: Confidence threshold (from evaluation, Step 14)
    # eval_score is on a 1-3 scale. Below threshold = agent isn't doing well.
    threshold = settings.CONFIDENCE_FALLBACK_THRESHOLD  # default: 1.5
    if eval_score is not None and eval_score < threshold:
        logger.info(f"[fallback] CONFIDENCE escalation: score {eval_score} < {threshold}")
        return EscalationDecision(
            should_escalate=True,
            reason=f"Agent confidence score ({eval_score:.1f}) below threshold ({threshold})",
            trigger="confidence",
            severity="medium",
        )

    # Check 4: Stuck in conversation (too many turns without resolution)
    if turn_count > 6:
        logger.info(f"[fallback] TURN_COUNT escalation: {turn_count} turns")
        return EscalationDecision(
            should_escalate=True,
            reason=f"Conversation exceeded {turn_count} turns without resolution",
            trigger="turn_count",
            severity="low",
        )

    # No escalation needed
    return EscalationDecision(
        should_escalate=False,
        reason="No escalation triggers met",
        trigger="none",
    )


async def handle_escalation(
    call_id: str,
    role: Optional[str],
    decision: EscalationDecision,
    user_text: str,
) -> str:
    """
    Execute the escalation — log, notify, and generate handoff message.

    In production this would:
    1. Send Slack notification to on-call analyst
    2. Send email to team lead
    3. Create a ticket in the support system
    4. Transfer the call via Bolna API

    We simplify to: log in DB + WebSocket broadcast + return handoff message.

    Args:
        call_id: the active call
        role: detected user role
        decision: the escalation decision
        user_text: what triggered the escalation

    Returns:
        Handoff message to speak to the user
    """
    now = datetime.now().isoformat()

    # Store escalation in DB
    conn = get_connection()
    conn.execute(
        """INSERT INTO escalations (call_id, trigger, severity, reason, user_text, created_at)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (call_id, decision.trigger, decision.severity, decision.reason, user_text, now),
    )

    # Update call record — mark as escalated
    conn.execute(
        "UPDATE calls SET state = 'CLOSING', escalated = 1 WHERE call_id = ?",
        (call_id,),
    )
    conn.commit()
    conn.close()

    logger.warning(
        f"[fallback] ESCALATION for call {call_id}: "
        f"trigger={decision.trigger}, severity={decision.severity}, "
        f"reason={decision.reason}"
    )

    # Broadcast to dashboard
    await manager.broadcast("escalation", {
        "call_id": call_id,
        "role": role,
        "trigger": decision.trigger,
        "severity": decision.severity,
        "reason": decision.reason,
        "user_text": user_text,
        "timestamp": now,
    })

    # TODO (production): Send Slack notification
    # TODO (production): Send email alert
    # TODO (production): Create support ticket
    # TODO (production): Bolna API call transfer

    # Generate handoff message based on trigger
    if decision.trigger == "explicit":
        return (
            "Absolutely, let me connect you with a live analyst right away. "
            "They'll have the full context of our conversation. "
            "Please hold for just a moment."
        )
    elif decision.trigger == "sentiment":
        return (
            "I can see this isn't quite meeting your needs. "
            "Let me connect you with one of our analysts who can "
            "give you a more detailed, personalized walkthrough. "
            "Transferring you now."
        )
    elif decision.trigger == "confidence":
        return (
            "I want to make sure you get the most accurate information. "
            "Let me connect you with a senior analyst who can verify "
            "these numbers and provide additional context. One moment please."
        )
    else:
        return (
            "I appreciate your patience. Let me connect you with "
            "a team member who can help you further. Transferring now."
        )
