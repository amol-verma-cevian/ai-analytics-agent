"""
Conversation State Machine.

Every call moves through defined stages. The state machine:
1. Knows which stage the call is in
2. Knows which transitions are valid from each stage
3. Runs entry actions when entering a new state
4. Prevents invalid transitions

States:
  GREETING → ROLE_DETECTION → ANOMALY_SCAN → BRIEFING → DRILL_DOWN → FOLLOW_UP → CLOSING

This replaces nested if/else with a clean graph. Adding a new state
means adding one entry to TRANSITIONS — not touching 10 different places.

Swiggy connection: Their Databricks article describes moving from
"hardcoded logic" to "node-based graph execution where different
intent handlers are modeled as graph branches." This is that pattern.
"""

import logging
from enum import Enum
from typing import Optional, Callable
from datetime import datetime

logger = logging.getLogger(__name__)


class State(str, Enum):
    """All possible conversation states."""
    GREETING = "GREETING"
    ROLE_DETECTION = "ROLE_DETECTION"
    ANOMALY_SCAN = "ANOMALY_SCAN"
    BRIEFING = "BRIEFING"
    DRILL_DOWN = "DRILL_DOWN"
    FOLLOW_UP = "FOLLOW_UP"
    CLOSING = "CLOSING"


# Valid transitions: from_state → [list of allowed next states]
TRANSITIONS: dict[State, list[State]] = {
    State.GREETING: [State.ROLE_DETECTION, State.CLOSING],
    State.ROLE_DETECTION: [State.ANOMALY_SCAN, State.CLOSING],
    State.ANOMALY_SCAN: [State.BRIEFING],
    State.BRIEFING: [State.DRILL_DOWN, State.FOLLOW_UP, State.CLOSING],
    State.DRILL_DOWN: [State.DRILL_DOWN, State.FOLLOW_UP, State.CLOSING],
    State.FOLLOW_UP: [State.DRILL_DOWN, State.FOLLOW_UP, State.CLOSING],
    State.CLOSING: [],  # terminal state — no transitions out
}


class ConversationStateMachine:
    """
    Manages state for a single call.

    Each call gets its own instance. The worker creates one on call_started
    and uses it throughout the call lifecycle.
    """

    def __init__(self, call_id: str, initial_state: State = State.GREETING):
        self.call_id = call_id
        self.current_state = initial_state
        self.history: list[dict] = [{
            "state": initial_state.value,
            "timestamp": datetime.now().isoformat(),
            "reason": "call_started",
        }]
        self.role: Optional[str] = None
        self.turn_count: int = 0

    def can_transition(self, target: State) -> bool:
        """Check if a transition is valid without actually doing it."""
        return target in TRANSITIONS.get(self.current_state, [])

    def transition(self, target: State, reason: str = "") -> State:
        """
        Move to a new state.

        Args:
            target: the state to move to
            reason: why we're transitioning (logged for debugging)

        Returns:
            The new current state

        Raises:
            InvalidTransition if the transition is not allowed
        """
        if not self.can_transition(target):
            allowed = [s.value for s in TRANSITIONS.get(self.current_state, [])]
            raise InvalidTransition(
                f"Cannot go from {self.current_state.value} to {target.value}. "
                f"Allowed: {allowed}"
            )

        old_state = self.current_state
        self.current_state = target
        self.history.append({
            "from": old_state.value,
            "to": target.value,
            "timestamp": datetime.now().isoformat(),
            "reason": reason,
        })

        logger.info(f"[state] Call {self.call_id}: {old_state.value} → {target.value} ({reason})")
        return self.current_state

    def get_allowed_transitions(self) -> list[str]:
        """What states can we move to from here?"""
        return [s.value for s in TRANSITIONS.get(self.current_state, [])]

    def is_terminal(self) -> bool:
        """Is this call done?"""
        return self.current_state == State.CLOSING

    def get_context(self) -> dict:
        """
        Full state context — passed to the orchestrator so it knows
        where we are in the conversation and what's happened so far.
        """
        return {
            "call_id": self.call_id,
            "current_state": self.current_state.value,
            "allowed_transitions": self.get_allowed_transitions(),
            "role": self.role,
            "turn_count": self.turn_count,
            "history": self.history,
            "is_terminal": self.is_terminal(),
        }

    def auto_advance(self, user_text: str) -> Optional[State]:
        """
        Automatically determine the next state based on conversation context.

        Called by the worker on each user_spoke event. Returns the state
        we should transition to, or None if we should stay in current state.

        This is the "intelligence" of the state machine — it reads the
        conversation context and decides what should happen next.
        """
        current = self.current_state

        # GREETING → always move to ROLE_DETECTION after first utterance
        if current == State.GREETING:
            return State.ROLE_DETECTION

        # ROLE_DETECTION → once role is set, move to ANOMALY_SCAN
        if current == State.ROLE_DETECTION and self.role:
            return State.ANOMALY_SCAN

        # ANOMALY_SCAN → always proceed to BRIEFING (scan runs automatically)
        if current == State.ANOMALY_SCAN:
            return State.BRIEFING

        # BRIEFING → check if user is asking for more detail
        if current == State.BRIEFING:
            drill_signals = ["more", "detail", "breakdown", "explain", "why", "show me", "drill", "dig"]
            if any(signal in user_text.lower() for signal in drill_signals):
                return State.DRILL_DOWN
            closing_signals = ["thanks", "bye", "that's all", "done", "no more"]
            if any(signal in user_text.lower() for signal in closing_signals):
                return State.CLOSING
            return State.FOLLOW_UP

        # DRILL_DOWN → check what user wants next
        if current == State.DRILL_DOWN:
            closing_signals = ["thanks", "bye", "that's all", "done", "no more"]
            if any(signal in user_text.lower() for signal in closing_signals):
                return State.CLOSING
            drill_signals = ["more", "detail", "breakdown", "also", "what about"]
            if any(signal in user_text.lower() for signal in drill_signals):
                return State.DRILL_DOWN
            return State.FOLLOW_UP

        # FOLLOW_UP → similar to DRILL_DOWN
        if current == State.FOLLOW_UP:
            closing_signals = ["thanks", "bye", "that's all", "done", "no more"]
            if any(signal in user_text.lower() for signal in closing_signals):
                return State.CLOSING
            return State.FOLLOW_UP

        return None


class InvalidTransition(Exception):
    """Raised when an invalid state transition is attempted."""
    pass


# --- In-memory store of active state machines (one per call) ---
_active_machines: dict[str, ConversationStateMachine] = {}


def get_or_create_machine(call_id: str) -> ConversationStateMachine:
    """Get existing state machine for a call, or create a new one."""
    if call_id not in _active_machines:
        _active_machines[call_id] = ConversationStateMachine(call_id)
    return _active_machines[call_id]


def remove_machine(call_id: str):
    """Clean up when a call ends."""
    _active_machines.pop(call_id, None)
