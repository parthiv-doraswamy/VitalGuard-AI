"""In-process WebSocket fan-out for the single-instance synthetic demo."""
from __future__ import annotations

import asyncio
from fastapi import WebSocket, WebSocketDisconnect


class LiveEventHub:
    """Broadcast persisted demo events to connected dashboard clients.

    Events are persisted before broadcast. The hub is intentionally
    single-process; reconnect recovery uses REST history. A slow/broken client
    is removed instead of holding up delivery to all other clients.
    """

    def __init__(self, send_timeout_seconds: float = 2.0) -> None:
        if send_timeout_seconds <= 0:
            raise ValueError("send_timeout_seconds must be positive")
        self._clients: set[WebSocket] = set()
        self._lock = asyncio.Lock()
        self._send_timeout_seconds = send_timeout_seconds

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        async with self._lock:
            self._clients.add(websocket)
        await websocket.send_json({"type": "connected", "demo_only": True})

    async def disconnect(self, websocket: WebSocket) -> None:
        async with self._lock:
            self._clients.discard(websocket)

    async def broadcast(self, event: dict) -> None:
        async with self._lock:
            clients = list(self._clients)
        stale = []
        for client in clients:
            try:
                await asyncio.wait_for(
                    client.send_json(event), timeout=self._send_timeout_seconds
                )
            except (Exception, asyncio.TimeoutError):
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
        except WebSocketDisconnect:
            await self.disconnect(websocket)
        except Exception:
            await self.disconnect(websocket)


hub = LiveEventHub()
