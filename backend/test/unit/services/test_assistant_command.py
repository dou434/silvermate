"""问 AI 界面「自然语言控制」的解析与执行测试。

重点锁三件事：
1. 只有明确的指令才动手，提问和日常闲聊必须原样交还给智能体（绝不误写数据）；
2. 发留言的内容要切干净（"告诉小李我今天血压130"不能把名字吃掉一个字）；
3. 只有本人能标记自己的提醒，和 reminder_service 的口径保持一致。
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from yuxi.services import assistant_command_service, family_service, reminder_service
from yuxi.storage.postgres.models_business import Base, User
from yuxi.storage.postgres.models_family import FamilyLink
from yuxi.utils.datetime_utils import SHANGHAI_TZ

pytestmark = [pytest.mark.asyncio, pytest.mark.unit]

# 固定"当天上午 10 点"作为测试时钟，用例结果不再随实际运行时刻变化：
# 09:00 已到点，12:00 还没到点，两者恒在同一个上海自然日内。
_FROZEN_NOW = datetime(2025, 1, 15, 10, 0, tzinfo=SHANGHAI_TZ)
_DUE_AT = _FROZEN_NOW - timedelta(hours=1)
_LATER_TODAY_AT = _FROZEN_NOW + timedelta(hours=2)


def _freeze_clock(monkeypatch) -> None:
    """把 reminder_service 的时间源钉死在 _FROZEN_NOW。"""
    monkeypatch.setattr(reminder_service, "shanghai_now", lambda: _FROZEN_NOW)
    monkeypatch.setattr(
        reminder_service,
        "utc_now_naive",
        lambda: _FROZEN_NOW.astimezone(UTC).replace(tzinfo=None),
    )


@pytest_asyncio.fixture()
async def ctx(monkeypatch):
    """老人 + 已绑定子女 + 陌生人。"""
    _freeze_clock(monkeypatch)
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


async def _make_delivered_reminder(db, child, elder, title="吃降压药"):
    """建一条提醒并把执行记录推进到 delivered，模拟"已经到点了"。"""
    created = await reminder_service.create_reminder(
        db,
        child,
        target_uid="elder_1",
        title=title,
        content="饭后一片",
        category="用药",
        remind_at=_DUE_AT,
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
        remind_at=_LATER_TODAY_AT,
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


# ==================== 提醒管理（建/改/停） ====================

@pytest.fixture()
def frozen(monkeypatch):
    """只冻结时钟、不建库，供 parse_when 纯函数用例复用。"""
    _freeze_clock(monkeypatch)
    return monkeypatch


def _local(year, month, day, hour, minute):
    return datetime(year, month, day, hour, minute, tzinfo=SHANGHAI_TZ)


@pytest.mark.parametrize(
    "text, expected, expected_rule",
    [
        # 日期 × 时段 × 整点/半点/X:Y/中文数字
        ("今天凌晨两点", _local(2025, 1, 15, 2, 0), {"type": "none"}),
        ("今天早上八点", _local(2025, 1, 15, 8, 0), {"type": "none"}),
        ("今天上午10点", _local(2025, 1, 15, 10, 0), {"type": "none"}),
        ("今天中午十二点", _local(2025, 1, 15, 12, 0), {"type": "none"}),
        ("今天中午一点", _local(2025, 1, 15, 13, 0), {"type": "none"}),
        ("今天下午三点", _local(2025, 1, 15, 15, 0), {"type": "none"}),
        ("今天下午三点半", _local(2025, 1, 15, 15, 30), {"type": "none"}),
        ("今天傍晚六点", _local(2025, 1, 15, 18, 0), {"type": "none"}),
        ("今天晚上九点", _local(2025, 1, 15, 21, 0), {"type": "none"}),
        ("今晚八点", _local(2025, 1, 15, 20, 0), {"type": "none"}),
        ("下午3:30", _local(2025, 1, 15, 15, 30), {"type": "none"}),
        ("14点", _local(2025, 1, 15, 14, 0), {"type": "none"}),
        ("十四点", _local(2025, 1, 15, 14, 0), {"type": "none"}),
        ("明天早上八点", _local(2025, 1, 16, 8, 0), {"type": "none"}),
        ("明早7点", _local(2025, 1, 16, 7, 0), {"type": "none"}),
        ("明晚十一点", _local(2025, 1, 16, 23, 0), {"type": "none"}),
        ("明天下午三点二十分", _local(2025, 1, 16, 15, 20), {"type": "none"}),
        ("后天上午十点", _local(2025, 1, 17, 10, 0), {"type": "none"}),
        ("后天晚上8点", _local(2025, 1, 17, 20, 0), {"type": "none"}),
        # 晚上十二点是午夜零点，落在下一天
        ("晚上十二点", _local(2025, 1, 16, 0, 0), {"type": "none"}),
        # 重复规则
        ("每天晚上九点", _local(2025, 1, 15, 21, 0), {"type": "daily"}),
        ("每天早上7点半", _local(2025, 1, 15, 7, 30), {"type": "daily"}),
        ("每周一早上八点", _local(2025, 1, 15, 8, 0), {"type": "weekly", "weekdays": [1]}),
        ("每星期三下午四点", _local(2025, 1, 15, 16, 0), {"type": "weekly", "weekdays": [3]}),
        ("每周日晚上九点", _local(2025, 1, 15, 21, 0), {"type": "weekly", "weekdays": [7]}),
    ],
)
async def test_parse_when_combinations(frozen, text, expected, expected_rule):
    """表驱动锁死时间解析：重点是 ±12 小时补正、半点、明早等边界。"""
    parsed = assistant_command_service.parse_when(text)
    assert parsed is not None, text
    when, rule = parsed
    assert when == expected
    assert rule == expected_rule


@pytest.mark.parametrize(
    "text",
    [
        "大后天早上八点",  # 不支持的日期词，硬套会错成"后天"
        "下周一早上八点",
        "周一早上八点",  # 裸周几没说"每"，不能当成今天
        "每月十五号早上八点",
        "工作日早上八点",
        "每隔三天早上八点",
        "三点二十",  # 中文分钟没带"分"，不能当整点猜
        "三点一刻",
        "25点",
        "8点75分",
        "晚上",  # 没有时刻
        "吃药",
        "",
    ],
)
async def test_parse_when_unsupported_returns_none(frozen, text):
    """解析不出确定时间必须返回 None，宁可漏不可错。"""
    assert assistant_command_service.parse_when(text) is None


async def test_create_reminder_for_self(ctx):
    db, elder, _, _ = ctx

    result = await assistant_command_service.handle(db, elder, "提醒我明天早上八点吃药")

    assert result["handled"] is True
    assert result["intent"] == "reminder_create"
    assert "吃药" in result["reply"]
    assert any(a["type"] == "refresh" and a["target"] == "reminders" for a in result["actions"])

    reminders = await reminder_service.list_reminders(db, elder)
    item = next(r for r in reminders["reminders"] if r["title"] == "吃药")
    assert item["is_mine"] is True
    assert item["target_uid"] == "elder_1"
    assert item["category"] == "other"
    assert item["repeat_rule"] == {"type": "none"}
    # 上海 2025-01-16 08:00 = UTC 00:00
    assert item["remind_at"] == "2025-01-16T00:00:00Z"


async def test_create_daily_reminder(ctx):
    db, elder, _, _ = ctx

    result = await assistant_command_service.handle(db, elder, "每天晚上九点提醒我量血压")

    assert result["intent"] == "reminder_create"
    reminders = await reminder_service.list_reminders(db, elder)
    item = next(r for r in reminders["reminders"] if r["title"] == "量血压")
    assert item["repeat_rule"] == {"type": "daily"}
    # 上海 2025-01-15 21:00 = UTC 13:00
    assert item["remind_at"] == "2025-01-15T13:00:00Z"


async def test_create_weekly_reminder(ctx):
    db, elder, _, _ = ctx

    result = await assistant_command_service.handle(db, elder, "每周一早上八点提醒我吃降压药")

    assert result["intent"] == "reminder_create"
    reminders = await reminder_service.list_reminders(db, elder)
    item = next(r for r in reminders["reminders"] if r["title"] == "吃降压药")
    assert item["repeat_rule"] == {"type": "weekly", "weekdays": [1]}


async def test_create_without_time_asks_instead_of_guessing(ctx):
    db, elder, _, _ = ctx

    result = await assistant_command_service.handle(db, elder, "提醒我吃药")

    assert result["handled"] is True
    assert result["needs_input"] is True
    assert "几点" in result["reply"]
    assert await reminder_service.list_reminders(db, elder) == {"reminders": [], "total": 0}


async def test_create_without_matter_asks_instead_of_guessing(ctx):
    db, elder, _, _ = ctx

    result = await assistant_command_service.handle(db, elder, "提醒我明天八点")

    assert result["handled"] is True
    assert result["needs_input"] is True
    assert "做什么" in result["reply"]


async def test_create_past_time_reports_error(ctx):
    """"今天凌晨两点"早就过了：如实告知，不能悄悄改天也不能建出去。"""
    db, elder, _, _ = ctx

    result = await assistant_command_service.handle(db, elder, "提醒我今天凌晨两点吃药")

    assert result["handled"] is True
    assert "已过" in result["reply"]
    assert await reminder_service.list_reminders(db, elder) == {"reminders": [], "total": 0}


async def test_change_own_reminder_time(ctx):
    db, elder, _, _ = ctx
    await reminder_service.create_reminder(
        db,
        elder,
        target_uid="elder_1",
        title="吃药",
        content=None,
        category="other",
        remind_at=_FROZEN_NOW + timedelta(hours=11),  # 今晚 21:00
    )

    result = await assistant_command_service.handle(db, elder, "把吃药提醒改到下午三点")

    assert result["handled"] is True
    assert result["intent"] == "reminder_change"
    assert "吃药" in result["reply"]
    assert any(a["type"] == "refresh" and a["target"] == "reminders" for a in result["actions"])

    reminders = await reminder_service.list_reminders(db, elder)
    item = next(r for r in reminders["reminders"] if r["title"] == "吃药")
    # 上海 2025-01-15 15:00 = UTC 07:00
    assert item["remind_at"] == "2025-01-15T07:00:00Z"


async def test_change_child_owned_reminder_transfers_instead(ctx):
    """子女建的提醒老人改不了：数据不动，留言转达给设置人，并告知老人已转达。"""
    db, elder, child, _ = ctx
    created, _ = await _make_delivered_reminder(db, child, elder)  # 小李建的「吃降压药」

    result = await assistant_command_service.handle(db, elder, "把吃降压药提醒改到下午三点")

    assert result["handled"] is True
    assert result["intent"] == "reminder_change"
    assert "小李" in result["reply"]
    assert "留言" in result["reply"]

    # 不改数据
    reminders = await reminder_service.list_reminders(db, elder)
    item = next(r for r in reminders["reminders"] if r["id"] == created["id"])
    assert item["remind_at"] == created["remind_at"]
    assert item["enabled"] is True

    # 转达留言到子女端，带原话便于一次性处理
    inbox = await family_service.list_messages(db, child, with_uid="elder_1")
    last = inbox["messages"][-1]["content"]
    assert "调整" in last
    assert "吃降压药" in last
    assert "把吃降压药提醒改到下午三点" in last


async def test_change_ambiguous_asks_which_one(ctx):
    db, elder, _, _ = ctx
    for title, hours in (("早上吃药", 2), ("晚上吃药", 11)):
        await reminder_service.create_reminder(
            db,
            elder,
            target_uid="elder_1",
            title=title,
            content=None,
            category="other",
            remind_at=_FROZEN_NOW + timedelta(hours=hours),
        )

    result = await assistant_command_service.handle(db, elder, "把吃药提醒改到下午三点")

    assert result["handled"] is True
    assert result["needs_input"] is True
    assert "哪一条" in result["reply"]
    # 追问时不能顺手改掉任何一条
    reminders = await reminder_service.list_reminders(db, elder)
    assert all(r["remind_at"] != "2025-01-15T07:00:00Z" for r in reminders["reminders"])


async def test_change_unknown_reminder_replies_not_found(ctx):
    db, elder, _, _ = ctx
    await reminder_service.create_reminder(
        db,
        elder,
        target_uid="elder_1",
        title="吃药",
        content=None,
        category="other",
        remind_at=_FROZEN_NOW + timedelta(hours=11),
    )

    result = await assistant_command_service.handle(db, elder, "把跳舞提醒改到下午三点")

    assert result["handled"] is True
    assert "没有找到" in result["reply"]


async def test_stop_own_reminder_disables_it(ctx):
    db, elder, _, _ = ctx
    await reminder_service.create_reminder(
        db,
        elder,
        target_uid="elder_1",
        title="吃药",
        content=None,
        category="other",
        remind_at=_FROZEN_NOW + timedelta(hours=11),
    )

    result = await assistant_command_service.handle(db, elder, "吃药提醒不要了")

    assert result["handled"] is True
    assert result["intent"] == "reminder_stop"
    reminders = await reminder_service.list_reminders(db, elder)
    item = next(r for r in reminders["reminders"] if r["title"] == "吃药")
    assert item["enabled"] is False


async def test_stop_child_owned_reminder_transfers_instead(ctx):
    """否定优先 + 转达：「别再提醒我吃降压药」走停用转达，而不是建提醒。"""
    db, elder, child, _ = ctx
    created, _ = await _make_delivered_reminder(db, child, elder)

    result = await assistant_command_service.handle(db, elder, "别再提醒我吃降压药")

    assert result["handled"] is True
    assert result["intent"] == "reminder_stop"
    assert "小李" in result["reply"]

    reminders = await reminder_service.list_reminders(db, elder)
    item = next(r for r in reminders["reminders"] if r["id"] == created["id"])
    assert item["enabled"] is True

    inbox = await family_service.list_messages(db, child, with_uid="elder_1")
    last = inbox["messages"][-1]["content"]
    assert "停用" in last
    assert "吃降压药" in last


async def test_stop_twice_says_already_stopped(ctx):
    db, elder, _, _ = ctx
    await reminder_service.create_reminder(
        db,
        elder,
        target_uid="elder_1",
        title="吃药",
        content=None,
        category="other",
        remind_at=_FROZEN_NOW + timedelta(hours=11),
    )
    await assistant_command_service.handle(db, elder, "吃药提醒不要了")

    result = await assistant_command_service.handle(db, elder, "吃药提醒不要了")

    assert result["handled"] is True
    assert "已经停" in result["reply"]


@pytest.mark.parametrize(
    "text",
    [
        "医生提醒我要按时吃药",  # 第三方陈述
        "怎么设置提醒？",  # 问方法
        "提醒很重要",  # 闲聊
    ],
)
async def test_third_party_mentions_fall_through_to_agent(ctx, text):
    """不是给"我"建的指令必须放行给 AI，绝不能误建提醒。"""
    db, elder, child, _ = ctx
    created, _ = await _make_delivered_reminder(db, child, elder)

    result = await assistant_command_service.handle(db, elder, text)

    assert result["handled"] is False
    # 放行的同时一条数据都不能多
    reminders = await reminder_service.list_reminders(db, elder)
    assert [r["id"] for r in reminders["reminders"]] == [created["id"]]
