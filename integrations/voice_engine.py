"""
OOA Voice Engine
=================
File    : integrations/voice_engine.py
Author  : Lead Backend Developer
Version : 1.0.0

STT : OpenAI Whisper API
TTS : ElevenLabs eleven_multilingual_v2
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Voice IDs per language (ElevenLabs)
# Get voice IDs from: elevenlabs.io/voice-library
# ---------------------------------------------------------------------------

VOICE_IDS = {
    "en": os.environ.get("ELEVENLABS_VOICE_EN", "JBFqnCBsd6RMkjVDRZzb"),  # George
    "ar": os.environ.get("ELEVENLABS_VOICE_AR", "JBFqnCBsd6RMkjVDRZzb"),  # Same until Arabic voice configured
    "ur": os.environ.get("ELEVENLABS_VOICE_UR", "JBFqnCBsd6RMkjVDRZzb"),
}


# ---------------------------------------------------------------------------
# Whisper STT
# ---------------------------------------------------------------------------

class WhisperSTT:
    """
    Transcribes audio using OpenAI Whisper API.
    Handles Arabic, Urdu, English with regional accents.
    """

    def __init__(self, api_key: str | None = None) -> None:
        import openai
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY required for WhisperSTT.")
        self.client = openai.OpenAI(api_key=self.api_key)

    def transcribe(
        self,
        audio_path   : str,
        language_hint: str | None = None,
    ) -> str:
        """
        Transcribes audio file to text.

        Args:
            audio_path    : Path to audio file (wav, mp3, m4a, webm, ogg)
            language_hint : ISO 639-1 hint for better accuracy (en, ar, ur)

        Returns:
            Transcribed text string.
        """
        logger.info("[WhisperSTT] Transcribing: %s", audio_path)

        with open(audio_path, "rb") as audio_file:
            kwargs = {
                "model"          : "whisper-1",
                "file"           : audio_file,
                "response_format": "text",
            }
            # Language hint improves accuracy for Arabic/Urdu
            if language_hint and language_hint in ("en", "ar", "ur"):
                kwargs["language"] = language_hint

            transcript = self.client.audio.transcriptions.create(**kwargs)

        result = transcript.strip() if isinstance(transcript, str) else str(transcript).strip()
        logger.info("[WhisperSTT] Transcript: '%s'", result[:80])
        return result


# ---------------------------------------------------------------------------
# ElevenLabs TTS
# ---------------------------------------------------------------------------

class ElevenLabsTTS:
    """
    Converts text to speech using ElevenLabs eleven_multilingual_v2.
    Supports Arabic, English, Urdu natively.
    """

    def __init__(self, api_key: str | None = None) -> None:
        self.api_key = api_key or os.environ.get("ELEVENLABS_API_KEY")
        if not self.api_key:
            raise ValueError("ELEVENLABS_API_KEY required for ElevenLabsTTS.")

    def synthesize(
        self,
        text    : str,
        language: str = "en",
    ) -> bytes:
        """
        Converts text to speech audio bytes.

        Args:
            text     : Text to speak
            language : ISO 639-1 language code (en, ar, ur)

        Returns:
            Audio bytes in MP3 format.
        """
        import requests

        voice_id = VOICE_IDS.get(language, VOICE_IDS["en"])

        logger.info(
            "[ElevenLabsTTS] Synthesizing — lang: %s | voice: %s | text: '%s...'",
            language, voice_id, text[:50],
        )

        # Clean text for TTS — remove markdown
        clean_text = self._clean_for_tts(text)

        response = requests.post(
            f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}",
            headers={
                "xi-api-key"  : self.api_key,
                "Content-Type": "application/json",
            },
            json={
                "text"         : clean_text,
                "model_id"     : "eleven_multilingual_v2",
                "voice_settings": {
                    "stability"        : 0.5,
                    "similarity_boost" : 0.75,
                    "style"            : 0.0,
                    "use_speaker_boost": True,
                },
            },
            timeout=30,
        )

        if response.status_code != 200:
            raise RuntimeError(
                f"ElevenLabs error {response.status_code}: {response.text[:200]}"
            )

        logger.info(
            "[ElevenLabsTTS] Synthesized %d bytes", len(response.content)
        )
        return response.content

    def _clean_for_tts(self, text: str) -> str:
        """Removes markdown formatting that sounds bad in speech."""
        import re
        # Remove markdown bold/italic
        text = re.sub(r'\*+([^*]+)\*+', r'\1', text)
        # Remove markdown headers
        text = re.sub(r'^#+\s+', '', text, flags=re.MULTILINE)
        # Remove bullet points
        text = re.sub(r'^\s*[-•]\s+', '', text, flags=re.MULTILINE)
        # Remove numbered lists markers
        text = re.sub(r'^\s*\d+\.\s+', '', text, flags=re.MULTILINE)
        # Remove extra whitespace
        text = re.sub(r'\n{3,}', '\n\n', text)
        # Limit length for TTS (ElevenLabs has limits)
        if len(text) > 2500:
            text = text[:2500] + "..."
        return text.strip()