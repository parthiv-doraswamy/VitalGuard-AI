"""In-process WebSocket fan-out for the single-instance synthetic demo."""
from __future__ import annotations
import asyncio
import json
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
    return {"type": "pong", "client_time": client_time if isinstance(client_time, (int, float)) else None,
            "server_time": _server_time()}


class LiveEventHub:
    """Broadcast persisted demo events to currently connected dashboard clients.

    Events are persisted before broadcast. This in-memory hub is intentionally
    single-process; reconnect recovery uses the REST history endpoint.
    """
    def __init__(self) -> None:
        self._clients: set[WebSocket] = set()
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        async with self._lock:
            self._clients.add(websocket)
        await websocket.send_json({"type": "connected", "server_time": _server_time(), "demo_only": True})

    async def disconnect(self, websocket: WebSocket) -> None:
        async with self._lock:
            self._clients.discard(websocket)

    async def broadcast(self, event: dict) -> None:
        async with self._lock:
            clients = list(self._clients)
        stale = []
        for client in clients:
            try:
                await client.send_json(event)
            except Exception:
                stale.append(client)
        if stale:
            async with self._lock:
                for client in stale:
                    self._clients.discard(client)

    async def serve(self, websocket: WebSocket) -> None:
        await self.connect(websocket)
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
