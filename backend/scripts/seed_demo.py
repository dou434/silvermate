"""创建一套自洽的演示数据：绑定好的演示账号 + 一周提醒与执行记录 + 留言 + 已解除紧急事件。

跑完 `seed_initial_users`（部门账号）与 `seed_knowledge_base`（知识库）后执行本脚本，
新环境即得完整可演示的养老故事，全程不改任何产品代码：

- 老人「王秀兰」（elder）+ 子女「王小明」（young），绑定 active；
- 5 条提醒：吃降压药 / 量血压 / 每周二复诊 / 喝水（子女建）+ 晨间遛弯（老人自建，
  展示语音自建能力）；
- 过去 6 天执行记录按固定剧本铺 done / missed（约八成完成），依从率呈现真实感；
  当天未到点/未过宽限期的记录交给现有调度器幂等补齐，避免与 advisory lock 竞争；
  当天**已过宽限期**的槽位调度器永不补建（见 ``_ensure_occurrence_for_day`` 的
  宽限期跳过），由 seed 直接写入：晨间遛弯记 done（今早遛完了）、吃降压药记
  missed（今早忘了，子女端可见"漏服"、现场演示可让老人点「做完了」补记）；
- 留言 4 条（1 条未读驱动角标）+ 1 条已解除（resolved）的 SOS 紧急事件及配套留言。

幂等：演示数据已就绪时直接成功退出；`--reset` 删除 demo 两账号名下全部数据后重建
（删除严格限定 demo 两账号 uid，不碰其他数据）。

在 api 容器内执行：docker compose exec api uv run python scripts/seed_demo.py
"""

from __future__ import annotations

import asyncio
import os
import sys
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import TypedDict

APP_ROOT = Path(__file__).resolve().parents[1]
for import_path in (APP_ROOT, APP_ROOT / "package"):
    import_path_str = str(import_path)
    if import_path_str not in sys.path:
        sys.path.insert(0, import_path_str)

from yuxi.services.reminder_service import MISSED_GRACE_MINUTES, to_naive_utc  # noqa: E402
from yuxi.utils.datetime_utils import SHANGHAI_TZ  # noqa: E402

ELDER_UID = "elder"
ELDER_NAME = "王秀兰"
CHILD_UID = "young"
CHILD_NAME = "王小明"
RELATION = "子女"
DEMO_PASSWORD_ENV = "YUXI_DEMO_PASSWORD"
HISTORY_DAYS = 6


class SeedError(Exception):
    pass


class DemoReminderSpec(TypedDict):
    key: str
    owner_uid: str
    target_uid: str
    title: str
    content: str | None
    category: str
    remind_at: datetime  # naive UTC
    repeat_rule: dict


class DemoOccurrenceSpec(TypedDict):
    reminder_key: str
    target_uid: str
    scheduled_at: datetime  # naive UTC
    status: str  # done / missed
    confirmed_at: datetime | None
    finished_at: datetime | None


class DemoMessageSpec(TypedDict):
    from_uid: str
    to_uid: str
    content: str
    created_at: datetime  # naive UTC
    read_at: datetime | None


class DemoEventSpec(TypedDict):
    elder_uid: str
    source: str
    category: str
    detail: str | None
    status: str
    created_at: datetime  # naive UTC
    resolved_at: datetime


class DemoSpec(TypedDict):
    elder_uid: str
    elder_name: str
    child_uid: str
    child_name: str
    relation: str
    reminders: list[DemoReminderSpec]
    occurrences: list[DemoOccurrenceSpec]
    messages: list[DemoMessageSpec]
    emergency_events: list[DemoEventSpec]


def _local(day, hour: int, minute: int = 0) -> datetime:
    """上海时区的某天某时刻（aware）。"""
    return datetime.combine(day, time(hour, minute), tzinfo=SHANGHAI_TZ)


def _cn_time_text(local: datetime) -> str:
    """留言里给人看的时间文案，与 emergency_service 的口径一致（10月24日 14:00）。"""
    return f"{local.month}月{local.day:02d}日 {local.strftime('%H:%M')}"


def _first_tuesday(start: date) -> date:
    day = start
    while day.weekday() != 1:
        day += timedelta(days=1)
    return day


def build_demo_spec(now: datetime) -> DemoSpec:
    """以上海时区当前时刻为锚构建整套演示数据。

    纯函数：所有时刻、状态在冻结时钟下完全确定；当天不写执行记录（留给调度器）。
    """
    today = now.date()
    window = [today - timedelta(days=offset) for offset in range(HISTORY_DAYS, 0, -1)]

    # 单次「喝水」定在当天下午 15:00； seeding 时已过则顺延到明天，避免造出永不触发的僵尸提醒
    water_day = today
    if _local(today, 15) <= now:
        water_day = today + timedelta(days=1)

    clinic_anchor = _first_tuesday(window[0])
    water_local = _local(water_day, 15)

    reminders: list[DemoReminderSpec] = [
        {
            "key": "bp_med",
            "owner_uid": CHILD_UID,
            "target_uid": ELDER_UID,
            "title": "吃降压药",
            "content": "餐后服用，一杯温水送服",
            "category": "用药",
            "remind_at": to_naive_utc(_local(window[0], 8)),
            "repeat_rule": {"type": "daily"},
        },
        {
            "key": "bp_measure",
            "owner_uid": CHILD_UID,
            "target_uid": ELDER_UID,
            "title": "量血压",
            "content": "睡前测量并记下来",
            "category": "other",
            "remind_at": to_naive_utc(_local(window[0], 21)),
            "repeat_rule": {"type": "daily"},
        },
        {
            "key": "clinic",
            "owner_uid": CHILD_UID,
            "target_uid": ELDER_UID,
            "title": "复诊",
            "content": "带上医保卡和病历本",
            "category": "复诊",
            "remind_at": to_naive_utc(_local(clinic_anchor, 9)),
            "repeat_rule": {"type": "weekly", "weekdays": [2]},
        },
        {
            "key": "water",
            "owner_uid": CHILD_UID,
            "target_uid": ELDER_UID,
            "title": "喝水",
            "content": None,
            "category": "饮食",
            "remind_at": to_naive_utc(water_local),
            "repeat_rule": {"type": "none"},
        },
        {
            "key": "walk",
            "owner_uid": ELDER_UID,  # 老人自建，展示语音自建能力
            "target_uid": ELDER_UID,
            "title": "晨间遛弯",
            "content": None,
            "category": "活动",
            "remind_at": to_naive_utc(_local(window[0], 7, 30)),
            "repeat_rule": {"type": "daily"},
        },
    ]

    # 过去 6 天执行记录的固定剧本：量血压在 D-4、D-2 漏服，其余全完成；
    # 复诊只落在窗口内的周二；当天记录留给调度器。
    missed_days = {today - timedelta(days=4), today - timedelta(days=2)}
    occurrences: list[DemoOccurrenceSpec] = []
    for day in window:
        plan = [
            ("bp_med", 8, 0, 2, 10),
            ("bp_measure", 21, 0, 2, 5),
            ("walk", 7, 30, 2, 40),
        ]
        if day.weekday() == 1:
            plan.append(("clinic", 9, 0, 2, 60))
        for key, hour, minute, confirmed_in, finished_in in plan:
            scheduled = _local(day, hour, minute)
            done = not (key == "bp_measure" and day in missed_days)
            occurrences.append(
                {
                    "reminder_key": key,
                    "target_uid": ELDER_UID,
                    "scheduled_at": to_naive_utc(scheduled),
                    "status": "done" if done else "missed",
                    "confirmed_at": to_naive_utc(scheduled + timedelta(minutes=confirmed_in)) if done else None,
                    "finished_at": to_naive_utc(scheduled + timedelta(minutes=finished_in)) if done else None,
                }
            )

    # 当天已过宽限期的槽位：调度器永不补建（补出来必然立刻 missed），由 seed 写入。
    # 晨间遛弯记 done（今早遛完了，延续 6 天全 done）、吃降压药记 missed（今早忘了）。
    # 未过宽限期的当天槽位不写，留给调度器幂等补齐，避免与 advisory lock 竞争。
    grace = timedelta(minutes=MISSED_GRACE_MINUTES)
    today_plan = [
        ("walk", 7, 30, "done"),
        ("bp_med", 8, 0, "missed"),
        ("bp_measure", 21, 0, "missed"),
    ]
    if clinic_anchor == today:
        today_plan.append(("clinic", 9, 0, "done"))
    if water_day == today:
        today_plan.append(("water", 15, 0, "missed"))
    for key, hour, minute, status in today_plan:
        slot = _local(today, hour, minute)
        if slot + grace > now:
            continue  # 未过宽限期：交给调度器，seed 不抢写
        if status == "done":
            confirmed_at = to_naive_utc(slot + timedelta(minutes=2))
            finished_at = to_naive_utc(slot + timedelta(minutes=40))
        else:
            confirmed_at = finished_at = None
        occurrences.append(
            {
                "reminder_key": key,
                "target_uid": ELDER_UID,
                "scheduled_at": to_naive_utc(slot),
                "status": status,
                "confirmed_at": confirmed_at,
                "finished_at": finished_at,
            }
        )

    # 留言与事件全部锚在过去（昨天），任何时刻执行 seed 都不会造出"未来留言"
    sos_local = _local(today - timedelta(days=1), 14)
    resolved_local = sos_local + timedelta(minutes=5)
    sos_time_text = _cn_time_text(sos_local)
    resolved_time_text = _cn_time_text(resolved_local)
    resolved_content = (
        f"【紧急求助】老人已标记「我没事了」，刚才的紧急求助已解除，可能是误触，请放心。时间：{resolved_time_text}"
    )
    messages: list[DemoMessageSpec] = [
        {  # 子女→老人 关怀留言，未读，驱动老人端角标
            "from_uid": CHILD_UID,
            "to_uid": ELDER_UID,
            "content": "妈，今天降温了记得添衣服，我周末回来看您。",
            "created_at": to_naive_utc(_local(today - timedelta(days=1), 19, 30)),
            "read_at": None,
        },
        {  # 老人→子女 已读回复
            "from_uid": ELDER_UID,
            "to_uid": CHILD_UID,
            "content": "好，知道了，你上班路上慢一点。",
            "created_at": to_naive_utc(_local(today - timedelta(days=1), 20, 0)),
            "read_at": to_naive_utc(_local(today - timedelta(days=1), 20, 30)),
        },
        {  # 紧急事件配套：求助留言（子女已读），文案对齐 emergency_service 的 SOS 格式
            "from_uid": ELDER_UID,
            "to_uid": CHILD_UID,
            "content": f"【紧急求助】老人按下了 SOS 求助按钮，请尽快电话联系确认情况。时间：{sos_time_text}",
            "created_at": to_naive_utc(sos_local),
            "read_at": to_naive_utc(resolved_local),
        },
        {  # 紧急事件配套：解除安抚留言（已读）
            "from_uid": ELDER_UID,
            "to_uid": CHILD_UID,
            "content": resolved_content,
            "created_at": to_naive_utc(resolved_local),
            "read_at": to_naive_utc(resolved_local + timedelta(minutes=5)),
        },
    ]

    emergency_events: list[DemoEventSpec] = [
        {
            "elder_uid": ELDER_UID,
            "source": "sos",
            "category": "general",
            "detail": None,
            "status": "resolved",
            "created_at": to_naive_utc(sos_local),
            "resolved_at": to_naive_utc(resolved_local),
        }
    ]

    return DemoSpec(
        elder_uid=ELDER_UID,
        elder_name=ELDER_NAME,
        child_uid=CHILD_UID,
        child_name=CHILD_NAME,
        relation=RELATION,
        reminders=reminders,
        occurrences=occurrences,
        messages=messages,
        emergency_events=emergency_events,
    )


def load_project_env() -> None:
    from dotenv import load_dotenv

    load_dotenv(APP_ROOT / ".env", override=False)
    load_dotenv(APP_ROOT.parent / ".env", override=False)
    load_dotenv(Path.cwd() / ".env", override=False)


def load_demo_password() -> str:
    """演示两账号共用密码来自环境变量，缺失即失败，报错只暴露变量名。"""
    password = (os.getenv(DEMO_PASSWORD_ENV) or "").strip()
    if not password:
        raise SeedError(f"缺少必需的环境变量：{DEMO_PASSWORD_ENV}。请在 .env 中补齐后重试。")
    return password


async def is_demo_ready(session) -> bool:
    """演示数据已就绪：demo 老人存在且名下已有提醒。"""
    from sqlalchemy import func, select

    from yuxi.storage.postgres.models_business import User
    from yuxi.storage.postgres.models_family import Reminder

    elder = await session.scalar(select(User.id).where(User.uid == ELDER_UID))
    if elder is None:
        return False
    reminder_count = await session.scalar(select(func.count(Reminder.id)).where(Reminder.target_uid == ELDER_UID))
    return bool(reminder_count)


async def wipe_demo_data(session) -> None:
    """删除 demo 两账号名下的全部业务数据与账号本身，严格限定两个 uid。"""
    from sqlalchemy import delete, select

    from yuxi.storage.postgres.models_business import OperationLog, User
    from yuxi.storage.postgres.models_family import (
        EmergencyEvent,
        FamilyLink,
        FamilyMessage,
        Reminder,
        ReminderOccurrence,
    )

    demo_uids = (ELDER_UID, CHILD_UID)
    demo_user_ids = select(User.id).where(User.uid.in_(demo_uids)).scalar_subquery()
    reminder_ids = (
        select(Reminder.id)
        .where((Reminder.owner_uid.in_(demo_uids)) | (Reminder.target_uid.in_(demo_uids)))
        .scalar_subquery()
    )
    await session.execute(
        delete(ReminderOccurrence).where(
            ReminderOccurrence.reminder_id.in_(reminder_ids) | ReminderOccurrence.target_uid.in_(demo_uids)
        )
    )
    await session.execute(
        delete(Reminder).where((Reminder.owner_uid.in_(demo_uids)) | (Reminder.target_uid.in_(demo_uids)))
    )
    await session.execute(
        delete(FamilyMessage).where((FamilyMessage.from_uid.in_(demo_uids)) | (FamilyMessage.to_uid.in_(demo_uids)))
    )
    await session.execute(delete(EmergencyEvent).where(EmergencyEvent.elder_uid.in_(demo_uids)))
    await session.execute(
        delete(FamilyLink).where((FamilyLink.elder_uid.in_(demo_uids)) | (FamilyLink.child_uid.in_(demo_uids)))
    )
    # operation_logs 外键无级联（登录/注册会写审计日志），不先清掉删 users 会违反外键
    await session.execute(delete(OperationLog).where(OperationLog.user_id.in_(demo_user_ids)))
    await session.execute(delete(User).where(User.uid.in_(demo_uids)))
    await session.flush()


async def write_demo_data(session, spec: DemoSpec, password: str) -> None:
    """把 spec 落库（薄层，不做业务计算；时间与状态全部来自 spec）。"""
    from yuxi.storage.postgres.models_business import User
    from yuxi.storage.postgres.models_family import (
        EmergencyEvent,
        FamilyLink,
        FamilyMessage,
        Reminder,
        ReminderOccurrence,
    )
    from yuxi.utils.auth_utils import AuthUtils
    from yuxi.utils.datetime_utils import utc_now_naive

    password_hash = AuthUtils.hash_password(password)
    now = utc_now_naive()
    session.add_all(
        [
            User(
                uid=spec["elder_uid"],
                username=spec["elder_name"],
                password_hash=password_hash,
                role="user",
                identity="elder",
                last_login=now,
            ),
            User(
                uid=spec["child_uid"],
                username=spec["child_name"],
                password_hash=password_hash,
                role="user",
                identity="child",
                last_login=now,
            ),
            FamilyLink(
                elder_uid=spec["elder_uid"],
                child_uid=spec["child_uid"],
                relation=spec["relation"],
                status="active",
                invited_by=spec["child_uid"],
            ),
        ]
    )
    await session.flush()

    reminders_by_key = {
        item["key"]: Reminder(
            owner_uid=item["owner_uid"],
            target_uid=item["target_uid"],
            title=item["title"],
            content=item["content"],
            category=item["category"],
            remind_at=item["remind_at"],
            repeat_rule=item["repeat_rule"],
            enabled=True,
        )
        for item in spec["reminders"]
    }
    session.add_all(reminders_by_key.values())
    await session.flush()

    session.add_all(
        ReminderOccurrence(
            reminder_id=reminders_by_key[item["reminder_key"]].id,
            target_uid=item["target_uid"],
            scheduled_at=item["scheduled_at"],
            status=item["status"],
            confirmed_at=item["confirmed_at"],
            finished_at=item["finished_at"],
        )
        for item in spec["occurrences"]
    )
    session.add_all(
        FamilyMessage(
            from_uid=item["from_uid"],
            to_uid=item["to_uid"],
            content=item["content"],
            created_at=item["created_at"],
            read_at=item["read_at"],
        )
        for item in spec["messages"]
    )
    session.add_all(
        EmergencyEvent(
            elder_uid=item["elder_uid"],
            source=item["source"],
            category=item["category"],
            detail=item["detail"],
            status=item["status"],
            created_at=item["created_at"],
            resolved_at=item["resolved_at"],
        )
        for item in spec["emergency_events"]
    )
    await session.flush()


async def seed_demo(password: str, *, reset: bool = False) -> tuple[DemoSpec, bool]:
    """入口：默认幂等（已就绪即返回，不重建），数据缺失或 --reset 时清掉 demo 数据全量重建。"""
    from yuxi.services.reminder_service import shanghai_now
    from yuxi.storage.postgres.manager import pg_manager

    try:
        pg_manager.initialize()
        await pg_manager.create_business_tables()
        await pg_manager.ensure_business_schema()

        async with pg_manager.get_async_session_context() as session:
            if not reset and await is_demo_ready(session):
                return build_demo_spec(shanghai_now()), True

            await wipe_demo_data(session)
            spec = build_demo_spec(shanghai_now())
            await write_demo_data(session, spec, password)
            return spec, False
    finally:
        await pg_manager.close()


def build_success_message(spec: DemoSpec, *, already_ready: bool = False) -> str:
    """成功提示：只包含账号与数量，不包含密码等敏感值。"""
    if already_ready:
        return (
            f"演示数据已就绪：{spec['elder_name']}（{spec['elder_uid']}）/ "
            f"{spec['child_name']}（{spec['child_uid']}）。如需重建到当前时刻，执行："
            "docker compose exec api uv run python scripts/seed_demo.py --reset"
        )
    done = sum(1 for item in spec["occurrences"] if item["status"] == "done")
    missed = len(spec["occurrences"]) - done
    return (
        f"演示数据已创建：{spec['elder_name']}（{spec['elder_uid']}）/ "
        f"{spec['child_name']}（{spec['child_uid']}），"
        f"{len(spec['reminders'])} 条提醒、过去 {HISTORY_DAYS} 天执行记录 {done} 完成 / {missed} 漏服、"
        f"留言 {len(spec['messages'])} 条、已解除紧急事件 {len(spec['emergency_events'])} 起。\n"
        "两账号共用环境变量 YUXI_DEMO_PASSWORD 配置的密码。演示账号，请勿用于真实环境。"
    )


def main(argv: list[str] | None = None) -> int:
    load_project_env()
    reset = "--reset" in (sys.argv[1:] if argv is None else argv)
    try:
        password = load_demo_password()
        spec, already_ready = asyncio.run(seed_demo(password, reset=reset))
    except SeedError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"创建演示数据失败：{exc}", file=sys.stderr)
        return 1

    print(build_success_message(spec, already_ready=already_ready))
    return 0


if __name__ == "__main__":
    code = main()
    sys.stdout.flush()
    sys.stderr.flush()
    # 与 seed_knowledge_base 保持一致：绕过解释器退出阶段的第三方清理钩子，
    # 避免偶发的退出挂起导致 make seed-demo 不返回。
    os._exit(code)
