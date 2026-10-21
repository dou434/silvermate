"""提醒调度的单元测试：当日记录补齐的幂等性与状态推进边界。"""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest
import pytest_asyncio
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from yuxi.services import reminder_service
from yuxi.storage.postgres.models_business import Base, User
from yuxi.storage.postgres.models_family import FamilyLink, Reminder, ReminderOccurrence
from yuxi.utils.datetime_utils import utc_now_naive

pytestmark = [pytest.mark.asyncio, pytest.mark.unit]


def _current_hour() -> datetime:
    """今天（上海）的当前整点，带时区。

    一定落在当天、且距现在不超过宽限期，避免用例受运行时刻影响。
    """
    return reminder_service.shanghai_now().replace(minute=0, second=0, microsecond=0)


@pytest_asyncio.fixture()
async def ctx():
    """一位老人 + 一位已绑定子女。"""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as db:
        elder = User(uid="elder_1", username="张阿姨", password_hash="$argon2id$placeholder", role="user")
        child = User(uid="child_1", username="小李", password_hash="$argon2id$placeholder", role="user")
        db.add_all([elder, child])
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
        yield db, elder, child
    await engine.dispose()


async def _make_occurrence(db, reminder_id: int, *, offset_minutes: int, status: str) -> ReminderOccurrence:
    occurrence = ReminderOccurrence(
        reminder_id=reminder_id,
        target_uid="elder_1",
        scheduled_at=utc_now_naive() + timedelta(minutes=offset_minutes),
        status=status,
    )
    db.add(occurrence)
    await db.commit()
    await db.refresh(occurrence)
    return occurrence


async def test_sync_day_occurrences_is_idempotent(ctx):
    db, _, child = ctx

    await reminder_service.create_reminder(
        db,
        child,
        target_uid="elder_1",
        title="每日散步",
        content=None,
        category="活动",
        remind_at=_current_hour(),
        repeat_rule={"type": "daily"},
    )

    first = await reminder_service.sync_day_occurrences(db)
    second = await reminder_service.sync_day_occurrences(db)

    assert first["created"] == 1
    assert second["created"] == 0
    assert first["scanned"] == second["scanned"] == 1


async def test_advance_marks_due_as_delivered_and_overdue_as_missed(ctx):
    db, _, child = ctx

    created = await reminder_service.create_reminder(
        db,
        child,
        target_uid="elder_1",
        title="测血压",
        content=None,
        category="复诊",
        remind_at=_current_hour(),
    )

    due = await _make_occurrence(db, created["id"], offset_minutes=-10, status="pending")
    overdue = await _make_occurrence(db, created["id"], offset_minutes=-180, status="pending")
    finished = await _make_occurrence(db, created["id"], offset_minutes=-180, status="done")

    result = await reminder_service.advance_due_status(db, grace_minutes=120)
    await db.commit()

    assert result == {"missed": 1, "delivered": 1}

    # 直接读列值，避免 identity map 返回更新前的旧对象
    rows = await db.execute(select(ReminderOccurrence.id, ReminderOccurrence.status))
    refreshed = dict(rows.all())
    assert refreshed[due.id] == "delivered"
    assert refreshed[overdue.id] == "missed"
    assert refreshed[finished.id] == "done"


async def test_advance_does_not_touch_future_occurrences(ctx):
    db, _, child = ctx

    created = await reminder_service.create_reminder(
        db,
        child,
        target_uid="elder_1",
        title="晚上泡脚",
        content=None,
        category="活动",
        remind_at=reminder_service.shanghai_now().replace(hour=21, minute=0, second=0, microsecond=0),
    )
    future = await _make_occurrence(db, created["id"], offset_minutes=120, status="pending")

    result = await reminder_service.advance_due_status(db, grace_minutes=120)
    await db.commit()
    await db.refresh(future)

    assert result == {"missed": 0, "delivered": 0}
    assert future.status == "pending"


async def test_missed_occurrence_can_still_be_confirmed(ctx):
    """超时未处理的记录，老人晚点看到仍能确认。"""
    db, elder, child = ctx

    created = await reminder_service.create_reminder(
        db,
        child,
        target_uid="elder_1",
        title="吃药",
        content=None,
        category="用药",
        remind_at=_current_hour(),
    )
    occurrence = await _make_occurrence(db, created["id"], offset_minutes=-300, status="pending")
    await reminder_service.advance_due_status(db, grace_minutes=120)
    await db.commit()
    await db.refresh(occurrence)
    assert occurrence.status == "missed"

    confirmed = await reminder_service.confirm_occurrence(db, elder, occurrence.id)

    assert confirmed["status"] == "confirmed"
    assert confirmed["confirmed_at"] is not None


async def test_disabled_reminder_is_not_synced(ctx):
    """停用或软删除的提醒不应再产生当日记录。"""
    db, _, child = ctx

    created = await reminder_service.create_reminder(
        db,
        child,
        target_uid="elder_1",
        title="临时提醒",
        content=None,
        category="other",
        remind_at=reminder_service.shanghai_now().replace(hour=7, minute=30, second=0, microsecond=0),
        repeat_rule={"type": "daily"},
    )
    await reminder_service.update_reminder(db, child, created["id"], enabled=False)

    result = await reminder_service.sync_day_occurrences(db)

    assert result["created"] == 0
    assert result["scanned"] == 0
    remaining = (await db.execute(select(Reminder).where(Reminder.id == created["id"]))).scalar_one()
    assert remaining.enabled is False


async def test_changing_remind_time_drops_stale_occurrence(ctx):
    """改了提醒时间后，旧时刻的未处理记录应被清理，避免留下幽灵待办。"""
    db, _, child = ctx

    morning = _current_hour()
    created = await reminder_service.create_reminder(
        db,
        child,
        target_uid="elder_1",
        title="晨练",
        content=None,
        category="活动",
        remind_at=morning,
        repeat_rule={"type": "daily"},
    )

    await reminder_service.sync_day_occurrences(db)
    before = (await db.execute(select(ReminderOccurrence.scheduled_at))).all()
    assert len(before) == 1

    moved = morning + timedelta(minutes=30)
    if moved.date() != morning.date():
        moved = morning - timedelta(minutes=30)
    await reminder_service.update_reminder(db, child, created["id"], remind_at=moved)
    await db.commit()
    after = (await db.execute(select(ReminderOccurrence.scheduled_at))).all()
    assert after == []

    reloaded = await reminder_service.sync_day_occurrences(db)
    assert reloaded["created"] == 1
    final = (await db.execute(select(ReminderOccurrence.scheduled_at))).all()
    assert len(final) == 1
    assert final[0][0] == reminder_service.to_naive_utc(moved)


async def test_past_slot_beyond_grace_is_not_synthesized(ctx):
    """已过宽限期的时刻不再补建记录，避免凭空生成一条"已错过"。"""
    db, _, child = ctx

    await reminder_service.create_reminder(
        db,
        child,
        target_uid="elder_1",
        title="吃降压药",
        content=None,
        category="用药",
        remind_at=reminder_service.shanghai_now().replace(hour=7, minute=0, second=0, microsecond=0),
        repeat_rule={"type": "daily"},
    )
    reminder = (await db.execute(select(Reminder))).scalar_one()

    local_day = reminder_service.shanghai_now().date()
    day_start_utc, _ = reminder_service.day_range_utc(local_day)
    result = await reminder_service._ensure_occurrence_for_day(
        db, reminder, local_day, now=day_start_utc + timedelta(hours=12)
    )

    assert result is None
    rows = (await db.execute(select(ReminderOccurrence.id))).all()
    assert rows == []


async def test_slot_within_grace_still_generates_occurrence(ctx):
    """宽限期内的过去时刻仍要生成记录，老人晚几分钟看到也能确认。"""
    db, _, child = ctx

    await reminder_service.create_reminder(
        db,
        child,
        target_uid="elder_1",
        title="喝水",
        content=None,
        category="饮食",
        remind_at=reminder_service.shanghai_now().replace(hour=7, minute=0, second=0, microsecond=0),
        repeat_rule={"type": "daily"},
    )
    reminder = (await db.execute(select(Reminder))).scalar_one()

    local_day = reminder_service.shanghai_now().date()
    day_start_utc, _ = reminder_service.day_range_utc(local_day)
    result = await reminder_service._ensure_occurrence_for_day(
        db, reminder, local_day, now=day_start_utc + timedelta(hours=7, minutes=30)
    )

    assert result is not None
    assert result[1] is True


async def test_one_off_reminder_in_the_past_is_rejected(ctx):
    """一次性提醒定在过去会永远不触发，必须在入口拦住。"""
    db, _, child = ctx

    with pytest.raises(HTTPException) as excinfo:
        await reminder_service.create_reminder(
            db,
            child,
            target_uid="elder_1",
            title="缴电费",
            content=None,
            category="other",
            remind_at=reminder_service.shanghai_now() - timedelta(hours=3),
        )

    assert excinfo.value.status_code == 400


async def test_daily_reminder_in_the_past_is_allowed(ctx):
    """重复提醒允许错过后从第二天开始，不能被当成非法输入拒绝。"""
    db, _, child = ctx

    created = await reminder_service.create_reminder(
        db,
        child,
        target_uid="elder_1",
        title="散步",
        content=None,
        category="活动",
        remind_at=reminder_service.shanghai_now() - timedelta(hours=3),
        repeat_rule={"type": "daily"},
    )

    assert created["id"] is not None
