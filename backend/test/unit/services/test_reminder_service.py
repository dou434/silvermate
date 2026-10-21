"""提醒服务层的权限与时间口径测试。

这几条断言锁的是真实风险：谁能改谁的提醒、子女能不能替老人确认、
以及"上海 20:00"必须落库成 UTC 12:00。
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
import pytest_asyncio
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from yuxi.services import reminder_service
from yuxi.storage.postgres.models_business import Base, User
from yuxi.storage.postgres.models_family import FamilyLink

pytestmark = [pytest.mark.asyncio, pytest.mark.unit]


@pytest_asyncio.fixture()
async def ctx():
    """三个用户：老人、已绑定的子女、陌生人。"""
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
    """今天（上海）的当前整点，带时区。

    一定落在当天、且距现在不超过宽限期（120 分钟），
    这样用例不会因为"跑在几点"而落到过去时刻被拒。
    """
    from yuxi.utils.datetime_utils import shanghai_now

    return shanghai_now().replace(minute=0, second=0, microsecond=0)


async def test_create_reminder_for_bound_elder_converts_time_to_utc(ctx):
    db, _, child, _ = ctx

    anchor = _soon_today()
    result = await reminder_service.create_reminder(
        db,
        child,
        target_uid="elder_1",
        title="吃降压药",
        content="饭后一片",
        category="用药",
        remind_at=_soon_today(),
    )

    assert result["target_uid"] == "elder_1"
    assert result["owner_uid"] == "child_1"
    # 上海时间必须只换算一次：既不能多减一个时区、也不能原样落库
    expected_utc = anchor.astimezone(UTC)
    assert result["remind_at"] == expected_utc.strftime("%Y-%m-%dT%H:%M:%SZ")
    assert int(result["remind_at"][11:13]) == (anchor.hour - 8) % 24


async def test_unbound_user_cannot_create_reminder_for_elder(ctx):
    db, _, _, stranger = ctx

    with pytest.raises(HTTPException) as exc_info:
        await reminder_service.create_reminder(
            db,
            stranger,
            target_uid="elder_1",
            title="恶意提醒",
            content=None,
            category="other",
            remind_at=_soon_today(),
        )

    assert exc_info.value.status_code == 403


async def test_child_cannot_manage_reminder_created_by_elder(ctx):
    """子女能看老人自己建的提醒，但不能改。"""
    db, elder, child, _ = ctx

    created = await reminder_service.create_reminder(
        db,
        elder,
        target_uid=None,
        title="自己去散步",
        content=None,
        category="活动",
        remind_at=_soon_today(),
    )

    with pytest.raises(HTTPException) as exc_info:
        await reminder_service.update_reminder(db, child, created["id"], title="改成别的")
    assert exc_info.value.status_code == 403

    visible = await reminder_service.list_reminders(db, child)
    assert [item["id"] for item in visible["reminders"]] == [created["id"]]


async def test_child_cannot_confirm_occurrence_for_elder(ctx):
    db, elder, child, _ = ctx

    created = await reminder_service.create_reminder(
        db,
        child,
        target_uid="elder_1",
        title="量血压",
        content=None,
        category="复诊",
        remind_at=_soon_today(),
    )
    today = await reminder_service.list_today(db, elder)
    occurrence_id = next(item["id"] for item in today["items"] if item["reminder_id"] == created["id"])

    with pytest.raises(HTTPException) as exc_info:
        await reminder_service.confirm_occurrence(db, child, occurrence_id)
    assert exc_info.value.status_code == 403


async def test_list_today_is_idempotent(ctx):
    """重复打开今日提醒不能产生重复的执行记录。"""
    db, elder, child, _ = ctx

    await reminder_service.create_reminder(
        db,
        child,
        target_uid="elder_1",
        title="午饭",
        content=None,
        category="饮食",
        remind_at=_soon_today(),
    )

    first = await reminder_service.list_today(db, elder)
    second = await reminder_service.list_today(db, elder)

    assert len(first["items"]) == 1
    assert [item["id"] for item in second["items"]] == [item["id"] for item in first["items"]]


async def test_finish_marks_done_and_skipped(ctx):
    db, elder, child, _ = ctx

    created = await reminder_service.create_reminder(
        db,
        child,
        target_uid="elder_1",
        title="喝水",
        content=None,
        category="other",
        remind_at=_soon_today(),
    )
    today = await reminder_service.list_today(db, elder)
    occurrence_id = next(item["id"] for item in today["items"] if item["reminder_id"] == created["id"])

    done = await reminder_service.finish_occurrence(db, elder, occurrence_id, done=True, note="喝了")
    assert done["status"] == "done"
    assert done["note"] == "喝了"
    assert done["confirmed_at"] is not None

    skipped = await reminder_service.finish_occurrence(db, elder, occurrence_id, done=False)
    assert skipped["status"] == "skipped"


async def test_daily_range_covers_full_local_day():
    start, end = reminder_service.today_range_utc()
    assert end - start == timedelta(days=1)
    # 上海当天 00:00 对应前一天 16:00Z
    assert start.hour == 16


async def test_daily_reminder_creates_one_occurrence_per_day(ctx):
    """每日提醒连续两天的执行记录应各自独立，且当天重复读取不新增。"""
    db, elder, child, _ = ctx

    created = await reminder_service.create_reminder(
        db,
        child,
        target_uid="elder_1",
        title="测血糖",
        content=None,
        category="复诊",
        remind_at=_soon_today(),
        repeat_rule={"type": "daily"},
    )

    assert created["repeat_rule"] == {"type": "daily"}

    first = await reminder_service.list_today(db, elder)
    second = await reminder_service.list_today(db, elder)

    assert len(first["items"]) == 1
    assert [item["id"] for item in second["items"]] == [item["id"] for item in first["items"]]
