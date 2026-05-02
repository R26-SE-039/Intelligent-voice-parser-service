"""Configuration for speech-to-text microservice."""

from __future__ import annotations

import os
from dotenv import load_dotenv
from dataclasses import dataclass


@dataclass(frozen=True)
class SpeechServiceSettings:
    """Runtime settings loaded from environment variables."""

    assemblyai_api_key: str
    assemblyai_base_url: str
    transcription_timeout_seconds: int
    polling_interval_seconds: float
    cors_origins: list[str]
    auth_secret: str


def load_settings() -> SpeechServiceSettings:
    """Load and normalize service settings."""
    load_dotenv()
    return SpeechServiceSettings(
        assemblyai_api_key=os.getenv("ASSEMBLYAI_API_KEY", "").strip(),
        assemblyai_base_url=os.getenv("ASSEMBLYAI_BASE_URL", "https://api.assemblyai.com/v2").strip(),
        transcription_timeout_seconds=int(os.getenv("TRANSCRIPTION_TIMEOUT_SECONDS", "120")),
        polling_interval_seconds=float(os.getenv("TRANSCRIPTION_POLL_INTERVAL_SECONDS", "1.2")),
        cors_origins=[
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            "http://localhost:5174",
            "http://127.0.0.1:5174",
            "http://localhost:5175",
            "http://127.0.0.1:5175",
            "http://localhost:3000",
            "http://127.0.0.1:3000",
        ],
        auth_secret=os.getenv("AUTH_SECRET", "dev-change-me-secret").strip(),
    )
