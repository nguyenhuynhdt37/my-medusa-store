import asyncio
from datetime import datetime, timezone
import pytest

from app.api.websocket import ConnectionManager, PresenceEntry


@pytest.mark.asyncio
async def test_presence_set_heartbeat_and_remove():
    mgr = ConnectionManager()
    conv_id = "conv_test"
    client_key = "client_1"

    entry = PresenceEntry(
        client_key=client_key,
        user_id=None,
        guest_id="guest_1",
        user_type="guest",
        name="Guest",
        online=True,
        last_seen_at=datetime.now(timezone.utc).isoformat(),
    )

    await mgr.set_presence(conv_id, client_key, entry)
    lst = await mgr.get_presence_list(conv_id)
    assert len(lst) == 1
    assert lst[0].client_key == client_key
    assert lst[0].online is True

    # heartbeat updates last_seen_at and keeps online
    old_last = lst[0].last_seen_at
    await asyncio.sleep(0.01)
    await mgr.heartbeat(conv_id, client_key)
    lst2 = await mgr.get_presence_list(conv_id)
    assert lst2[0].last_seen_at != old_last
    assert lst2[0].online is True

    # remove presence marks offline
    await mgr.remove_presence(conv_id, client_key)
    lst3 = await mgr.get_presence_list(conv_id)
    assert lst3[0].online is False
