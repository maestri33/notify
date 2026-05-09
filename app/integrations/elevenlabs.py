"""
Cliente para ElevenLabs Text-to-Speech.

Usa o SDK oficial elevenlabs (modelo eleven_v3).
"""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import TYPE_CHECKING

from app.config import get_settings
from app.utils.logging import get_logger

if TYPE_CHECKING:
    from elevenlabs.client import ElevenLabs

log = get_logger(__name__)

# Lazy import — o SDK faz chamadas de rede no __init__
_elevenlabs: ElevenLabs | None = None


def _get_client() -> ElevenLabs:
    global _elevenlabs
    if _elevenlabs is None:
        from elevenlabs.client import ElevenLabs

        _elevenlabs = ElevenLabs(api_key=get_settings().elevenlabs_api_key)
    return _elevenlabs


class ElevenLabsClient:
    """Cliente para geracao de audio via ElevenLabs TTS (eleven_v3)."""

    def __init__(self) -> None:
        settings = get_settings()
        self._voice_id = settings.elevenlabs_voice_id
        self._model_id: str = settings.elevenlabs_model_id
        self._output_format: str = settings.elevenlabs_output_format

    def text_to_speech(self, text: str) -> bytes:
        """Converte texto em audio (bytes MP3).

        Retorna bytes do arquivo MP3 pronto para salvar ou enviar.
        """
        client = _get_client()
        audio = client.text_to_speech.convert(
            text=text,
            voice_id=self._voice_id,
            model_id=self._model_id,
            output_format=self._output_format,
        )
        # SDK v2.x: convert() retorna iterable de chunks
        data = b"".join(audio) if not isinstance(audio, (bytes, bytearray)) else bytes(audio)
        log.info("elevenlabs.tts_generated", chars=len(text), bytes=len(data))
        return data

    def generate_and_save(self, text: str, output_dir: str = "media/audio") -> str:
        """Gera audio e salva em disco. Retorna o path relativo (p/ URL publica).

        Args:
            text: Texto a converter.
            output_dir: Pasta de destino (relativa a raiz do projeto).

        Returns:
            Path relativo para URL (ex: 'audio/abc123.mp3').
        """
        data = self.text_to_speech(text)
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)
        filename = f"{uuid.uuid4().hex}.mp3"
        path = out / filename
        path.write_bytes(data)
        relative = f"{out.name}/{filename}"
        log.info("elevenlabs.audio_saved", path=str(path), relative=relative)
        return relative
