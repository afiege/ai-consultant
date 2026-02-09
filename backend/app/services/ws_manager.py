"""WebSocket connection manager for real-time 6-3-5 brainstorming collaboration."""

import asyncio
import json
import logging
from typing import Dict, List, Set

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Manages WebSocket connections grouped by session UUID.

    Thread-safe for concurrent connect/disconnect operations.
    Broadcasts events to all participants in a session.
    """

    def __init__(self):
        # session_uuid -> set of (participant_uuid, websocket)
        self._connections: Dict[str, Set[tuple]] = {}

    async def connect(self, websocket: WebSocket, session_uuid: str, participant_uuid: str):
        """Accept a WebSocket connection and register it for a session."""
        await websocket.accept()
        if session_uuid not in self._connections:
            self._connections[session_uuid] = set()
        self._connections[session_uuid].add((participant_uuid, websocket))
        logger.info(f"WS connect: participant={participant_uuid[:8]}… session={session_uuid[:8]}… "
                     f"(total={len(self._connections[session_uuid])})")

    def disconnect(self, websocket: WebSocket, session_uuid: str, participant_uuid: str):
        """Remove a connection from the session."""
        conns = self._connections.get(session_uuid, set())
        conns.discard((participant_uuid, websocket))
        if not conns:
            self._connections.pop(session_uuid, None)
        logger.info(f"WS disconnect: participant={participant_uuid[:8]}… session={session_uuid[:8]}…")

    async def broadcast(self, session_uuid: str, event: str, data: dict, exclude: str = None):
        """Send a JSON message to all connections in a session.

        Args:
            session_uuid: Target session.
            event: Event type (e.g. 'ideas_submitted', 'round_advanced', 'session_started').
            data: Payload dict.
            exclude: Optional participant_uuid to exclude (sender).
        """
        conns = self._connections.get(session_uuid, set())
        message = json.dumps({"event": event, "data": data})
        stale = []
        for participant_uuid, ws in conns:
            if exclude and participant_uuid == exclude:
                continue
            try:
                await ws.send_text(message)
            except Exception:
                stale.append((participant_uuid, ws))
        # Cleanup broken connections
        for item in stale:
            conns.discard(item)

    def get_connected_count(self, session_uuid: str) -> int:
        return len(self._connections.get(session_uuid, set()))

    def get_connected_participants(self, session_uuid: str) -> List[str]:
        return [p for p, _ in self._connections.get(session_uuid, set())]


# Singleton instance shared across the application
ws_manager = ConnectionManager()
