"""Supabase integration helpers local to speech-to-text service."""

from __future__ import annotations

import os
import jwt
from dataclasses import dataclass
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from supabase import Client
else:  # pragma: no cover - typing fallback only
    Client = Any

try:
    from supabase import create_client
except ImportError:  # pragma: no cover - validated at runtime when enabled
    create_client = None


@dataclass(frozen=True)
class SupabaseSettings:
    """Environment-driven Supabase configuration for speech service."""

    url: str
    service_role_key: str
    schema: str
    transcripts_table: str
    utterances_table: str
    chunks_table: str
    story_runs_table: str
    stories_table: str
    speech_sessions_table: str
    captions_table: str
    meetings_table: str

    @property
    def enabled(self) -> bool:
        return bool(self.url and self.service_role_key)


def load_supabase_settings() -> SupabaseSettings:
    from dotenv import load_dotenv
    load_dotenv()
    return SupabaseSettings(
        url=os.getenv("SUPABASE_URL", "").strip(),
        service_role_key=os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip(),
        schema=os.getenv("SUPABASE_SCHEMA", "speech_to_text").strip() or "speech_to_text",
        transcripts_table=os.getenv("SUPABASE_TRANSCRIPTS_TABLE", "transcripts").strip(),
        utterances_table=os.getenv("SUPABASE_UTTERANCES_TABLE", "transcript_utterances").strip(),
        chunks_table=os.getenv("SUPABASE_CHUNKS_TABLE", "transcript_chunks").strip(),
        story_runs_table=os.getenv("SUPABASE_STORY_RUNS_TABLE", "story_runs").strip(),
        stories_table=os.getenv("SUPABASE_STORIES_TABLE", "generated_stories").strip(),
        speech_sessions_table=os.getenv("SUPABASE_SPEECH_SESSIONS_TABLE", "speech_sessions").strip(),
        captions_table=os.getenv("SUPABASE_CAPTIONS_TABLE", "speech_captions").strip(),
        meetings_table=os.getenv("SUPABASE_MEETINGS_TABLE", "meetings").strip(),
    )


class SupabaseGateway:
    """Thin wrapper over Supabase client with no-op behavior when disabled."""

    def __init__(self, settings: SupabaseSettings) -> None:
        self.settings = settings
        self._client: Client | None = None

        if not settings.enabled:
            return

        if create_client is None:
            raise RuntimeError(
                "Supabase is configured but the 'supabase' package is not installed. "
                "Install it before enabling Supabase persistence."
            )

        self._client = create_client(settings.url, settings.service_role_key)

    @classmethod
    def from_env(cls) -> "SupabaseGateway":
        return cls(load_supabase_settings())

    def _get_table(self, table: str):
        """Helper to get a table reference with the correct schema."""
        if not self._client:
            return None
        return self._client.schema(self.settings.schema).table(table)

    def upsert(self, table: str, rows: dict[str, Any] | list[dict[str, Any]], on_conflict: str | None = None) -> None:
        table_ref = self._get_table(table)
        if not table_ref:
            return

        query = table_ref.upsert(rows)
        if on_conflict:
            query = table_ref.upsert(rows, on_conflict=on_conflict)
        query.execute()

    def insert(self, table: str, rows: dict[str, Any] | list[dict[str, Any]]) -> None:
        table_ref = self._get_table(table)
        if not table_ref:
            return

        table_ref.insert(rows).execute()

    def update(self, table: str, values: dict[str, Any], *, eq: dict[str, Any]) -> None:
        table_ref = self._get_table(table)
        if not table_ref:
            return

        query = table_ref.update(values)
        for key, value in eq.items():
            query = query.eq(key, value)
        query.execute()

    def select(self, table: str, *, eq: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        table_ref = self._get_table(table)
        if not table_ref:
            return []

        query = table_ref.select("*")
        if eq:
            for key, value in eq.items():
                query = query.eq(key, value)
        
        result = query.execute()
        return result.data or []

    def get_user(self, token: str, secret: str) -> dict[str, Any] | None:
        """Verify a custom JWT issued by the auth-service."""
        try:
            decoded = jwt.decode(token, secret, algorithms=["HS256"])
            if not decoded.get("sub"):
                return None
            
            return {
                "id": decoded["sub"],
                "email": decoded.get("email", "unknown@example.com"),
                "role": decoded.get("role", "user"),
            }
        except jwt.ExpiredSignatureError:
            print("Auth error: Token expired")
            return None
        except jwt.InvalidTokenError as e:
            print(f"Auth error: Invalid token ({e})")
            return None
        except Exception as e:
            print(f"Auth error: {e}")
            return None
