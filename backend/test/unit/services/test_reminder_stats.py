"""依从性统计的口径测试。

锁两类风险：
1. 完成率分母只算"有结论"的记录——待确认的不能进分母，否则今天还没到点的提醒
   会把历史完成率算低；
2. 窗口必须是连续 N 天，缺数据的日期补 0，前端才能画成完整 7 根柱子。
"""

from __future__ import annotations

from datetime import timedelta

import pytest
import pytest_asyncio
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from yuxi.services import reminder_service
from yuxi.storage.postgres.models_business import Base, User
from yuxi.storage.postgres.models_family import FamilyLink, Reminder, ReminderOccurrence

pytestmark = [pytest.mark.asyncio, pytest.mark.unit]


@pytest_asyncio.fixture()
async def ctx():
    """老人 + 已绑定子女 + 陌生人。"""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as db:
        db.add_all(
            [
                User(uid="elder_1", username="张阿姨", password_hash="$argon2id$placeholder", role="user"),
                User(uid="child_1", username="小李", password_hash="$argon2id$placeholder", role="user"),
                User(uid="stranger_1", username="路人", password_hash="$argon2id$placeholder", role="user"),
            ]
        )
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

        async def load(uid: str) -> User:
            return (await db.execute(select(User).where(User.uid == uid))).scalar_one()

        yield db, await load("elder_1"), await load("child_1"), await load("stranger_1")
    await engine.dispose()


async def _add_reminder(db, title: str, category: str) -> int:
    reminder = Reminder(
        owner_uid="child_1",
        target_uid="elder_1",
        title=title,
        category=category,
        remind_at=reminder_service.to_naive_utc(reminder_service.shanghai_now()),
        repeat_rule={"type": "daily"},
        enabled=True,
    )
    db.add(reminder)
    await db.commit()
    return reminder.id


async def _add_occurrence(db, *, reminder_id: int, days_ago: int, hour: int, status: str) -> None:
    """在某天的某个上海时刻造一条执行记录。"""
    local_midnight = reminder_service.shanghai_now().replace(hour=0, minute=0, second=0, microsecond=0)
    local_time = local_midnight - timedelta(days=days_ago) + timedelta(hours=hour)
    db.add(
        ReminderOccurrence(
            reminder_id=reminder_id,
            target_uid="elder_1",
            scheduled_at=reminder_service.to_naive_utc(local_time),
            status=status,
        )
    )
    await db.commit()


async def test_rate_excludes_undecided_records(ctx):
    """已完成 2 条、未完成 1 条、待确认 2 条 → 完成率 2/3，待确认不进分母。"""
    db, _, child, _ = ctx
    medicine = await _add_reminder(db, "吃降压药", "用药")

    await _add_occurrence(db, reminder_id=medicine, days_ago=0, hour=8, status="done")
    await _add_occurrence(db, reminder_id=medicine, days_ago=1, hour=8, status="done")
    await _add_occurrence(db, reminder_id=medicine, days_ago=2, hour=8, status="missed")
    await _add_occurrence(db, reminder_id=medicine, days_ago=3, hour=8, status="confirmed")
    await _add_occurrence(db, reminder_id=medicine, days_ago=4, hour=8, status="pending")

    result = await reminder_service.adherence_stats(db, child, target_uid="elder_1", days=7)

    assert result["summary"]["total"] == 5
    assert result["summary"]["completed"] == 2
    assert result["summary"]["failed"] == 1
    assert result["summary"]["pending"] == 2
    assert result["summary"]["rate"] == 0.667  # 2 / (2 + 1)


async def test_skipped_and_missed_both_count_as_failed(ctx):
    """老人自述的未完成与超时未处理都进分母。"""
    db, _, child, _ = ctx
    walk = await _add_reminder(db, "散步", "活动")

    await _add_occurrence(db, reminder_id=walk, days_ago=0, hour=9, status="skipped")
    await _add_occurrence(db, reminder_id=walk, days_ago=5, hour=9, status="delivered")

    result = await reminder_service.adherence_stats(db, child, target_uid="elder_1", days=7)
    assert result["summary"]["failed"] == 1
    assert result["summary"]["pending"] == 1
    assert result["summary"]["rate"] == 0.0  # 有结论的只有 1 条，且是未完成


async def test_by_day_is_continuous_and_zero_filled(ctx):
    """窗口内每一天都要出现，没数据的补 0，最后一天是今天。"""
    db, _, child, _ = ctx
    medicine = await _add_reminder(db, "吃钙片", "用药")
    await _add_occurrence(db, reminder_id=medicine, days_ago=0, hour=8, status="done")

    result = await reminder_service.adherence_stats(db, child, target_uid="elder_1", days=7)

    days = [item["date"] for item in result["by_day"]]
    assert len(days) == 7
    assert days == sorted(days)
    assert days[-1] == reminder_service.shanghai_now().date().isoformat()
    assert [item["total"] for item in result["by_day"]] == [0, 0, 0, 0, 0, 0, 1]
    assert result["by_day"][-1]["rate"] == 1.0


async def test_by_category_sorted_by_total_desc(ctx):
    """分类明细按总条数降序，前端可直接铺开。"""
    db, _, child, _ = ctx
    medicine = await _add_reminder(db, "吃降压药", "用药")
    walk = await _add_reminder(db, "散步", "活动")

    for days_ago in range(3):
        await _add_occurrence(db, reminder_id=medicine, days_ago=days_ago, hour=8, status="done")
    await _add_occurrence(db, reminder_id=walk, days_ago=0, hour=18, status="done")

    result = await reminder_service.adherence_stats(db, child, target_uid="elder_1", days=7)
    assert [item["category"] for item in result["by_category"]] == ["用药", "活动"]
    assert result["by_category"][0]["total"] == 3


async def test_empty_range_returns_none_rate_not_zero(ctx):
    """完全没有记录时 rate 是 None —— 返回 0 会污蔑老人一次没做。"""
    db, _, child, _ = ctx
    result = await reminder_service.adherence_stats(db, child, target_uid="elder_1", days=7)
    assert result["summary"]["total"] == 0
    assert result["summary"]["rate"] is None
    assert len(result["by_day"]) == 7


async def test_days_is_clamped_to_30(ctx):
    db, _, child, _ = ctx
    result = await reminder_service.adherence_stats(db, child, target_uid="elder_1", days=90)
    assert result["range"]["days"] == 30
    assert len(result["by_day"]) == 30


async def test_stranger_cannot_read_stats(ctx):
    """没有绑定关系的人查不了，跨账号看老人数据必须挡住。"""
    db, _, _, stranger = ctx
    with pytest.raises(HTTPException) as exc:
        await reminder_service.adherence_stats(db, stranger, target_uid="elder_1", days=7)
    assert exc.value.status_code == 403
