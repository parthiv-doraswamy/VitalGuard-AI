"""Per-instance WebSocket fan-out.

Each backend instance pushes events to its connected clients. Event ordering and
replay come from the shared outbox (event_broker.py); this hub only delivers.
Slow clients are removed after a bounded send timeout so they cannot stall
healthy clients. Missed events must be recovered through REST history.
"""
from __future__ import annotations

import asyncio
import json
import math
import os
from datetime import datetime, timezone

from fastapi import WebSocket, WebSocketDisconnect


def _server_time() -> str:
    return datetime.now(timezone.utc).isoformat()


def _timed_pong(message: str) -> dict:
    """Echo the client's clock with the server's so receivers can estimate clock offset."""
    try:
        payload = json.loads(message)
    except ValueError:
        return {"type": "error", "detail": "Unsupported message"}
    if not isinstance(payload, dict) or payload.get("type") != "ping":
        return {"type": "error", "detail": "Unsupported message"}
    client_time = payload.get("client_time")
    return {
        "type": "pong",
        "client_time": client_time if isinstance(client_time, (int, float)) else None,
        "server_time": _server_time(),
    }


class LiveEventHub:
    """Broadcast committed events to this instance's connected dashboard clients."""

    def __init__(self, send_timeout_seconds: float | None = None) -> None:
        if send_timeout_seconds is None:
            raw_timeout = os.getenv("VITALGUARD_WEBSOCKET_SEND_TIMEOUT_SECONDS", "2")
            try:
                send_timeout_seconds = float(raw_timeout)
            except (TypeError, ValueError) as exc:
                raise ValueError("WebSocket send timeout must be a finite positive number") from exc
        if not math.isfinite(send_timeout_seconds) or send_timeout_seconds <= 0:
            raise ValueError("WebSocket send timeout must be a finite positive number")
        self._send_timeout_seconds = send_timeout_seconds
        self._clients: set[WebSocket] = set()
        self.rejected_connections = 0
        self.dropped_clients = 0

    def client_count(self) -> int:
        return len(self._clients)

    async def connect(self, websocket: WebSocket) -> bool:
        await websocket.accept()
        if len(self._clients) >= int(os.getenv("VITALGUARD_MAX_WEBSOCKETS", "1000")):
            self.rejected_connections += 1
            await websocket.send_json({"type": "error", "detail": "Live channel is at capacity; retry later"})
            await websocket.close(code=1013)
            return False
        self._clients.add(websocket)
        await websocket.send_json({"type": "connected", "server_time": _server_time(), "demo_only": True})
        return True

    async def disconnect(self, websocket: WebSocket) -> None:
        self._clients.discard(websocket)

    async def broadcast(self, event: dict) -> None:
        clients = list(self._clients)

        async def send(client: WebSocket) -> WebSocket | None:
            try:
                await asyncio.wait_for(client.send_json(event), timeout=self._send_timeout_seconds)
                return None
            except Exception:
                return client

        # Concurrent sends keep a slow socket from serially delaying every client.
        dropped = await asyncio.gather(*(send(client) for client in clients))
        for client in dropped:
            if client is not None:
                self._clients.discard(client)
                self.dropped_clients += 1

    async def serve(self, websocket: WebSocket) -> None:
        if not await self.connect(websocket):
            return
        try:
            while True:
                # Client messages are heartbeats/control only; no data writes.
                message = await websocket.receive_text()
                if message == "ping":
                    await websocket.send_json({"type": "pong"})
                elif message.startswith("{"):
                    await websocket.send_json(_timed_pong(message))
        except WebSocketDisconnect:
            await self.disconnect(websocket)
        except Exception:
            await self.disconnect(websocket)


hub = LiveEventHub()
