"""家庭养老业务数据模型 - 家庭绑定、提醒、执行记录与关怀留言。

时间字段统一使用不带时区的 TIMESTAMP，存 UTC（与 ``models_business`` 中的
``users.created_at`` 等字段保持一致），对外暴露前由服务层转成 Asia/Shanghai。
"""

from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from yuxi.storage.postgres.models_business import Base
from yuxi.utils.datetime_utils import format_utc_datetime, utc_now_naive

# 家庭绑定状态：待老人确认 / 已生效 / 已解除
FAMILY_LINK_STATUSES = ("pending", "active", "revoked")

# 提醒执行状态：待触发 / 已投递到站内 / 老人已看到 / 已确认收到 / 已完成 / 已跳过 / 已错过
REMINDER_OCCURRENCE_STATUSES = (
    "pending",
    "delivered",
    "seen",
    "confirmed",
    "done",
    "skipped",
    "missed",
)

# 紧急事件来源：老人按下 SOS 按钮 / 聊天命中紧急关键词后老人选择通知
EMERGENCY_EVENT_SOURCES = ("sos", "keyword")
# 紧急事件状态：待处理 / 老人已标记「我没事了」
EMERGENCY_EVENT_STATUSES = ("open", "resolved")


class FamilyLink(Base):
    """家庭绑定关系：一条记录表示一位子女可以照护一位老人。

    绑定由子女发起，需老人确认后才置为 ``active``；``revoked`` 保留历史不再生效。
    """

    __tablename__ = "family_links"

    id = Column(Integer, primary_key=True, autoincrement=True)
    elder_uid = Column(
        String(64),
        ForeignKey("users.uid", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="被照护的老人 uid",
    )
    child_uid = Column(
        String(64),
        ForeignKey("users.uid", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="发起照护的子女 uid",
    )
    relation = Column(String(32), nullable=False, default="子女", comment="关系称谓：子女/配偶/亲属/照护者")
    status = Column(String(16), nullable=False, default="pending", index=True, comment="pending/active/revoked")
    invited_by = Column(String(64), nullable=False, comment="发起绑定的一方 uid")
    created_at = Column(DateTime, default=utc_now_naive)
    updated_at = Column(DateTime, default=utc_now_naive, onupdate=utc_now_naive)

    __table_args__ = (
        UniqueConstraint("elder_uid", "child_uid", name="uq_family_links_pair"),
        Index("ix_family_links_elder_status", "elder_uid", "status"),
        Index("ix_family_links_child_status", "child_uid", "status"),
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "elder_uid": self.elder_uid,
            "child_uid": self.child_uid,
            "relation": self.relation,
            "status": self.status,
            "invited_by": self.invited_by,
            "created_at": format_utc_datetime(self.created_at),
            "updated_at": format_utc_datetime(self.updated_at),
        }


class Reminder(Base):
    """提醒定义。

    ``owner_uid`` 是创建者，``target_uid`` 是被提醒的人。老人给自己建提醒时两者相同；
    子女给老人建提醒时 ``owner_uid`` 是子女、``target_uid`` 是老人。
    """

    __tablename__ = "reminders"

    id = Column(Integer, primary_key=True, autoincrement=True)
    owner_uid = Column(String(64), nullable=False, index=True, comment="提醒创建者 uid")
    target_uid = Column(String(64), nullable=False, index=True, comment="被提醒的老人 uid")
    title = Column(String(120), nullable=False, comment="提醒标题，如“吃降压药”")
    content = Column(Text, nullable=True, comment="补充说明")
    category = Column(String(32), nullable=False, default="other", comment="用药/复诊/饮食/活动/other")
    remind_at = Column(DateTime, nullable=False, index=True, comment="首次提醒时间（UTC）")
    repeat_rule = Column(JSON, nullable=False, default=dict, comment="重复规则：{type,weekdays,interval,until}")
    enabled = Column(Boolean, nullable=False, default=True, index=True, comment="是否启用")
    deleted_at = Column(DateTime, nullable=True, comment="软删除时间，非空表示已删除")
    created_at = Column(DateTime, default=utc_now_naive)
    updated_at = Column(DateTime, default=utc_now_naive, onupdate=utc_now_naive)

    __table_args__ = (
        Index("ix_reminders_target_time", "target_uid", "remind_at"),
        Index("ix_reminders_enabled_time", "enabled", "remind_at"),
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "owner_uid": self.owner_uid,
            "target_uid": self.target_uid,
            "title": self.title,
            "content": self.content,
            "category": self.category,
            "remind_at": format_utc_datetime(self.remind_at),
            "repeat_rule": self.repeat_rule or {},
            "enabled": bool(self.enabled),
            "deleted_at": format_utc_datetime(self.deleted_at),
            "created_at": format_utc_datetime(self.created_at),
            "updated_at": format_utc_datetime(self.updated_at),
        }


class ReminderOccurrence(Base):
    """提醒的每一次触发记录。

    一个每日提醒会产生多条记录；``(reminder_id, scheduled_at)`` 唯一约束保证
    调度器重复扫描时不会插入重复记录。
    """

    __tablename__ = "reminder_occurrences"

    id = Column(Integer, primary_key=True, autoincrement=True)
    reminder_id = Column(
        Integer,
        ForeignKey("reminders.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="所属提醒 id",
    )
    target_uid = Column(String(64), nullable=False, index=True, comment="冗余的老人 uid，便于按人查询")
    scheduled_at = Column(DateTime, nullable=False, index=True, comment="本次计划触发时间（UTC）")
    status = Column(
        String(16), nullable=False, default="pending", index=True, comment="见 REMINDER_OCCURRENCE_STATUSES"
    )
    confirmed_at = Column(DateTime, nullable=True, comment="老人确认收到的时间")
    finished_at = Column(DateTime, nullable=True, comment="标记完成或未完成的时间")
    note = Column(Text, nullable=True, comment="老人补充说明")
    created_at = Column(DateTime, default=utc_now_naive)

    __table_args__ = (
        UniqueConstraint("reminder_id", "scheduled_at", name="uq_reminder_occurrences_slot"),
        Index("ix_reminder_occurrences_target_status", "target_uid", "status"),
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "reminder_id": self.reminder_id,
            "target_uid": self.target_uid,
            "scheduled_at": format_utc_datetime(self.scheduled_at),
            "status": self.status,
            "confirmed_at": format_utc_datetime(self.confirmed_at),
            "finished_at": format_utc_datetime(self.finished_at),
            "note": self.note,
            "created_at": format_utc_datetime(self.created_at),
        }


class EmergencyEvent(Base):
    """老人的紧急求助事件。

    由老人侧触发（SOS 按钮或聊天紧急关键词），落库后由 ``emergency_service``
    通过 ``family_messages`` 通知 active 绑定的子女；紧急性由本表承载，
    ``FamilyMessage`` 不加紧急标记列，留言内容以「【紧急求助】」前缀区分。
    """

    __tablename__ = "emergency_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    elder_uid = Column(
        String(64),
        ForeignKey("users.uid", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="求助的老人 uid",
    )
    source = Column(String(16), nullable=False, comment="sos/keyword")
    category = Column(String(32), nullable=False, default="general", comment="急症类型：cardiac/stroke/fall 等，sos 时为 general")
    detail = Column(Text, nullable=True, comment="触发时的补充说明，如聊天命中的原话")
    status = Column(String(16), nullable=False, default="open", index=True, comment="open/resolved")
    resolved_at = Column(DateTime, nullable=True, comment="老人标记「我没事了」的时间")
    created_at = Column(DateTime, default=utc_now_naive)

    __table_args__ = (Index("ix_emergency_events_elder_status_time", "elder_uid", "status", "created_at"),)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "elder_uid": self.elder_uid,
            "source": self.source,
            "category": self.category,
            "detail": self.detail,
            "status": self.status,
            "resolved_at": format_utc_datetime(self.resolved_at),
            "created_at": format_utc_datetime(self.created_at),
        }


class FamilyMessage(Base):
    """家庭关怀留言。

    不复用 ``messages`` 表：那张表挂在 ``conversations`` 上，混入会污染 AI 对话的
    会话统计与线程上下文。
    """

    __tablename__ = "family_messages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    from_uid = Column(String(64), nullable=False, index=True, comment="发送方 uid")
    to_uid = Column(String(64), nullable=False, index=True, comment="接收方 uid")
    content = Column(Text, nullable=False, comment="留言内容")
    read_at = Column(DateTime, nullable=True, comment="已读时间，空表示未读")
    created_at = Column(DateTime, default=utc_now_naive, index=True)

    __table_args__ = (Index("ix_family_messages_to_read", "to_uid", "read_at", "created_at"),)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "from_uid": self.from_uid,
            "to_uid": self.to_uid,
            "content": self.content,
            "read_at": format_utc_datetime(self.read_at),
            "created_at": format_utc_datetime(self.created_at),
        }
