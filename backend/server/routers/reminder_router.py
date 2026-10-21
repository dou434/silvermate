"""提醒与执行记录路由。"""

from datetime import datetime

from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from yuxi.services import reminder_service
from yuxi.storage.postgres.models_business import User

from server.utils.auth_middleware import get_db, get_required_user

reminders = APIRouter(prefix="/reminders", tags=["reminders"])


class ReminderCreateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=120, description="提醒标题")
    remind_at: datetime = Field(description="提醒时间，建议传带时区的 ISO 8601")
    target_uid: str | None = Field(default=None, description="被提醒人，缺省表示自己")
    content: str | None = Field(default=None, description="补充说明")
    category: str | None = Field(default=None, description="用药/复诊/饮食/活动/other")
    repeat_rule: dict | None = Field(
        default=None,
        description='重复规则：{"type": "none|daily|weekly|custom", "weekdays": [1,3], "interval": 2, "until": "2026-12-31"}',
    )


class ReminderUpdateRequest(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=120)
    remind_at: datetime | None = None
    content: str | None = None
    category: str | None = None
    enabled: bool | None = None
    repeat_rule: dict | None = None


class OccurrenceFinishRequest(BaseModel):
    done: bool = Field(description="true 表示已完成，false 表示未完成")
    note: str | None = Field(default=None, description="老人补充说明")


@reminders.get("")
async def list_reminders(
    target_uid: str | None = Query(default=None, description="只看某位老人的提醒"),
    current_user: User = Depends(get_required_user),
    db: AsyncSession = Depends(get_db),
):
    """列出我可见的提醒：自己的、我创建的、以及已绑定老人的。"""
    return await reminder_service.list_reminders(db, current_user, target_uid=target_uid)


@reminders.get("/today")
async def list_today_reminders(
    target_uid: str | None = Query(default=None, description="查看某位老人的今日提醒，缺省为自己"),
    current_user: User = Depends(get_required_user),
    db: AsyncSession = Depends(get_db),
):
    """今日提醒（含执行状态）。首次调用会按需补齐今天的执行记录。"""
    return await reminder_service.list_today(db, current_user, target_uid=target_uid)


@reminders.post("", status_code=status.HTTP_201_CREATED)
async def create_reminder(
    data: ReminderCreateRequest,
    current_user: User = Depends(get_required_user),
    db: AsyncSession = Depends(get_db),
):
    """创建提醒。给自己建或给已绑定的老人建。"""
    return await reminder_service.create_reminder(
        db,
        current_user,
        target_uid=data.target_uid,
        title=data.title,
        content=data.content,
        category=data.category,
        remind_at=data.remind_at,
        repeat_rule=data.repeat_rule,
    )


@reminders.put("/{reminder_id}")
async def update_reminder(
    reminder_id: int,
    data: ReminderUpdateRequest,
    current_user: User = Depends(get_required_user),
    db: AsyncSession = Depends(get_db),
):
    """修改提醒，仅限创建者本人。"""
    return await reminder_service.update_reminder(
        db,
        current_user,
        reminder_id,
        title=data.title,
        content=data.content,
        category=data.category,
        remind_at=data.remind_at,
        enabled=data.enabled,
        repeat_rule=data.repeat_rule,
    )


@reminders.delete("/{reminder_id}")
async def delete_reminder(
    reminder_id: int,
    current_user: User = Depends(get_required_user),
    db: AsyncSession = Depends(get_db),
):
    """删除提醒（软删除），仅限创建者本人。"""
    return await reminder_service.delete_reminder(db, current_user, reminder_id)


@reminders.get("/{reminder_id}/occurrences")
async def list_reminder_occurrences(
    reminder_id: int,
    current_user: User = Depends(get_required_user),
    db: AsyncSession = Depends(get_db),
):
    """某条提醒的历史执行记录。"""
    return await reminder_service.list_occurrences(db, current_user, reminder_id)


@reminders.post("/occurrences/{occurrence_id}/confirm")
async def confirm_occurrence(
    occurrence_id: int,
    current_user: User = Depends(get_required_user),
    db: AsyncSession = Depends(get_db),
):
    """老人确认收到提醒。"""
    return await reminder_service.confirm_occurrence(db, current_user, occurrence_id)


@reminders.post("/occurrences/{occurrence_id}/finish")
async def finish_occurrence(
    occurrence_id: int,
    data: OccurrenceFinishRequest,
    current_user: User = Depends(get_required_user),
    db: AsyncSession = Depends(get_db),
):
    """老人标记完成或未完成。"""
    return await reminder_service.finish_occurrence(
        db, current_user, occurrence_id, done=data.done, note=data.note
    )
