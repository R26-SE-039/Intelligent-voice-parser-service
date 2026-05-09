"""Microsoft Azure Speech Service integration utilities."""

from __future__ import annotations

import azure.cognitiveservices.speech as speechsdk
from fastapi import HTTPException
from core.config import SpeechServiceSettings

class AzureSpeechClient:
    """Client for Azure Speech Service operations."""

    def __init__(self, settings: SpeechServiceSettings) -> None:
        self._settings = settings

    def get_speech_config(self) -> speechsdk.SpeechConfig:
        """Create and configure the Azure Speech SDK config."""
        if not self._settings.azure_speech_key or not self._settings.azure_speech_region:
            raise HTTPException(
                status_code=500,
                detail="Azure Speech credentials (AZURE_SPEECH_KEY, AZURE_SPEECH_REGION) are not configured."
            )
        
        speech_config = speechsdk.SpeechConfig(
            subscription=self._settings.azure_speech_key,
            region=self._settings.azure_speech_region
        )
        
        # We can also set language
        speech_config.speech_recognition_language = "en-US"
        
        return speech_config

    def create_push_stream(self) -> speechsdk.audio.PushAudioInputStream:
        """Create a push stream to feed audio bytes into Azure."""
        # Using a standard 16kHz, 16-bit, Mono PCM format (common for most mics)
        stream_format = speechsdk.audio.AudioStreamFormat(samples_per_second=16000, bits_per_sample=16, channels=1)
        return speechsdk.audio.PushAudioInputStream(stream_format)
