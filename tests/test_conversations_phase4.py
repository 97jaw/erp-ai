from __future__ import annotations

import os

import pytest

requires_db = pytest.mark.skipif(
    not os.environ.get("OOA_DB_URL"),
    reason="OOA_DB_URL not set",
)


@pytest.mark.asyncio
@requires_db
async def test_conversation_persistence_and_isolation() -> None:
    from admin.db.connection import close_admin_db, init_admin_db
    from admin.db.repositories.conversations import ConversationRepository
    from admin.db.repositories.users import UserRepository
    from gateway.conversation_store import ConversationStore

    db = await init_admin_db()
    users = UserRepository(db)
    conv_repo = ConversationRepository(db)

    user_a = await users.provision_user(file_id="conv-test-a", name="Conv A", role_name="user")
    user_b = await users.provision_user(file_id="conv-test-b", name="Conv B", role_name="user")
    session_a = "session-key-a-001"
    session_b = "session-key-b-001"

    try:
        await ConversationStore.append(
            session_a, "user", "Hello from A", user_id=user_a
        )
        await ConversationStore.append(
            session_a, "assistant", "Reply to A", user_id=user_a, language="en"
        )
        await ConversationStore.append(
            session_b, "user", "Hello from B", user_id=user_b
        )

        conv_id_a = await conv_repo.get_or_create(user_a, session_a)
        conv_id_b = await conv_repo.get_or_create(user_b, session_b)
        assert conv_id_a != conv_id_b

        msgs_a = await conv_repo.get_agent_messages(conv_id_a)
        msgs_b = await conv_repo.get_agent_messages(conv_id_b)
        assert any("Hello from A" in m["content"] for m in msgs_a)
        assert any("Hello from B" in m["content"] for m in msgs_b)
        assert not any("Hello from B" in m["content"] for m in msgs_a)

        listed = await conv_repo.list_for_user(user_a, search="Hello")
        assert any(str(r["id"]) == str(conv_id_a) for r in listed)

        other_view = await conv_repo.get_conversation(user_b, conv_id_a)
        assert other_view is None
    finally:
        for uid, key in ((user_a, session_a), (user_b, session_b)):
            cid = await conv_repo.resolve_id(uid, key)
            if cid:
                await conv_repo.delete_conversation(uid, cid)
        await close_admin_db()


@pytest.mark.asyncio
@requires_db
async def test_agent_message_window() -> None:
    from admin.db.connection import close_admin_db, init_admin_db
    from admin.db.repositories.conversations import ConversationRepository
    from admin.db.repositories.users import UserRepository

    db = await init_admin_db()
    users = UserRepository(db)
    repo = ConversationRepository(db)
    uid = await users.provision_user(file_id="conv-window-test", name="Window", role_name="user")
    conv_id = await repo.get_or_create(uid, "window-session")

    try:
        for i in range(25):
            await repo.append_message(
                conv_id,
                user_id=uid,
                role="user" if i % 2 == 0 else "assistant",
                content=f"message-{i}",
            )
        agent_msgs = await repo.get_agent_messages(conv_id, limit=20)
        assert len(agent_msgs) == 20
        assert agent_msgs[0]["content"] == "message-5"
        assert agent_msgs[-1]["content"] == "message-24"
    finally:
        await repo.delete_conversation(uid, conv_id)
        await close_admin_db()
