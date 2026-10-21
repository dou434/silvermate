"""家庭养老业务模型的单元测试。

覆盖两件容易回归的事：表结构能否落在同一个 metadata 上，
以及"重复绑定"和"同一提醒同一时刻重复触发"这两条唯一约束是否真的生效。
"""

from __future__ import annotations

import pytest
import pytest_asyncio
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from yuxi.storage.postgres.models_business import Base
from yuxi.storage.postgres.models_family import (
    FamilyLink,
    FamilyMessage,
    Reminder,
    ReminderOccurrence,
)
from yuxi.utils.datetime_utils import utc_now_naive

pytestmark = [pytest.mark.asyncio, pytest.mark.unit]


@pytest_asyncio.fixture()
async def session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as db:
        yield db
    await engine.dispose()


async def test_family_tables_are_registered_on_business_metadata(session):
    """四张表必须注册到 models_business 的同一个 Base，否则 create_all 不会建表。"""
    table_names = set(Base.metadata.tables)
    assert {"family_links", "reminders", "reminder_occurrences", "family_messages"} <= table_names


async def test_family_link_roundtrip(session):
    session.add(FamilyLink(elder_uid="elder_01", child_uid="child_01", invited_by="child_01"))
    await session.commit()

    link = await session.get(FamilyLink, 1)
    assert link.status == "pending"
    assert link.relation == "子女"
    assert link.to_dict()["elder_uid"] == "elder_01"


async def test_family_link_pair_is_unique(session):
    session.add(FamilyLink(elder_uid="elder_01", child_uid="child_01", invited_by="child_01"))
    await session.commit()

    session.add(FamilyLink(elder_uid="elder_01", child_uid="child_01", invited_by="child_01"))
    with pytest.raises(IntegrityError):
        await session.commit()
    await session.rollback()


async def test_reminder_occurrence_slot_is_unique(session):
    reminder = Reminder(
        owner_uid="child_01",
        target_uid="elder_01",
        title="吃降压药",
        remind_at=utc_now_naive(),
    )
    session.add(reminder)
    await session.commit()

    slot = utc_now_naive()
    session.add(ReminderOccurrence(reminder_id=reminder.id, target_uid="elder_01", scheduled_at=slot))
    await session.commit()

    # 调度器重复扫描时必须靠这条约束兜底，而不是插入第二条记录
    session.add(ReminderOccurrence(reminder_id=reminder.id, target_uid="elder_01", scheduled_at=slot))
    with pytest.raises(IntegrityError):
        await session.commit()
    await session.rollback()


async def test_reminder_defaults_and_serialization(session):
    remind_at = utc_now_naive()
    session.add(
        Reminder(
            owner_uid="elder_01",
            target_uid="elder_01",
            title="散步 30 分钟",
            remind_at=remind_at,
        )
    )
    await session.commit()

    reminder = await session.get(Reminder, 1)
    assert reminder.enabled is True
    assert reminder.category == "other"
    assert reminder.repeat_rule == {}

    payload = reminder.to_dict()
    assert payload["remind_at"].endswith("Z")
    assert payload["deleted_at"] is None


async def test_family_message_unread_tracking(session):
    session.add(FamilyMessage(from_uid="child_01", to_uid="elder_01", content="妈，记得吃药"))
    await session.commit()

    message = await session.get(FamilyMessage, 1)
    assert message.read_at is None
    assert message.to_dict()["read_at"] is None

    message.read_at = utc_now_naive()
    await session.commit()
    await session.refresh(message)
    assert message.to_dict()["read_at"].endswith("Z")
