"""ElevenLabs TTS — generates OGG/Opus audio suitable for WhatsApp PTT."""

import httpx

from app.models import ServiceConfig


class TTSError(Exception):
    pass


def synthesize(text: str, cfg: ServiceConfig) -> bytes:
    """Synthesize `text` using ElevenLabs, return OGG/Opus bytes.

    WhatsApp voice notes (PTT) require OGG container with Opus codec.
    ElevenLabs supports `output_format=opus_48000_128` which ships as OGG.
    """
    if not cfg.elevenlabs_api_key or not cfg.elevenlabs_voice_id:
        raise TTSError("ElevenLabs credentials not configured")

    url = f"https://api.elevenlabs.io/v1/text-to-speech/{cfg.elevenlabs_voice_id}"
    headers = {
        "xi-api-key": cfg.elevenlabs_api_key,
        "accept": "audio/ogg",
        "content-type": "application/json",
    }
    payload = {
        "text": text,
        "model_id": cfg.elevenlabs_model_id,
        "output_format": "opus_48000_128",
    }
    with httpx.Client(timeout=60.0) as c:
        r = c.post(url, headers=headers, json=payload)
    if r.status_code >= 400:
        raise TTSError(f"elevenlabs {r.status_code}: {r.text[:300]}")
    return r.content
