"""Pydantic schemas for speech-to-text API."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class VoiceSessionStartResponse(BaseModel):
    """Response returned when creating a voice session."""

    session_id: str
    realtime_token: str | None = None
    provider: str = "assemblyai"


class VoiceSessionStopRequest(BaseModel):
    """Request body for ending a voice session."""

    session_id: str


class CaptionPushRequest(BaseModel):
    """Append a caption line for an active voice session."""

    session_id: str
    speaker: str = Field(min_length=1)
    text: str = Field(min_length=1)


class CaptionLine(BaseModel):
    """Normalized caption line returned by the service."""

    id: str
    speaker: str
    text: str
    created_at: str


class CaptionsResponse(BaseModel):
    """All captions associated with a session."""

    session_id: str
    captions: list[CaptionLine]


class UrlTranscriptionRequest(BaseModel):
    """Request body for transcribing an audio URL via AssemblyAI."""

    audio_url: str
    speaker_labels: bool = True
    sentiment_analysis: bool = True
    language_code: str = "en_us"
    speech_model: str = "universal-2"
    speaker_map: dict[str, str] = Field(
        default_factory=dict,
        description="Optional mapping of speaker labels (e.g., 'A', 'B' or '1', '2') to roles or names.",
    )


class UrlTranscriptionResponse(BaseModel):
    """Response for URL transcription endpoint."""

    transcript_id: str
    status: str
    text: str
    utterances: list[dict[str, Any]] = Field(default_factory=list)
    sentiment_results: list[dict[str, Any]] = Field(default_factory=list)
