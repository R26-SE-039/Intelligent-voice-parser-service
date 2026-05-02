"""In-memory session and caption storage."""

from __future__ import annotations

from datetime import datetime, timezone
from threading import Lock
from uuid import uuid4

from fastapi import HTTPException

from models.schemas import CaptionLine


class SessionStore:
    """Thread-safe in-memory store for voice sessions."""

    def __init__(self) -> None:
        self._sessions: dict[str, list[CaptionLine]] = {}
        self._participants: dict[str, dict[str, str]] = {} # meeting_id -> {conn_id: name}
        self._connections: dict[str, list[Any]] = {} # meeting_id -> [websocket_objs]
        self._lock = Lock()

    def create_session(self) -> str:
        session_id = f"voice-{uuid4()}"
        with self._lock:
            self._sessions[session_id] = []
        return session_id

    def stop_session(self, session_id: str) -> None:
        with self._lock:
            if session_id not in self._sessions:
                raise HTTPException(status_code=404, detail="Session not found")
            self._sessions.pop(session_id)

    def push_caption(self, session_id: str, speaker: str, text: str) -> CaptionLine:
        with self._lock:
            if session_id not in self._sessions:
                raise HTTPException(status_code=404, detail="Session not found")

            caption = CaptionLine(
                id=f"cap-{uuid4()}",
                speaker=speaker,
                text=text,
                created_at=datetime.now(timezone.utc).isoformat(),
            )
            self._sessions[session_id].append(caption)
            return caption

    def get_captions(self, session_id: str) -> list[CaptionLine]:
        with self._lock:
            captions = self._sessions.get(session_id)
            if captions is None:
                raise HTTPException(status_code=404, detail="Session not found")
            return list(captions)

    def add_participant(self, meeting_id: str, conn_id: str, name: str, websocket: Any):
        with self._lock:
            if meeting_id not in self._participants:
                self._participants[meeting_id] = {}
                self._connections[meeting_id] = []
                self._sessions[meeting_id] = []
            
            self._participants[meeting_id][conn_id] = name
            self._connections[meeting_id].append(websocket)
            return list(self._participants[meeting_id].values())

    def remove_participant(self, meeting_id: str, conn_id: str, websocket: Any):
        with self._lock:
            if meeting_id in self._participants:
                if conn_id in self._participants[meeting_id]:
                    self._participants[meeting_id].pop(conn_id)
                if websocket in self._connections[meeting_id]:
                    self._connections[meeting_id].remove(websocket)
                
                # Cleanup if empty
                if not self._participants[meeting_id]:
                    self._participants.pop(meeting_id)
                    self._connections.pop(meeting_id)
                    # We might keep sessions for history
            
            return list(self._participants.get(meeting_id, {}).values())

    def get_participants(self, meeting_id: str) -> list[dict[str, str]]:
        with self._lock:
            participants_map = self._participants.get(meeting_id, {})
            return [{"id": k, "name": v} for k, v in participants_map.items()]

    def get_connections(self, meeting_id: str) -> list[Any]:
        with self._lock:
            return list(self._connections.get(meeting_id, []))
