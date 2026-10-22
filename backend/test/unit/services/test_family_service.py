"""家庭绑定与留言服务的权限测试。"""

from __future__ import annotations

import pytest
import pytest_asyncio
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from yuxi.services import family_service
from yuxi.storage.postgres.models_business import Base, User

pytestmark = [pytest.mark.asyncio, pytest.mark.unit]


@pytest_asyncio.fixture()
async def ctx():
    """三个用户：老人、子女、陌生人，彼此尚未绑定。"""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as db:
        elder = User(uid="elder_1", username="张阿姨", password_hash="$argon2id$placeholder", role="user")
        child = User(uid="child_1", username="小李", password_hash="$argon2id$placeholder", role="user")
        stranger = User(uid="stranger_1", username="路人", password_hash="$argon2id$placeholder", role="user")
        db.add_all([elder, child, stranger])
        await db.commit()
        yield db, elder, child, stranger
    await engine.dispose()


async def test_cannot_bind_self(ctx):
    db, elder, _, _ = ctx

    with pytest.raises(HTTPException) as exc_info:
        await family_service.create_link(db, elder, elder_uid="elder_1", relation="子女")

    assert exc_info.value.status_code == 400


async def test_duplicate_pending_request_is_rejected(ctx):
    db, elder, child, _ = ctx

    await family_service.create_link(db, child, elder_uid="elder_1", relation="子女")

    with pytest.raises(HTTPException) as exc_info:
        await family_service.create_link(db, child, elder_uid="elder_1", relation="子女")

    assert exc_info.value.status_code == 409


async def test_only_elder_can_approve_link(ctx):
    db, elder, child, stranger = ctx

    link = await family_service.create_link(db, child, elder_uid="elder_1", relation="子女")

    # 子女自己不能替老人确认
    with pytest.raises(HTTPException) as exc_info:
        await family_service.approve_link(db, child, link["id"])
    assert exc_info.value.status_code == 403

    # 无关的第三人也不能确认
    with pytest.raises(HTTPException) as exc_info:
        await family_service.approve_link(db, stranger, link["id"])
    assert exc_info.value.status_code == 403

    approved = await family_service.approve_link(db, elder, link["id"])
    assert approved["status"] == "active"


async def test_revoked_link_can_be_requested_again(ctx):
    db, elder, child, _ = ctx

    link = await family_service.create_link(db, child, elder_uid="elder_1", relation="子女")
    await family_service.approve_link(db, elder, link["id"])
    await family_service.revoke_link(db, elder, link["id"])

    again = await family_service.create_link(db, child, elder_uid="elder_1", relation="子女")
    assert again["status"] == "pending"
    assert again["id"] == link["id"]


async def test_cannot_message_without_active_link(ctx):
    db, elder, child, _ = ctx

    with pytest.raises(HTTPException) as exc_info:
        await family_service.send_message(db, child, to_uid="elder_1", content="妈，记得吃药")
    assert exc_info.value.status_code == 403

    link = await family_service.create_link(db, child, elder_uid="elder_1", relation="子女")
    await family_service.approve_link(db, elder, link["id"])

    message = await family_service.send_message(db, child, to_uid="elder_1", content="妈，记得吃药")
    assert message["from_uid"] == "child_1"
    assert message["read_at"] is None


async def test_unread_count_and_mark_read(ctx):
    db, elder, child, _ = ctx

    link = await family_service.create_link(db, child, elder_uid="elder_1", relation="子女")
    await family_service.approve_link(db, elder, link["id"])
    await family_service.send_message(db, child, to_uid="elder_1", content="第一条")

    assert (await family_service.unread_summary(db, elder))["total"] == 1

    thread = await family_service.list_messages(db, elder, with_uid="child_1")
    assert thread["marked_read"] == 1
    assert (await family_service.unread_summary(db, elder))["total"] == 0


async def test_message_length_is_limited(ctx):
    db, elder, child, _ = ctx

    link = await family_service.create_link(db, child, elder_uid="elder_1", relation="子女")
    await family_service.approve_link(db, elder, link["id"])

    with pytest.raises(HTTPException) as exc_info:
        await family_service.send_message(db, child, to_uid="elder_1", content="x" * 501)

    assert exc_info.value.status_code == 400


async def test_links_carry_per_child_unread_count(ctx):
    """老人有多个家人时，要能看出未读来自谁，否则默认打开错的人等于收不到。"""
    db, elder, child, stranger = ctx

    for uid, relation in (("child_1", "子女"), ("stranger_1", "侄子")):
        link = await family_service.create_link(db, await family_service._load_user(db, uid), elder_uid="elder_1", relation=relation)
        await family_service.approve_link(db, elder, link["id"])

    await family_service.send_message(db, child, to_uid="elder_1", content="妈，我周末回来")
    await family_service.send_message(db, child, to_uid="elder_1", content="路上买点水果")

    links = await family_service.list_links(db, elder)
    unread = {item["child_uid"]: item["unread_count"] for item in links["as_elder"]}

    assert unread["child_1"] == 2
    assert unread["stranger_1"] == 0

    # 读掉其中一位的留言，只清这一位的计数
    await family_service.list_messages(db, elder, with_uid="child_1")
    links = await family_service.list_links(db, elder)
    unread = {item["child_uid"]: item["unread_count"] for item in links["as_elder"]}
    assert unread["child_1"] == 0
