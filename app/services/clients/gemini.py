"""
Cliente para Google Gemini API — geracao de imagens + visao.

Modelos:
    - gemini-3.1-flash-image-preview (Nano Banana) — geracao de imagens
    - gemini-3-flash-preview — compreensao/descricao de imagens (visao)

API: https://generativelanguage.googleapis.com/v1beta/models/
"""

import base64
import uuid
from pathlib import Path

import httpx

from app.config import get_settings
from app.exceptions import IntegrationError
from app.utils.logging import get_logger

log = get_logger(__name__)

BASE_URL = "https://generativelanguage.googleapis.com/v1beta/models"
IMAGE_MODEL = "gemini-3.1-flash-image-preview"
VISION_MODEL = "gemini-3-flash-preview"


class GeminiClient:
    """Cliente para Gemini — geracao de imagens (Nano Banana) + visao."""

    def __init__(self, client: httpx.AsyncClient) -> None:
        settings = get_settings()
        self._client = client
        self._api_key = settings.gemini_api_key

    async def generate_image(
        self,
        prompt: str,
        *,
        extra_instruction: str | None = None,
        reference_image_url: str | None = None,
    ) -> str:
        """Gera uma imagem a partir de um prompt textual.

        Args:
            prompt: Descricao da imagem a gerar.
            extra_instruction: Instrucao adicional de estilo/refinamento.
            reference_image_url: URL de imagem de referencia para edicao.

        Returns:
            Path relativo (ex: 'media/abc123.png') do arquivo gerado.
        """
        full_prompt = prompt
        if extra_instruction:
            full_prompt = f"{prompt}\n\nInstrucoes de estilo: {extra_instruction}"

        parts: list[dict] = [{"text": full_prompt}]

        # Se tem imagem de referencia, faz download e anexa como inline_data
        if reference_image_url:
            ref_bytes, ref_mime = await self._fetch_reference(reference_image_url)
            parts.append({
                "inline_data": {
                    "mime_type": ref_mime,
                    "data": base64.b64encode(ref_bytes).decode(),
                }
            })

        payload = {
            "contents": [{"parts": parts}],
            "generationConfig": {"responseModalities": ["IMAGE"]},
        }

        resp = await self._client.post(
            f"{BASE_URL}/{IMAGE_MODEL}:generateContent",
            headers={
                "x-goog-api-key": self._api_key,
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=120.0,
        )

        if resp.status_code >= 400:
            raise IntegrationError(
                f"Gemini API falhou ({resp.status_code}): {resp.text}"
            )

        body = resp.json()
        image_data = self._extract_image(body)
        if not image_data:
            raise IntegrationError("Gemini nao retornou imagem na resposta")

        return self._save_image(image_data)

    async def _fetch_reference(self, url: str) -> tuple[bytes, str]:
        """Baixa imagem de referencia e retorna (bytes, mime_type)."""
        resp = await self._client.get(url, timeout=30.0)
        resp.raise_for_status()
        mime = resp.headers.get("content-type", "image/png")
        return resp.content, mime

    def _extract_image(self, body: dict) -> tuple[bytes, str] | None:
        """Extrai a primeira imagem da resposta da API."""
        candidates = body.get("candidates", [])
        for candidate in candidates:
            for part in candidate.get("content", {}).get("parts", []):
                inline = part.get("inlineData")
                if inline:
                    return base64.b64decode(inline["data"]), inline.get("mimeType", "image/png")
        return None

    def _save_image(self, image_data: tuple[bytes, str]) -> str:
        """Salva imagem em disco e retorna path relativo."""
        raw, mime = image_data
        ext_map = {
            "image/png": ".png", "image/jpeg": ".jpg", "image/webp": ".webp",
        }
        ext = ext_map.get(mime, ".png")
        filename = f"{uuid.uuid4().hex}{ext}"
        out = Path("data/public/media")
        out.mkdir(parents=True, exist_ok=True)
        path = out / filename
        path.write_bytes(raw)
        relative = f"media/{filename}"
        log.info("gemini.image_saved", mime=mime, size=len(raw), relative=relative)
        return relative

    # ------------------------------------------------------------------
    # Visao (image understanding)
    # ------------------------------------------------------------------

    async def describe_image(
        self,
        image_url: str,
        prompt: str = "Descreva esta imagem em detalhes.",
        *,
        language: str = "pt-BR",
    ) -> str:
        """Analisa uma imagem e retorna descricao textual (visao computacional).

        Usa gemini-3-flash-preview — o modelo de compreensao de imagens.
        Util para OCR natural, descricao de cenas, extracao de contexto visual.

        Args:
            image_url: URL da imagem a analisar (local /files/... ou externa).
            prompt: O que perguntar sobre a imagem.
            language: Idioma da resposta (default pt-BR).

        Returns:
            Texto da resposta do modelo.
        """
        img_bytes, mime = await self._fetch_reference(image_url)

        payload = {
            "contents": [{
                "parts": [
                    {
                        "inline_data": {
                            "mime_type": mime,
                            "data": base64.b64encode(img_bytes).decode(),
                        }
                    },
                    {"text": f"{prompt}\n\nResponda em {language}."},
                ]
            }],
        }

        resp = await self._client.post(
            f"{BASE_URL}/{VISION_MODEL}:generateContent",
            headers={
                "x-goog-api-key": self._api_key,
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=60.0,
        )

        if resp.status_code >= 400:
            raise IntegrationError(
                f"Gemini Vision falhou ({resp.status_code}): {resp.text}"
            )

        body = resp.json()
        text = self._extract_text(body)
        log.info(
            "gemini.image_described",
            url_preview=image_url[:80],
            prompt_preview=prompt[:60],
            response_len=len(text),
        )
        return text

    def _extract_text(self, body: dict) -> str:
        """Extrai texto da resposta de visao."""
        candidates = body.get("candidates", [])
        parts = []
        for candidate in candidates:
            parts.extend(candidate.get("content", {}).get("parts", []))
        texts = [p.get("text", "") for p in parts if "text" in p]
        return "\n".join(texts).strip()
