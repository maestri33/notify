"""
Cliente para a API Evolution GO v2 (WhatsApp via whatsmeow).

API alvo: 10.10.10.149 (configurado em Settings.whatsapp_api_base_url).

Endpoints implementados:
    - health()                — status global da API
    - check_numbers()         — verifica se numeros tem WhatsApp
    - get_jid()               — resolve JID a partir de numero
    - fetch_profile()         — perfil do usuario (foto, nome, status)
    - fetch_business_profile()— perfil comercial (endereco, categoria, etc.)
    - reject_call()           — rejeita uma chamada (Call)
    - send_text()             — envia mensagem de texto
    - send_media()            — envia imagem, video, audio, documento
    - send_whatsapp_audio()   — envia audio como nota de voz nativa (PTT)
    - send_sticker()          — envia sticker (WebP)
    - send_location()         — envia localizacao (pin no mapa)
    - send_contact()          — envia contato(s) vCard
    - send_poll()             — envia enquete interativa
    - send_buttons()          — envia botoes interativos (reply/url/copy)
    - send_reaction()         — reage a uma mensagem com emoji
    - send_status()           — publica status (story) no WhatsApp

Auth: header apikey (Settings.whatsapp_global_api_key).
Instancia: padrao "default", sobreponivel no construtor.
"""

from typing import Any

import httpx

from app.config import get_settings
from app.exceptions import IntegrationError
from app.integrations.http_client import request_with_retry
from app.utils.logging import get_logger

log = get_logger(__name__)

MEDIA_TYPES = {"image", "video", "audio", "document"}


class WhatsAppClient:
    """Cliente de alto nivel para a API Evolution GO v2 (WhatsApp)."""

    def __init__(self, client: httpx.AsyncClient, *, instance: str | None = None) -> None:
        settings = get_settings()
        self._client = client
        self._base_url = settings.whatsapp_api_base_url
        self._apikey = settings.whatsapp_global_api_key
        self._instance = instance or settings.whatsapp_instance_name

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _headers(self) -> dict[str, str]:
        return {"apikey": self._apikey}

    def _msg_path(self, endpoint: str) -> str:
        """POST /message/<endpoint>/<instance>"""
        return f"/message/{endpoint}/{self._instance}"

    def _chat_path(self, endpoint: str) -> str:
        """POST /chat/<endpoint>/<instance>"""
        return f"/chat/{endpoint}/{self._instance}"

    async def _post(self, path: str, json: dict[str, Any], *, timeout: float | None = None) -> dict[str, Any]:
        kwargs: dict[str, Any] = {}
        if timeout is not None:
            kwargs["timeout"] = httpx.Timeout(timeout, connect=5.0)
        resp = await request_with_retry(
            self._client,
            "POST",
            f"{self._base_url}{path}",
            json=json,
            headers=self._headers(),
            **kwargs,
        )
        if resp.status_code >= 400:
            raise IntegrationError(
                f"WhatsApp API {path} falhou ({resp.status_code}): {resp.text}"
            )
        return resp.json()

    async def _get(self, path: str) -> dict[str, Any]:
        resp = await request_with_retry(
            self._client,
            "GET",
            f"{self._base_url}{path}",
            headers=self._headers(),
        )
        if resp.status_code >= 400:
            raise IntegrationError(
                f"WhatsApp API {path} falhou ({resp.status_code}): {resp.text}"
            )
        return resp.json()

    def _build_quoted(
        self,
        message_id: str | None,
        participant: str | None = None,
    ) -> dict[str, str] | None:
        """Monta o objeto quoted (reply) se houver message_id."""
        if not message_id:
            return None
        quoted: dict[str, str] = {"messageId": message_id}
        if participant:
            quoted["participant"] = participant
        return quoted

    # ------------------------------------------------------------------
    # Health
    # ------------------------------------------------------------------

    async def health(self) -> dict[str, Any]:
        """Verifica o status global da API Evolution."""
        return await self._get("/instance/status")

    # ------------------------------------------------------------------
    # Chat / User
    # ------------------------------------------------------------------

    async def check_numbers(self, numbers: list[str]) -> list[dict[str, Any]]:
        """Verifica se numeros possuem WhatsApp.

        Endpoint: POST /chat/whatsappNumbers/{instance}

        Request: {"numbers": ["5543996648750", "5511999999999"]}

        Response: [
            {"jid": "554396648750@s.whatsapp.net", "exists": true,
             "number": "5543996648750", "name": "Fulano"},
        ]

        Args:
            numbers: Lista de numeros (formato: DDI+DDD+numero, ex: "5543996648750").
        """
        result = await self._post(
            self._chat_path("whatsappNumbers"),
            {"numbers": numbers},
        )
        log.info("whatsapp.check", count=len(numbers))
        return result

    async def get_jid(self, number: str) -> str | None:
        """Obtem o JID de um numero WhatsApp.

        Chama /chat/whatsappNumbers e extrai o JID do primeiro resultado.

        Args:
            number: Numero DDI+DDD+numero (ex: "5543996648750").

        Returns:
            JID (ex: "554396648750@s.whatsapp.net") ou None se nao encontrado.
        """
        result = await self.check_numbers([number])
        if not result or not result[0].get("exists"):
            log.info("whatsapp.jid_not_found", number=number)
            return None
        jid = result[0].get("jid")
        log.info("whatsapp.jid_resolved", number=number, jid=jid)
        return jid

    async def fetch_profile(self, number: str) -> dict[str, Any]:
        """Obtem perfil de um usuario WhatsApp (foto, nome, status).

        Endpoint: POST /chat/fetchProfile/{instance}

        Args:
            number: Numero DDI+DDD+numero (ex: "5543996648750").

        Returns:
            dict com chaves: wuid, name, numberExists, picture (URL),
            status ({status, setAt}), isBusiness.
        """
        result = await self._post(
            self._chat_path("fetchProfile"),
            {"number": number},
        )
        log.info(
            "whatsapp.profile_fetched",
            number=number,
            has_picture=bool(result.get("picture")),
        )
        return result

    async def fetch_business_profile(self, number: str) -> dict[str, Any]:
        """Obtem perfil comercial de um usuario WhatsApp Business.

        Endpoint: POST /chat/fetchBusinessProfile/{instance}

        Args:
            number: Numero DDI+DDD+numero (ex: "554220181533").

        Returns:
            dict com dados do perfil comercial (address, website,
            category, business_hours, etc.). Para contas pessoais,
            retorna isBusiness=false.
        """
        result = await self._post(
            self._chat_path("fetchBusinessProfile"),
            {"number": number},
        )
        log.info(
            "whatsapp.business_profile_fetched",
            number=number,
            is_business=result.get("isBusiness", False),
        )
        return result

    # ------------------------------------------------------------------
    # Call
    # ------------------------------------------------------------------

    async def reject_call(
        self,
        call_id: str,
        call_creator: str,
    ) -> dict[str, Any]:
        """Rejeita uma chamada WhatsApp entrante.

        Endpoint: POST /call/reject/{instance}

        Args:
            call_id: ID da chamada recebida via webhook.
            call_creator: JID do originador da chamada
                (ex: "5511999999999@s.whatsapp.net").
        """
        result = await self._post(
            f"/call/reject/{self._instance}",
            {"callId": call_id, "callCreator": call_creator},
        )
        log.info("whatsapp.call_rejected", call_id=call_id, creator=call_creator)
        return result

    # ------------------------------------------------------------------
    # Send text
    # ------------------------------------------------------------------

    async def send_text(
        self,
        number: str,
        text: str,
        *,
        delay: int | None = None,
        quoted_msg_id: str | None = None,
        quoted_participant: str | None = None,
        mention_all: bool = False,
        mentioned_jid: list[str] | None = None,
        format_jid: bool | None = None,
    ) -> dict[str, Any]:
        """Envia uma mensagem de texto.

        Endpoint: POST /message/sendText/{instance}

        Args:
            number: Destinatario DDI+DDD+numero (ex: "5543996648750").
            text: Conteudo da mensagem.
            delay: ms de "digitando..." antes do envio.
            quoted_msg_id: ID da mensagem a responder (reply).
            quoted_participant: Remetente original da msg citada (grupos).
            mention_all: Menciona todos os participantes (grupos).
            mentioned_jid: Lista de JIDs especificos para @mencionar.
            format_jid: Se false, pula validacao/formatacao do numero.
        """
        payload: dict[str, Any] = {"number": number, "text": text}
        if delay is not None:
            payload["delay"] = delay
        if quoted := self._build_quoted(quoted_msg_id, quoted_participant):
            payload["quoted"] = quoted
        if mention_all:
            payload["mentionAll"] = True
        if mentioned_jid:
            payload["mentionedJid"] = mentioned_jid
        if format_jid is not None:
            payload["formatJid"] = format_jid

        result = await self._post(self._msg_path("sendText"), payload)
        log.info("whatsapp.text_sent", number=number, text_preview=text[:50])
        return result

    # ------------------------------------------------------------------
    # Send media (todos os tipos)
    # ------------------------------------------------------------------

    async def send_media(
        self,
        number: str,
        media_url: str,
        media_type: str,
        *,
        caption: str | None = None,
        filename: str | None = None,
        mimetype: str | None = None,
        delay: int | None = None,
        quoted_msg_id: str | None = None,
        quoted_participant: str | None = None,
        mention_all: bool = False,
        mentioned_jid: list[str] | None = None,
        format_jid: bool | None = None,
    ) -> dict[str, Any]:
        """Envia midia (imagem, video, audio, documento).

        Endpoint: POST /message/sendMedia/{instance}

        ┌──────────┬──────────────────────┬─────────────────────────────────┐
        │ type     │ O que envia          │ Aparece como                     │
        ├──────────┼──────────────────────┼─────────────────────────────────┤
        │ image    │ Foto                 │ Imagem inline (JPEG, PNG, WebP)  │
        │ video    │ Video                │ Player de video (MP4)            │
        │ audio    │ Audio                │ Arquivo de audio                 │
        │ document │ Documento / PDF      │ Arquivo com nome (qualquer ext.) │
        └──────────┴──────────────────────┴─────────────────────────────────┘

        Args:
            number: Destinatario.
            media_url: URL publica do arquivo ou base64 PURO (sem prefixo).
            media_type: Tipo — "image", "video", "audio" ou "document".
            caption: Legenda abaixo da midia (image/video/document).
            filename: Nome do arquivo (obrigatorio p/ document).
            mimetype: MIME type explicito (ex: "image/png").
            delay: ms de "digitando..." antes do envio.
            quoted_msg_id: ID da mensagem a responder (reply).
            quoted_participant: Remetente original da msg citada (grupos).
            mention_all: Menciona todos os participantes (grupos).
            mentioned_jid: Lista de JIDs especificos para @mencionar.
            format_jid: Se false, pula validacao/formatacao do numero.
        """
        if media_type not in MEDIA_TYPES:
            raise IntegrationError(
                f"media_type invalido: {media_type}. Use: {', '.join(sorted(MEDIA_TYPES))}"
            )

        payload: dict[str, Any] = {
            "number": number,
            "mediatype": media_type,
            "media": media_url,
        }
        if caption:
            payload["caption"] = caption
        if filename:
            payload["fileName"] = filename
        if mimetype:
            payload["mimetype"] = mimetype
        if delay is not None:
            payload["delay"] = delay
        if quoted := self._build_quoted(quoted_msg_id, quoted_participant):
            payload["quoted"] = quoted
        if mention_all:
            payload["mentionAll"] = True
        if mentioned_jid:
            payload["mentionedJid"] = mentioned_jid
        if format_jid is not None:
            payload["formatJid"] = format_jid

        result = await self._post(self._msg_path("sendMedia"), payload)
        log.info(
            "whatsapp.media_sent",
            number=number,
            type=media_type,
            url=media_url[:80],
        )
        return result

    # ------------------------------------------------------------------
    # Send WhatsApp Audio (nota de voz nativa)
    # ------------------------------------------------------------------

    async def send_whatsapp_audio(
        self,
        number: str,
        audio_url: str,
        *,
        delay: int | None = None,
        quoted_msg_id: str | None = None,
        quoted_participant: str | None = None,
    ) -> dict[str, Any]:
        """Envia audio como nota de voz nativa do WhatsApp (PTT).

        Endpoint: POST /message/sendWhatsAppAudio/{instance}

        Diferente do send_media com mediatype="audio", este endpoint
        forcça o formato de mensagem de voz nativa (waveform + UI de audio).

        Args:
            number: Destinatario.
            audio_url: URL publica do arquivo de audio (mp3, wav, ogg, etc.).
            delay: ms de "digitando..." antes do envio.
            quoted_msg_id: ID da mensagem a responder.
            quoted_participant: Remetente original da msg citada (grupos).
        """
        payload: dict[str, Any] = {"number": number, "audio": audio_url}
        if delay is not None:
            payload["delay"] = delay
        if quoted := self._build_quoted(quoted_msg_id, quoted_participant):
            payload["quoted"] = quoted

        result = await self._post(self._msg_path("sendWhatsAppAudio"), payload, timeout=60.0)
        log.info("whatsapp.audio_sent", number=number, url=audio_url[:80])
        return result

    # ------------------------------------------------------------------
    # Send sticker
    # ------------------------------------------------------------------

    async def send_sticker(
        self,
        number: str,
        sticker_url: str,
        *,
        delay: int | None = None,
        quoted_msg_id: str | None = None,
        quoted_participant: str | None = None,
    ) -> dict[str, Any]:
        """Envia um sticker (WebP recomendado).

        Endpoint: POST /message/sendSticker/{instance}

        Args:
            number: Destinatario.
            sticker_url: URL publica do arquivo WebP ou base64 PURO (sem prefixo).
            delay: ms de "digitando..." antes do envio.
            quoted_msg_id: ID da mensagem a responder (reply).
            quoted_participant: Remetente original da msg citada (grupos).
        """
        payload: dict[str, Any] = {
            "number": number,
            "sticker": sticker_url,
        }
        if delay is not None:
            payload["delay"] = delay
        if quoted := self._build_quoted(quoted_msg_id, quoted_participant):
            payload["quoted"] = quoted

        result = await self._post(self._msg_path("sendSticker"), payload)
        log.info("whatsapp.sticker_sent", number=number, url=sticker_url[:80])
        return result

    # ------------------------------------------------------------------
    # Send location
    # ------------------------------------------------------------------

    async def send_location(
        self,
        number: str,
        latitude: float,
        longitude: float,
        *,
        name: str | None = None,
        address: str | None = None,
        delay: int | None = None,
        quoted_msg_id: str | None = None,
        quoted_participant: str | None = None,
    ) -> dict[str, Any]:
        """Envia uma localizacao (pin no mapa).

        Endpoint: POST /message/sendLocation/{instance}

        Args:
            number: Destinatario.
            latitude: Latitude (ex: -23.5505).
            longitude: Longitude (ex: -46.6333).
            name: Nome do local (opcional).
            address: Endereco (opcional).
            delay: ms de "digitando..." antes do envio.
            quoted_msg_id: ID da mensagem a responder.
            quoted_participant: Remetente original da msg citada (grupos).
        """
        payload: dict[str, Any] = {
            "number": number,
            "latitude": latitude,
            "longitude": longitude,
        }
        if name:
            payload["name"] = name
        if address:
            payload["address"] = address
        if delay is not None:
            payload["delay"] = delay
        if quoted := self._build_quoted(quoted_msg_id, quoted_participant):
            payload["quoted"] = quoted

        result = await self._post(self._msg_path("sendLocation"), payload)
        log.info(
            "whatsapp.location_sent",
            number=number,
            lat=latitude,
            lon=longitude,
        )
        return result

    # ------------------------------------------------------------------
    # Send contact
    # ------------------------------------------------------------------

    async def send_contact(
        self,
        number: str,
        contacts: list[dict[str, str]],
        *,
        delay: int | None = None,
        quoted_msg_id: str | None = None,
        quoted_participant: str | None = None,
    ) -> dict[str, Any]:
        """Envia um ou mais contatos (vCard).

        Endpoint: POST /message/sendContact/{instance}

        Args:
            number: Destinatario.
            contacts: Lista de contatos. Cada dict deve ter:
                - fullName (obrigatorio)
                - phoneNumber (obrigatorio, formato internacional)
                - organization (opcional)
                - email (opcional)
            delay: ms de "digitando..." antes do envio.
            quoted_msg_id: ID da mensagem a responder.
            quoted_participant: Remetente original da msg citada (grupos).
        """
        payload: dict[str, Any] = {
            "number": number,
            "contact": contacts,
        }
        if delay is not None:
            payload["delay"] = delay
        if quoted := self._build_quoted(quoted_msg_id, quoted_participant):
            payload["quoted"] = quoted

        result = await self._post(self._msg_path("sendContact"), payload)
        log.info(
            "whatsapp.contact_sent",
            number=number,
            contact_count=len(contacts),
        )
        return result

    # ------------------------------------------------------------------
    # Send poll
    # ------------------------------------------------------------------

    async def send_poll(
        self,
        number: str,
        name: str,
        values: list[str],
        *,
        selectable_count: int = 1,
        delay: int | None = None,
        quoted_msg_id: str | None = None,
        quoted_participant: str | None = None,
    ) -> dict[str, Any]:
        """Envia uma enquete interativa.

        Endpoint: POST /message/sendPoll/{instance}

        Args:
            number: Destinatario.
            name: Titulo/pergunta da enquete.
            values: Lista de opcoes (max 12).
            selectable_count: Quantas opcoes o usuario pode escolher (default 1).
            delay: ms de "digitando..." antes do envio.
            quoted_msg_id: ID da mensagem a responder.
            quoted_participant: Remetente original da msg citada (grupos).
        """
        payload: dict[str, Any] = {
            "number": number,
            "name": name,
            "selectableCount": selectable_count,
            "values": values,
        }
        if delay is not None:
            payload["delay"] = delay
        if quoted := self._build_quoted(quoted_msg_id, quoted_participant):
            payload["quoted"] = quoted

        result = await self._post(self._msg_path("sendPoll"), payload)
        log.info(
            "whatsapp.poll_sent",
            number=number,
            name=name,
            options=len(values),
        )
        return result

    # ------------------------------------------------------------------
    # Send buttons
    # ------------------------------------------------------------------

    async def send_buttons(
        self,
        number: str,
        title: str,
        buttons: list[dict[str, Any]],
        *,
        description: str | None = None,
        footer: str | None = None,
        thumbnail_url: str | None = None,
        delay: int | None = None,
        quoted_msg_id: str | None = None,
        quoted_participant: str | None = None,
    ) -> dict[str, Any]:
        """Envia mensagem com botoes interativos.

        Endpoint: POST /message/sendButtons/{instance}

        Args:
            number: Destinatario.
            title: Titulo da mensagem (aparece em negrito).
            buttons: Lista de botoes (max 3). Cada botao:
                - type: "reply" | "url" | "copy"
                - displayText: texto exibido
                - Para reply: id do botao
                - Para url: url de destino
                - Para copy: copyText com texto a copiar
            description: Subtitulo/descricao (opcional).
            footer: Rodape (opcional).
            thumbnail_url: URL da miniatura (opcional).
            delay: ms de "digitando..." antes do envio.
            quoted_msg_id: ID da mensagem a responder.
            quoted_participant: Remetente original da msg citada (grupos).
        """
        payload: dict[str, Any] = {
            "number": number,
            "title": title,
            "buttons": buttons,
        }
        if description:
            payload["description"] = description
        if footer:
            payload["footer"] = footer
        if thumbnail_url:
            payload["thumbnailUrl"] = thumbnail_url
        if delay is not None:
            payload["delay"] = delay
        if quoted := self._build_quoted(quoted_msg_id, quoted_participant):
            payload["quoted"] = quoted

        result = await self._post(self._msg_path("sendButtons"), payload)
        log.info(
            "whatsapp.buttons_sent",
            number=number,
            title=title,
            button_count=len(buttons),
        )
        return result

    # ------------------------------------------------------------------
    # Send reaction
    # ------------------------------------------------------------------

    async def send_reaction(
        self,
        number: str,
        key: dict[str, Any],
        reaction: str,
        *,
        delay: int | None = None,
    ) -> dict[str, Any]:
        """Envia uma reacao (emoji) a uma mensagem.

        Endpoint: POST /message/sendReaction/{instance}

        Args:
            number: Destinatario (chat onde a mensagem esta).
            key: Identificador da mensagem alvo:
                {"remoteJid": "5511...@s.whatsapp.net",
                 "id": "MESSAGE_ID",
                 "fromMe": true/false}
            reaction: Emoji da reacao (ex: "❤️"). String vazia remove.
            delay: ms de "digitando..." antes do envio.
        """
        payload: dict[str, Any] = {
            "number": number,
            "key": key,
            "reaction": reaction,
        }
        if delay is not None:
            payload["delay"] = delay

        result = await self._post(self._msg_path("sendReaction"), payload)
        log.info("whatsapp.reaction_sent", number=number, reaction=reaction)
        return result

    # ------------------------------------------------------------------
    # Send status (story)
    # ------------------------------------------------------------------

    async def send_status(
        self,
        number: str,
        status_type: str,
        content: str,
        *,
        status_jid_list: list[str] | None = None,
        all_contacts: bool = False,
        background_color: str | None = None,
        font: int | None = None,
        caption: str | None = None,
    ) -> dict[str, Any]:
        """Publica um status (story) no WhatsApp.

        Endpoint: POST /message/sendStatus/{instance}

        Args:
            number: Numero do remetente (quem publica).
            status_type: "text" ou "image".
            content: Texto do status ou URL da imagem.
            status_jid_list: Lista de JIDs que podem ver o status.
            all_contacts: Se True, todos os contatos podem ver.
            background_color: Cor de fundo hex (p/ status de texto).
            font: Fonte 1-5 (SERIF, NORICAN, BRYNDAN, BEBASNEUE, OSWALD).
            caption: Legenda (p/ status de imagem).
        """
        payload: dict[str, Any] = {
            "number": number,
            "type": status_type,
            "content": content,
        }
        if status_jid_list is not None:
            payload["statusJidList"] = status_jid_list
        if all_contacts:
            payload["allContacts"] = True
        if background_color:
            payload["backgroundColor"] = background_color
        if font is not None:
            payload["font"] = font
        if caption:
            payload["caption"] = caption

        result = await self._post(self._msg_path("sendStatus"), payload)
        log.info(
            "whatsapp.status_sent",
            number=number,
            type=status_type,
        )
        return result
