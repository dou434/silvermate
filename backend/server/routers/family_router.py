"""家庭绑定与关怀留言路由。"""

from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from yuxi.services import emergency_service, family_service
from yuxi.storage.postgres.models_business import User

from server.utils.auth_middleware import get_db, get_required_user

family = APIRouter(prefix="/family", tags=["family"])


class LinkCreateRequest(BaseModel):
    elder_uid: str = Field(description="要绑定的老人 uid")
    relation: str = Field(default="子女", max_length=32, description="关系称谓")


class MessageCreateRequest(BaseModel):
    to_uid: str = Field(description="接收方 uid")
    content: str = Field(description="留言内容")


class EmergencyReportRequest(BaseModel):
    source: str = Field(description="触发来源：sos 或 keyword")
    category: str | None = Field(default=None, max_length=32, description="急症类型，如 cardiac/stroke，sos 时可省略")
    detail: str | None = Field(default=None, max_length=200, description="补充说明，如聊天命中的原话")


@family.post("/links", status_code=status.HTTP_201_CREATED)
async def create_family_link(
    data: LinkCreateRequest,
    current_user: User = Depends(get_required_user),
    db: AsyncSession = Depends(get_db),
):
    """子女发起绑定申请，需老人确认后生效。"""
    return await family_service.create_link(
        db, current_user, elder_uid=data.elder_uid, relation=data.relation.strip() or "子女"
    )


@family.get("/links")
async def list_family_links(
    current_user: User = Depends(get_required_user),
    db: AsyncSession = Depends(get_db),
):
    """列出与我相关的绑定：作为老人收到的、作为子女发起的。"""
    return await family_service.list_links(db, current_user)


@family.post("/links/{link_id}/approve")
async def approve_family_link(
    link_id: int,
    current_user: User = Depends(get_required_user),
    db: AsyncSession = Depends(get_db),
):
    """老人确认绑定。"""
    return await family_service.approve_link(db, current_user, link_id)


@family.post("/links/{link_id}/revoke")
async def revoke_family_link(
    link_id: int,
    current_user: User = Depends(get_required_user),
    db: AsyncSession = Depends(get_db),
):
    """解除绑定，任一方均可操作。"""
    return await family_service.revoke_link(db, current_user, link_id)


@family.get("/elders")
async def list_bound_elders(
    current_user: User = Depends(get_required_user),
    db: AsyncSession = Depends(get_db),
):
    """子女端：已绑定的老人列表。"""
    return {"elders": await family_service.list_elders(db, current_user)}


@family.post("/messages", status_code=status.HTTP_201_CREATED)
async def send_family_message(
    data: MessageCreateRequest,
    current_user: User = Depends(get_required_user),
    db: AsyncSession = Depends(get_db),
):
    """发送关怀留言，双方需已建立绑定。"""
    return await family_service.send_message(db, current_user, to_uid=data.to_uid, content=data.content)


@family.get("/messages")
async def list_family_messages(
    with_uid: str = Query(description="对话对方的 uid"),
    limit: int = Query(default=50, ge=1, le=200),
    current_user: User = Depends(get_required_user),
    db: AsyncSession = Depends(get_db),
):
    """读取与某位家庭成员的留言，同时把对方发来的未读标记为已读。"""
    return await family_service.list_messages(db, current_user, with_uid=with_uid, limit=limit)


@family.get("/messages/unread-count")
async def unread_message_count(
    current_user: User = Depends(get_required_user),
    db: AsyncSession = Depends(get_db),
):
    """未读留言总数与名下老人的未处理紧急数。"""
    return await family_service.unread_summary(db, current_user)


@family.post("/emergency", status_code=status.HTTP_201_CREATED)
async def report_emergency(
    data: EmergencyReportRequest,
    current_user: User = Depends(get_required_user),
    db: AsyncSession = Depends(get_db),
):
    """老人触发紧急求助：事件落库并向 active 绑定的子女发「【紧急求助】」留言。"""
    return await emergency_service.report_emergency(
        db, current_user, source=data.source, category=data.category, detail=data.detail
    )


@family.post("/emergency/{event_id}/resolve")
async def resolve_emergency(
    event_id: int,
    current_user: User = Depends(get_required_user),
    db: AsyncSession = Depends(get_db),
):
    """老人标记「我没事了」：撤销自己的 open 事件并补发安抚留言。"""
    return await emergency_service.resolve_emergency(db, current_user, event_id)


@family.get("/emergency/events")
async def list_emergency_events(
    limit: int = Query(default=50, ge=1, le=200),
    current_user: User = Depends(get_required_user),
    db: AsyncSession = Depends(get_db),
):
    """子女端：我绑定老人的紧急事件，未处理在前、按时间倒序。"""
    return await emergency_service.list_events_of_bound_elders(db, current_user, limit=limit)
