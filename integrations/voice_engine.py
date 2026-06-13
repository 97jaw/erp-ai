"""
OOA Voice Engine
=================
File    : integrations/voice_engine.py
STT     : OpenAI Whisper API  (async-wrapped, language-hinted)
TTS     : ElevenLabs eleven_multilingual_v2  (streaming via httpx)
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
from io import BytesIO
from pathlib import Path
from typing import AsyncIterator

from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Voice IDs per language (ElevenLabs)
# ---------------------------------------------------------------------------
VOICE_IDS = {
    "en": os.environ.get("ELEVENLABS_VOICE_EN", "JBFqnCBsd6RMkjVDRZzb"),  # George
    "ar": os.environ.get("ELEVENLABS_VOICE_AR", ""),                        # Set Arabic voice ID in .env
    "ur": os.environ.get("ELEVENLABS_VOICE_UR", "JBFqnCBsd6RMkjVDRZzb"),
}

# Max chars to synthesize — ElevenLabs free tier limit; also keeps latency low.
# We summarize longer responses before TTS.
_TTS_MAX_CHARS = 800

# Whisper models: "whisper-1" is the only available model via OpenAI API.
_WHISPER_MODEL = "whisper-1"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _detect_language_hint(text: str) -> str | None:
    """Detect dominant language from transcript for Whisper hint."""
    arabic_chars = sum(1 for c in text if "؀" <= c <= "ۿ")
    if arabic_chars > len(text) * 0.25:
        return "ar"
    return None


def prepare_for_tts(text: str, max_chars: int = _TTS_MAX_CHARS) -> str:
    """Convert AI response text to voice-friendly speech.

    - Strips markdown (bold, headers, bullets, tables)
    - Converts numbered lists to natural sentences
    - Summarises table rows to a spoken count + first few items
    - Truncates at a sentence boundary within max_chars
    """
    # Remove markdown bold / italic
    text = re.sub(r"\*{1,3}([^*]+)\*{1,3}", r"\1", text)
    # Remove markdown headers
    text = re.sub(r"^#{1,6}\s+", "", text, flags=re.MULTILINE)
    # Remove horizontal rules
    text = re.sub(r"^[-=_]{3,}\s*$", "", text, flags=re.MULTILINE)

    # Detect and summarise markdown tables
    table_rows = re.findall(r"^\|.+\|$", text, flags=re.MULTILINE)
    if len(table_rows) > 3:
        # Count data rows (skip header + separator)
        data_rows = [r for r in table_rows if not re.match(r"^\|[-| :]+\|$", r)]
        # Extract first cell of first 3 data rows as a spoken preview
        preview_items = []
        for row in data_rows[:3]:
            cells = [c.strip() for c in row.strip("|").split("|")]
            if cells and cells[0]:
                preview_items.append(cells[0])
        summary = f"Found {len(data_rows)} items."
        if preview_items:
            summary += " Including: " + ", ".join(preview_items)
            if len(data_rows) > 3:
                summary += f", and {len(data_rows) - 3} more."
        # Replace table block with summary
        text = re.sub(r"(\|.+\|\n?)+", summary + "\n", text)

    # Convert bullet / numbered lists to spoken form
    text = re.sub(r"^\s*[-•]\s+", "- ", text, flags=re.MULTILINE)
    text = re.sub(r"^\s*(\d+)[.)]\s+", r"\1. ", text, flags=re.MULTILINE)

    # Collapse extra blank lines
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = text.strip()

    if len(text) <= max_chars:
        return text

    # Truncate at sentence boundary
    truncated = text[:max_chars]
    last_period = max(
        truncated.rfind(". "),
        truncated.rfind(".\n"),
        truncated.rfind("! "),
        truncated.rfind("? "),
    )
    if last_period > max_chars // 2:
        truncated = truncated[: last_period + 1]
    return truncated.strip()


# ---------------------------------------------------------------------------
# Whisper STT
# ---------------------------------------------------------------------------

class WhisperSTT:
    """Transcribes audio using OpenAI Whisper API (sync + async wrappers)."""

    def __init__(self, api_key: str | None = None) -> None:
        import openai
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY required for WhisperSTT.")
        self._client = openai.OpenAI(api_key=self.api_key)

    def transcribe(
        self,
        audio_path: str,
        language_hint: str | None = None,
    ) -> str:
        """Transcribe audio file to text (blocking).

        Args:
            audio_path    : Path to audio file (wav, mp3, m4a, webm, ogg)
            language_hint : ISO 639-1 hint — 'en', 'ar', or 'ur'.
                            Passing the correct language improves accuracy
                            and cuts Whisper latency by ~30%.
        """
        logger.info("[WhisperSTT] Transcribing: %s lang_hint=%s", audio_path, language_hint)

        audio_bytes = Path(audio_path).read_bytes()
        if len(audio_bytes) < 1024:
            raise ValueError("Audio recording is too short to transcribe.")

        audio_file = BytesIO(audio_bytes)
        audio_file.name = Path(audio_path).name or "audio.webm"

        kwargs: dict = {
            "model": _WHISPER_MODEL,
            "file": audio_file,
            "response_format": "text",
        }
        # Language hint improves accuracy for Arabic/Urdu-accented English too
        if language_hint and language_hint in ("en", "ar", "ur"):
            kwargs["language"] = language_hint if language_hint != "ur" else "hi"
            # Whisper uses "hi" (Hindi) for Urdu since they share the same model

        transcript = self._client.audio.transcriptions.create(**kwargs)
        result = transcript.strip() if isinstance(transcript, str) else str(transcript).strip()
        logger.info("[WhisperSTT] Transcript (%d chars): '%s'", len(result), result[:80])
        return result

    async def async_transcribe(
        self,
        audio_path: str,
        language_hint: str | None = None,
    ) -> str:
        """Non-blocking wrapper — runs Whisper in a thread so the event loop is free."""
        return await asyncio.to_thread(self.transcribe, audio_path, language_hint)


# ---------------------------------------------------------------------------
# ElevenLabs TTS
# ---------------------------------------------------------------------------

class ElevenLabsTTS:
    """Text-to-speech via ElevenLabs — supports streaming for lower latency."""

    def __init__(self, api_key: str | None = None) -> None:
        self.api_key = api_key or os.environ.get("ELEVENLABS_API_KEY")
        if not self.api_key:
            raise ValueError("ELEVENLABS_API_KEY required for ElevenLabsTTS.")

    def _voice_id(self, language: str) -> str:
        vid = VOICE_IDS.get(language) or VOICE_IDS["en"]
        if not vid:
            vid = VOICE_IDS["en"]
        return vid

    def _payload(self, text: str) -> dict:
        return {
            "text": text,
            "model_id": "eleven_multilingual_v2",
            "voice_settings": {
                "stability": 0.5,
                "similarity_boost": 0.75,
                "style": 0.0,
                "use_speaker_boost": True,
            },
        }

    def synthesize(self, text: str, language: str = "en") -> bytes:
        """Full synthesis (blocking). Returns complete MP3 bytes."""
        import requests

        voice_id = self._voice_id(language)
        clean = prepare_for_tts(text)
        logger.info("[ElevenLabsTTS] Synthesizing %d chars lang=%s", len(clean), language)

        response = requests.post(
            f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}",
            headers={"xi-api-key": self.api_key, "Content-Type": "application/json"},
            json=self._payload(clean),
            timeout=30,
        )
        if response.status_code != 200:
            raise RuntimeError(f"ElevenLabs error {response.status_code}: {response.text[:200]}")

        logger.info("[ElevenLabsTTS] Synthesized %d bytes", len(response.content))
        return response.content

    async def stream_synthesize(
        self,
        text: str,
        language: str = "en",
        chunk_size: int = 4096,
    ) -> AsyncIterator[bytes]:
        """Streaming synthesis — yields audio chunks as they arrive.

        First chunk arrives in ~500ms vs ~3s for full synthesis, which
        lets the frontend start playback immediately.
        """
        import httpx

        voice_id = self._voice_id(language)
        clean = prepare_for_tts(text)
        logger.info(
            "[ElevenLabsTTS] Stream-synthesizing %d chars lang=%s voice=%s",
            len(clean), language, voice_id,
        )

        url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}/stream"
        headers = {"xi-api-key": self.api_key, "Content-Type": "application/json"}

        async with httpx.AsyncClient(timeout=60) as client:
            async with client.stream("POST", url, headers=headers, json=self._payload(clean)) as resp:
                if resp.status_code != 200:
                    body = await resp.aread()
                    raise RuntimeError(f"ElevenLabs stream error {resp.status_code}: {body[:200]!r}")
                total = 0
                async for chunk in resp.aiter_bytes(chunk_size):
                    if chunk:
                        total += len(chunk)
                        yield chunk
                logger.info("[ElevenLabsTTS] Streamed %d bytes total", total)

    def _clean_for_tts(self, text: str) -> str:
        return prepare_for_tts(text)
