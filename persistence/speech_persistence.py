"""Supabase-backed persistence helpers for the speech-to-text service."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from models.schemas import CaptionLine
from persistence.supabase_gateway import SupabaseGateway


class SpeechPersistence:
    """Persist speech sessions, captions, and transcription results."""

    def __init__(self, gateway: SupabaseGateway) -> None:
        self._gateway = gateway

    def create_session(self, session_id: str) -> None:
        self._gateway.upsert(
            self._gateway.settings.speech_sessions_table,
            {
                "session_id": session_id,
                "provider": "assemblyai",
                "status": "active",
                "started_at": _utc_now(),
                "updated_at": _utc_now(),
            },
            on_conflict="session_id",
        )

    def stop_session(self, session_id: str) -> None:
        self._gateway.update(
            self._gateway.settings.speech_sessions_table,
            {
                "status": "stopped",
                "ended_at": _utc_now(),
                "updated_at": _utc_now(),
            },
            eq={"session_id": session_id},
        )

    def save_caption(self, session_id: str, caption: CaptionLine) -> None:
        self._gateway.insert(
            self._gateway.settings.captions_table,
            {
                "caption_id": caption.id,
                "session_id": session_id,
                "speaker": caption.speaker,
                "text": caption.text,
                "created_at": caption.created_at,
            },
        )

    def save_transcription(self, audio_url: str, payload: dict[str, Any]) -> None:
        transcript_id = str(payload.get("id", "")).strip()
        if not transcript_id:
            return

        utterances = payload.get("utterances") or []
        participants = sorted({str(item.get("speaker", "Unknown")) for item in utterances if item.get("speaker")})

        self._gateway.upsert(
            self._gateway.settings.transcripts_table,
            {
                "transcript_id": transcript_id,
                "source": audio_url,
                "participants": participants,
                "metadata": {
                    "provider": "assemblyai",
                    "status": payload.get("status", "unknown"),
                    "text": payload.get("text", ""),
                    "sentiment_results": payload.get("sentiment_analysis_results") or [],
                },
                "updated_at": _utc_now(),
            },
            on_conflict="transcript_id",
        )

        if not utterances:
            return

        rows = []
        for index, item in enumerate(utterances):
            rows.append(
                {
                    "utterance_id": f"{transcript_id}:{index}",
                    "transcript_id": transcript_id,
                    "utterance_index": index,
                    "speaker": item.get("speaker", "Unknown"),
                    "text": item.get("text", ""),
                    "timestamp_start": item.get("start"),
                    "timestamp_end": item.get("end"),
                    "metadata": {
                        "confidence": item.get("confidence"),
                    },
                }
            )

        self._gateway.upsert(self._gateway.settings.utterances_table, rows, on_conflict="utterance_id")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()
