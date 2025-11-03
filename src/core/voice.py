
import os
import io
import time
import json
import requests
from pathlib import Path
from typing import Optional

from openai import OpenAI
from .config import settings
from .utils import save_bytes

class Speech:
    def __init__(self):
        self.client = OpenAI(api_key=settings.OPENAI_API_KEY)
        settings.validate()

    # ---- STT ----
    def stt(self, audio_path: str) -> Optional[str]:
        """Transcribe using OpenAI Whisper."""
        with open(audio_path, "rb") as f:
            resp = self.client.audio.transcriptions.create(
                model=settings.OPENAI_WHISPER_MODEL,
                file=f
            )
        # Newer SDKs return .text; keep generic
        text = getattr(resp, "text", None) or getattr(resp, "text", "")
        return text

    # ---- TTS ----
    def tts(self, text: str) -> str:
        """Synthesize speech using ElevenLabs. Returns a file path to an MP3."""
        voice_id = settings.ELEVENLABS_VOICE_ID
        if not voice_id:
            raise RuntimeError("ELEVENLABS_VOICE_ID not set")

        url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
        headers = {
            "xi-api-key": settings.ELEVENLABS_API_KEY,
            "Content-Type": "application/json"
        }
        payload = {
            "text": text,
            "model_id": "eleven_monolingual_v1",
            "voice_settings": {"stability": 0.4, "similarity_boost": 0.7}
        }
        r = requests.post(url, headers=headers, json=payload, timeout=60)
        r.raise_for_status()
        audio_bytes = r.content

        ts = int(time.time() * 1000)
        out_path = Path(settings.DEMOS_DIR) / f"assistant_{ts}.mp3"
        return save_bytes(str(out_path), audio_bytes)
