"""紧急求助事件的用例层。

SOS 按钮与聊天紧急关键词都汇聚到这里：事件落库、冷却去重、向 active
绑定的子女分发「【紧急求助】」留言，以及老人「我没事了」的撤销与安抚补发。
权限口径：创建/撤销仅限老人本人；子女只能查询自己绑定老人的事件。
无绑定家人时事件仍落库，接口返回空通知名单，由前端明示「未能通知」。
"""

from __future__ import annotations

from datetime import timedelta

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from yuxi.repositories.family_repository import FamilyRepository
from yuxi.storage.postgres.models_business import User
from yuxi.storage.postgres.models_family import EMERGENCY_EVENT_SOURCES, EmergencyEvent
from yuxi.utils.datetime_utils import SHANGHAI_TZ, UTC, utc_now_naive

repository = FamilyRepository()

# 同一老人 10 分钟内的重复触发只保留第一条事件，防 SOS 连点与关键词反复命中
EMERGENCY_COOLDOWN = timedelta(minutes=10)

# 与前端 emergencyDetector 的 7 类急症保持一致；未知分类原样展示
EMERGENCY_CATEGORY_LABELS = {
    "cardiac": "心血管急症",
    "stroke": "脑血管急症",
    "fall": "跌倒/外伤",
    "breathing": "呼吸困难",
    "consciousness": "意识障碍",
    "bleeding": "严重出血",
    "psychological": "心理危机",
}


def category_label(category: str) -> str:
    return EMERGENCY_CATEGORY_LABELS.get(category, category)


async def report_emergency(
    db: AsyncSession, current_user: User, *, source: str, category: str | None = None, detail: str | None = None
) -> dict:
    """老人触发一次紧急求助；冷却窗口内的重复触发去重，不重发留言。"""
    if source not in EMERGENCY_EVENT_SOURCES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="source 只能是 sos 或 keyword")

    recent = await repository.get_recent_open_event(db, current_user.uid, EMERGENCY_COOLDOWN)
    if recent is not None:
        return {"event": recent.to_dict(), "event_id": recent.id, "notified": [], "deduped": True}

    event = await repository.create_event(
        db,
        {
            "elder_uid": current_user.uid,
            "source": source,
            "category": (category or "general").strip() or "general",
            "detail": (detail or "").strip() or None,
            "status": "open",
        },
    )
    notified = await _notify_children(db, event.elder_uid, _help_message(event))
    return {"event": event.to_dict(), "event_id": event.id, "notified": notified, "deduped": False}


async def resolve_emergency(db: AsyncSession, current_user: User, event_id: int) -> dict:
    """老人标记「我没事了」：事件置 resolved，并向同一批子女补发安抚留言。"""
    event = await repository.get_event(db, event_id)
    if event is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="紧急事件不存在")
    if event.elder_uid != current_user.uid:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="只有老人本人可以撤销")
    if event.status == "resolved":
        return {"event": event.to_dict(), "notified": [], "already_resolved": True}

    event.status = "resolved"
    event.resolved_at = utc_now_naive()
    notified = await _notify_children(db, event.elder_uid, _resolved_message(event))
    await db.flush()
    return {"event": event.to_dict(), "notified": notified}


async def list_events_of_bound_elders(db: AsyncSession, current_user: User, *, limit: int = 50) -> dict:
    """子女端：我绑定的老人们的紧急事件，未处理在前、按时间倒序。"""
    elder_uids = await repository.list_active_elder_uids_of_child(db, current_user.uid)
    if not elder_uids:
        return {"events": []}

    events = await repository.list_events_of_elders(db, elder_uids, limit=limit)
    result = await db.execute(select(User.uid, User.username).where(User.uid.in_(elder_uids)))
    names = dict(result.all())
    return {"events": [{**event.to_dict(), "elder_name": names.get(event.elder_uid)} for event in events]}


async def _notify_children(db: AsyncSession, elder_uid: str, content: str) -> list[str]:
    """向该老人 active 绑定的每位子女发一条留言，返回通知到的 uid 列表。"""
    links = await repository.list_children_of_elder(db, elder_uid)
    for link in links:
        await repository.create_message(db, {"from_uid": elder_uid, "to_uid": link.child_uid, "content": content})
    return [link.child_uid for link in links]


def _shanghai_text(naive_utc) -> str:
    """DB 里存的 naive UTC（见 ``utc_now_naive``），转成上海时间给人看。"""
    return naive_utc.replace(tzinfo=UTC).astimezone(SHANGHAI_TZ).strftime("%m月%d日 %H:%M")


def _help_message(event: EmergencyEvent) -> str:
    time_text = _shanghai_text(event.created_at)
    if event.source == "sos":
        return f"【紧急求助】老人按下了 SOS 求助按钮，请尽快电话联系确认情况。时间：{time_text}"
    label = category_label(event.category)
    quote = f"（原话：{event.detail}）" if event.detail else ""
    return (
        f"【紧急求助】老人聊天中提到身体不适，疑似「{label}」{quote}，"
        f"请尽快电话联系确认情况。时间：{time_text}"
    )


def _resolved_message(event: EmergencyEvent) -> str:
    return (
        f"【紧急求助】老人已标记「我没事了」，刚才的紧急求助已解除，"
        f"可能是误触，请放心。时间：{_shanghai_text(event.resolved_at)}"
    )
