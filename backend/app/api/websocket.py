"""WebSocket endpoints for real-time updates."""

from __future__ import annotations

import asyncio
import json
from datetime import datetime
from typing import Set

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter(tags=["WebSocket"])


class ConnectionManager:
    """Manages WebSocket connections for real-time updates."""

    def __init__(self) -> None:
        self.active_connections: Set[WebSocket] = set()
        self.store_connections: dict[str, Set[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, store_id: str = None):
        """Accept a WebSocket connection."""
        await websocket.accept()
        self.active_connections.add(websocket)
        if store_id:
            if store_id not in self.store_connections:
                self.store_connections[store_id] = set()
            self.store_connections[store_id].add(websocket)

    def disconnect(self, websocket: WebSocket, store_id: str = None):
        """Remove a WebSocket connection."""
        self.active_connections.discard(websocket)
        if store_id and store_id in self.store_connections:
            self.store_connections[store_id].discard(websocket)

    async def broadcast(self, message: dict):
        """Broadcast to all connected clients."""
        data = json.dumps(message, default=str)
        disconnected = set()
        for connection in self.active_connections:
            try:
                await connection.send_text(data)
            except Exception:
                disconnected.add(connection)
        self.active_connections -= disconnected

    async def broadcast_to_store(self, store_id: str, message: dict):
        """Broadcast to clients watching a specific store."""
        if store_id not in self.store_connections:
            return
        data = json.dumps(message, default=str)
        disconnected = set()
        for connection in self.store_connections[store_id]:
            try:
                await connection.send_text(data)
            except Exception:
                disconnected.add(connection)
        self.store_connections[store_id] -= disconnected


# Global connection manager
manager = ConnectionManager()


@router.websocket("/ws")
async def websocket_global(websocket: WebSocket):
    """Global WebSocket for all store updates."""
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            # Echo back or handle commands
            await websocket.send_json({
                "type": "ack",
                "timestamp": datetime.utcnow().isoformat(),
            })
    except WebSocketDisconnect:
        manager.disconnect(websocket)


@router.websocket("/ws/store/{store_id}")
async def websocket_store(websocket: WebSocket, store_id: str):
    """Store-specific WebSocket for live monitoring."""
    await manager.connect(websocket, store_id)
    try:
        while True:
            data = await websocket.receive_text()
            await websocket.send_json({
                "type": "ack",
                "store_id": store_id,
                "timestamp": datetime.utcnow().isoformat(),
            })
    except WebSocketDisconnect:
        manager.disconnect(websocket, store_id)
