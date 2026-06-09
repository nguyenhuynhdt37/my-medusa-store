import pytest

from app.domain import AssignmentStatus, ConversationOwner, ConversationStatus, MessageStatus
from app.services.agent_service import AgentService
from app.services.chat_constants import RESUME_BOT_MESSAGE
from app.services.conversation_service import ConversationService, InvalidConversationTransition
from tests.test_facebook_webhook import FakeRepo


class FakeChannelAdapter:
    def __init__(self) -> None:
        self.sent: list[dict[str, str]] = []

    async def send_message(self, external_user_id: str, text: str) -> dict:
        self.sent.append({"external_user_id": external_user_id, "text": text})
        return {"recipient_id": external_user_id, "message_id": "fake_outbound"}


async def create_waiting_conversation(repo: FakeRepo):
    conversation = await repo.create_conversation(
        channel="MESSENGER",
        channel_account_id="page_1",
        external_user_id="psid_1",
        metadata={"source": "test"},
    )
    return await ConversationService(repo).mark_waiting_agent(
        conversation,
        reason="fallback",
    )


@pytest.mark.asyncio
async def test_take_conversation_assigns_agent_without_sending_message():
    repo = FakeRepo()
    adapter = FakeChannelAdapter()
    conversation = await create_waiting_conversation(repo)

    updated = await AgentService(repo, adapter).take_conversation(
        conversation.id,
        agent_id="agent_1",
        assigned_by="lead_1",
    )

    assert updated.status == ConversationStatus.AGENT_ASSIGNED
    assert updated.current_owner == ConversationOwner.AGENT
    assert updated.assigned_agent_id == "agent_1"
    assert adapter.sent == []
    assert repo.assignments[0].status == AssignmentStatus.ACTIVE
    assert repo.assignments[0].assigned_by == "lead_1"
    assert "AGENT_ASSIGNED" in [event.event_type for event in repo.events]


@pytest.mark.asyncio
async def test_send_agent_message_activates_waiting_conversation_and_sends_to_channel():
    repo = FakeRepo()
    adapter = FakeChannelAdapter()
    conversation = await create_waiting_conversation(repo)

    message = await AgentService(repo, adapter).send_agent_message(
        conversation.id,
        agent_id="agent_1",
        text="Shop hỗ trợ mình đây ạ.",
    )

    updated = await repo.get_conversation(conversation.id)
    assert updated.status == ConversationStatus.AGENT_ACTIVE
    assert message.status == MessageStatus.SENT
    assert message.sender_id == "agent_1"
    assert adapter.sent == [{"external_user_id": "psid_1", "text": "Shop hỗ trợ mình đây ạ."}]
    event_types = [event.event_type for event in repo.events]
    assert "AGENT_ACTIVE" in event_types
    assert "AGENT_MESSAGE_SENT" in event_types


@pytest.mark.asyncio
async def test_send_agent_message_after_take_marks_conversation_active():
    repo = FakeRepo()
    adapter = FakeChannelAdapter()
    conversation = await create_waiting_conversation(repo)
    service = AgentService(repo, adapter)
    await service.take_conversation(conversation.id, agent_id="agent_1", assigned_by="lead_1")

    await service.send_agent_message(
        conversation.id,
        agent_id="agent_1",
        text="Mình tiếp tục hỗ trợ nhé.",
    )

    updated = await repo.get_conversation(conversation.id)
    assert updated.status == ConversationStatus.AGENT_ACTIVE
    assert "AGENT_ACTIVE" in [event.event_type for event in repo.events]


@pytest.mark.asyncio
async def test_other_agent_cannot_take_active_assignment():
    repo = FakeRepo()
    adapter = FakeChannelAdapter()
    conversation = await create_waiting_conversation(repo)
    service = AgentService(repo, adapter)
    await service.take_conversation(conversation.id, agent_id="agent_1", assigned_by="lead_1")

    with pytest.raises(InvalidConversationTransition):
        await service.take_conversation(conversation.id, agent_id="agent_2", assigned_by="lead_2")

    updated = await repo.get_conversation(conversation.id)
    assert updated.assigned_agent_id == "agent_1"
    assert len(repo.assignments) == 1


@pytest.mark.asyncio
async def test_return_to_bot_releases_assignment_and_sends_resume_notice():
    repo = FakeRepo()
    adapter = FakeChannelAdapter()
    conversation = await create_waiting_conversation(repo)
    service = AgentService(repo, adapter)
    await service.take_conversation(conversation.id, agent_id="agent_1", assigned_by="lead_1")

    updated = await service.return_to_bot(conversation.id, agent_id="agent_1")

    assert updated.status == ConversationStatus.BOT_ACTIVE
    assert updated.current_owner == ConversationOwner.BOT
    assert updated.assigned_agent_id is None
    assert repo.assignments[0].status == AssignmentStatus.RELEASED
    assert adapter.sent == [{"external_user_id": "psid_1", "text": RESUME_BOT_MESSAGE}]
    assert "RETURNED_TO_BOT" in [event.event_type for event in repo.events]


@pytest.mark.asyncio
async def test_agent_cannot_send_message_while_bot_active():
    repo = FakeRepo()
    adapter = FakeChannelAdapter()
    conversation = await repo.create_conversation(
        channel="MESSENGER",
        channel_account_id="page_1",
        external_user_id="psid_1",
    )

    with pytest.raises(InvalidConversationTransition):
        await AgentService(repo, adapter).send_agent_message(
            conversation.id,
            agent_id="agent_1",
            text="Không được gửi khi bot active.",
        )

    assert adapter.sent == []
    assert repo.messages == []
