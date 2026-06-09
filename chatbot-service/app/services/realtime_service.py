from __future__ import annotations

from typing import Any


class RealtimeService:
    async def broadcast(self, event_type: str, payload: dict[str, Any]) -> None:
        print("[REALTIME_EVENT]", {"type": event_type, **payload}, flush=True)
