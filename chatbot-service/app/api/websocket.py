from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from typing import Dict, List, Any, Optional
from pydantic import BaseModel
import logging
import asyncio
import json
from datetime import datetime, timezone
import httpx
from app.clients.medusa_client import get_medusa_client
from app.core.config import settings

logger = logging.getLogger(__name__)
router = APIRouter()


class PresenceEntry(BaseModel):
    client_key: str
    user_id: Optional[str] = None
    guest_id: Optional[str] = None
    user_type: str
    name: Optional[str] = None
    online: bool = True
    last_seen_at: str


class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, List[WebSocket]] = {}
        self.admin_connections: List[WebSocket] = []
        # presence per conversation_id -> client_key -> PresenceEntry
        self.presence: Dict[str, Dict[str, PresenceEntry]] = {}
        # typing per conversation_id -> client_key -> typing payload
        self.typing: Dict[str, Dict[str, Dict[str, Any]]] = {}
        self._presence_lock = asyncio.Lock()
        self._typing_lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket, room_id: str):
        await websocket.accept()
        if room_id == "admin":
            self.admin_connections.append(websocket)
            logger.info("Admin connected to websocket")
        else:
            if room_id not in self.active_connections:
                self.active_connections[room_id] = []
            self.active_connections[room_id].append(websocket)
            logger.info(f"User connected to conversation: {room_id}")

    def disconnect(self, websocket: WebSocket, room_id: str):
        if room_id == "admin":
            if websocket in self.admin_connections:
                self.admin_connections.remove(websocket)
                logger.info("Admin disconnected from websocket")
        else:
            if room_id in self.active_connections and websocket in self.active_connections[room_id]:
                self.active_connections[room_id].remove(websocket)
                logger.info(f"User disconnected from conversation: {room_id}")

    async def _safe_broadcast(self, connections: List[WebSocket], message: Any) -> int:
        delivered = 0
        for connection in connections:
            try:
                await connection.send_json(message)
                delivered += 1
            except Exception as e:
                logger.error(f"Error sending WS message: {e}")
        return delivered

    async def broadcast(self, conversation_id: str, message: Any, notify_admin: bool = False):
        delivered = 0
        if conversation_id in self.active_connections:
            delivered += await self._safe_broadcast(self.active_connections[conversation_id], message)

        if notify_admin:
            delivered += await self._safe_broadcast(self.admin_connections, message)

        return delivered

    async def should_notify_admin(self, conversation_id: str) -> bool:
        if not conversation_id.startswith("01"):
            return False

        try:
            async with httpx.AsyncClient(base_url=settings.medusa_base_url, timeout=3.0) as client:
                response = await client.get(f"/admin/chats/{conversation_id}")
            if not response.is_success:
                logger.debug("Failed to resolve conversation status for admin WS notify: %s", response.status_code)
                return False
            status = (response.json().get("conversation") or {}).get("status")
            return status in {"WAITING_ADMIN", "IN_PROGRESS"}
        except Exception as e:
            logger.debug(f"Failed checking admin notification status: {e}")
            return False

    async def set_presence(self, conversation_id: str, client_key: str, entry: PresenceEntry):
        async with self._presence_lock:
            if conversation_id not in self.presence:
                self.presence[conversation_id] = {}
            self.presence[conversation_id][client_key] = entry
        # broadcast presence update to conversation and admin
        await self.broadcast_presence_update(conversation_id)

    async def heartbeat(self, conversation_id: str, client_key: str):
        async with self._presence_lock:
            conv = self.presence.get(conversation_id, {})
            if client_key in conv:
                conv[client_key].last_seen_at = datetime.now(timezone.utc).isoformat()
                conv[client_key].online = True
        await self.broadcast_presence_update(conversation_id)

    async def remove_presence(self, conversation_id: str, client_key: str):
        async with self._presence_lock:
            conv = self.presence.get(conversation_id, {})
            if client_key in conv:
                conv[client_key].online = False
                conv[client_key].last_seen_at = datetime.now(timezone.utc).isoformat()
        await self.broadcast_presence_update(conversation_id)

    async def get_presence_list(self, conversation_id: str) -> List[PresenceEntry]:
        async with self._presence_lock:
            conv = self.presence.get(conversation_id, {})
            return list(conv.values())

    async def broadcast_presence_update(self, conversation_id: str):
        entries = await self.get_presence_list(conversation_id)
        notify_admin = await self.should_notify_admin(conversation_id)
        payload = {
            "event": "presence.updated",
            "data": [e.dict() for e in entries],
            "conversation_id": conversation_id,
        }
        await self.broadcast(conversation_id, payload, notify_admin=notify_admin)

    async def set_typing(self, conversation_id: str, client_key: str, payload: Dict[str, Any]):
        async with self._typing_lock:
            if conversation_id not in self.typing:
                self.typing[conversation_id] = {}
            self.typing[conversation_id][client_key] = {
                **payload,
                "client_key": client_key,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
        notify_admin = await self.should_notify_admin(conversation_id)
        await self.broadcast(conversation_id, {
            "event": "typing.start",
            "conversation_id": conversation_id,
            "data": self.typing[conversation_id][client_key],
        }, notify_admin=notify_admin)

    async def clear_typing(self, conversation_id: str, client_key: str, payload: Optional[Dict[str, Any]] = None):
        async with self._typing_lock:
            conv = self.typing.get(conversation_id, {})
            typing_payload = conv.pop(client_key, None) or {}
        notify_admin = await self.should_notify_admin(conversation_id)
        await self.broadcast(conversation_id, {
            "event": "typing.stop",
            "conversation_id": conversation_id,
            "data": {
                **typing_payload,
                **(payload or {}),
                "client_key": client_key,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            },
        }, notify_admin=notify_admin)

    async def timeout_typing(self):
        timeout_seconds = 5
        now = datetime.now(timezone.utc)
        expired: List[tuple[str, str, Dict[str, Any]]] = []
        async with self._typing_lock:
            for conv_id, conv in list(self.typing.items()):
                for key, payload in list(conv.items()):
                    last = datetime.fromisoformat(payload["updated_at"])
                    if (now - last).total_seconds() > timeout_seconds:
                        expired.append((conv_id, key, conv.pop(key)))

        for conv_id, key, payload in expired:
            notify_admin = await self.should_notify_admin(conv_id)
            await self.broadcast(conv_id, {
                "event": "typing.stop",
                "conversation_id": conv_id,
                "data": {
                    **payload,
                    "client_key": key,
                    "timeout": True,
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                },
            }, notify_admin=notify_admin)


manager = ConnectionManager()


async def _presence_timeout_loop():
    # mark offline if no heartbeat for timeout seconds
    timeout_seconds = 30
    while True:
        try:
            now = datetime.now(timezone.utc)
            for conv_id, conv in list(manager.presence.items()):
                for key, entry in list(conv.items()):
                    last = datetime.fromisoformat(entry.last_seen_at)
                    delta = (now - last).total_seconds()
                    if entry.online and delta > timeout_seconds:
                        logger.info(f"Presence timeout: marking offline {key} in {conv_id}")
                        await manager.remove_presence(conv_id, key)
        except Exception as e:
            logger.error(f"Error in presence timeout loop: {e}")
        await asyncio.sleep(5)


async def _typing_timeout_loop():
    while True:
        try:
            await manager.timeout_typing()
        except Exception as e:
            logger.error(f"Error in typing timeout loop: {e}")
        await asyncio.sleep(2)


@router.on_event("startup")
async def _start_presence_loop():
    asyncio.create_task(_presence_timeout_loop())
    asyncio.create_task(_typing_timeout_loop())


@router.websocket("/ws/chat/{room_id}")
async def websocket_endpoint(websocket: WebSocket, room_id: str):
    await manager.connect(websocket, room_id)
    client_key = f"ws_{id(websocket)}"
    try:
        while True:
            data = await websocket.receive_text()
            # handle simple ping
            if data == "ping":
                await websocket.send_text("pong")
                continue

            try:
                payload = json.loads(data)
            except Exception:
                # ignore non-json messages
                continue

            event = payload.get("event")
            pdata = payload.get("data") or {}

            if event == "presence.subscribe":
                entry = PresenceEntry(
                    client_key=client_key,
                    user_id=pdata.get("user_id"),
                    guest_id=pdata.get("guest_id"),
                    user_type=pdata.get("user_type", "guest"),
                    name=pdata.get("name"),
                    online=True,
                    last_seen_at=datetime.now(timezone.utc).isoformat(),
                )
                await manager.set_presence(room_id, client_key, entry)
                # Persist presence to Medusa backend
                if room_id != "admin":
                    try:
                        async with httpx.AsyncClient(base_url=settings.medusa_base_url, timeout=5.0) as client:
                            await client.post(f"/admin/chats/{room_id}/presence", json=entry.dict())
                    except Exception as e:
                        logger.debug(f"Failed to persist presence to medusa: {e}")
            elif event == "presence.heartbeat":
                await manager.heartbeat(room_id, client_key)
                # update last_seen in Medusa
                if room_id != "admin":
                    try:
                        async with httpx.AsyncClient(base_url=settings.medusa_base_url, timeout=5.0) as client:
                            await client.post(f"/admin/chats/{room_id}/presence", json={"client_key": client_key, "last_seen_at": datetime.now(timezone.utc).isoformat(), "online": True})
                    except Exception as e:
                        logger.debug(f"Failed to persist heartbeat to medusa: {e}")
            elif event == "typing.start":
                target_room_id = pdata.get("conversation_id") if room_id == "admin" else room_id
                if not target_room_id:
                    continue
                await manager.set_typing(target_room_id, client_key, {
                    "user_type": pdata.get("user_type", "guest"),
                    "name": pdata.get("name"),
                })
            elif event == "typing.stop":
                target_room_id = pdata.get("conversation_id") if room_id == "admin" else room_id
                if not target_room_id:
                    continue
                await manager.clear_typing(target_room_id, client_key, {
                    "user_type": pdata.get("user_type", "guest"),
                    "name": pdata.get("name"),
                })
            else:
                # other events currently ignored here
                pass
    except WebSocketDisconnect:
        await manager.clear_typing(room_id, client_key)
        await manager.remove_presence(room_id, client_key)
        # mark offline in Medusa
        if room_id != "admin":
            try:
                async with httpx.AsyncClient(base_url=settings.medusa_base_url, timeout=5.0) as client:
                    await client.post(f"/admin/chats/{room_id}/presence", json={"client_key": client_key, "online": False, "last_seen_at": datetime.now(timezone.utc).isoformat()})
            except Exception as e:
                logger.debug(f"Failed to persist presence removal to medusa: {e}")
        manager.disconnect(websocket, room_id)


class BroadcastPayload(BaseModel):
    conversation_id: str
    event: str
    data: Any
    notify_admin: bool = False


@router.post("/api/broadcast")
async def broadcast_message(payload: BroadcastPayload):
    logger.info(
        "Broadcast request received conversation_id=%s event=%s notify_admin=%s sender_type=%s message_id=%s",
        payload.conversation_id,
        payload.event,
        payload.notify_admin,
        payload.data.get("sender_type") if isinstance(payload.data, dict) else None,
        payload.data.get("id") if isinstance(payload.data, dict) else None,
    )
    delivered = await manager.broadcast(
        payload.conversation_id,
        {
            "event": payload.event,
            "data": payload.data,
            "conversation_id": payload.conversation_id,
        },
        notify_admin=payload.notify_admin,
    )
    logger.info(
        "Broadcast completed conversation_id=%s delivered_to=%s",
        payload.conversation_id,
        delivered,
    )
    return {"status": "ok", "delivered_to": delivered}
