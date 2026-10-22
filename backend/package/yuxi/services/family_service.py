"""家庭绑定与关怀留言的用例层。

权限口径集中在这里，路由层只做参数解析与响应装配：
- 绑定：子女发起，必须由老人本人确认后才生效；
- 留言：双方存在 ``active`` 绑定时才能互通，未绑定的两人之间不能留言。
"""

from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from yuxi.repositories.family_repository import FamilyRepository
from yuxi.storage.postgres.models_business import User
from yuxi.storage.postgres.models_family import FamilyLink
from yuxi.utils.datetime_utils import utc_now_naive

repository = FamilyRepository()

MAX_MESSAGE_LENGTH = 500


async def _load_user(db: AsyncSession, uid: str) -> User:
    result = await db.execute(select(User).where(User.uid == uid, User.is_deleted == 0))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"用户 {uid} 不存在")
    return user


def link_to_dict(link: FamilyLink, *, elder_name: str | None = None, child_name: str | None = None) -> dict:
    payload = link.to_dict()
    payload["elder_name"] = elder_name
    payload["child_name"] = child_name
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
    names = await _load_user_names(db, uids)
    # 每位家人各有多少句没读：老人端据此默认打开有未读的那一位
    unread_by_sender = await repository.count_unread_by_sender(db, current_user.uid)

    return {
        "as_elder": [
            {
                **link_to_dict(link, child_name=names.get(link.child_uid)),
                "unread_count": unread_by_sender.get(link.child_uid, 0),
            }
            for link in elder_side
        ],
        "as_child": [
            link_to_dict(link, elder_name=names.get(link.elder_uid)) for link in child_side
        ],
    }


async def list_elders(db: AsyncSession, current_user: User) -> list[dict]:
    """子女端：我已经绑定的老人（只含 active）。"""
    links = await repository.list_elders_of_child(db, current_user.uid)
    names = await _load_user_names(db, {link.elder_uid for link in links})
    return [link_to_dict(link, elder_name=names.get(link.elder_uid)) for link in links]


async def _load_user_names(db: AsyncSession, uids: set[str]) -> dict[str, str]:
    if not uids:
        return {}
    result = await db.execute(select(User.uid, User.username).where(User.uid.in_(uids)))
    return {uid: username for uid, username in result.all()}


async def _is_linked(db: AsyncSession, uid_a: str, uid_b: str) -> bool:
    """两个方向任一存在 active 绑定，即视为已建立家庭关联。"""
    return await repository.is_active_child(db, uid_b, uid_a) or await repository.is_active_child(db, uid_a, uid_b)


async def send_message(db: AsyncSession, current_user: User, *, to_uid: str, content: str) -> dict:
    """发送关怀留言。双方必须存在 active 绑定。"""
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
        db, {"from_uid": current_user.uid, "to_uid": to_uid, "content": content}
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


async def unread_summary(db: AsyncSession, current_user: User) -> dict:
    """未读留言总数，用于老人端与子女端的角标。"""
    return {"total": await repository.count_unread(db, current_user.uid)}
