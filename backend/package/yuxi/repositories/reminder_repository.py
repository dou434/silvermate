"""提醒与执行记录的数据访问层。"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import delete, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from yuxi.storage.postgres.models_family import Reminder, ReminderOccurrence


class ReminderRepository:
    """提醒定义与执行记录的查询。"""

    async def get(self, db: AsyncSession, reminder_id: int) -> Reminder | None:
        """取未删除的提醒。"""
        result = await db.execute(select(Reminder).where(Reminder.id == reminder_id, Reminder.deleted_at.is_(None)))
        return result.scalar_one_or_none()

    async def list_visible(
        self,
        db: AsyncSession,
        *,
        uid: str,
        elder_uids: list[str],
        target_uid: str | None = None,
        limit: int = 200,
    ) -> list[Reminder]:
        """列出用户可见的提醒。

        可见范围：被提醒的人是自己、自己创建的、或者被提醒的人是已绑定的老人。
        """
        visible_owner = {uid, *elder_uids}
        stmt = select(Reminder).where(
            Reminder.deleted_at.is_(None),
            or_(Reminder.target_uid.in_(visible_owner), Reminder.owner_uid == uid),
        )
        if target_uid:
            stmt = stmt.where(Reminder.target_uid == target_uid)
        stmt = stmt.order_by(Reminder.remind_at.asc()).limit(max(1, min(limit, 500)))
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def list_active_started_before(self, db: AsyncSession, target_uid: str, end: datetime) -> list[Reminder]:
        """取某个老人所有"在 end 之前已经开始"的启用提醒。

        重复提醒的后续触发日不在 ``remind_at`` 所在区间内，因此按天展开时
        不能再用区间过滤，只能取全部已开始且仍启用的提醒再逐条判断。
        """
        result = await db.execute(
            select(Reminder)
            .where(
                Reminder.target_uid == target_uid,
                Reminder.deleted_at.is_(None),
                Reminder.enabled.is_(True),
                Reminder.remind_at < end,
            )
            .order_by(Reminder.remind_at.asc())
        )
        return list(result.scalars().all())

    async def list_all_active_started_before(
        self, db: AsyncSession, end: datetime, *, limit: int = 5000
    ) -> list[Reminder]:
        """取所有老人"在 end 之前已经开始"的启用提醒，供调度器按天展开。"""
        result = await db.execute(
            select(Reminder)
            .where(
                Reminder.deleted_at.is_(None),
                Reminder.enabled.is_(True),
                Reminder.remind_at < end,
            )
            .order_by(Reminder.remind_at.asc())
            .limit(max(1, limit))
        )
        return list(result.scalars().all())

    async def create(self, db: AsyncSession, data: dict[str, Any]) -> Reminder:
        reminder = Reminder(**data)
        db.add(reminder)
        await db.flush()
        return reminder

    async def get_occurrence(self, db: AsyncSession, occurrence_id: int) -> ReminderOccurrence | None:
        return await db.get(ReminderOccurrence, occurrence_id)

    async def get_occurrence_by_slot(
        self, db: AsyncSession, reminder_id: int, scheduled_at: datetime
    ) -> ReminderOccurrence | None:
        result = await db.execute(
            select(ReminderOccurrence).where(
                ReminderOccurrence.reminder_id == reminder_id,
                ReminderOccurrence.scheduled_at == scheduled_at,
            )
        )
        return result.scalar_one_or_none()

    async def create_occurrence(self, db: AsyncSession, data: dict[str, Any]) -> ReminderOccurrence:
        occurrence = ReminderOccurrence(**data)
        db.add(occurrence)
        await db.flush()
        return occurrence

    async def list_occurrences_between(
        self,
        db: AsyncSession,
        *,
        target_uids: list[str],
        start: datetime,
        end: datetime,
    ) -> list[ReminderOccurrence]:
        """取若干老人在 [start, end) 区间内的执行记录。"""
        if not target_uids:
            return []
        result = await db.execute(
            select(ReminderOccurrence)
            .where(
                ReminderOccurrence.target_uid.in_(target_uids),
                ReminderOccurrence.scheduled_at >= start,
                ReminderOccurrence.scheduled_at < end,
            )
            .order_by(ReminderOccurrence.scheduled_at.asc())
        )
        return list(result.scalars().all())

    async def list_occurrences_of_reminder(
        self, db: AsyncSession, reminder_id: int, *, limit: int = 30
    ) -> list[ReminderOccurrence]:
        result = await db.execute(
            select(ReminderOccurrence)
            .where(ReminderOccurrence.reminder_id == reminder_id)
            .order_by(ReminderOccurrence.scheduled_at.desc())
            .limit(max(1, min(limit, 200)))
        )
        return list(result.scalars().all())

    async def delete_unhandled_occurrences(
        self,
        db: AsyncSession,
        reminder_id: int,
        *,
        start: datetime,
        end: datetime,
        keep_scheduled_at: datetime,
    ) -> int:
        """删除某条提醒在指定区间内、且不是目标时刻的未处理记录。

        用于提醒时间被修改后清掉旧时刻留下的"幽灵待办"；已完成/已确认的
        历史记录不动，保留老人真实的操作痕迹。
        """
        result = await db.execute(
            delete(ReminderOccurrence)
            .where(
                ReminderOccurrence.reminder_id == reminder_id,
                ReminderOccurrence.scheduled_at >= start,
                ReminderOccurrence.scheduled_at < end,
                ReminderOccurrence.scheduled_at != keep_scheduled_at,
                ReminderOccurrence.status.in_(("pending", "delivered")),
            )
            .execution_options(synchronize_session=False)
        )
        return result.rowcount or 0
