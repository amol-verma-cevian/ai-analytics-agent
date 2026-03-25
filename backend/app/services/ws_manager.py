"""
WebSocket connection manager.

Tracks all connected dashboard clients and broadcasts events to them.
Think of it as a radio station — clients tune in, we broadcast to everyone.

Why a manager class?
- Multiple dashboards can connect simultaneously (e.g., CEO and Ops on different screens)
- We need to handle disconnects gracefully (browser closes, network drops)
- The worker needs a simple API: just call broadcast() with the event
"""

import json
import logging
from typing import Any

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Manages active WebSocket connections."""

    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        """Accept a new dashboard connection."""
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"[ws] Dashboard connected. Total: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        """Remove a disconnected dashboard."""
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        logger.info(f"[ws] Dashboard disconnected. Total: {len(self.active_connections)}")

    async def broadcast(self, event_type: str, data: Any):
        """
        Send an event to ALL connected dashboards.

        Args:
            event_type: what happened (e.g., "call_started", "anomaly_detected", "evaluation_scored")
            data: the payload (dict, will be JSON-serialized)
        """
        if not self.active_connections:
            return

        message = json.dumps({"type": event_type, "data": data})
        disconnected = []

        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except Exception:
                # Connection died — mark for removal
                disconnected.append(connection)

        # Clean up dead connections
        for conn in disconnected:
            self.disconnect(conn)

        if self.active_connections:
            logger.info(f"[ws] Broadcast '{event_type}' to {len(self.active_connections)} clients")

    async def send_to_one(self, websocket: WebSocket, event_type: str, data: Any):
        """Send an event to a specific dashboard (e.g., initial state on connect)."""
        message = json.dumps({"type": event_type, "data": data})
        await websocket.send_text(message)


# Global instance — imported by main.py and worker
manager = ConnectionManager()
