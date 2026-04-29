"""WebSocket client for the Baileys sidecar.

Connects to ws://{host}:{port}/ws and receives real-time events:
  connection.update  — status changes, QR, disconnects
  messages.upsert    — incoming & outgoing messages
  contacts.update    — contact changes
  creds.update       — credential updates

Usage:
    from app.baileys_ws import BaileysWS

    ws = BaileysWS()
    await ws.connect()

    async for event in ws:
        print(event)  # {"event": "messages.upsert", "data": {...}}

    # Or callback style:
    ws.on("messages.upsert", lambda data: print(data["messages"]))
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import AsyncIterator
from typing import Any, Callable, Optional

import websockets
from websockets.exceptions import ConnectionClosed, WebSocketException

log = logging.getLogger(__name__)

# Default sidecar URL; override via env BA ILEYS_WS_URL
DEFAULT_WS_URL = "ws://localhost:3000/ws"


class BaileysWS:
    """Async WebSocket client with auto-reconnect and event dispatch."""

    def __init__(self, url: str | None = None) -> None:
        self.url = url or DEFAULT_WS_URL
        self._ws: Optional[websockets.WebSocketClientProtocol] = None
        self._listeners: dict[str, list[Callable]] = {}
        self._queue: asyncio.Queue[dict] = asyncio.Queue()
        self._running = False
        self._task: Optional[asyncio.Task] = None

    # ── Public API ──────────────────────────────────────────────────────

    async def connect(self) -> None:
        """Start the WebSocket connection loop (non-blocking)."""
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._loop())

    async def disconnect(self) -> None:
        """Stop the connection loop."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        if self._ws:
            await self._ws.close()
            self._ws = None

    def on(self, event: str, handler: Callable[[dict], Any]) -> None:
        """Register a callback for a specific event type."""
        self._listeners.setdefault(event, []).append(handler)

    def off(self, event: str, handler: Callable[[dict], Any]) -> None:
        """Remove a previously registered callback."""
        if event in self._listeners:
            self._listeners[event] = [h for h in self._listeners[event] if h is not handler]

    async def __aiter__(self) -> AsyncIterator[dict]:
        """Iterate over incoming events (blocks until new event)."""
        while self._running:
            try:
                event = await self._queue.get()
                yield event
            except asyncio.CancelledError:
                break

    # ── Internal ─────────────────────────────────────────────────────────

    async def _loop(self) -> None:
        backoff = 1
        while self._running:
            try:
                async with websockets.connect(self.url, ping_interval=30, ping_timeout=10) as ws:
                    self._ws = ws
                    backoff = 1
                    log.info("WebSocket connected to %s", self.url)
                    await self._read_loop(ws)
            except (WebSocketException, OSError, asyncio.TimeoutError) as e:
                log.warning("WebSocket disconnected: %s — reconnecting in %ds", e, backoff)
            except Exception as e:
                log.error("WebSocket unexpected error: %s", e)

            self._ws = None
            if not self._running:
                break
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, 30)  # exponential backoff capped at 30s

    async def _read_loop(self, ws) -> None:
        async for raw in ws:
            if not self._running:
                break
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                continue

            event_type = msg.get("event", "unknown")
            data = msg.get("data", {})

            # Dispatch to registered callbacks
            for handler in self._listeners.get(event_type, []):
                try:
                    handler(data)
                except Exception:
                    log.exception("Handler for %s failed", event_type)

            # Also push to async iterator queue (skip if full, non-blocking)
            try:
                self._queue.put_nowait(msg)
            except asyncio.QueueFull:
                pass
