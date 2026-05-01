"""ElevenLabs TTS — generates OGG/Opus audio suitable for WhatsApp PTT."""

import base64

import niquests

from app.models import ServiceConfig
from app.services.config_store import load_service_config
from app.services.markdown import md_to_plain


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
    r = niquests.post(url, headers=headers, json=payload, timeout=60.0)

    if r.status_code >= 400:
        raise TTSError(f"elevenlabs {r.status_code}: {r.text[:300]}")
    return r.content


def synthesize_b64(markdown_content: str, *, strict: bool = False) -> str | None:
    """Convert markdown to plain text, synthesize as TTS, return base64-encoded audio.

    With strict=False (default), returns None on failure (graceful degradation).
    With strict=True, raises TTSError or ValueError on failure.
    """
    plain = md_to_plain(markdown_content)
    if not plain:
        if strict:
            raise ValueError("content is empty after stripping markdown")
        return None
    cfg = load_service_config()
    try:
        audio_bytes = synthesize(plain, cfg)
    except TTSError:
        if strict:
            raise
        return None
    if not audio_bytes:
        if strict:
            raise TTSError("TTS returned empty audio")
        return None
    return base64.b64encode(audio_bytes).decode()
