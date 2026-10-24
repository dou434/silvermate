"""紧急求助事件服务的分支测试：冷却去重、active 过滤、撤销补发、无绑定。"""

from __future__ import annotations

import pytest
import pytest_asyncio
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from yuxi.services import emergency_service, family_service
from yuxi.storage.postgres.models_business import Base, User
from yuxi.storage.postgres.models_family import EmergencyEvent, FamilyMessage

pytestmark = [pytest.mark.asyncio, pytest.mark.unit]


@pytest_asyncio.fixture()
async def ctx():
    """一位老人、两位子女（child_1 最终 active、child_2 不会 active）、一位无绑定老人。"""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as db:
        users = {
            "elder_1": User(uid="elder_1", username="张阿姨", password_hash="$argon2id$placeholder", role="user"),
            "child_1": User(uid="child_1", username="小李", password_hash="$argon2id$placeholder", role="user"),
            "child_2": User(uid="child_2", username="小王", password_hash="$argon2id$placeholder", role="user"),
            "stranger_1": User(uid="stranger_1", username="路人", password_hash="$argon2id$placeholder", role="user"),
        }
        db.add_all(users.values())
        await db.commit()
        yield db, users
    await engine.dispose()


async def _messages_to(db, uid: str) -> list[FamilyMessage]:
    result = await db.execute(select(FamilyMessage).where(FamilyMessage.to_uid == uid))
    return list(result.scalars().all())


async def _bind(db, ctx, child_uid: str, relation: str = "子女") -> int:
    _, users = ctx
    link = await family_service.create_link(db, users[child_uid], elder_uid="elder_1", relation=relation)
    await family_service.approve_link(db, users["elder_1"], link["id"])
    return link["id"]


async def test_sos_notifies_active_children_only(ctx):
    db, users = ctx
    await _bind(db, ctx, "child_1")
    # child_2：pending 申请不通知
    pending_link = await family_service.create_link(db, users["child_2"], elder_uid="elder_1", relation="侄子")
    # 再绑一个后解除：revoked 不通知
    revoked_link = await family_service.create_link(db, users["stranger_1"], elder_uid="elder_1", relation="邻居")
    await family_service.approve_link(db, users["elder_1"], revoked_link["id"])
    await family_service.revoke_link(db, users["elder_1"], revoked_link["id"])

    result = await emergency_service.report_emergency(db, users["elder_1"], source="sos")

    assert result["deduped"] is False
    assert result["notified"] == ["child_1"]
    messages = await _messages_to(db, "child_1")
    assert len(messages) == 1
    assert messages[0].content.startswith("【紧急求助】")
    assert messages[0].content.count("SOS") == 1
    assert messages[0].from_uid == "elder_1"
    # pending / revoked 绑定的一方收不到
    assert await _messages_to(db, "child_2") == []
    assert await _messages_to(db, "stranger_1") == []
    assert pending_link["status"] == "pending"  # 前置条件自证


async def test_repeat_report_within_cooldown_dedupes(ctx):
    db, users = ctx
    await _bind(db, ctx, "child_1")

    first = await emergency_service.report_emergency(db, users["elder_1"], source="sos")
    second = await emergency_service.report_emergency(db, users["elder_1"], source="sos")

    assert second["event_id"] == first["event_id"]
    assert second["deduped"] is True
    assert second["notified"] == []
    # 去重不重发留言
    assert len(await _messages_to(db, "child_1")) == 1
    result = await db.execute(select(EmergencyEvent))
    assert len(list(result.scalars().all())) == 1


async def test_event_recorded_without_family(ctx):
    db, users = ctx

    result = await emergency_service.report_emergency(db, users["stranger_1"], source="sos")

    assert result["deduped"] is False
    assert result["notified"] == []
    assert result["event"]["status"] == "open"


async def test_keyword_event_carries_category_and_detail(ctx):
    db, users = ctx
    await _bind(db, ctx, "child_1")

    result = await emergency_service.report_emergency(
        db, users["elder_1"], source="keyword", category="cardiac", detail="我胸口疼得厉害"
    )

    assert result["event"]["category"] == "cardiac"
    message = (await _messages_to(db, "child_1"))[0]
    assert "心血管急症" in message.content
    assert "我胸口疼得厉害" in message.content


async def test_resolve_sends_comfort_and_is_idempotent(ctx):
    db, users = ctx
    await _bind(db, ctx, "child_1")

    reported = await emergency_service.report_emergency(db, users["elder_1"], source="sos")
    resolved = await emergency_service.resolve_emergency(db, users["elder_1"], reported["event_id"])

    assert resolved["event"]["status"] == "resolved"
    assert resolved["notified"] == ["child_1"]
    messages = await _messages_to(db, "child_1")
    assert len(messages) == 2
    assert "我没事了" in messages[-1].content

    # 重复撤销幂等成功，不再补发
    again = await emergency_service.resolve_emergency(db, users["elder_1"], reported["event_id"])
    assert again["event"]["status"] == "resolved"
    assert again["notified"] == []
    assert len(await _messages_to(db, "child_1")) == 2


async def test_only_elder_can_resolve(ctx):
    db, users = ctx
    await _bind(db, ctx, "child_1")

    reported = await emergency_service.report_emergency(db, users["elder_1"], source="sos")

    for outsider in ("child_1", "stranger_1"):
        with pytest.raises(HTTPException) as exc_info:
            await emergency_service.resolve_emergency(db, users[outsider], reported["event_id"])
        assert exc_info.value.status_code == 403

    with pytest.raises(HTTPException) as exc_info:
        await emergency_service.resolve_emergency(db, users["elder_1"], 99999)
    assert exc_info.value.status_code == 404


async def test_invalid_source_is_rejected(ctx):
    db, users = ctx
    with pytest.raises(HTTPException) as exc_info:
        await emergency_service.report_emergency(db, users["elder_1"], source="sms")
    assert exc_info.value.status_code == 400


def test_message_time_is_shanghai_not_utc():
    """DB 存 naive UTC，留言时间要转成上海时间，否则会整体偏移 8 小时。"""
    import datetime as dt

    event = EmergencyEvent(
        elder_uid="elder_1", source="sos", status="open", created_at=dt.datetime(2026, 10, 24, 8, 0)
    )
    assert "时间：10月24日 16:00" in emergency_service._help_message(event)

    event.resolved_at = dt.datetime(2026, 10, 24, 8, 30)
    assert "时间：10月24日 16:30" in emergency_service._resolved_message(event)


async def test_child_sees_bound_elders_events_and_unread_badge(ctx):
    db, users = ctx
    await _bind(db, ctx, "child_1")
    await emergency_service.report_emergency(db, users["elder_1"], source="sos")
    # 其他老人的事件不在 child_1 的列表里
    await emergency_service.report_emergency(db, users["stranger_1"], source="keyword", category="fall")

    events = await emergency_service.list_events_of_bound_elders(db, users["child_1"])
    assert [event["elder_uid"] for event in events["events"]] == ["elder_1"]
    assert events["events"][0]["elder_name"] == "张阿姨"

    summary = await family_service.unread_summary(db, users["child_1"])
    assert summary["open_emergency_count"] == 1

    await emergency_service.resolve_emergency(db, users["elder_1"], events["events"][0]["id"])
    summary = await family_service.unread_summary(db, users["child_1"])
    assert summary["open_emergency_count"] == 0

    # 无绑定的老人/路人看到的紧急数为 0
    assert (await family_service.unread_summary(db, users["elder_1"]))["open_emergency_count"] == 0
    assert (await family_service.unread_summary(db, users["stranger_1"]))["open_emergency_count"] == 0
