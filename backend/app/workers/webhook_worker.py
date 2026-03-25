"""
ARQ worker — processes conversation jobs from the Redis queue.

This is the HEART of the async pipeline. When a conversation event
arrives (from chat UI, voice API, or any client), the route pushes
a job here. This worker does all the heavy lifting:

1. Initialize conversation state  (Step 7)
2. Detect user role               (Step 11)
3. Scan for anomalies             (Step 8)
4. Check data freshness           (Step 9)
5. RAG retrieval                  (Step 6)
6. Orchestrator ReAct loop        (Step 10)
7. Sentiment detection            (Step 12)
8. Evaluation scoring             (Step 14)
9. A/B test recording             (Step 15)
10. Update dashboard via WebSocket (Step 5)
"""

import json
import logging
from datetime import datetime

from arq import create_pool
from arq.connections import RedisSettings

from app.config import settings
from app.models.database import get_connection
from app.services.ws_manager import manager
from app.state.machine import State, get_or_create_machine, remove_machine
from app.services.anomaly_service import scan_all_anomalies
from app.agents.role_router import detect_role, route_to_agent
from app.agents.sentiment import detect_sentiment
from app.services.fallback_service import check_escalation, handle_escalation
from app.agents.evaluation import evaluate_response
from app.services.ab_test_service import assign_prompt_version, record_ab_result

logger = logging.getLogger(__name__)


async def process_webhook(ctx: dict, payload: dict) -> dict:
    """
    Main job handler — processes a single conversation event.

    Args:
        ctx: ARQ context (contains the Redis connection pool)
        payload: The event data
            - call_id: unique session identifier
            - event: call_started | user_spoke | call_ended | silence_detected
            - text: what the user said (for user_spoke events)
            - caller_id: user identifier
    """
    call_id = payload.get("call_id", "unknown")
    event = payload.get("event", "unknown")
    text = payload.get("text", "")

    logger.info(f"[worker] Processing {event} for session {call_id}")

    if event == "call_started":
        return await _handle_call_started(payload)
    elif event == "user_spoke":
        return await _handle_user_spoke(payload)
    elif event == "call_ended":
        return await _handle_call_ended(payload)
    elif event == "silence_detected":
        return await _handle_silence(payload)
    else:
        logger.warning(f"[worker] Unknown event: {event}")
        return {"status": "ignored", "reason": f"Unknown event: {event}"}


async def _handle_call_started(payload: dict) -> dict:
    """Initialize a new session — create state machine + DB record."""
    call_id = payload["call_id"]
    caller_id = payload.get("caller_id", "")

    # Create state machine for this session
    machine = get_or_create_machine(call_id)

    # Store in DB
    conn = get_connection()
    conn.execute(
        """INSERT OR IGNORE INTO calls (call_id, direction, state, started_at)
           VALUES (?, 'inbound', 'GREETING', ?)""",
        (call_id, datetime.now().isoformat()),
    )
    conn.commit()
    conn.close()

    logger.info(f"[worker] Session {call_id} started — state: {machine.current_state.value}")

    # Notify dashboard
    await manager.broadcast("call_started", {
        "call_id": call_id,
        "caller_id": caller_id,
        "state": machine.current_state.value,
        "timestamp": datetime.now().isoformat(),
    })

    return {"status": "session_initialized", "call_id": call_id, "state": machine.current_state.value}


async def _handle_user_spoke(payload: dict) -> dict:
    """
    Process what the user said — THE FULL PIPELINE.

    1. State machine advances
    2. Role detection (first utterance)
    3. Anomaly scan (before briefing)
    4. A/B prompt version assignment
    5. Route to role-specific sub-agent
    6. LLM generates response via ReAct loop
    7. Sentiment detection
    8. Evaluation scoring (7 dimensions)
    9. A/B result recording
    10. Escalation check
    11. Dashboard updated via WebSocket
    """
    call_id = payload["call_id"]
    text = payload.get("text", "")
    caller_id = payload.get("caller_id", "")

    logger.info(f"[worker] User said: '{text[:80]}' (session: {call_id})")

    # Get or create state machine for this session
    machine = get_or_create_machine(call_id)
    machine.turn_count += 1

    # Update turn count in DB
    conn = get_connection()
    conn.execute(
        "UPDATE calls SET total_turns = total_turns + 1 WHERE call_id = ?",
        (call_id,),
    )
    conn.commit()
    conn.close()

    # ─── Step 7: State machine auto-advance ───
    next_state = machine.auto_advance(text)
    if next_state:
        machine.transition(next_state, reason=f"user said: {text[:40]}")

    # ─── Step 11: Role detection (during ROLE_DETECTION state) ───
    if machine.current_state == State.ROLE_DETECTION and not machine.role:
        role_result = detect_role(text, caller_id=caller_id)
        machine.role = role_result["role"]
        logger.info(
            f"[worker] Role detected: {machine.role} "
            f"(confidence: {role_result['confidence']}, method: {role_result['method']})"
        )

        # Update DB with detected role
        conn = get_connection()
        conn.execute(
            "UPDATE calls SET role_detected = ? WHERE call_id = ?",
            (machine.role, call_id),
        )
        conn.commit()
        conn.close()

        # Auto-advance past ROLE_DETECTION → ANOMALY_SCAN
        next_state = machine.auto_advance(text)
        if next_state:
            machine.transition(next_state, reason="role detected")

    # ─── Step 8: Anomaly scan (during ANOMALY_SCAN state) ───
    anomalies = []
    if machine.current_state == State.ANOMALY_SCAN:
        anomalies = scan_all_anomalies()
        logger.info(f"[worker] Anomaly scan found {len(anomalies)} issues")

        # Auto-advance past ANOMALY_SCAN → BRIEFING
        next_state = machine.auto_advance(text)
        if next_state:
            machine.transition(next_state, reason=f"anomaly scan done ({len(anomalies)} found)")

    # ─── Step 15: A/B prompt version assignment ───
    prompt_version = assign_prompt_version(machine.role or "ceo")

    # ─── Steps 10+11: Route to agent and get response ───
    response_text = ""
    agent_result = {}

    if machine.current_state in (State.BRIEFING, State.DRILL_DOWN, State.FOLLOW_UP):
        state_context = machine.get_context()

        agent_result = await route_to_agent(
            role=machine.role or "ceo",
            user_text=text,
            anomalies=anomalies,
            state_context=state_context,
            prompt_version=prompt_version,
        )
        response_text = agent_result.get("response", "")

        logger.info(
            f"[worker] Agent responded: {len(response_text)} chars, "
            f"{len(agent_result.get('tool_calls', []))} tool calls, "
            f"{agent_result.get('latency_ms', 0)}ms"
        )

    elif machine.current_state == State.CLOSING:
        response_text = "Thank you for your time. Have a great day!"

    elif machine.current_state == State.GREETING:
        response_text = (
            "Hello! I'm your analytics briefing agent. "
            "Could you tell me your role — are you a CEO, "
            "operations manager, or data analyst?"
        )

    elif machine.current_state == State.ROLE_DETECTION:
        response_text = (
            f"Got it, I've identified you as a {machine.role or 'executive'}. "
            "Let me scan the latest data and prepare your briefing."
        )

    else:
        response_text = f"I'm processing your request. Current state: {machine.current_state.value}"

    # ─── Step 12: Sentiment detection ───
    if not hasattr(machine, "utterance_history"):
        machine.utterance_history = []
    machine.utterance_history.append(text)

    sentiment_result = await detect_sentiment(
        text=text,
        conversation_history=machine.utterance_history[:-1],
    )
    logger.info(
        f"[worker] Sentiment: {sentiment_result['sentiment']} "
        f"({sentiment_result['confidence']}, escalate: {sentiment_result['should_escalate']})"
    )

    # ─── Step 14: Evaluation scoring (7 dimensions) ───
    eval_scores = {}
    if agent_result.get("response"):
        eval_scores = await evaluate_response(
            user_text=text,
            response_text=response_text,
            role=machine.role,
            state=machine.current_state.value,
            tool_calls=agent_result.get("tool_calls", []),
            token_count=agent_result.get("token_count", 0),
            latency_ms=agent_result.get("latency_ms", 0),
            call_id=call_id,
            turn_number=machine.turn_count,
            prompt_version=prompt_version,
        )

        # ─── Step 15: Record A/B test result ───
        if eval_scores.get("avg_score"):
            record_ab_result(
                role=machine.role or "ceo",
                prompt_version=prompt_version,
                call_id=call_id,
                avg_score=eval_scores["avg_score"],
            )

    # ─── Step 13: Fallback to human check (now with eval score) ───
    escalation = check_escalation(
        user_text=text,
        sentiment_result=sentiment_result,
        eval_score=eval_scores.get("avg_score"),
        turn_count=machine.turn_count,
    )

    if escalation.should_escalate:
        handoff_message = await handle_escalation(
            call_id=call_id,
            role=machine.role,
            decision=escalation,
            user_text=text,
        )
        response_text = handoff_message
        logger.warning(f"[worker] ESCALATION triggered: {escalation.trigger}")

    # ─── Step 5: Update dashboard via WebSocket ───
    await manager.broadcast("user_spoke", {
        "call_id": call_id,
        "user_text": text,
        "agent_response": response_text[:200],
        "role": machine.role,
        "state": machine.current_state.value,
        "turn_number": machine.turn_count,
        "sentiment": sentiment_result["sentiment"],
        "should_escalate": sentiment_result["should_escalate"],
        "eval_avg": eval_scores.get("avg_score", 0),
        "tool_calls": len(agent_result.get("tool_calls", [])),
        "latency_ms": agent_result.get("latency_ms", 0),
        "timestamp": datetime.now().isoformat(),
    })

    # Update session state in DB
    conn = get_connection()
    conn.execute(
        "UPDATE calls SET state = ? WHERE call_id = ?",
        (machine.current_state.value, call_id),
    )
    conn.commit()
    conn.close()

    return {
        "status": "escalated" if escalation.should_escalate else "processed",
        "call_id": call_id,
        "state": machine.current_state.value,
        "role": machine.role,
        "response": response_text,
        "sentiment": sentiment_result,
        "escalation": escalation.to_dict(),
        "tool_calls": agent_result.get("tool_calls", []),
        "token_count": agent_result.get("token_count", 0),
        "latency_ms": agent_result.get("latency_ms", 0),
    }


async def _handle_call_ended(payload: dict) -> dict:
    """Finalize the session — clean up state machine, update DB."""
    call_id = payload["call_id"]

    # Get final state info before cleanup
    machine = get_or_create_machine(call_id)
    final_role = machine.role
    final_turns = machine.turn_count

    conn = get_connection()
    conn.execute(
        "UPDATE calls SET ended_at = ?, state = 'CLOSING' WHERE call_id = ?",
        (datetime.now().isoformat(), call_id),
    )
    conn.commit()
    conn.close()

    # Clean up state machine
    remove_machine(call_id)

    logger.info(f"[worker] Session {call_id} ended (role: {final_role}, turns: {final_turns})")

    # Notify dashboard
    await manager.broadcast("call_ended", {
        "call_id": call_id,
        "role": final_role,
        "total_turns": final_turns,
        "timestamp": datetime.now().isoformat(),
    })

    return {"status": "session_ended", "call_id": call_id, "role": final_role}


async def _handle_silence(payload: dict) -> dict:
    """Handle silence — might indicate user confusion or dropped connection."""
    call_id = payload["call_id"]
    logger.info(f"[worker] Silence detected on session {call_id}")
    return {
        "status": "silence_handled",
        "call_id": call_id,
        "response": "Are you still there? I can continue the briefing or answer any questions.",
    }


# --- ARQ Worker Settings ---

async def startup(ctx: dict):
    """Runs when the worker starts."""
    logger.info("[worker] ARQ worker started")


async def shutdown(ctx: dict):
    """Runs when the worker stops."""
    logger.info("[worker] ARQ worker shutting down")


class WorkerSettings:
    """ARQ worker configuration — this is what `arq app.workers.webhook_worker.WorkerSettings` reads."""
    redis_settings = RedisSettings.from_dsn(settings.REDIS_URL)
    functions = [process_webhook]
    on_startup = startup
    on_shutdown = shutdown
    max_jobs = 10
    job_timeout = 60
    poll_delay = 0.5
    queue_name = "voice_agent"
