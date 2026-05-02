"""AssemblyAI API integration utilities."""

from __future__ import annotations

import json
from time import monotonic, sleep
from typing import Any
from urllib import error, request

from fastapi import HTTPException

from ..core.config import SpeechServiceSettings


class AssemblyAIClient:
    """HTTP client for AssemblyAI operations used by this service."""

    def __init__(self, settings: SpeechServiceSettings) -> None:
        self._settings = settings

    def _api_key(self) -> str:
        if not self._settings.assemblyai_api_key:
            raise HTTPException(
                status_code=500,
                detail="ASSEMBLYAI_API_KEY is not configured for speech-to-text service",
            )
        return self._settings.assemblyai_api_key

    def _request(self, method: str, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        url = f"{self._settings.assemblyai_base_url}{path}"
        body: bytes | None = None
        if payload is not None:
            body = json.dumps(payload).encode("utf-8")

        req = request.Request(
            url=url,
            data=body,
            method=method,
            headers={
                "authorization": self._api_key(),
                "content-type": "application/json",
            },
        )

        try:
            with request.urlopen(req, timeout=30) as resp:
                raw = resp.read().decode("utf-8")
                return json.loads(raw) if raw else {}
        except error.HTTPError as exc:
            detail = exc.read().decode("utf-8")
            raise HTTPException(status_code=502, detail=f"AssemblyAI HTTP error: {detail}") from exc
        except error.URLError as exc:
            raise HTTPException(status_code=502, detail=f"AssemblyAI unavailable: {exc.reason}") from exc

    def create_realtime_token(self, expires_in_seconds: int = 3600) -> str | None:
        try:
            response = self._request(
                "POST",
                "/realtime/token",
                payload={"expires_in_seconds": expires_in_seconds},
            )
            token = str(response.get("token", "")).strip()
            return token or None
        except HTTPException:
            return None

    def transcribe_url(
        self,
        audio_url: str,
        speaker_labels: bool,
        sentiment_analysis: bool,
        language_code: str,
        speech_model: str,
    ) -> dict[str, Any]:
        create_resp = self._request(
            "POST",
            "/transcript",
            payload={
                "audio_url": audio_url,
                "speaker_labels": speaker_labels,
                "sentiment_analysis": sentiment_analysis,
                "speech_model": speech_model,
                "language_code": language_code,
            },
        )

        transcript_id = str(create_resp.get("id", "")).strip()
        if not transcript_id:
            raise HTTPException(status_code=502, detail="AssemblyAI did not return transcript id")

        return self._wait_for_completion(transcript_id)

    def _wait_for_completion(self, transcript_id: str) -> dict[str, Any]:
        start = monotonic()

        while True:
            current = self._request("GET", f"/transcript/{transcript_id}")
            status = str(current.get("status", ""))

            if status == "completed":
                return current
            if status == "error":
                raise HTTPException(
                    status_code=502,
                    detail=f"AssemblyAI transcription failed: {current.get('error', 'unknown error')}",
                )

            if monotonic() - start > self._settings.transcription_timeout_seconds:
                raise HTTPException(
                    status_code=504,
                    detail=(
                        "Timed out waiting for transcript completion "
                        f"(transcript_id={transcript_id})"
                    ),
                )

            sleep(self._settings.polling_interval_seconds)
