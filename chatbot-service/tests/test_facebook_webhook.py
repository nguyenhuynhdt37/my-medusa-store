import asyncio
import hashlib
import hmac
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone

from fastapi.testclient import TestClient

import app.api.facebook as facebook_api
from app.core.config import settings
from app.domain import (
    AssignmentStatus,
    BotReplyResult,
    Conversation,
    ConversationAssignment,
    ConversationEvent,
    ConversationOwner,
    ConversationStatus,
    Message,
    MessageDirection,
    MessageStatus,
    SenderType,
)
from app.main import app
from app.services.conversation_service import ConversationService


def test_facebook_webhook_verification(monkeypatch):
    monkeypatch.setattr(settings, "facebook_verify_token", "verify-token")

    response = TestClient(app).get(
        "/facebook/webhook",
        params={
            "hub.mode": "subscribe",
            "hub.verify_token": "verify-token",
            "hub.challenge": "challenge-value",
        },
    )

    assert response.status_code == 200
    assert response.text == "challenge-value"


def test_facebook_webhook_rejects_invalid_signature(monkeypatch):
    monkeypatch.setattr(settings, "facebook_app_secret", "secret")

    response = TestClient(app).post(
        "/facebook/webhook",
        content=b'{"object":"page","entry":[]}',
        headers={"X-Hub-Signature-256": "sha256=invalid"},
    )

    assert response.status_code == 403


def test_facebook_webhook_ignores_echo_message(monkeypatch):
    monkeypatch.setattr(settings, "facebook_app_secret", "secret")
    body = {
        "object": "page",
        "entry": [
            {
                "id": "page_1",
                "messaging": [
                    {
                        "sender": {"id": "psid_1"},
                        "recipient": {"id": "page_1"},
                        "timestamp": 1,
                        "message": {
                            "mid": "mid_1",
                            "text": "hello",
                            "is_echo": True,
                        },
                    }
                ],
            }
        ],
    }
    raw_body = json.dumps(body).encode("utf-8")
    signature = hmac.new(b"secret", raw_body, hashlib.sha256).hexdigest()

    response = TestClient(app).post(
        "/facebook/webhook",
        content=raw_body,
        headers={
            "Content-Type": "application/json",
            "X-Hub-Signature-256": f"sha256={signature}",
        },
    )

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@dataclass
class FakeStateStore:
    duplicates: set[str] = field(default_factory=set)
    human_mode: set[str] = field(default_factory=set)
    expired: set[str] = field(default_factory=set)
    disabled: list[str] = field(default_factory=list)
    enabled: list[str] = field(default_factory=list)
    processed: list[str] = field(default_factory=list)

    async def is_duplicate(self, message_id):
        return message_id in self.duplicates

    async def mark_processed(self, message_id):
        self.processed.append(message_id)
        self.duplicates.add(message_id)

    async def is_human_mode(self, psid):
        return psid in self.human_mode

    async def enable_human_mode(self, psid):
        self.human_mode.add(psid)
        self.enabled.append(psid)

    async def disable_human_mode(self, psid):
        self.human_mode.discard(psid)
        self.disabled.append(psid)

    async def consume_expired_handover(self, psid):
        if psid in self.expired:
            self.expired.remove(psid)
            return True
        return False


class FakeTransaction:
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False


class FakeConn:
    def transaction(self):
        return FakeTransaction()


class FakeAcquire:
    async def __aenter__(self):
        return FakeConn()

    async def __aexit__(self, exc_type, exc, tb):
        return False


class FakePool:
    def acquire(self):
        return FakeAcquire()


class FakeRepo:
    def __init__(self):
        self.conversations = {}
        self.messages = []
        self.events = []
        self.assignments = []

    async def find_conversation(self, channel, channel_account_id, external_user_id):
        return next(
            (
                item
                for item in self.conversations.values()
                if item.channel == channel
                and item.channel_account_id == channel_account_id
                and item.external_user_id == external_user_id
            ),
            None,
        )

    async def get_conversation(self, conversation_id):
        return self.conversations.get(conversation_id)

    async def list_conversations(self, **kwargs):
        return list(self.conversations.values())

    async def create_conversation(self, **fields):
        existing = await self.find_conversation(
            fields["channel"], fields["channel_account_id"], fields["external_user_id"]
        )
        if existing:
            return existing
        conversation = Conversation(
            id=f"conv_{len(self.conversations) + 1}",
            channel=fields["channel"],
            channel_account_id=fields["channel_account_id"],
            external_user_id=fields["external_user_id"],
            external_conversation_id=fields.get("external_conversation_id"),
            status=ConversationStatus.BOT_ACTIVE,
            current_owner=ConversationOwner.BOT,
            metadata=fields.get("metadata"),
            created_at=now(),
            updated_at=now(),
        )
        self.conversations[conversation.id] = conversation
        return conversation

    async def update_conversation(self, conversation_id, **fields):
        conversation = self.conversations[conversation_id]
        converted = normalize_conversation_fields(fields)
        updated = Conversation.model_validate({**conversation.model_dump(), **converted, "updated_at": now()})
        self.conversations[conversation_id] = updated
        return updated

    async def find_message_by_external_id(self, channel, external_message_id):
        return next(
            (
                item
                for item in self.messages
                if item.channel == channel and item.external_message_id == external_message_id
            ),
            None,
        )

    async def create_message(self, **fields):
        if fields.get("external_message_id"):
            existing = await self.find_message_by_external_id(fields["channel"], fields["external_message_id"])
            if existing:
                return existing
        message = Message(
            id=f"msg_{len(self.messages) + 1}",
            conversation_id=fields["conversation_id"],
            channel=fields["channel"],
            external_message_id=fields.get("external_message_id"),
            direction=MessageDirection(fields["direction"]),
            sender_type=SenderType(fields["sender_type"]),
            sender_id=fields.get("sender_id"),
            content_type=fields.get("content_type") or "text",
            content=fields.get("content"),
            payload=fields.get("payload"),
            intent=fields.get("intent"),
            confidence=fields.get("confidence"),
            status=MessageStatus(fields["status"]),
            error_message=fields.get("error_message"),
            correlation_id=fields.get("correlation_id"),
            created_at=now(),
            metadata=fields.get("metadata"),
        )
        self.messages.append(message)
        return message

    async def update_message(self, message_id, **fields):
        for idx, message in enumerate(self.messages):
            if message.id == message_id:
                updated = Message.model_validate({**message.model_dump(), **normalize_message_fields(fields)})
                self.messages[idx] = updated
                return updated
        raise KeyError(message_id)

    async def list_messages(self, conversation_id, **kwargs):
        return [item for item in self.messages if item.conversation_id == conversation_id]

    async def create_event(self, **fields):
        event = ConversationEvent(
            id=f"evt_{len(self.events) + 1}",
            conversation_id=fields["conversation_id"],
            event_type=fields["event_type"],
            actor_type=SenderType(normalize_value(fields["actor_type"])),
            actor_id=fields.get("actor_id"),
            from_status=ConversationStatus(normalize_value(fields["from_status"])) if fields.get("from_status") else None,
            to_status=ConversationStatus(normalize_value(fields["to_status"])) if fields.get("to_status") else None,
            reason=fields.get("reason"),
            payload=fields.get("payload"),
            created_at=now(),
        )
        self.events.append(event)
        return event

    async def list_events(self, conversation_id, **kwargs):
        return [item for item in self.events if item.conversation_id == conversation_id]

    async def get_active_assignment(self, conversation_id):
        return next(
            (
                item
                for item in self.assignments
                if item.conversation_id == conversation_id and item.status == AssignmentStatus.ACTIVE
            ),
            None,
        )

    async def create_assignment(self, **fields):
        assignment = ConversationAssignment(
            id=f"asgn_{len(self.assignments) + 1}",
            conversation_id=fields["conversation_id"],
            agent_id=fields["agent_id"],
            assigned_by=fields.get("assigned_by"),
            status=AssignmentStatus(fields.get("status") or "ACTIVE"),
            assigned_at=now(),
            metadata=fields.get("metadata"),
        )
        self.assignments.append(assignment)
        return assignment

    async def release_active_assignments(self, conversation_id):
        self.assignments = [
            item.model_copy(update={"status": AssignmentStatus.RELEASED, "released_at": now()})
            if item.conversation_id == conversation_id and item.status == AssignmentStatus.ACTIVE
            else item
            for item in self.assignments
        ]

    async def lock_conversation(self, conversation_id):
        return None


def now():
    return datetime.now(timezone.utc).isoformat()


def normalize_value(value):
    if isinstance(value, datetime):
        return value.isoformat()
    if hasattr(value, "value"):
        return value.value
    return value


def normalize_conversation_fields(fields):
    converted = {key: normalize_value(value) for key, value in fields.items()}
    if "status" in converted:
        converted["status"] = ConversationStatus(converted["status"])
    if "current_owner" in converted:
        converted["current_owner"] = ConversationOwner(converted["current_owner"])
    return converted


def normalize_message_fields(fields):
    converted = {key: normalize_value(value) for key, value in fields.items()}
    if "direction" in converted:
        converted["direction"] = MessageDirection(converted["direction"])
    if "sender_type" in converted:
        converted["sender_type"] = SenderType(converted["sender_type"])
    if "status" in converted:
        converted["status"] = MessageStatus(converted["status"])
    return converted


def signed_headers(body: dict, secret: str = "secret") -> tuple[bytes, dict[str, str]]:
    raw_body = json.dumps(body).encode("utf-8")
    signature = hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
    return raw_body, {
        "Content-Type": "application/json",
        "X-Hub-Signature-256": f"sha256={signature}",
    }


def messenger_body(*events: dict) -> dict:
    return {
        "object": "page",
        "entry": [
            {
                "id": "page_1",
                "messaging": list(events),
            }
        ],
    }


def customer_message(mid="mid_customer", text="hello", psid="psid_1") -> dict:
    return {
        "sender": {"id": psid},
        "recipient": {"id": "page_1"},
        "timestamp": 1,
        "message": {"mid": mid, "text": text},
    }


def admin_echo(mid="mid_admin", text="#bot", psid="psid_1") -> dict:
    return {
        "sender": {"id": "page_1"},
        "recipient": {"id": psid},
        "timestamp": 1,
        "message": {"mid": mid, "text": text, "is_echo": True},
    }


def install_fakes(monkeypatch, state: FakeStateStore, bot_result: dict | None = None, repo: FakeRepo | None = None):
    calls = {"bot": [], "send": [], "logs": []}
    fake_repo = repo or FakeRepo()

    class FakeBotOrchestrator:
        async def process_customer_message(self, **kwargs):
            calls["bot"].append(kwargs)
            result = bot_result or {"reply": "bot reply", "intent": "product_price", "confidence": 1.0}
            handover = "fallback" in str(result.get("intent", "")).lower() or (result.get("escalation") or {}).get("escalate")
            handover = bool(handover)
            return BotReplyResult(
                reply=result.get("reply"),
                messages=result.get("messages") or [],
                intent=result.get("intent"),
                confidence=result.get("confidence"),
                handover=handover,
                fallback=handover,
                escalation=result.get("escalation"),
            )

    async def fake_send_message(psid, text):
        calls["send"].append({"psid": psid, "text": text})
        return {"recipient_id": psid, "message_id": "out_mid"}

    async def fake_send_bot_messages(psid, text, messages=None):
        calls["send"].append({"psid": psid, "text": text, "messages": messages or []})
        return [{"recipient_id": psid, "message_id": "out_mid"}]

    def fake_log(**kwargs):
        calls["logs"].append(kwargs)

    monkeypatch.setattr(settings, "facebook_app_secret", "secret")
    monkeypatch.setattr(facebook_api, "state_store", state)
    monkeypatch.setattr(facebook_api, "BotOrchestrator", FakeBotOrchestrator)
    monkeypatch.setattr(facebook_api.facebook_adapter, "send_message", fake_send_message)
    monkeypatch.setattr(facebook_api.facebook_adapter, "send_bot_messages", fake_send_bot_messages)
    monkeypatch.setattr(facebook_api, "log_facebook_event", fake_log)
    monkeypatch.setattr(facebook_api, "PostgresConversationRepository", lambda _db: fake_repo)
    monkeypatch.setattr(facebook_api, "get_pool", lambda: fake_pool())
    calls["repo"] = fake_repo
    return calls


async def fake_pool():
    return FakePool()


def test_handover_trigger_sets_human_mode_and_does_not_send_bot_reply(monkeypatch):
    state = FakeStateStore()
    calls = install_fakes(
        monkeypatch,
        state,
        {
            "reply": "fallback",
            "intent": "FallbackIntent",
            "confidence": 0.2,
            "escalation": {"escalate": True},
        },
    )
    raw_body, headers = signed_headers(messenger_body(customer_message(text="không hiểu")))

    response = TestClient(app).post("/facebook/webhook", content=raw_body, headers=headers)

    assert response.status_code == 200
    assert calls["bot"]
    assert calls["send"][0]["text"] == facebook_api.HANDOVER_MESSAGE
    assert calls["logs"][-1]["event"] == "handover_start"
    conversation = next(iter(calls["repo"].conversations.values()))
    assert conversation.status == ConversationStatus.WAITING_AGENT
    assert conversation.current_owner == ConversationOwner.AGENT
    assert any(event.event_type == "HANDOVER_STARTED" for event in calls["repo"].events)


def test_admin_hash_bot_resumes_without_calling_lex(monkeypatch):
    state = FakeStateStore(human_mode={"psid_1"})
    calls = install_fakes(monkeypatch, state)
    raw_body, headers = signed_headers(messenger_body(admin_echo(text="#bot")))

    response = TestClient(app).post("/facebook/webhook", content=raw_body, headers=headers)

    assert response.status_code == 200
    assert state.disabled == ["psid_1"]
    assert calls["bot"] == []
    assert calls["send"] == [{"psid": "psid_1", "text": facebook_api.RESUME_BOT_MESSAGE}]
    assert calls["logs"][-1]["event"] == "resume_bot_admin"
    conversation = next(iter(calls["repo"].conversations.values()))
    assert conversation.status == ConversationStatus.BOT_ACTIVE


def test_admin_slash_bot_resumes_without_calling_lex(monkeypatch):
    state = FakeStateStore(human_mode={"psid_1"})
    calls = install_fakes(monkeypatch, state)
    raw_body, headers = signed_headers(messenger_body(admin_echo(text="/bot")))

    response = TestClient(app).post("/facebook/webhook", content=raw_body, headers=headers)

    assert response.status_code == 200
    assert state.disabled == ["psid_1"]
    assert calls["bot"] == []
    assert calls["send"] == [{"psid": "psid_1", "text": facebook_api.RESUME_BOT_MESSAGE}]
    assert calls["logs"][-1]["event"] == "resume_bot_admin"


def test_customer_resume_when_enabled(monkeypatch):
    monkeypatch.setattr(settings, "enable_customer_resume_bot", True)
    state = FakeStateStore(human_mode={"psid_1"})
    calls = install_fakes(monkeypatch, state)
    raw_body, headers = signed_headers(messenger_body(customer_message(text="#bot")))

    response = TestClient(app).post("/facebook/webhook", content=raw_body, headers=headers)

    assert response.status_code == 200
    assert state.disabled == ["psid_1"]
    assert calls["bot"] == []
    assert calls["send"] == [{"psid": "psid_1", "text": facebook_api.RESUME_BOT_MESSAGE}]
    assert calls["logs"][-1]["event"] == "resume_bot_customer"
    conversation = next(iter(calls["repo"].conversations.values()))
    assert conversation.status == ConversationStatus.BOT_ACTIVE
    assert any(event.event_type == "RESUME_BOT_CUSTOMER_NOTICE_SENT" for event in calls["repo"].events)


def test_customer_resume_existing_waiting_conversation(monkeypatch):
    monkeypatch.setattr(settings, "enable_customer_resume_bot", True)
    repo = FakeRepo()
    asyncio.run(seed_waiting_conversation(repo))
    state = FakeStateStore()
    calls = install_fakes(monkeypatch, state, repo=repo)
    raw_body, headers = signed_headers(messenger_body(customer_message(text="bot ơi")))

    response = TestClient(app).post("/facebook/webhook", content=raw_body, headers=headers)

    assert response.status_code == 200
    assert calls["bot"] == []
    assert calls["send"] == [{"psid": "psid_1", "text": facebook_api.RESUME_BOT_MESSAGE}]
    conversation = next(iter(calls["repo"].conversations.values()))
    assert conversation.status == ConversationStatus.BOT_ACTIVE
    event_types = [event.event_type for event in calls["repo"].events]
    assert "RETURNED_TO_BOT" in event_types
    assert "RESUME_BOT_CUSTOMER_NOTICE_SENT" in event_types


def test_customer_resume_command_does_not_go_to_lex_when_bot_active(monkeypatch):
    monkeypatch.setattr(settings, "enable_customer_resume_bot", True)
    state = FakeStateStore()
    calls = install_fakes(monkeypatch, state)
    raw_body, headers = signed_headers(messenger_body(customer_message(text="#bot")))

    response = TestClient(app).post("/facebook/webhook", content=raw_body, headers=headers)

    assert response.status_code == 200
    assert calls["bot"] == []
    assert calls["send"] == [{"psid": "psid_1", "text": facebook_api.RESUME_BOT_MESSAGE}]
    conversation = next(iter(calls["repo"].conversations.values()))
    assert conversation.status == ConversationStatus.BOT_ACTIVE
    assert not any(event.event_type == "HANDOVER_STARTED" for event in calls["repo"].events)


async def seed_waiting_conversation(repo: FakeRepo):
    conversation = await repo.create_conversation(
        channel="MESSENGER",
        channel_account_id="page_1",
        external_user_id="psid_1",
    )
    await ConversationService(repo).mark_waiting_agent(conversation, reason="fallback")


def test_ttl_expiry_allows_bot_and_logs(monkeypatch):
    state = FakeStateStore(expired={"psid_1"})
    calls = install_fakes(monkeypatch, state)
    raw_body, headers = signed_headers(messenger_body(customer_message(text="iPhone giá sao")))

    response = TestClient(app).post("/facebook/webhook", content=raw_body, headers=headers)

    assert response.status_code == 200
    assert calls["bot"]
    assert any(log["event"] == "handover_expired" for log in calls["logs"])
    assert calls["logs"][-1]["event"] == "bot_replied"
