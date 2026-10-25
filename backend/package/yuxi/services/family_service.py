"""家庭绑定与关怀留言的用例层。

权限口径集中在这里，路由层只做参数解析与响应装配：
- 绑定：子女发起，必须由老人本人确认后才生效；
- 留言：双方存在 ``active`` 绑定时才能互通，未绑定的两人之间不能留言。
"""

from __future__ import annotations

from datetime import datetime

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from yuxi.repositories.family_repository import FamilyRepository
from yuxi.services import reminder_service
from yuxi.storage.postgres.models_business import User
from yuxi.storage.postgres.models_family import FamilyLink, FamilyMessage
from yuxi.utils.datetime_utils import ensure_shanghai, utc_isoformat, utc_now_naive

repository = FamilyRepository()

MAX_MESSAGE_LENGTH = 500

# 转达请求的处理动作：approve=同意执行；dismiss=先不动/保留，仅标记已处理
RESOLVE_REQUEST_ACTIONS = ("approve", "dismiss")


async def _load_user(db: AsyncSession, uid: str) -> User:
    result = await db.execute(select(User).where(User.uid == uid, User.is_deleted == 0))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"用户 {uid} 不存在")
    return user


def link_to_dict(
    link: FamilyLink,
    *,
    elder_name: str | None = None,
    child_name: str | None = None,
    elder_phone: str | None = None,
    child_phone: str | None = None,
) -> dict:
    payload = link.to_dict()
    payload["elder_name"] = elder_name
    payload["child_name"] = child_name
    payload["elder_phone"] = elder_phone
    payload["child_phone"] = child_phone
    return payload


async def create_link(db: AsyncSession, current_user: User, *, elder_uid: str, relation: str) -> dict:
    """子女发起绑定，等待老人确认。"""
    elder_uid = elder_uid.strip()
    if elder_uid == current_user.uid:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="不能绑定自己")

    await _load_user(db, elder_uid)

    existing = await repository.get_link_by_pair(db, elder_uid, current_user.uid)
    if existing is not None:
        if existing.status == "active":
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="已经绑定该老人，无需重复申请")
        if existing.status == "pending":
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="已提交过申请，请等待老人确认")
        # 曾被解除，重新发起
        existing.status = "pending"
        existing.relation = relation
        existing.invited_by = current_user.uid
        await db.flush()
        return existing.to_dict()

    link = await repository.create_link(
        db,
        {
            "elder_uid": elder_uid,
            "child_uid": current_user.uid,
            "relation": relation,
            "status": "pending",
            "invited_by": current_user.uid,
        },
    )
    return link.to_dict()


async def approve_link(db: AsyncSession, current_user: User, link_id: int) -> dict:
    """老人确认绑定。只有被绑定的老人本人可以确认。"""
    link = await repository.get_link(db, link_id)
    if link is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="绑定申请不存在")
    if link.elder_uid != current_user.uid:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="只有被绑定的老人本人可以确认")
    if link.status == "active":
        return link.to_dict()
    if link.status != "pending":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="该申请已失效，请让对方重新发起")

    link.status = "active"
    await db.flush()
    return link.to_dict()


async def revoke_link(db: AsyncSession, current_user: User, link_id: int) -> dict:
    """解除绑定，老人或子女任一方都可以解除。"""
    link = await repository.get_link(db, link_id)
    if link is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="绑定关系不存在")
    if current_user.uid not in {link.elder_uid, link.child_uid}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权解除该绑定")

    link.status = "revoked"
    await db.flush()
    return link.to_dict()


async def list_links(db: AsyncSession, current_user: User) -> dict:
    """返回当前用户作为老人和作为子女的两个视角。"""
    links = await repository.list_links_of_user(db, current_user.uid)

    elder_side = [link for link in links if link.elder_uid == current_user.uid]
    child_side = [link for link in links if link.child_uid == current_user.uid]

    uids = {link.elder_uid for link in child_side} | {link.child_uid for link in elder_side}
    profiles = await _load_user_profiles(db, uids)
    # 每位家人各有多少句没读：老人端据此默认打开有未读的那一位
    unread_by_sender = await repository.count_unread_by_sender(db, current_user.uid)

    return {
        "as_elder": [
            {
                **link_to_dict(
                    link,
                    child_name=profiles[link.child_uid]["name"],
                    child_phone=profiles[link.child_uid]["phone"],
                ),
                "unread_count": unread_by_sender.get(link.child_uid, 0),
            }
            for link in elder_side
        ],
        "as_child": [
            link_to_dict(
                link,
                elder_name=profiles[link.elder_uid]["name"],
                elder_phone=profiles[link.elder_uid]["phone"],
            )
            for link in child_side
        ],
    }


async def list_elders(db: AsyncSession, current_user: User) -> list[dict]:
    """子女端：我已经绑定的老人（只含 active）。"""
    links = await repository.list_elders_of_child(db, current_user.uid)
    profiles = await _load_user_profiles(db, {link.elder_uid for link in links})
    return [
        link_to_dict(
            link,
            elder_name=profiles[link.elder_uid]["name"],
            elder_phone=profiles[link.elder_uid]["phone"],
        )
        for link in links
    ]


async def _load_user_profiles(db: AsyncSession, uids: set[str]) -> dict[str, dict[str, str | None]]:
    """uid → {name, phone}，用于给绑定列表补充对方的称呼与联系电话（SOS 弹窗拨打用）。"""
    if not uids:
        return {}
    result = await db.execute(select(User.uid, User.username, User.phone_number).where(User.uid.in_(uids)))
    return {uid: {"name": username, "phone": phone_number} for uid, username, phone_number in result.all()}


async def _is_linked(db: AsyncSession, uid_a: str, uid_b: str) -> bool:
    """两个方向任一存在 active 绑定，即视为已建立家庭关联。"""
    return await repository.is_active_child(db, uid_b, uid_a) or await repository.is_active_child(db, uid_a, uid_b)


async def send_message(
    db: AsyncSession, current_user: User, *, to_uid: str, content: str, meta: dict | None = None
) -> dict:
    """发送关怀留言。双方必须存在 active 绑定。

    ``meta`` 仅供服务端写入结构化元数据（如提醒转达请求），不对公开接口开放，
    客户端无法伪造。
    """
    to_uid = to_uid.strip()
    content = content.strip()
    if to_uid == current_user.uid:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="不能给自己留言")
    if not content:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="留言内容不能为空")
    if len(content) > MAX_MESSAGE_LENGTH:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"留言内容不能超过 {MAX_MESSAGE_LENGTH} 字",
        )

    await _load_user(db, to_uid)

    if not await _is_linked(db, current_user.uid, to_uid):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="尚未与该用户建立家庭绑定")

    message = await repository.create_message(
        db, {"from_uid": current_user.uid, "to_uid": to_uid, "content": content, "meta": meta}
    )
    return message.to_dict()


async def list_messages(db: AsyncSession, current_user: User, *, with_uid: str, limit: int = 50) -> dict:
    """读取与某位家庭成员的留言，并把对方发来的未读标记为已读。"""
    with_uid = with_uid.strip()
    if not await _is_linked(db, current_user.uid, with_uid):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="尚未与该用户建立家庭绑定")

    messages = await repository.list_messages_between(db, current_user.uid, with_uid, limit=limit)
    read_count = await repository.mark_thread_read(db, current_user.uid, with_uid, utc_now_naive())
    await db.flush()

    return {
        "messages": [message.to_dict() for message in messages],
        "marked_read": read_count,
    }


def _mark_request_resolved(message: FamilyMessage) -> None:
    """meta 追加 resolved_at。整体重新赋值，确保 JSON 列的变更被 ORM 检测到。"""
    meta = dict(message.meta or {})
    meta["resolved_at"] = utc_isoformat()
    message.meta = meta


async def resolve_request(db: AsyncSession, current_user: User, message_id: int, *, action: str) -> dict:
    """处理老人发来的提醒转达请求（子女端留言卡片一键执行）。

    ``action="approve"`` 按老人诉求执行（改时间或停用）并以子女名义给老人补发回执；
    ``"dismiss"`` 仅标记已处理，不动数据、不发回执。执行仍走
    ``reminder_service.assert_can_manage``——只有提醒设置人（也是转达收件人）本人能确认。
    提醒已被删除/停用、目标时间已过时返回明确错误，meta 不置位，子女可改用手动方式。
    """
    if action not in RESOLVE_REQUEST_ACTIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="action 只能是 approve 或 dismiss"
        )

    message = await db.get(FamilyMessage, message_id)
    if message is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="留言不存在")
    if message.to_uid != current_user.uid:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="只有收件人可以处理转达请求")

    meta = message.meta or {}
    if meta.get("kind") not in ("reminder_change", "reminder_stop"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="这条留言不是提醒转达请求")
    if meta.get("resolved_at"):
        # 幂等：已处理过的请求直接返回现状，不再执行、不再补发留言
        return message.to_dict()

    if action == "dismiss":
        _mark_request_resolved(message)
        await db.flush()
        return message.to_dict()

    reminder = await reminder_service.repository.get(db, meta.get("reminder_id"))
    if reminder is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="这条提醒已经不在了，请到提醒管理里确认"
        )
    reminder_service.assert_can_manage(current_user, reminder)
    if meta["kind"] == "reminder_change" and not reminder.enabled:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="这条提醒已停用，请先到提醒管理里启用"
        )

    title = meta.get("title") or "提醒"
    if meta["kind"] == "reminder_change":
        requested_at = datetime.fromisoformat(meta["requested_at"])
        await reminder_service.update_reminder(db, current_user, reminder.id, remind_at=requested_at)
        clock = ensure_shanghai(requested_at).strftime("%m-%d %H:%M")
        receipt = f"{current_user.username}已把「{title}」改到 {clock}。"
    else:
        await reminder_service.update_reminder(db, current_user, reminder.id, enabled=False)
        receipt = f"{current_user.username}已停用「{title}」提醒。"

    # 回执以子女名义发给老人（家人在说话，不是系统广播）；发送失败则整个事务回滚
    await send_message(db, current_user, to_uid=message.from_uid, content=receipt)
    _mark_request_resolved(message)
    await db.flush()
    return message.to_dict()


async def unread_summary(db: AsyncSession, current_user: User) -> dict:
    """未读留言总数 + 名下绑定老人的未处理紧急数，用于老人端与子女端的角标。"""
    elder_uids = await repository.list_active_elder_uids_of_child(db, current_user.uid)
    open_emergency = await repository.count_open_events_of_elders(db, elder_uids)
    return {
        "total": await repository.count_unread(db, current_user.uid),
        "open_emergency_count": open_emergency,
    }
