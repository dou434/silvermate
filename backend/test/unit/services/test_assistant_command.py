"""问 AI 界面「自然语言控制」的解析与执行测试。

重点锁三件事：
1. 只有明确的指令才动手，提问和日常闲聊必须原样交还给智能体（绝不误写数据）；
2. 发留言的内容要切干净（"告诉小李我今天血压130"不能把名字吃掉一个字）；
3. 只有本人能标记自己的提醒，和 reminder_service 的口径保持一致。
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from yuxi.services import assistant_command_service, family_service, reminder_service
from yuxi.storage.postgres.models_business import Base, User
from yuxi.storage.postgres.models_family import FamilyLink

pytestmark = [pytest.mark.asyncio, pytest.mark.unit]


@pytest_asyncio.fixture()
async def ctx():
    """老人 + 已绑定子女 + 陌生人。"""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as db:
        elder = User(uid="elder_1", username="张阿姨", password_hash="$placeholder", role="user")
        child = User(uid="child_1", username="小李", password_hash="$placeholder", role="user")
        stranger = User(uid="stranger_1", username="路人", password_hash="$placeholder", role="user")
        db.add_all([elder, child, stranger])
        await db.commit()
        db.add(
            FamilyLink(
                elder_uid="elder_1",
                child_uid="child_1",
                relation="子女",
                status="active",
                invited_by="child_1",
            )
        )
        await db.commit()
        yield db, elder, child, stranger
    await engine.dispose()


def _soon_today() -> datetime:
    """当天当前整点，落在宽限期内，不会因为跑在几点被当成过期提醒。"""
    from yuxi.utils.datetime_utils import shanghai_now

    return shanghai_now().replace(minute=0, second=0, microsecond=0)


async def _make_delivered_reminder(db, child, elder, title="吃降压药"):
    """建一条提醒并把执行记录推进到 delivered，模拟"已经到点了"。"""
    created = await reminder_service.create_reminder(
        db,
        child,
        target_uid="elder_1",
        title=title,
        content="饭后一片",
        category="用药",
        remind_at=_soon_today(),
    )
    today = await reminder_service.list_today(db, elder)
    occurrence_id = next(item["id"] for item in today["items"] if item["reminder_id"] == created["id"])

    occurrence = await reminder_service.repository.get_occurrence(db, occurrence_id)
    occurrence.status = "delivered"
    await db.flush()
    return created, occurrence_id


@pytest.mark.parametrize(
    "text",
    [
        "高血压吃什么好",
        "怎么给小李发消息",
        "小李给我发消息了吗？",
        "今天天气不错",
        "",
    ],
)
async def test_plain_text_falls_through_to_agent(ctx, text):
    """不是指令就必须放行，否则普通问答会被吞掉。"""
    db, elder, _, _ = ctx
    result = await assistant_command_service.handle(db, elder, text)
    assert result["handled"] is False


async def test_send_message_to_child(ctx):
    db, elder, child, _ = ctx

    result = await assistant_command_service.handle(db, elder, "给小李发一条消息：我下午去公园散步")

    assert result["handled"] is True
    assert result["intent"] == "family_message"
    assert "我下午去公园散步" in result["reply"]

    inbox = await family_service.list_messages(db, child, with_uid="elder_1")
    assert any("公园散步" in item["content"] for item in inbox["messages"])


async def test_tell_pattern_keeps_full_content(ctx):
    """'告诉小李我今天血压130' 的人名只能切一次，内容不能少字。"""
    db, elder, child, _ = ctx

    result = await assistant_command_service.handle(db, elder, "告诉小李我今天血压130")

    assert result["handled"] is True
    assert "我今天血压130" in result["reply"]

    inbox = await family_service.list_messages(db, child, with_uid="elder_1")
    assert inbox["messages"][-1]["content"] == "我今天血压130"


async def test_send_message_without_content_asks_instead_of_sending(ctx):
    db, elder, _, _ = ctx

    result = await assistant_command_service.handle(db, elder, "给小李发一条消息")

    assert result["handled"] is True
    assert result["needs_input"] is True
    assert "说什么" in result["reply"]


async def test_unknown_contact_lists_bound_family(ctx):
    db, elder, _, _ = ctx

    result = await assistant_command_service.handle(db, elder, "给老王发一条消息：你好")

    assert result["handled"] is True
    assert "没找到" in result["reply"]
    assert "小李" in result["reply"]


async def test_complete_reminder_by_keyword(ctx):
    db, elder, child, _ = ctx
    _, occurrence_id = await _make_delivered_reminder(db, child, elder)

    result = await assistant_command_service.handle(db, elder, "把吃药的提醒标记为完成")

    assert result["handled"] is True
    assert result["intent"] == "reminder_done"
    assert "吃降压药" in result["reply"]

    today = await reminder_service.list_today(db, elder)
    status = next(item["status"] for item in today["items"] if item["id"] == occurrence_id)
    assert status == "done"


async def test_complete_all_settles_only_due_items(ctx):
    """'都做完了' 只处理已经到点的，没到时间的 pending 不能替老人记完成。"""
    db, elder, child, _ = ctx
    _, delivered_id = await _make_delivered_reminder(db, child, elder)
    later = await reminder_service.create_reminder(
        db,
        child,
        target_uid="elder_1",
        title="晚上泡脚",
        content=None,
        category="other",
        remind_at=_soon_today() + timedelta(hours=3),
    )

    result = await assistant_command_service.handle(db, elder, "提醒都做完了")
    assert result["handled"] is True

    today = await reminder_service.list_today(db, elder)
    by_occurrence = {item["id"]: item["status"] for item in today["items"]}
    assert by_occurrence[delivered_id] == "done"

    pending_occurrence = next(item for item in today["items"] if item["reminder_id"] == later["id"])
    assert pending_occurrence["status"] == "pending"


async def test_unmatched_daily_talk_is_not_treated_as_command(ctx):
    """'我把饭做完了' 里没有能对上提醒的关键词，应当交还给智能体，而不是猜一个来标记。"""
    db, elder, child, _ = ctx
    await _make_delivered_reminder(db, child, elder)

    result = await assistant_command_service.handle(db, elder, "我把饭做完了")

    assert result["handled"] is False


async def test_confirm_reminder(ctx):
    db, elder, child, _ = ctx
    _, occurrence_id = await _make_delivered_reminder(db, child, elder)

    result = await assistant_command_service.handle(db, elder, "确认一下吃药的提醒")

    assert result["intent"] == "reminder_confirmed"

    today = await reminder_service.list_today(db, elder)
    status = next(item["status"] for item in today["items"] if item["id"] == occurrence_id)
    assert status == "confirmed"


async def test_child_cannot_complete_elder_reminder(ctx):
    """子女替老人说话时只能被指路，不能动老人的记录。"""
    db, elder, child, _ = ctx
    _, occurrence_id = await _make_delivered_reminder(db, child, elder)

    result = await assistant_command_service.handle(db, child, "把吃药的提醒标记为完成")

    assert result["handled"] is True
    assert "老人本人确认" in result["reply"]
    assert result["actions"][0]["path"] == "/family"

    today = await reminder_service.list_today(db, elder)
    status = next(item["status"] for item in today["items"] if item["id"] == occurrence_id)
    assert status == "delivered"


async def test_navigate_to_reminders_and_family(ctx):
    db, elder, _, _ = ctx

    to_reminders = await assistant_command_service.handle(db, elder, "打开我的提醒")
    assert to_reminders["intent"] == "navigate"
    assert to_reminders["actions"][0]["path"] == "/elder"

    # 老人视角进「我的家人」，不是子女端的 /family
    to_family = await assistant_command_service.handle(db, elder, "看看家人")
    assert to_family["actions"][0]["path"] == "/elder/family"


async def test_navigate_when_already_on_page_refreshes_instead(ctx):
    """已经在提醒页还说"打开我的提醒"，不要原地跳转（会像没反应），改成刷新。"""
    db, elder, _, _ = ctx

    result = await assistant_command_service.handle(db, elder, "打开我的提醒", page="/elder")

    assert result["handled"] is True
    assert "已经在" in result["reply"] or "就在" in result["reply"]
    assert result["actions"][0]["type"] == "refresh"


async def test_bare_confirmation_confirms_due_reminders(ctx):
    """老人只说"我收到了"，按"确认所有已到点的提醒"处理。"""
    db, elder, child, _ = ctx
    _, occurrence_id = await _make_delivered_reminder(db, child, elder)

    result = await assistant_command_service.handle(db, elder, "我收到了")

    assert result["handled"] is True
    assert result["intent"] == "reminder_confirmed"

    today = await reminder_service.list_today(db, elder)
    status = next(item["status"] for item in today["items"] if item["id"] == occurrence_id)
    assert status == "confirmed"
