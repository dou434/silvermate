"""家庭数据查询工具的单测。

锁住四件事：
1. 家人清单双向都对（老人看子女、子女看老人），且只算 active 绑定；
2. 名字对不上就报错并给出真实家人名字，不许模型猜；
3. "谁给谁设的提醒"按设置人、被提醒人任意一侧都能查到，今天的状态要翻成中文；
4. 查留言**不能**把对方的留言标成已读——标记已读是界面的活，工具不能替用户点掉红点。
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from yuxi.agents.toolkits.buildin import family_tools
from yuxi.services import reminder_service
from yuxi.storage.postgres.models_business import Base, User
from yuxi.storage.postgres.models_family import FamilyLink, FamilyMessage
from yuxi.utils.datetime_utils import SHANGHAI_TZ

pytestmark = [pytest.mark.asyncio, pytest.mark.unit]

# 固定"当天上午 10 点"，用例结果不随实际运行时刻变化
_FROZEN_NOW = datetime(2025, 1, 15, 10, 0, tzinfo=SHANGHAI_TZ)
_DUE_AT = _FROZEN_NOW - timedelta(hours=1)


def _freeze_clock(monkeypatch) -> None:
    monkeypatch.setattr(reminder_service, "shanghai_now", lambda: _FROZEN_NOW)
    monkeypatch.setattr(
        reminder_service,
        "utc_now_naive",
        lambda: _FROZEN_NOW.astimezone(UTC).replace(tzinfo=None),
    )


@pytest_asyncio.fixture()
async def ctx(monkeypatch):
    """老人张阿姨 + 已绑定子女小李 + 一个还没确认的绑定 + 一个陌生人。"""
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
        db.add_all(
            [
                FamilyLink(
                    elder_uid="elder_1",
                    child_uid="child_1",
                    relation="子女",
                    status="active",
                    invited_by="child_1",
                ),
                # 还没被老人确认的绑定不该出现在家人清单里
                FamilyLink(
                    elder_uid="elder_1",
                    child_uid="stranger_1",
                    relation="子女",
                    status="pending",
                    invited_by="stranger_1",
                ),
            ]
        )
        await db.commit()
        yield db, elder, child
    await engine.dispose()


async def _make_reminder(db, child, elder, title="吃降压药"):
    return await reminder_service.create_reminder(
        db,
        child,
        target_uid=elder.uid,
        title=title,
        content="饭后一片",
        category="用药",
        remind_at=_DUE_AT,
    )


async def test_family_members_cover_both_sides(ctx):
    db, elder, child = ctx

    as_elder = await family_tools._collect_family(db, elder)
    assert as_elder["me"]["name"] == "张阿姨"
    assert [(item["name"], item["who"]) for item in as_elder["family"]] == [("小李", "我的子女")]

    as_child = await family_tools._collect_family(db, child)
    assert [(item["name"], item["who"]) for item in as_child["family"]] == [("张阿姨", "我照护的老人")]


async def test_family_members_skip_pending_links(ctx):
    db, elder, _ = ctx

    payload = await family_tools._collect_family(db, elder)

    assert "路人" not in [item["name"] for item in payload["family"]]


async def test_family_members_carry_unread_count(ctx):
    db, elder, child = ctx
    db.add(FamilyMessage(from_uid=child.uid, to_uid=elder.uid, content="妈，记得吃药"))
    await db.commit()

    payload = await family_tools._collect_family(db, elder)

    assert payload["family"][0]["unread_messages"] == 1


def test_resolve_person_matches_name_and_self():
    me = {"name": "张阿姨", "uid": "elder_1"}
    family = [{"name": "小李", "uid": "child_1", "who": "我的子女", "unread_messages": 0}]

    assert family_tools._resolve_person(me, family, "小李")["uid"] == "child_1"
    assert family_tools._resolve_person(me, family, None)["uid"] == "elder_1"
    assert family_tools._resolve_person(me, family, "我自己")["uid"] == "elder_1"


def test_resolve_person_rejects_unknown_name():
    me = {"name": "张阿姨", "uid": "elder_1"}
    family = [{"name": "小李", "uid": "child_1", "who": "我的子女", "unread_messages": 0}]

    with pytest.raises(ValueError) as excinfo:
        family_tools._resolve_person(me, family, "老王")

    # 报错里必须带上真实家人名字，模型才有机会自查而不是瞎猜
    assert "老王" in str(excinfo.value)
    assert "小李" in str(excinfo.value)


async def test_reminders_show_who_set_what(ctx):
    db, elder, child = ctx
    await _make_reminder(db, child, elder)

    payload = await family_tools._collect_reminders(db, elder)

    assert payload["total"] == 1
    item = payload["reminders"][0]
    assert item["title"] == "吃降压药"
    assert item["set_by"] == "小李"
    assert item["set_for"] == "张阿姨"
    assert item["repeat"] == "一次性"
    # 库里存的是 naive UTC（上海 09:00 = UTC 01:00），直接念 UTC 会差 8 小时
    assert "1月15日" in item["time"]
    assert "09:00" in item["time"]


async def test_reminders_filter_by_setter(ctx):
    """老人问"小李给我设了什么提醒"时，小李是设置人而不是被提醒人。"""
    db, elder, child = ctx
    await _make_reminder(db, child, elder)

    payload = await family_tools._collect_reminders(db, elder, person="小李")

    assert payload["person"] == "小李"
    assert payload["total"] == 1


async def test_reminders_only_today_reports_status(ctx):
    db, elder, child = ctx
    await _make_reminder(db, child, elder)

    payload = await family_tools._collect_reminders(db, elder, only_today=True)

    assert payload["date"] == "2025-01-15"
    assert payload["reminders"][0]["set_by"] == "小李"
    assert payload["reminders"][0]["status"] in family_tools._OCCURRENCE_STATUS_LABELS.values()


async def test_reminders_empty_result_says_so(ctx):
    db, elder, _ = ctx

    payload = await family_tools._collect_reminders(db, elder, only_today=True)

    assert payload["total"] == 0
    assert payload["note"]


async def test_messages_are_read_without_marking_read(ctx):
    db, elder, child = ctx
    db.add(FamilyMessage(from_uid=child.uid, to_uid=elder.uid, content="妈，我晚上回来吃饭"))
    await db.commit()

    payload = await family_tools._collect_messages(db, elder, person="小李")

    assert payload["messages"][-1]["content"] == "妈，我晚上回来吃饭"
    assert payload["messages"][-1]["from"] == "小李"
    assert payload["messages"][-1]["read"] is False

    # 关键断言：查完以后未读红点必须还在
    result = await db.execute(select(FamilyMessage))
    assert result.scalars().all()[0].read_at is None


async def test_messages_reject_self(ctx):
    db, elder, _ = ctx

    with pytest.raises(ValueError):
        await family_tools._collect_messages(db, elder, person="我")


def test_runtime_uid_requires_login():
    with pytest.raises(ValueError):
        family_tools._runtime_uid(SimpleNamespace(context=None, config={}))


def test_runtime_uid_falls_back_to_configurable():
    runtime = SimpleNamespace(context=SimpleNamespace(uid=None), config={"configurable": {"uid": "elder_1"}})

    assert family_tools._runtime_uid(runtime) == "elder_1"


def test_buildin_tool_schemas_are_json_serializable():
    """工具列表接口要为每个内置工具生成 JSON Schema。

    带 ``runtime: ToolRuntime`` 的工具如果拿 ``args_schema`` 去生成，会在
    ``get_tool_metadata`` 里抛 ``Cannot generate a JsonSchema for
    core_schema.CallableSchema``，而这个调用发生在准备对话上下文阶段 ——
    线上表现是**整轮对话直接失败**，不是某次工具调用失败。这条用例守住这个坑。
    """
    from yuxi.agents.toolkits.registry import get_all_tool_instances
    from yuxi.agents.toolkits.service import _extract_tool_info

    infos = {info["slug"]: info for info in (_extract_tool_info(tool_obj) for tool_obj in get_all_tool_instances())}

    assert {"get_family_members", "list_family_reminders", "list_family_messages"} <= set(infos)
    # 注入参数不能出现在模型可见的参数列表里，否则模型会去编一个 runtime 出来
    for slug in ("get_family_members", "list_family_reminders", "list_family_messages"):
        assert "runtime" not in [arg["name"] for arg in infos[slug]["args"]]
    assert [arg["name"] for arg in infos["list_family_reminders"]["args"]] == ["person", "only_today"]


async def test_tool_wrapper_reads_session_from_pg_manager(ctx, monkeypatch):
    """工具本体要能自己开 session 跑通，别只在辅助函数上绿。"""
    db, elder, _ = ctx

    @asynccontextmanager
    async def fake_session():
        yield db

    from yuxi.storage.postgres import manager as manager_module

    monkeypatch.setattr(manager_module.pg_manager, "get_async_session_context", fake_session)
    runtime = SimpleNamespace(context=SimpleNamespace(uid=elder.uid), config={})

    payload = await family_tools.get_family_members.coroutine(runtime=runtime)

    assert payload["me"]["uid"] == "elder_1"
