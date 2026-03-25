"""
Sentiment Detection Agent (Step 12).

After each user utterance, analyzes emotional state:
- Satisfied: user is happy with the response
- Neutral: user is engaged but not strongly emotional
- Frustrated: user is unhappy — repeated questions, negative language, short responses

Why this matters in voice AI:
On a phone call, you can't see the user's face. If a CEO asks the same
question 3 times, they're frustrated — the agent should recognize this
and offer human handoff instead of repeating the same data.

Swiggy connection:
- Databricks article: "Conversational Coherence" evaluation dimension
- Hermes V3: escalation detection for routing to human support
"""

import json
import logging
from typing import Optional

from app.config import settings

logger = logging.getLogger(__name__)

# --- Frustration signals (rule-based pre-check) ---
# Quick keyword check BEFORE calling LLM. If no frustration signals,
# skip the LLM call entirely → saves cost and latency.

FRUSTRATION_KEYWORDS = [
    "wrong", "incorrect", "not what i asked", "already said",
    "again", "repeat", "listen", "useless", "waste",
    "terrible", "awful", "horrible", "confused", "confusing",
    "doesn't make sense", "not helpful", "connect me", "human",
    "agent", "supervisor", "manager", "escalate",
    "ridiculous", "unacceptable", "frustrated",
]

SATISFACTION_KEYWORDS = [
    "great", "thanks", "perfect", "exactly", "helpful",
    "good", "nice", "appreciate", "excellent", "wonderful",
    "that's what i needed", "makes sense", "clear",
]


def _quick_sentiment_check(text: str) -> Optional[str]:
    """
    Rule-based pre-check. Returns sentiment if confident, None if ambiguous.

    Why rule-based first?
    - LLM calls cost money and add latency (~1-2 seconds)
    - "Thanks, that's perfect" is obviously satisfied — no need for LLM
    - "This is wrong, connect me to a human" is obviously frustrated
    - Only ambiguous cases need the LLM

    This saves ~60-70% of LLM calls in production.
    """
    text_lower = text.lower()

    frustration_score = sum(1 for kw in FRUSTRATION_KEYWORDS if kw in text_lower)
    satisfaction_score = sum(1 for kw in SATISFACTION_KEYWORDS if kw in text_lower)

    if frustration_score >= 2:
        return "frustrated"
    if satisfaction_score >= 2:
        return "satisfied"
    if frustration_score == 1 and satisfaction_score == 0:
        return "frustrated"
    if satisfaction_score == 1 and frustration_score == 0:
        return "satisfied"

    return None  # ambiguous → need LLM


async def detect_sentiment(
    text: str,
    conversation_history: Optional[list[str]] = None,
) -> dict:
    """
    Detect user sentiment from their utterance.

    Two-tier approach:
    1. Rule-based keywords (fast, free) → handles obvious cases
    2. LLM classification (slower, costs tokens) → handles ambiguous cases

    Args:
        text: the user's latest utterance
        conversation_history: previous utterances (for pattern detection)

    Returns:
        dict with:
        - sentiment: "satisfied" | "neutral" | "frustrated"
        - confidence: "high" | "medium" | "low"
        - method: "rule_based" | "llm"
        - should_escalate: bool (true if frustrated + high confidence)
        - signals: list of detected frustration/satisfaction signals
    """
    # Tier 1: Rule-based check
    quick_result = _quick_sentiment_check(text)
    if quick_result:
        should_escalate = quick_result == "frustrated"
        logger.info(f"[sentiment] Rule-based: {quick_result} (escalate: {should_escalate})")
        return {
            "sentiment": quick_result,
            "confidence": "high",
            "method": "rule_based",
            "should_escalate": should_escalate,
            "signals": _extract_signals(text),
        }

    # Check for pattern-based frustration (repeated questions)
    if conversation_history and len(conversation_history) >= 2:
        if _detect_repetition(text, conversation_history):
            logger.info("[sentiment] Pattern-based: frustrated (repetition detected)")
            return {
                "sentiment": "frustrated",
                "confidence": "medium",
                "method": "pattern",
                "should_escalate": True,
                "signals": ["repeated_question"],
            }

    # Check for short clipped responses (frustration signal)
    if len(text.split()) <= 3 and conversation_history and len(conversation_history) >= 3:
        logger.info("[sentiment] Pattern-based: frustrated (short clipped response)")
        return {
            "sentiment": "frustrated",
            "confidence": "low",
            "method": "pattern",
            "should_escalate": False,
            "signals": ["short_response"],
        }

    # Tier 2: LLM classification for ambiguous cases
    try:
        llm_result = await _llm_sentiment_check(text, conversation_history)
        return llm_result
    except Exception as e:
        logger.error(f"[sentiment] LLM check failed: {e}")
        # Fallback to neutral if LLM fails
        return {
            "sentiment": "neutral",
            "confidence": "low",
            "method": "fallback",
            "should_escalate": False,
            "signals": [],
        }


def _detect_repetition(text: str, history: list[str]) -> bool:
    """
    Check if the user is repeating themselves — a strong frustration signal.

    If the current text is very similar to a recent utterance, the user
    probably didn't get a good answer the first time.
    """
    text_words = set(text.lower().split())
    for prev in history[-3:]:  # check last 3 utterances
        prev_words = set(prev.lower().split())
        if not text_words or not prev_words:
            continue
        overlap = len(text_words & prev_words) / max(len(text_words), len(prev_words))
        if overlap > 0.6:  # 60% word overlap = likely repetition
            return True
    return False


def _extract_signals(text: str) -> list[str]:
    """Extract which specific signals were detected in the text."""
    text_lower = text.lower()
    signals = []
    for kw in FRUSTRATION_KEYWORDS:
        if kw in text_lower:
            signals.append(f"frustration:{kw}")
    for kw in SATISFACTION_KEYWORDS:
        if kw in text_lower:
            signals.append(f"satisfaction:{kw}")
    return signals


async def _llm_sentiment_check(
    text: str,
    conversation_history: Optional[list[str]] = None,
) -> dict:
    """
    Use LLM for ambiguous sentiment detection.

    This is the expensive path — only called when rule-based check
    can't determine sentiment confidently.
    """
    history_context = ""
    if conversation_history:
        recent = conversation_history[-3:]
        history_context = "\n".join(f"- Previous: \"{u}\"" for u in recent)
        history_context = f"\nRecent conversation:\n{history_context}"

    prompt = f"""Classify the user's emotional state from this phone call utterance.

User said: "{text}"{history_context}

Respond with ONLY a JSON object:
{{"sentiment": "satisfied"|"neutral"|"frustrated", "confidence": "high"|"medium"|"low", "reason": "brief explanation"}}"""

    provider = settings.LLM_PROVIDER.lower()

    if provider == "anthropic":
        import anthropic
        client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
        response = client.messages.create(
            model=settings.CLAUDE_MODEL,
            max_tokens=100,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = response.content[0].text
    else:
        import openai
        client = openai.OpenAI(api_key=settings.OPENAI_API_KEY)
        response = client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            max_tokens=100,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = response.choices[0].message.content

    # Parse LLM response
    try:
        # Strip markdown code fences if present
        clean = raw.strip()
        if clean.startswith("```"):
            clean = clean.split("\n", 1)[1].rsplit("```", 1)[0].strip()
        parsed = json.loads(clean)
        sentiment = parsed.get("sentiment", "neutral")
        confidence = parsed.get("confidence", "medium")
    except (json.JSONDecodeError, KeyError):
        logger.warning(f"[sentiment] Could not parse LLM response: {raw}")
        sentiment = "neutral"
        confidence = "low"

    should_escalate = sentiment == "frustrated" and confidence in ("high", "medium")

    logger.info(f"[sentiment] LLM: {sentiment} ({confidence}, escalate: {should_escalate})")
    return {
        "sentiment": sentiment,
        "confidence": confidence,
        "method": "llm",
        "should_escalate": should_escalate,
        "signals": [parsed.get("reason", "")] if "parsed" in dir() else [],
    }
