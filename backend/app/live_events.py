"""Per-instance WebSocket fan-out.

Each backend instance pushes events to its own connected clients. Which events
exist, and their order, comes from the shared outbox (event_broker.py); this hub
only delivers. Bounded per instance: VITALGUARD_MAX_WEBSOCKETS connections, and a
per-client send timeout so one slow client cannot stall delivery to the others.
"""
from __future__ import annotations
import asyncio
import json
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
    return {"type": "pong", "client_time": client_time if isinstance(client_time, (int, float)) else None,
            "server_time": _server_time()}


class LiveEventHub:
    """Broadcast committed events to this instance's connected dashboard clients."""
    def __init__(self) -> None:
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
        timeout = float(os.getenv("VITALGUARD_WEBSOCKET_SEND_TIMEOUT_SECONDS", "2"))

        async def send(client: WebSocket) -> WebSocket | None:
            try:
                await asyncio.wait_for(client.send_json(event), timeout=timeout)
                return None
            except Exception:
                return client

        for client in await asyncio.gather(*(send(client) for client in clients)):
            if client is not None:
                # Dropped clients reconnect and recover missed events through REST.
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
