"""AssemblyAI API integration utilities."""

from __future__ import annotations

import json
from time import monotonic, sleep
from typing import Any
from urllib import error, request

from fastapi import HTTPException

from core.config import SpeechServiceSettings


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
        base_url = self._settings.assemblyai_base_url.rstrip("/")
        path = path.lstrip("/")
        url = f"{base_url}/{path}"
        print(f"[AAI] API Request: {method} {url}")
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

    def create_realtime_token(self, expires_in: int = 3600) -> str | None:
        try:
            # We use a direct URL here to be 100% sure of the path
            url = "https://api.assemblyai.com/v2/realtime/token"
            req = request.Request(
                url=url,
                data=json.dumps({"expires_in": expires_in}).encode("utf-8"),
                method="POST",
                headers={
                    "authorization": self._api_key(),
                    "content-type": "application/json",
                },
            )
            with request.urlopen(req, timeout=10) as resp:
                response = json.loads(resp.read().decode("utf-8"))
                token = str(response.get("token", "")).strip()
                return token or None
        except error.HTTPError as e:
            error_body = e.read().decode("utf-8")
            print(f"[AAI] Token Error (v2): {e.code} - {error_body}")
            # Fallback to non-v2 path if v2 fails
            try:
                url = "https://api.assemblyai.com/realtime/token"
                req = request.Request(
                    url=url,
                    data=json.dumps({"expires_in": expires_in}).encode("utf-8"),
                    method="POST",
                    headers={
                        "authorization": self._api_key(),
                        "content-type": "application/json",
                    },
                )
                with request.urlopen(req, timeout=10) as resp:
                    response = json.loads(resp.read().decode("utf-8"))
                    token = str(response.get("token", "")).strip()
                    return token or None
            except error.HTTPError as e2:
                error_body2 = e2.read().decode("utf-8")
                print(f"[AAI] Token Error (root): {e2.code} - {error_body2}")
                # Final Fallback: EU Endpoint
                try:
                    url = "https://api.eu.assemblyai.com/v2/realtime/token"
                    req = request.Request(
                        url=url,
                        data=json.dumps({"expires_in": expires_in}).encode("utf-8"),
                        method="POST",
                        headers={
                            "authorization": self._api_key(),
                            "content-type": "application/json",
                        },
                    )
                    with request.urlopen(req, timeout=10) as resp:
                        response = json.loads(resp.read().decode("utf-8"))
                        token = str(response.get("token", ""))
                        return token or None
                except error.HTTPError as e:
                    error_body = e.read().decode("utf-8")
                    print(f"[AAI] Token Error (EU): {e.code} - {error_body}")
                    return None
                except Exception as e3:
                    print(f"[AAI] Token Error (EU): {e3}")
                    return None
            except Exception as e_root:
                print(f"[AAI] Token Error (root-generic): {e_root}")
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
                "speech_models": [speech_model],
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
