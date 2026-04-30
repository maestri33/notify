"""HTTP client for the Baileys Node.js sidecar."""

from typing import Any

import httpx

from app.config import settings


class BaileysError(Exception):
    pass


class BaileysClient:
    def __init__(self, base_url: str | None = None, timeout: float = 30.0) -> None:
        self.base_url = (base_url or settings.baileys_url).rstrip("/")
        self.timeout = timeout

    def _request(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        try:
            with httpx.Client(timeout=self.timeout) as c:
                r = c.request(method, f"{self.base_url}{path}", **kwargs)
        except httpx.HTTPError as e:
            raise BaileysError(f"sidecar unreachable: {e}") from e
        if r.status_code >= 400:
            raise BaileysError(f"sidecar {path} -> {r.status_code}: {r.text}")
        return r.json()

    # ── Status / Auth ────────────────────────────────────────────────────

    def status(self) -> dict[str, Any]:
        return self._request("GET", "/status")

    def qr_png(self) -> bytes | None:
        try:
            with httpx.Client(timeout=self.timeout) as c:
                r = c.get(f"{self.base_url}/qr")
        except httpx.HTTPError as e:
            raise BaileysError(f"sidecar unreachable: {e}") from e
        if r.status_code == 404:
            return None
        if r.status_code >= 400:
            raise BaileysError(f"qr -> {r.status_code}: {r.text}")
        return r.content

    def logs(self, limit: int = 50) -> list[str]:
        return self._request("GET", f"/logs?limit={limit}")["lines"]

    def logout(self) -> None:
        self._request("POST", "/logout")

    def restart(self) -> None:
        self._request("POST", "/restart")

    # ── Send ─────────────────────────────────────────────────────────────

    def validate(self, number: str) -> dict[str, Any]:
        """Returns {'exists': bool, 'jid': str|None}."""
        return self._request("POST", "/validate", json={"number": number})

    def send_text(self, jid: str, text: str) -> str:
        return self._request("POST", "/send/text", json={"jid": jid, "text": text})["message_id"]

    def send_media(
        self,
        jid: str,
        *,
        url: str | None = None,
        base64: str | None = None,
        mimetype: str,
        caption: str | None = None,
    ) -> str:
        payload: dict[str, Any] = {"jid": jid, "mimetype": mimetype}
        if url:
            payload["url"] = url
        if base64:
            payload["base64"] = base64
        if caption:
            payload["caption"] = caption
        return self._request("POST", "/send/media", json=payload)["message_id"]

    def send_ptt(self, jid: str, audio_base64: str) -> str:
        return self._request(
            "POST", "/send/ptt", json={"jid": jid, "audio_base64": audio_base64}
        )["message_id"]

    # ── Groups ───────────────────────────────────────────────────────────

    def list_groups(self) -> list[dict[str, Any]]:
        """GET /groups — all participating groups."""
        return self._request("GET", "/groups").get("groups", [])

    def get_group(self, jid: str) -> dict[str, Any]:
        """GET /groups/:jid — full group metadata including participants."""
        return self._request("GET", f"/groups/{jid}")

    def get_group_members(self, jid: str) -> dict[str, Any]:
        """GET /groups/:jid/members — subject + participants only."""
        return self._request("GET", f"/groups/{jid}/members")

    def get_group_invite(self, jid: str) -> dict[str, Any]:
        """GET /groups/:jid/invite — invite code + link."""
        return self._request("GET", f"/groups/{jid}/invite")

    # ── Users ────────────────────────────────────────────────────────────

    def get_user(self, jid: str) -> dict[str, Any]:
        """GET /users/:jid — profile picture URLs, status, contact info."""
        return self._request("GET", f"/users/{jid}")


def get_baileys() -> BaileysClient:
    return BaileysClient()
