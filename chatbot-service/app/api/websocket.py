from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()


class PresenceEntry(BaseModel):
    client_key: str
    user_id: str | None = None
    guest_id: str | None = None
    user_type: str
    name: str | None = None
    online: bool = True
    last_seen_at: str


class ConnectionManager:
    def __init__(self) -> None:
        self._presence: dict[str, dict[str, PresenceEntry]] = {}

    async def set_presence(
        self,
        conversation_id: str,
        client_key: str,
        entry: PresenceEntry,
    ) -> None:
        self._presence.setdefault(conversation_id, {})[client_key] = entry

    async def get_presence_list(self, conversation_id: str) -> list[PresenceEntry]:
        return list(self._presence.get(conversation_id, {}).values())

    async def heartbeat(self, conversation_id: str, client_key: str) -> None:
        entry = self._presence.get(conversation_id, {}).get(client_key)
        if not entry:
            return

        self._presence[conversation_id][client_key] = entry.model_copy(
            update={
                "online": True,
                "last_seen_at": datetime.now(timezone.utc).isoformat(),
            }
        )

    async def remove_presence(self, conversation_id: str, client_key: str) -> None:
        entry = self._presence.get(conversation_id, {}).get(client_key)
        if not entry:
            return

        self._presence[conversation_id][client_key] = entry.model_copy(
            update={
                "online": False,
                "last_seen_at": datetime.now(timezone.utc).isoformat(),
            }
        )
