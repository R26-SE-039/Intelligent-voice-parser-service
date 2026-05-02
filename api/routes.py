"""API routes for speech-to-text service."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from ..clients.assemblyai_client import AssemblyAIClient
from ..models.schemas import (
    CaptionPushRequest,
    CaptionsResponse,
    UrlTranscriptionRequest,
    UrlTranscriptionResponse,
    VoiceSessionStartResponse,
    VoiceSessionStopRequest,
)
from ..persistence.speech_persistence import SpeechPersistence
from ..storage.session_store import SessionStore


def _map_utterances(payload: dict[str, Any]) -> list[dict[str, Any]]:
    utterances_raw = payload.get("utterances") or []
    return [
        {
            "speaker": item.get("speaker", "Unknown"),
            "text": item.get("text", ""),
            "start": item.get("start", 0),
            "end": item.get("end", 0),
            "confidence": item.get("confidence", None),
        }
        for item in utterances_raw
    ]


def _map_sentiment(payload: dict[str, Any]) -> list[dict[str, Any]]:
    sentiment_raw = payload.get("sentiment_analysis_results") or []
    return [
        {
            "text": item.get("text", ""),
            "start": item.get("start", 0),
            "end": item.get("end", 0),
            "speaker": item.get("speaker", "Unknown"),
            "sentiment": item.get("sentiment", "NEUTRAL"),
            "emotion_hint": {
                "POSITIVE": "confident",
                "NEGATIVE": "frustrated",
                "NEUTRAL": "neutral",
            }.get(str(item.get("sentiment", "NEUTRAL")), "neutral"),
            "confidence": item.get("confidence", None),
        }
        for item in sentiment_raw
    ]


def build_router(
    store: SessionStore,
    assemblyai: AssemblyAIClient,
    persistence: SpeechPersistence,
) -> APIRouter:
    """Create API router with injected dependencies."""
    router = APIRouter()

    @router.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "service": "speech-to-text"}

    @router.post("/voice/session/start", response_model=VoiceSessionStartResponse)
    def start_voice_session() -> VoiceSessionStartResponse:
        session_id = store.create_session()
        persistence.create_session(session_id)
        token = assemblyai.create_realtime_token(expires_in_seconds=3600)
        return VoiceSessionStartResponse(session_id=session_id, realtime_token=token)

    @router.post("/voice/session/stop")
    def stop_voice_session(body: VoiceSessionStopRequest) -> dict[str, str]:
        store.stop_session(body.session_id)
        persistence.stop_session(body.session_id)
        return {"status": "stopped", "session_id": body.session_id}

    @router.post("/voice/captions/push")
    def push_caption(body: CaptionPushRequest):
        caption = store.push_caption(body.session_id, body.speaker, body.text)
        persistence.save_caption(body.session_id, caption)
        return caption

    @router.get("/voice/captions/{session_id}", response_model=CaptionsResponse)
    def get_captions(session_id: str) -> CaptionsResponse:
        return CaptionsResponse(session_id=session_id, captions=store.get_captions(session_id))

    @router.post("/voice/transcribe/url", response_model=UrlTranscriptionResponse)
    def transcribe_audio_url(body: UrlTranscriptionRequest) -> UrlTranscriptionResponse:
        payload = assemblyai.transcribe_url(
            audio_url=body.audio_url,
            speaker_labels=body.speaker_labels,
            sentiment_analysis=body.sentiment_analysis,
            language_code=body.language_code,
            speech_model=body.speech_model,
        )
        persistence.save_transcription(body.audio_url, payload)

        return UrlTranscriptionResponse(
            transcript_id=str(payload.get("id", "")),
            status=str(payload.get("status", "unknown")),
            text=str(payload.get("text", "")),
            utterances=_map_utterances(payload),
            sentiment_results=_map_sentiment(payload),
        )

    return router
