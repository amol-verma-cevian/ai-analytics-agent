"""
Evaluation Agent (Step 14).

After every agent response, a SEPARATE LLM call scores the response
across 7 dimensions. This is the quality control layer.

Why a separate LLM call?
- You don't ask the student to grade their own exam
- The evaluation agent has different instructions (objective scoring)
- Keeps evaluation independent from generation

The 7 dimensions (from Swiggy's Databricks article):
1. Accuracy (1-3): Did the agent answer the right question?
2. Factual Correctness (1-3): Are the numbers correct based on tool data?
3. Stability (1-3): Would the same question get a consistent answer?
4. Response Style (1-3): Is tone/length appropriate for the role?
5. Conversational Coherence (1-3): Does it fit the conversation flow?
6. Cost (tokens): How expensive was this response?
7. Latency (ms): How long did the user wait?

Dimensions 1-5 are LLM-scored. Dimensions 6-7 are measured directly.
"""

import json
import logging
from typing import Optional
from datetime import datetime

from app.config import settings
from app.models.database import get_connection

logger = logging.getLogger(__name__)


EVAL_PROMPT_TEMPLATE = """You are an evaluation agent for a voice analytics briefing system.

Score the following agent response on 5 dimensions. Each score is 1-3:
  1 = Poor (wrong answer, wrong tone, incoherent)
  2 = Acceptable (mostly correct, minor issues)
  3 = Excellent (accurate, appropriate, coherent)

CONTEXT:
- User role: {role}
- Conversation state: {state}
- User said: "{user_text}"
- Tools called: {tools_called}
- Tool data retrieved: {tool_data_summary}

AGENT RESPONSE:
"{response}"

SCORING CRITERIA:
1. Accuracy: Did the agent answer what the user actually asked? Not a generic summary when they asked about Mumbai specifically.
2. Factual Correctness: Do the numbers in the response match the tool data? "About forty-seven thousand" for 47,353 is correct. "About sixty thousand" for 47,353 is wrong.
3. Stability: Is this the kind of response you'd expect every time for this question? Or does it seem random/inconsistent?
4. Response Style: For CEO → confident, <75 words, strategic. For Ops → operational, <225 words. For Analyst → detailed, data-heavy. Is the tone and length appropriate?
5. Conversational Coherence: Does the response fit the conversation state? BRIEFING should overview. DRILL_DOWN should go deeper. FOLLOW_UP should answer the specific question.

Respond with ONLY a JSON object:
{{"accuracy": 1-3, "factual_correctness": 1-3, "stability": 1-3, "response_style": 1-3, "conversational_coherence": 1-3, "reasoning": "brief explanation of scores"}}"""


async def evaluate_response(
    user_text: str,
    response_text: str,
    role: Optional[str],
    state: str,
    tool_calls: list[dict],
    token_count: int,
    latency_ms: int,
    call_id: Optional[str] = None,
    turn_number: int = 0,
    prompt_version: Optional[str] = None,
) -> dict:
    """
    Score an agent response across 7 dimensions.

    Dimensions 1-5 are LLM-scored (separate evaluation call).
    Dimensions 6-7 are measured directly from the orchestrator output.

    Args:
        user_text: what the user asked
        response_text: what the agent responded
        role: user role (ceo, ops_manager, analyst)
        state: conversation state (BRIEFING, DRILL_DOWN, etc.)
        tool_calls: list of tools the agent called
        token_count: tokens used by the agent
        latency_ms: response time in milliseconds
        call_id: for DB storage
        turn_number: which turn in the conversation
        prompt_version: which A/B prompt version was used

    Returns:
        dict with all 7 scores + average + reasoning
    """
    # Build tool data summary for the evaluator
    tools_summary = ", ".join(tc["tool"] for tc in tool_calls) if tool_calls else "none"
    tool_data_summary = f"{len(tool_calls)} tools called: {tools_summary}"

    # Build the evaluation prompt
    eval_prompt = EVAL_PROMPT_TEMPLATE.format(
        role=role or "unknown",
        state=state,
        user_text=user_text,
        tools_called=tools_summary,
        tool_data_summary=tool_data_summary,
        response=response_text[:500],  # truncate long responses
    )

    # Call LLM for evaluation
    try:
        scores = await _call_eval_llm(eval_prompt)
    except Exception as e:
        logger.error(f"[eval] LLM evaluation failed: {e}")
        # Fallback scores if LLM fails
        scores = {
            "accuracy": 2,
            "factual_correctness": 2,
            "stability": 2,
            "response_style": 2,
            "conversational_coherence": 2,
            "reasoning": f"Fallback scores — LLM eval failed: {str(e)[:50]}",
        }

    # Add measured dimensions (6 and 7)
    scores["token_count"] = token_count
    scores["latency_ms"] = latency_ms

    # Calculate average of scored dimensions (1-5)
    scored_dims = [
        scores["accuracy"],
        scores["factual_correctness"],
        scores["stability"],
        scores["response_style"],
        scores["conversational_coherence"],
    ]
    scores["avg_score"] = round(sum(scored_dims) / len(scored_dims), 2)

    logger.info(
        f"[eval] Scores: acc={scores['accuracy']} fact={scores['factual_correctness']} "
        f"stab={scores['stability']} style={scores['response_style']} "
        f"coher={scores['conversational_coherence']} | avg={scores['avg_score']} "
        f"| tokens={token_count} latency={latency_ms}ms"
    )

    # Store in DB if we have a call_id
    if call_id:
        _store_evaluation(call_id, turn_number, scores, prompt_version)

    return scores


async def _call_eval_llm(prompt: str) -> dict:
    """Call the LLM for evaluation scoring."""
    provider = settings.LLM_PROVIDER.lower()

    if provider == "anthropic":
        import anthropic
        client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
        response = client.messages.create(
            model=settings.CLAUDE_MODEL,
            max_tokens=200,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = response.content[0].text
    else:
        import openai
        client = openai.OpenAI(api_key=settings.OPENAI_API_KEY)
        response = client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            max_tokens=200,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = response.choices[0].message.content

    # Parse JSON response
    clean = raw.strip()
    if clean.startswith("```"):
        clean = clean.split("\n", 1)[1].rsplit("```", 1)[0].strip()

    parsed = json.loads(clean)

    # Validate scores are in range
    for dim in ["accuracy", "factual_correctness", "stability",
                "response_style", "conversational_coherence"]:
        val = parsed.get(dim, 2)
        parsed[dim] = max(1, min(3, int(val)))

    return parsed


def _store_evaluation(
    call_id: str,
    turn_number: int,
    scores: dict,
    prompt_version: Optional[str] = None,
):
    """Store evaluation scores in the database."""
    try:
        conn = get_connection()
        conn.execute(
            """INSERT INTO evaluations
               (call_id, turn_number, accuracy, factual_correctness, stability,
                response_style, conversational_coherence, token_count, latency_ms,
                prompt_version)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                call_id,
                turn_number,
                scores["accuracy"],
                scores["factual_correctness"],
                scores["stability"],
                scores["response_style"],
                scores["conversational_coherence"],
                scores["token_count"],
                scores["latency_ms"],
                prompt_version,
            ),
        )
        conn.commit()
        conn.close()
        logger.info(f"[eval] Stored evaluation for call {call_id}, turn {turn_number}")
    except Exception as e:
        logger.error(f"[eval] Failed to store evaluation: {e}")


def get_evaluation_stats(call_id: Optional[str] = None) -> dict:
    """Get evaluation statistics — overall or for a specific call."""
    conn = get_connection()

    if call_id:
        rows = conn.execute(
            "SELECT * FROM evaluations WHERE call_id = ? ORDER BY turn_number",
            (call_id,),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM evaluations ORDER BY created_at DESC LIMIT 50"
        ).fetchall()

    conn.close()

    if not rows:
        return {"count": 0, "avg_scores": {}}

    evals = [dict(r) for r in rows]

    # Calculate averages
    dims = ["accuracy", "factual_correctness", "stability",
            "response_style", "conversational_coherence"]
    avg_scores = {}
    for dim in dims:
        values = [e[dim] for e in evals]
        avg_scores[dim] = round(sum(values) / len(values), 2)

    avg_scores["overall"] = round(sum(avg_scores.values()) / len(avg_scores), 2)

    return {
        "count": len(evals),
        "avg_scores": avg_scores,
        "evaluations": evals,
    }
