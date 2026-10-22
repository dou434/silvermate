"""家庭绑定与关怀留言的数据访问层。

所有方法都接收调用方传入的 ``AsyncSession``，与路由层的 ``get_db`` 保持同一事务，
避免仓储自开 session 导致"刚写入读不到"的一致性问题。
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from yuxi.storage.postgres.models_family import FamilyLink, FamilyMessage

ACTIVE = "active"


class FamilyRepository:
    """家庭绑定关系与留言查询。"""

    async def get_link(self, db: AsyncSession, link_id: int) -> FamilyLink | None:
        return await db.get(FamilyLink, link_id)

    async def get_link_by_pair(self, db: AsyncSession, elder_uid: str, child_uid: str) -> FamilyLink | None:
        result = await db.execute(
            select(FamilyLink).where(FamilyLink.elder_uid == elder_uid, FamilyLink.child_uid == child_uid)
        )
        return result.scalar_one_or_none()

    async def get_active_link(self, db: AsyncSession, elder_uid: str, child_uid: str) -> FamilyLink | None:
        result = await db.execute(
            select(FamilyLink).where(
                FamilyLink.elder_uid == elder_uid,
                FamilyLink.child_uid == child_uid,
                FamilyLink.status == ACTIVE,
            )
        )
        return result.scalar_one_or_none()

    async def is_active_child(self, db: AsyncSession, elder_uid: str, child_uid: str) -> bool:
        return await self.get_active_link(db, elder_uid, child_uid) is not None

    async def list_links_of_user(self, db: AsyncSession, uid: str) -> list[FamilyLink]:
        """列出与某个用户相关的全部绑定（无论作为老人还是子女）。"""
        result = await db.execute(
            select(FamilyLink)
            .where(or_(FamilyLink.elder_uid == uid, FamilyLink.child_uid == uid))
            .order_by(FamilyLink.created_at.desc())
        )
        return list(result.scalars().all())

    async def list_elders_of_child(self, db: AsyncSession, child_uid: str) -> list[FamilyLink]:
        """子女视角：我绑定的老人。"""
        result = await db.execute(
            select(FamilyLink)
            .where(FamilyLink.child_uid == child_uid, FamilyLink.status == ACTIVE)
            .order_by(FamilyLink.created_at.desc())
        )
        return list(result.scalars().all())

    async def list_children_of_elder(self, db: AsyncSession, elder_uid: str) -> list[FamilyLink]:
        """老人视角：绑定我的子女。"""
        result = await db.execute(
            select(FamilyLink)
            .where(FamilyLink.elder_uid == elder_uid, FamilyLink.status == ACTIVE)
            .order_by(FamilyLink.created_at.desc())
        )
        return list(result.scalars().all())

    async def list_active_elder_uids_of_child(self, db: AsyncSession, child_uid: str) -> list[str]:
        """子女可管理的老人 uid 列表，用于提醒可见性过滤。"""
        result = await db.execute(
            select(FamilyLink.elder_uid).where(FamilyLink.child_uid == child_uid, FamilyLink.status == ACTIVE)
        )
        return [uid for (uid,) in result.all()]

    async def create_link(self, db: AsyncSession, data: dict[str, Any]) -> FamilyLink:
        link = FamilyLink(**data)
        db.add(link)
        await db.flush()
        return link

    async def create_message(self, db: AsyncSession, data: dict[str, Any]) -> FamilyMessage:
        message = FamilyMessage(**data)
        db.add(message)
        await db.flush()
        return message

    async def list_messages_between(
        self, db: AsyncSession, uid_a: str, uid_b: str, *, limit: int = 50
    ) -> list[FamilyMessage]:
        result = await db.execute(
            select(FamilyMessage)
            .where(
                or_(
                    (FamilyMessage.from_uid == uid_a) & (FamilyMessage.to_uid == uid_b),
                    (FamilyMessage.from_uid == uid_b) & (FamilyMessage.to_uid == uid_a),
                )
            )
            .order_by(FamilyMessage.created_at.desc())
            .limit(max(1, min(limit, 200)))
        )
        return list(reversed(result.scalars().all()))

    async def mark_thread_read(self, db: AsyncSession, to_uid: str, from_uid: str, read_at) -> int:
        """把 from_uid 发给 to_uid 的未读留言标记为已读，返回条数。"""
        result = await db.execute(
            select(FamilyMessage).where(
                FamilyMessage.to_uid == to_uid,
                FamilyMessage.from_uid == from_uid,
                FamilyMessage.read_at.is_(None),
            )
        )
        messages = list(result.scalars().all())
        for message in messages:
            message.read_at = read_at
        return len(messages)

    async def count_unread(self, db: AsyncSession, to_uid: str) -> int:
        result = await db.execute(
            select(func.count(FamilyMessage.id)).where(FamilyMessage.to_uid == to_uid, FamilyMessage.read_at.is_(None))
        )
        return int(result.scalar() or 0)

    async def count_unread_by_sender(self, db: AsyncSession, to_uid: str) -> dict[str, int]:
        """按发送人分组统计未读数。

        老人可能有多个家人，只给总数的话他不知道该点开谁的对话；
        带上分组计数就能默认打开"有新消息的那一位"。
        """
        result = await db.execute(
            select(FamilyMessage.from_uid, func.count(FamilyMessage.id))
            .where(FamilyMessage.to_uid == to_uid, FamilyMessage.read_at.is_(None))
            .group_by(FamilyMessage.from_uid)
        )
        return {from_uid: int(count) for from_uid, count in result.all()}
