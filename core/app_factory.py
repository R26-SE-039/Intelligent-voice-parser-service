"""Application factory for speech-to-text microservice."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routes import build_router
from clients.azure_speech_client import AzureSpeechClient
from persistence.speech_persistence import SpeechPersistence
from persistence.supabase_gateway import SupabaseGateway
from storage.session_store import SessionStore
from core.config import load_settings


def create_app() -> FastAPI:
    """Build and configure FastAPI app instance."""
    settings = load_settings()

    app = FastAPI(title="Speech to Text Service", version="1.0.0")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    store = SessionStore()
    azure_speech = AzureSpeechClient(settings)
    persistence = SpeechPersistence(SupabaseGateway.from_env())
    app.include_router(build_router(
        store=store,
        azure_speech=azure_speech,
        persistence=persistence,
        settings=settings
    ))
    return app
