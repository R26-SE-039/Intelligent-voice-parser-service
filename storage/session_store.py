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
