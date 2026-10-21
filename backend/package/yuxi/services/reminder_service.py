"""提醒的用例层。

权限口径集中在这里：
- 可见：被提醒人是自己 / 自己创建的 / 被提醒人是已绑定的老人；
- 可管理（改、删）：只限创建者本人 —— 子女能管理自己给老人建的提醒，但改不了老人自己建的；
- 确认与标记完成：只限被提醒的老人本人，子女不能替老人点。
"""

from __future__ import annotations

import os
from datetime import UTC, date, datetime, time, timedelta

from fastapi import HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from yuxi.repositories.family_repository import FamilyRepository
from yuxi.repositories.reminder_repository import ReminderRepository
from yuxi.storage.postgres.models_business import User
from yuxi.storage.postgres.models_family import Reminder, ReminderOccurrence
from yuxi.utils.datetime_utils import SHANGHAI_TZ, ensure_utc, shanghai_now, utc_now_naive

family_repository = FamilyRepository()
repository = ReminderRepository()

REPEAT_TYPES = {"none", "daily", "weekly", "custom"}
DEFAULT_REPEAT_RULE = {"type": "none"}

ALLOWED_CATEGORIES = {"用药", "复诊", "饮食", "活动", "other"}

# 到点后多久仍未处理就标记为 missed；养老场景留足补做时间，默认 2 小时
MISSED_GRACE_MINUTES = int(os.getenv("REMINDER_MISSED_GRACE_MINUTES", "120"))


def to_naive_utc(value: datetime) -> datetime:
    """把入参时间统一成数据库使用的 naive UTC。

    前端应传带时区的 ISO 8601；若传的是 naive 值，按 Asia/Shanghai 理解。
    """
    return ensure_utc(value).astimezone(UTC).replace(tzinfo=None)


def to_shanghai(value: datetime) -> datetime:
    """把数据库里的 naive UTC 转成 Asia/Shanghai 的 aware 时间。"""
    return value.replace(tzinfo=UTC).astimezone(SHANGHAI_TZ)


def normalize_repeat_rule(rule: dict | None, *, anchor: datetime) -> dict:
    """校验并归一化重复规则。

    Args:
        rule: 前端传入的规则，形如 ``{"type": "weekly", "weekdays": [1, 3]}``。
        anchor: 提醒首次时间（naive UTC），用于校验 ``until`` 不早于起始日。

    Returns:
        只包含已知字段的干净字典，可直接落库。
    """
    if not rule:
        return dict(DEFAULT_REPEAT_RULE)

    kind = str(rule.get("type") or "none").strip()
    if kind not in REPEAT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="重复方式不合法，可选值：none / daily / weekly / custom",
        )

    normalized: dict = {"type": kind}

    if kind == "weekly":
        try:
            weekdays = sorted({int(value) for value in (rule.get("weekdays") or [])})
        except (TypeError, ValueError):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="weekdays 必须是 1-7 的整数") from None
        if not weekdays or any(value < 1 or value > 7 for value in weekdays):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="每周重复至少选择一个星期，取值 1-7"
            )
        normalized["weekdays"] = weekdays

    if kind == "custom":
        try:
            interval = int(rule.get("interval") or 0)
        except (TypeError, ValueError):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="间隔天数必须是整数") from None
        if not 1 <= interval <= 365:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="间隔天数需在 1-365 之间")
        normalized["interval"] = interval

    until = rule.get("until")
    if until:
        try:
            until_date = date.fromisoformat(str(until))
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="结束日期需要 YYYY-MM-DD 格式"
            ) from None
        if until_date < to_shanghai(anchor).date():
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="结束日期不能早于提醒开始日期")
        normalized["until"] = until_date.isoformat()

    return normalized


def occurrence_time_on(reminder: Reminder, local_day: date) -> datetime | None:
    """判断某条提醒在指定本地日期是否触发。

    Args:
        reminder: 提醒定义。
        local_day: Asia/Shanghai 时区下的日期。

    Returns:
        会触发时返回该次触发的 naive UTC 时刻，不触发返回 None。
    """
    anchor = to_shanghai(reminder.remind_at)
    if local_day < anchor.date():
        return None

    rule = reminder.repeat_rule or DEFAULT_REPEAT_RULE
    kind = rule.get("type") or "none"

    if kind == "none":
        if local_day != anchor.date():
            return None
    elif kind == "daily":
        pass
    elif kind == "weekly":
        if local_day.isoweekday() not in (rule.get("weekdays") or []):
            return None
    elif kind == "custom":
        interval = max(1, int(rule.get("interval") or 1))
        if (local_day - anchor.date()).days % interval != 0:
            return None
    else:
        # 库中出现未知类型时不展开，宁可漏发也不要乱发
        return None

    until = rule.get("until")
    if until and local_day > date.fromisoformat(str(until)):
        return None

    local_moment = datetime.combine(
        local_day,
        time(anchor.hour, anchor.minute, anchor.second),
        tzinfo=SHANGHAI_TZ,
    )
    return local_moment.astimezone(UTC).replace(tzinfo=None)


def day_range_utc(local_day: date | None = None) -> tuple[datetime, datetime]:
    """返回指定本地日期（缺省为今天，Asia/Shanghai）对应的 UTC 左闭右开区间。"""
    day = local_day or shanghai_now().date()
    start_local = datetime.combine(day, time.min, tzinfo=SHANGHAI_TZ)
    end_local = start_local + timedelta(days=1)
    return (
        start_local.astimezone(UTC).replace(tzinfo=None),
        end_local.astimezone(UTC).replace(tzinfo=None),
    )


def today_range_utc() -> tuple[datetime, datetime]:
    """返回"今天"（Asia/Shanghai）对应的 UTC 左闭右开区间。"""
    return day_range_utc()


async def _load_user(db: AsyncSession, uid: str) -> User:
    result = await db.execute(select(User).where(User.uid == uid, User.is_deleted == 0))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"用户 {uid} 不存在")
    return user


async def visible_elder_uids(db: AsyncSession, current_user: User) -> list[str]:
    """当前用户作为子女可以查看的老人 uid 列表。"""
    return await family_repository.list_active_elder_uids_of_child(db, current_user.uid)


async def assert_can_view(db: AsyncSession, current_user: User, reminder: Reminder) -> None:
    """校验提醒可见性。"""
    if reminder.target_uid == current_user.uid or reminder.owner_uid == current_user.uid:
        return
    if await family_repository.is_active_child(db, reminder.target_uid, current_user.uid):
        return
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权查看该提醒")


def assert_can_manage(current_user: User, reminder: Reminder) -> None:
    """只有创建者本人可以修改或删除提醒。"""
    if reminder.owner_uid != current_user.uid:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="只能管理自己创建的提醒")


async def assert_can_target(db: AsyncSession, current_user: User, target_uid: str) -> None:
    """校验能否给某个人建提醒：只能给自己或已绑定的老人。"""
    if target_uid == current_user.uid:
        return
    if await family_repository.is_active_child(db, target_uid, current_user.uid):
        return
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="只能给自己或已绑定的老人创建提醒")


def _assert_start_not_expired(remind_at: datetime, rule: dict) -> None:
    """一次性提醒不能定在过去的时刻。

    ``type="none"`` 的提醒只展开提醒日当天，若首个时刻已超出宽限期，它会永远
    不触发，只在列表里留一条僵尸数据。重复提醒不受此限：今天错过就从明天开始。
    """
    if rule.get("type", "none") != "none":
        return
    if remind_at + timedelta(minutes=MISSED_GRACE_MINUTES) > utc_now_naive():
        return
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="提醒时间已过，请选择将来的时间")


def _normalize_category(category: str | None) -> str:
    value = (category or "other").strip()
    if value not in ALLOWED_CATEGORIES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"提醒分类不合法，可选值：{'、'.join(sorted(ALLOWED_CATEGORIES))}",
        )
    return value


async def create_reminder(
    db: AsyncSession,
    current_user: User,
    *,
    target_uid: str | None,
    title: str,
    content: str | None,
    category: str | None,
    remind_at: datetime,
    repeat_rule: dict | None = None,
) -> dict:
    """创建提醒。``target_uid`` 缺省表示给自己建。"""
    target = (target_uid or current_user.uid).strip()
    await assert_can_target(db, current_user, target)
    await _load_user(db, target)

    first_remind_at = to_naive_utc(remind_at)
    rule = normalize_repeat_rule(repeat_rule, anchor=first_remind_at)
    _assert_start_not_expired(first_remind_at, rule)

    reminder = await repository.create(
        db,
        {
            "owner_uid": current_user.uid,
            "target_uid": target,
            "title": title.strip(),
            "content": (content or "").strip() or None,
            "category": _normalize_category(category),
            "remind_at": first_remind_at,
            "repeat_rule": rule,
            "enabled": True,
        },
    )
    return reminder.to_dict()


async def _drop_stale_occurrences(db: AsyncSession, reminder: Reminder) -> None:
    """提醒时间变更后，清掉当天因变更而失效的未处理记录。

    否则旧时刻的记录会留在库里慢慢变成 missed，形成"幽灵待办"和错误的统计。
    """
    day = to_shanghai(reminder.remind_at).date()
    keep = occurrence_time_on(reminder, day)
    if keep is None:
        return
    start, end = day_range_utc(day)
    await repository.delete_unhandled_occurrences(
        db, reminder.id, start=start, end=end, keep_scheduled_at=keep
    )


async def update_reminder(
    db: AsyncSession,
    current_user: User,
    reminder_id: int,
    *,
    title: str | None = None,
    content: str | None = None,
    category: str | None = None,
    remind_at: datetime | None = None,
    enabled: bool | None = None,
    repeat_rule: dict | None = None,
) -> dict:
    """更新提醒。只允许创建者本人操作。"""
    reminder = await repository.get(db, reminder_id)
    if reminder is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="提醒不存在")
    assert_can_manage(current_user, reminder)

    if title is not None:
        reminder.title = title.strip()
    if content is not None:
        reminder.content = content.strip() or None
    if category is not None:
        reminder.category = _normalize_category(category)
    # 时间或重复规则变化都会改变"今天该在几点触发"，需要先算出让时间再校验
    schedule_changed = remind_at is not None or repeat_rule is not None
    if schedule_changed:
        next_remind_at = to_naive_utc(remind_at) if remind_at is not None else reminder.remind_at
        next_rule = (
            normalize_repeat_rule(repeat_rule, anchor=next_remind_at)
            if repeat_rule is not None
            else (reminder.repeat_rule or dict(DEFAULT_REPEAT_RULE))
        )
        _assert_start_not_expired(next_remind_at, next_rule)
        reminder.remind_at = next_remind_at
        reminder.repeat_rule = next_rule
    if enabled is not None:
        reminder.enabled = enabled

    if schedule_changed:
        await db.flush()
        await _drop_stale_occurrences(db, reminder)

    await db.flush()
    return reminder.to_dict()


async def delete_reminder(db: AsyncSession, current_user: User, reminder_id: int) -> dict:
    """软删除提醒，保留历史执行记录。"""
    reminder = await repository.get(db, reminder_id)
    if reminder is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="提醒不存在")
    assert_can_manage(current_user, reminder)

    reminder.deleted_at = utc_now_naive()
    reminder.enabled = False
    await db.flush()
    return {"id": reminder_id, "deleted": True}


async def list_reminders(db: AsyncSession, current_user: User, *, target_uid: str | None = None) -> dict:
    """列出可见提醒。"""
    elders = await visible_elder_uids(db, current_user)
    reminders = await repository.list_visible(db, uid=current_user.uid, elder_uids=elders, target_uid=target_uid)

    names = await _load_names(db, {item.target_uid for item in reminders} | {item.owner_uid for item in reminders})
    items = []
    for item in reminders:
        payload = item.to_dict()
        payload["target_name"] = names.get(item.target_uid)
        payload["owner_name"] = names.get(item.owner_uid)
        payload["is_mine"] = item.owner_uid == current_user.uid
        items.append(payload)

    return {"reminders": items, "total": len(items)}


async def _ensure_occurrence_for_day(
    db: AsyncSession, reminder: Reminder, local_day: date, *, now: datetime | None = None
) -> tuple[ReminderOccurrence, bool] | None:
    """确保某条提醒在指定日期有执行记录。

    Returns:
        (执行记录, 是否新建)；该日不应触发、或该时刻已错过宽限期时返回 None。
    """
    scheduled_at = occurrence_time_on(reminder, local_day)
    if scheduled_at is None:
        return None

    existing = await repository.get_occurrence_by_slot(db, reminder.id, scheduled_at)
    if existing is not None:
        return existing, False

    # 已超出宽限期的时刻不再补建记录：补出来的记录必然立刻被判 missed，
    # 老人会凭空看到一条"已错过"，依从性统计也跟着失真。
    if scheduled_at + timedelta(minutes=MISSED_GRACE_MINUTES) <= (now or utc_now_naive()):
        return None

    created = await repository.create_occurrence(
        db,
        {
            "reminder_id": reminder.id,
            "target_uid": reminder.target_uid,
            "scheduled_at": scheduled_at,
            "status": "pending",
        },
    )
    return created, True


async def sync_day_occurrences(db: AsyncSession, local_day: date | None = None) -> dict:
    """为所有老人的当日提醒补齐执行记录，供调度器周期调用。

    依赖 ``(reminder_id, scheduled_at)`` 唯一约束与"先查后插"保证幂等，
    重复执行不会产生重复记录。
    """
    day = local_day or shanghai_now().date()
    _, end = day_range_utc(day)
    reminders = await repository.list_all_active_started_before(db, end)

    created = 0
    for reminder in reminders:
        result = await _ensure_occurrence_for_day(db, reminder, day)
        if result is not None and result[1]:
            created += 1

    return {"day": day.isoformat(), "scanned": len(reminders), "created": created}


async def advance_due_status(
    db: AsyncSession, *, now: datetime | None = None, grace_minutes: int | None = None
) -> dict:
    """推进到点与超时的执行记录状态。

    - 已到点但未处理：``pending`` → ``delivered``（表示"已提醒，等待老人确认"）
    - 超过宽限期仍未处理：``pending``/``delivered`` → ``missed``

    先处理超时再处理到点，避免同一批记录被更新两次。
    """
    moment = now or utc_now_naive()
    grace = MISSED_GRACE_MINUTES if grace_minutes is None else grace_minutes
    deadline = moment - timedelta(minutes=grace)

    missed_result = await db.execute(
        update(ReminderOccurrence)
        .where(
            ReminderOccurrence.status.in_(("pending", "delivered")),
            ReminderOccurrence.scheduled_at <= deadline,
        )
        .values(status="missed")
        .execution_options(synchronize_session=False)
    )
    delivered_result = await db.execute(
        update(ReminderOccurrence)
        .where(
            ReminderOccurrence.status == "pending",
            ReminderOccurrence.scheduled_at <= moment,
        )
        .values(status="delivered")
        .execution_options(synchronize_session=False)
    )

    return {
        "missed": missed_result.rowcount or 0,
        "delivered": delivered_result.rowcount or 0,
    }


async def list_today(db: AsyncSession, current_user: User, *, target_uid: str | None = None) -> dict:
    """今日提醒：按重复规则展开后返回，并在缺失时补齐执行记录。

    调度器（每分钟扫描）会主动生成记录；这里的按需补齐保证"刚建的提醒马上
    就能在页面上看到"，两者共用同一套幂等逻辑。
    """
    target = (target_uid or current_user.uid).strip()
    if target != current_user.uid:
        await assert_can_view_target(db, current_user, target)

    local_day = shanghai_now().date()
    _, end = day_range_utc(local_day)
    reminders = await repository.list_active_started_before(db, target, end)

    occurrences = []
    for reminder in reminders:
        result = await _ensure_occurrence_for_day(db, reminder, local_day)
        if result is not None:
            occurrences.append((reminder, result[0]))

    occurrences.sort(key=lambda pair: pair[1].scheduled_at)

    return {
        "date": local_day.isoformat(),
        "target_uid": target,
        "items": [
            {
                **occurrence.to_dict(),
                "title": reminder.title,
                "category": reminder.category,
                "content": reminder.content,
                "owner_uid": reminder.owner_uid,
                "repeat_rule": reminder.repeat_rule or DEFAULT_REPEAT_RULE,
            }
            for reminder, occurrence in occurrences
        ],
    }


def _empty_stats_bucket() -> dict:
    return {"total": 0, "completed": 0, "failed": 0, "pending": 0, "rate": None}


def _count_into(bucket: dict, occurrence_status: str) -> None:
    """把一个执行记录累加进统计桶。

    ``done`` 算完成；``skipped``（老人自述没做到）与 ``missed``（超时未处理）
    算未完成；其余（``pending``/``delivered``/``confirmed``）尚未定性，
    只计入 total，不进完成率分母 —— 否则"今天还有 3 条没到点"会把历史完成率拉低。
    """
    bucket["total"] += 1
    if occurrence_status == "done":
        bucket["completed"] += 1
    elif occurrence_status in {"skipped", "missed"}:
        bucket["failed"] += 1
    else:
        bucket["pending"] += 1

    settled = bucket["completed"] + bucket["failed"]
    bucket["rate"] = round(bucket["completed"] / settled, 3) if settled else None


async def _load_categories(db: AsyncSession, reminder_ids: set[int]) -> dict[int, str]:
    """一次查出这些提醒的分类，避免按条查询。"""
    if not reminder_ids:
        return {}
    result = await db.execute(select(Reminder.id, Reminder.category).where(Reminder.id.in_(reminder_ids)))
    return {reminder_id: category for reminder_id, category in result.all()}


async def adherence_stats(
    db: AsyncSession, current_user: User, *, target_uid: str | None = None, days: int = 7
) -> dict:
    """近 N 天的依从性统计，供子女端看"这几天做得怎么样"。

    Args:
        target_uid: 统计对象，缺省为自己。
        days: 统计天数，限制在 1-30 天。

    Returns:
        含 ``summary``（整体完成率）、``by_day``（逐日明细，缺的日期补 0 而不是断档）、
        ``by_category``（分类明细，按条数降序）三部分。
    """
    target = (target_uid or current_user.uid).strip()
    if target != current_user.uid:
        await assert_can_view_target(db, current_user, target)

    span = max(1, min(int(days), 30))
    today = shanghai_now().date()
    first_day = today - timedelta(days=span - 1)
    start, _ = day_range_utc(first_day)
    _, end = day_range_utc(today)

    occurrences = await repository.list_occurrences_between(db, target_uids=[target], start=start, end=end)
    categories = await _load_categories(db, {item.reminder_id for item in occurrences})

    # 先铺满整段日期，让前端拿到的永远是连续的 span 根柱子
    buckets = {first_day + timedelta(days=offset): _empty_stats_bucket() for offset in range(span)}
    category_buckets: dict[str, dict] = {}

    for item in occurrences:
        _count_into(buckets[to_shanghai(item.scheduled_at).date()], item.status)
        category = categories.get(item.reminder_id) or "other"
        _count_into(category_buckets.setdefault(category, _empty_stats_bucket()), item.status)

    summary = _empty_stats_bucket()
    for bucket in buckets.values():
        summary["total"] += bucket["total"]
        summary["completed"] += bucket["completed"]
        summary["failed"] += bucket["failed"]
        summary["pending"] += bucket["pending"]
    settled = summary["completed"] + summary["failed"]
    summary["rate"] = round(summary["completed"] / settled, 3) if settled else None

    return {
        "target_uid": target,
        "range": {"days": span, "start": first_day.isoformat(), "end": today.isoformat()},
        "summary": summary,
        "by_day": [{"date": day.isoformat(), **bucket} for day, bucket in buckets.items()],
        "by_category": [
            {"category": category, **bucket}
            for category, bucket in sorted(category_buckets.items(), key=lambda pair: -pair[1]["total"])
        ],
    }


async def assert_can_view_target(db: AsyncSession, current_user: User, target_uid: str) -> None:
    """校验能否查看某个老人的提醒。"""
    if target_uid == current_user.uid:
        return
    if await family_repository.is_active_child(db, target_uid, current_user.uid):
        return
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权查看该用户的提醒")


async def list_occurrences(db: AsyncSession, current_user: User, reminder_id: int) -> dict:
    """某条提醒的历史执行记录。"""
    reminder = await repository.get(db, reminder_id)
    if reminder is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="提醒不存在")
    await assert_can_view(db, current_user, reminder)

    occurrences = await repository.list_occurrences_of_reminder(db, reminder_id)
    return {
        "reminder": reminder.to_dict(),
        "occurrences": [item.to_dict() for item in occurrences],
    }


async def _load_occurrence_for_target(
    db: AsyncSession, current_user: User, occurrence_id: int
) -> tuple[Reminder, ReminderOccurrence]:
    occurrence = await repository.get_occurrence(db, occurrence_id)
    if occurrence is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="执行记录不存在")
    if occurrence.target_uid != current_user.uid:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="只有被提醒的老人本人可以操作")

    reminder = await repository.get(db, occurrence.reminder_id)
    if reminder is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="提醒已被删除")
    return reminder, occurrence


async def confirm_occurrence(db: AsyncSession, current_user: User, occurrence_id: int) -> dict:
    """老人确认收到提醒。

    允许从 ``pending``/``delivered``/``missed`` 转入 ``confirmed``：
    老人晚一点看到也应当能确认，否则超时记录就永远无法补救。
    """
    _, occurrence = await _load_occurrence_for_target(db, current_user, occurrence_id)

    if occurrence.status in {"pending", "delivered", "missed"}:
        occurrence.status = "confirmed"
        occurrence.confirmed_at = utc_now_naive()
        await db.flush()
    return occurrence.to_dict()


async def finish_occurrence(
    db: AsyncSession, current_user: User, occurrence_id: int, *, done: bool, note: str | None = None
) -> dict:
    """老人标记完成或未完成。

    ``done=True`` 记为 ``done``；``done=False`` 记为 ``skipped``（本人表示没做到），
    与调度器判定的超时 ``missed`` 区分开。
    """
    _, occurrence = await _load_occurrence_for_target(db, current_user, occurrence_id)

    occurrence.status = "done" if done else "skipped"
    occurrence.finished_at = utc_now_naive()
    if note is not None:
        occurrence.note = note.strip() or None
    if occurrence.confirmed_at is None:
        occurrence.confirmed_at = occurrence.finished_at
    await db.flush()
    return occurrence.to_dict()


async def _load_names(db: AsyncSession, uids: set[str]) -> dict[str, str]:
    if not uids:
        return {}
    result = await db.execute(select(User.uid, User.username).where(User.uid.in_(uids)))
    return {uid: username for uid, username in result.all()}
