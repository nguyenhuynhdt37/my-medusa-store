import asyncio

from fastapi.testclient import TestClient

import app.api.admin_conversations as admin_api
from app.domain import ConversationStatus
from app.main import app
from app.services.conversation_service import ConversationService
from app.services.chat_constants import RESUME_BOT_MESSAGE
from tests.test_facebook_webhook import FakeRepo


class FakeAdapter:
    def __init__(self) -> None:
        self.sent: list[dict[str, str]] = []

    async def send_message(self, external_user_id: str, text: str) -> dict:
        self.sent.append({"external_user_id": external_user_id, "text": text})
        return {"recipient_id": external_user_id, "message_id": "fake_outbound"}


async def create_waiting_repo() -> tuple[FakeRepo, str]:
    repo = FakeRepo()
    conversation = await repo.create_conversation(
        channel="MESSENGER",
        channel_account_id="page_1",
        external_user_id="psid_1",
    )
    conversation = await ConversationService(repo).mark_waiting_agent(conversation, reason="fallback")
    return repo, conversation.id


def install_admin_fakes(monkeypatch, repo: FakeRepo, adapter: FakeAdapter) -> None:
    async def fake_repo():
        return repo

    monkeypatch.setattr(admin_api, "repo", fake_repo)
    monkeypatch.setattr(admin_api, "get_channel_adapter", lambda channel: adapter)


def test_admin_take_send_and_return_to_bot(monkeypatch):
    repo, conversation_id = asyncio.run(create_waiting_repo())
    adapter = FakeAdapter()
    install_admin_fakes(monkeypatch, repo, adapter)
    client = TestClient(app)

    take_response = client.post(
        f"/admin/conversations/{conversation_id}/take",
        headers={"X-Agent-Id": "agent_1"},
    )
    assert take_response.status_code == 200
    assert take_response.json()["status"] == ConversationStatus.AGENT_ASSIGNED.value

    message_response = client.post(
        f"/admin/conversations/{conversation_id}/messages",
        json={"text": "Shop hỗ trợ mình đây ạ."},
        headers={"X-Agent-Id": "agent_1"},
    )
    assert message_response.status_code == 200
    assert message_response.json()["content"] == "Shop hỗ trợ mình đây ạ."
    assert adapter.sent[-1] == {"external_user_id": "psid_1", "text": "Shop hỗ trợ mình đây ạ."}

    return_response = client.post(
        f"/admin/conversations/{conversation_id}/return-to-bot",
        headers={"X-Agent-Id": "agent_1"},
    )
    assert return_response.status_code == 200
    assert return_response.json()["status"] == ConversationStatus.BOT_ACTIVE.value
    assert adapter.sent[-1] == {"external_user_id": "psid_1", "text": RESUME_BOT_MESSAGE}
