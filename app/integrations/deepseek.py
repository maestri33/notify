"""
Cliente para DeepSeek API — geracao de titulos e edicao de templates HTML.

Usa JSON mode para respostas estruturadas.
API: https://api.deepseek.com
"""

import json

import httpx

from app.config import get_settings
from app.exceptions import IntegrationError
from app.integrations.http_client import request_with_retry
from app.utils.logging import get_logger

log = get_logger(__name__)


class DeepSeekClient:
    """Cliente para a API do DeepSeek (chat completion com JSON mode)."""

    def __init__(self, client: httpx.AsyncClient) -> None:
        settings = get_settings()
        self._client = client
        self._api_key = settings.deepseek_api_key
        self._base_url = settings.deepseek_base_url
        self._default_model = settings.deepseek_default_model
        self._default_temperature = settings.deepseek_default_temperature

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

    async def _chat(
        self,
        system_prompt: str,
        user_message: str,
        *,
        model: str | None = None,
        temperature: float | None = None,
    ) -> dict:
        """Chama a API de chat e retorna o JSON parseado.

        Usa response_format json_object para garantir saida estruturada.
        Se model/temperature nao forem informados, usa os defaults do .env.
        """
        payload = {
            "model": model or self._default_model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            "temperature": temperature if temperature is not None else self._default_temperature,
            "response_format": {"type": "json_object"},
        }
        resp = await request_with_retry(
            self._client,
            "POST",
            f"{self._base_url}/chat/completions",
            json=payload,
            headers=self._headers(),
            timeout=60.0,
        )
        if resp.status_code >= 400:
            raise IntegrationError(
                f"DeepSeek API falhou ({resp.status_code}): {resp.text}"
            )

        body = resp.json()
        raw = body["choices"][0]["message"]["content"]
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            log.error(
                "deepseek.json_parse_failed",
                raw_preview=raw[:500],
                raw_len=len(raw),
            )
            raise

    # ------------------------------------------------------------------
    # Public
    # ------------------------------------------------------------------

    async def generate_title(self, content_text: str) -> str:
        """Gera um titulo curto (max 60 chars) baseado no conteudo da mensagem.

        Usa DeepSeek Flash para baixo custo e latencia.
        """
        result = await self._chat(
            system_prompt=(
                "Voce gera titulos curtos e descritivos para emails. "
                "Retorne um JSON com a chave 'title' contendo o titulo (max 60 caracteres). "
                "Sempre em portugues brasileiro, com acentuacao e pontuacao corretas. "
                "Tom natural, nao robotico."
            ),
            user_message=f"Gere um titulo para este conteudo:\n\n{content_text[:2000]}",
            model="deepseek-v4-flash",
        )
        title = result.get("title", "Nova mensagem")
        log.info("deepseek.title_generated", title=title)
        return title

    async def edit_html_template(self, current_html: str, instruction: str) -> str:
        """Edita um template HTML conforme instrucao do usuario.

        Usa DeepSeek Pro pela complexidade da tarefa (HTML + CSS + Jinja2).
        """
        result = await self._chat(
            system_prompt=(
                "Voce edita templates HTML de email conforme instrucoes do usuario. "
                "Retorne um JSON com a chave 'html' contendo o HTML completo editado. "
                "Preserve placeholders Jinja2 {{variavel}} intactos. "
                "Use CSS inline. O HTML deve ser responsivo e compativel com clientes de email. "
                "Textos do template sempre em portugues brasileiro com acentuacao correta."
            ),
            user_message=(
                f"Instrucao: {instruction}\n\n"
                f"HTML atual:\n{current_html}"
            ),
        )
        html = result.get("html", current_html)
        log.info("deepseek.template_edited", instruction_preview=instruction[:80])
        return html

    async def generate_message(
        self,
        prompt: str,
        *,
        extra_instruction: str | None = None,
        for_tts: bool = False,
    ) -> str:
        """Gera o texto de uma mensagem a partir de um prompt/instrucao.

        Usa DeepSeek Pro pela qualidade do texto gerado.
        Adapta o estilo se for para TTS (voz).
        """
        tts_guidance = (
            "O texto sera convertido em audio (TTS). "
            "Escreva de forma natural e conversacional, como se estivesse falando. "
            "Frases curtas. Sem marcacoes, emojis ou formatacao. "
            if for_tts
            else ""
        )
        instruction_line = (
            f"Instrucao adicional de estilo: {extra_instruction}"
            if extra_instruction
            else ""
        )
        result = await self._chat(
            system_prompt=(
                "Voce gera mensagens curtas e diretas para envio via WhatsApp e Email. "
                "Retorne um JSON com a chave 'message' contendo APENAS o texto final da mensagem. "
                "Regras: "
                "1. Sem meta-comentarios (ex: 'aqui esta a mensagem'). "
                "2. Sem aspas delimitando o texto. "
                "3. Sem marcacoes markdown (negrito, listas, etc) — texto puro. "
                "4. NUNCA use {{variavel}} ou qualquer placeholder com chaves duplas. "
                "Se precisar de um nome, use 'Voce' ou simplesmente omita. "
                "5. Tom natural e amigavel, nao-formal. "
                "6. Maximo 800 caracteres. "
                "7. SEMPRE portugues brasileiro com acentuacao e pontuacao corretas "
                "(ex: 'Voce' com acento circunflexo, 'nao' com til, etc). "
                + tts_guidance
            ),
            user_message=(
                f"Prompt: {prompt}\n{instruction_line}"
            ),
            temperature=0.7,
        )
        message = result.get("message", prompt)
        log.info(
            "deepseek.message_generated",
            prompt_preview=prompt[:80],
            tts=for_tts,
            length=len(message),
        )
        return message

    async def generate_image_prompt(self, context_text: str) -> str:
        """Gera um prompt de geracao de imagem coerente com o texto da mensagem.

        Usado quando --img vem sem instruction. O contexto (texto da mensagem)
        informa o que a imagem deve representar.
        """
        result = await self._chat(
            system_prompt=(
                "Voce gera prompts para geracao de imagens (Gemini/DALL-E). "
                "Retorne um JSON com a chave 'prompt' contendo o prompt. "
                "Regras: "
                "1. O prompt deve descrever uma imagem coerente com o texto fornecido. "
                "2. Seja visual e descritivo (estilo, cores, composicao). "
                "3. Inclua instrucoes de qualidade ('alta qualidade', 'profissional'). "
                "4. O prompt deve produzir uma imagem que combine com o contexto da mensagem. "
                "5. Maximo 300 caracteres. "
                "6. NAO inclua texto escrito na imagem (evite overtext). "
                "7. SEMPRE portugues brasileiro com acentuacao e pontuacao corretas. "
                "8. Retorne APENAS o prompt."
            ),
            user_message=(
                f"Contexto da mensagem (a imagem deve ser coerente com isto):\n\n"
                f"{context_text[:2000]}\n\n"
                f"Gere um prompt de geracao de imagem para este contexto."
            ),
            temperature=0.7,
        )
        prompt = result.get("prompt", context_text)
        log.info("deepseek.image_prompt_generated", length=len(prompt))
        return prompt
