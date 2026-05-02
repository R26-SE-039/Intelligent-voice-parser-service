"""API routes for speech-to-text service."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Header

from clients.assemblyai_client import AssemblyAIClient
from core.config import SpeechServiceSettings
from models.schemas import (
    CaptionPushRequest,
    CaptionsResponse,
    UrlTranscriptionRequest,
    UrlTranscriptionResponse,
    VoiceSessionStartResponse,
    VoiceSessionStopRequest,
)
from persistence.speech_persistence import SpeechPersistence
from storage.session_store import SessionStore


def _map_utterances(payload: dict[str, Any], speaker_map: dict[str, str]) -> list[dict[str, Any]]:
    utterances_raw = payload.get("utterances") or []
    return [
        {
            "speaker": speaker_map.get(str(item.get("speaker", "")), f"Speaker {item.get('speaker', 'Unknown')}"),
            "text": item.get("text", ""),
            "start": item.get("start", 0),
            "end": item.get("end", 0),
            "confidence": item.get("confidence", None),
        }
        for item in utterances_raw
    ]


def _map_sentiment(payload: dict[str, Any], speaker_map: dict[str, str]) -> list[dict[str, Any]]:
    sentiment_raw = payload.get("sentiment_analysis_results") or []
    return [
        {
            "text": item.get("text", ""),
            "start": item.get("start", 0),
            "end": item.get("end", 0),
            "speaker": speaker_map.get(str(item.get("speaker", "")), f"Speaker {item.get('speaker', 'Unknown')}"),
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
    settings: SpeechServiceSettings,
) -> APIRouter:
    """Create API router with injected dependencies."""
    router = APIRouter()

    def get_current_user(authorization: str | None = Header(None)) -> dict[str, Any]:
        if not authorization or not authorization.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="Invalid or missing authentication token")
        
        token = authorization.replace("Bearer ", "")
        user = persistence._gateway.get_user(token, settings.auth_secret)
        if not user:
            raise HTTPException(status_code=401, detail="User not found or token expired")
        return user

    @router.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "service": "speech-to-text"}

    @router.post("/voice/session/start", response_model=VoiceSessionStartResponse)
    def start_voice_session(user: dict = Depends(get_current_user)) -> VoiceSessionStartResponse:
        session_id = store.create_session()
        persistence.create_session(session_id)
        token = assemblyai.create_realtime_token(expires_in_seconds=3600)
        return VoiceSessionStartResponse(session_id=session_id, realtime_token=token)

    @router.post("/voice/session/stop")
    def stop_voice_session(
        body: VoiceSessionStopRequest,
        user: dict = Depends(get_current_user)
    ) -> dict[str, str]:
        store.stop_session(body.session_id)
        persistence.stop_session(body.session_id)
        return {"status": "stopped", "session_id": body.session_id}

    @router.post("/voice/captions/push")
    def push_caption(
        body: CaptionPushRequest,
        user: dict = Depends(get_current_user)
    ):
        caption = store.push_caption(body.session_id, body.speaker, body.text)
        persistence.save_caption(body.session_id, caption)
        return caption

    @router.get("/voice/captions/{session_id}", response_model=CaptionsResponse)
    def get_captions(
        session_id: str,
        user: dict = Depends(get_current_user)
    ) -> CaptionsResponse:
        return CaptionsResponse(session_id=session_id, captions=store.get_captions(session_id))

    @router.post("/voice/transcribe/url", response_model=UrlTranscriptionResponse)
    def transcribe_audio_url(
        body: UrlTranscriptionRequest,
        user: dict = Depends(get_current_user)
    ) -> UrlTranscriptionResponse:
        payload = assemblyai.transcribe_url(
            audio_url=body.audio_url,
            speaker_labels=body.speaker_labels,
            sentiment_analysis=body.sentiment_analysis,
            language_code=body.language_code,
            speech_model=body.speech_model,
        )
        
        # Apply speaker mapping to the payload before saving and returning
        mapped_utterances = _map_utterances(payload, body.speaker_map)
        mapped_sentiment = _map_sentiment(payload, body.speaker_map)
        
        # Update payload for persistence
        payload["utterances"] = mapped_utterances
        payload["sentiment_analysis_results"] = mapped_sentiment
        
        persistence.save_transcription(body.audio_url, payload)

        return UrlTranscriptionResponse(
            transcript_id=str(payload.get("id", "")),
            status=str(payload.get("status", "unknown")),
            text=str(payload.get("text", "")),
            utterances=mapped_utterances,
            sentiment_results=mapped_sentiment,
        )

    return router
