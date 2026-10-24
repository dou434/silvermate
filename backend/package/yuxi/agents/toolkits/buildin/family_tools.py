"""家庭业务数据查询工具（银发智伴）。

对话智能体默认只能看到沙盒文件，看不到应用自己的业务数据，于是用户问
"小李给我设置了什么提醒" 时它只能回答"没有关于小李的资料"。这里把
家人绑定、提醒计划、关怀留言以只读工具的形式挂给智能体。

三条边界：

1. **只读**。建提醒、完成提醒、给家人发留言这类写操作仍然走
   ``assistant_command_service`` 的规则解析（命中即执行、命不中交还对话）。
   写操作放进工具等于让模型替用户动手，养老场景里一次误执行就是真打扰。
2. **只读自己的数据**。所有查询都以 ``runtime.context.uid`` 为准，再用
   ``reminder_service`` / ``family_repository`` 里既有的可见性校验，
   不会因为模型换了个名字就查到别人头上。
3. **留言不标记已读**。``family_service.list_messages`` 会顺手把对方的留言
   标成已读，界面上未读红点就凭空消失了。这里直接走仓储层读原始记录。
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from langgraph.prebuilt.tool_node import ToolRuntime
from sqlalchemy import select

from yuxi.agents.toolkits.registry import tool
from yuxi.storage.postgres.models_business import User

_MAX_REMINDERS = 30
_MAX_MESSAGES = 20

_SELF_ALIASES = ("我", "我自己", "自己", "本人", "我的")

_WEEKDAY_LABELS = ("周一", "周二", "周三", "周四", "周五", "周六", "周日")

_OCCURRENCE_STATUS_LABELS = {
    "pending": "还没到时间",
    "delivered": "已提醒，还没回应",
    "seen": "已看到，还没确认",
    "confirmed": "已确认收到",
    "done": "已完成",
    "skipped": "已跳过",
    "missed": "已错过，没人处理",
}


# ---------------------------------------------------------------------------
# 运行时取值与数据装配（与 @tool 分开，便于单测直接调）
# ---------------------------------------------------------------------------


def _runtime_uid(runtime: ToolRuntime) -> str:
    """从运行时上下文里取当前登录用户 uid。

    正常链路下 ``prepare_agent_runtime_context`` 会把 uid 放进 context；
    子智能体或后台任务可能只带在 configurable 里，所以两处都看。
    """
    context = getattr(runtime, "context", None)
    uid = getattr(context, "uid", None) if context is not None else None
    if not uid:
        config = getattr(runtime, "config", None)
        configurable = config.get("configurable", {}) if isinstance(config, dict) else {}
        uid = configurable.get("uid") if isinstance(configurable, dict) else None

    uid_text = str(uid or "").strip()
    if not uid_text:
        raise ValueError("当前对话没有绑定登录用户，无法查询家庭数据。请提示用户重新登录后再试。")
    return uid_text


async def _load_current_user(db, uid: str) -> User:
    from yuxi.repositories.user_repository import UserRepository

    user = await UserRepository().get_by_uid_with_db(db, uid)
    if user is None:
        raise ValueError("当前登录用户不存在或已被删除，无法查询家庭数据。")
    return user


async def _load_names(db, uids: set[str]) -> dict[str, str]:
    if not uids:
        return {}
    result = await db.execute(select(User.uid, User.username).where(User.uid.in_(uids)))
    return {uid: name for uid, name in result.all()}


async def _collect_family(db, user: User) -> dict[str, Any]:
    """装配"我"和家人清单：谁是我、家人叫什么、对方是我的什么人、有几条未读留言。"""
    from yuxi.repositories.family_repository import FamilyRepository

    repository = FamilyRepository()
    links = [
        link
        for link in await repository.list_links_of_user(db, user.uid)
        if (link.status or "active") == "active"
    ]

    others = {link.child_uid for link in links if link.elder_uid == user.uid} | {
        link.elder_uid for link in links if link.child_uid == user.uid
    }
    names = await _load_names(db, others)
    unread_by_sender = await repository.count_unread_by_sender(db, user.uid)

    family: list[dict[str, Any]] = []
    for link in links:
        if link.elder_uid == user.uid:
            uid, who = link.child_uid, f"我的{link.relation or '家人'}"
        else:
            uid, who = link.elder_uid, "我照护的老人"
        family.append(
            {
                "name": names.get(uid) or uid,
                "uid": uid,
                "who": who,
                "unread_messages": int(unread_by_sender.get(uid, 0)),
            }
        )

    family.sort(key=lambda item: (-item["unread_messages"], item["name"]))
    return {
        "me": {"name": user.username or user.uid, "uid": user.uid},
        "family": family,
    }


def _match_family(family: list[dict[str, Any]], text: str) -> list[dict[str, Any]]:
    """按名字或 uid 找家人：先精确匹配，再退化为包含匹配。"""
    keyword = text.strip()
    exact = [item for item in family if item["name"] == keyword or item["uid"] == keyword]
    if exact:
        return exact
    lowered = keyword.lower()
    return [
        item
        for item in family
        if lowered in str(item["name"]).lower() or lowered in str(item["uid"]).lower()
    ]


def _resolve_person(
    me: dict[str, Any],
    family: list[dict[str, Any]],
    text: str | None,
) -> dict[str, Any]:
    """把用户口中的称呼落成具体的人；找不到或有歧义时抛错让模型来问，而不是猜。"""
    keyword = (text or "").strip()
    if not keyword or keyword in _SELF_ALIASES:
        return me

    hits = _match_family(family, keyword)
    known = "、".join(item["name"] for item in family) or "（暂无家人）"
    if not hits:
        raise ValueError(f"没有叫「{keyword}」的家人。当前家人是：{known}。请核对名字后再查，或先问用户指的是谁。")
    if len(hits) > 1:
        matched = "、".join(item["name"] for item in hits)
        raise ValueError(f"「{keyword}」同时匹配到：{matched}。请用更完整的名字再查，或先问用户指的是谁。")
    return hits[0]


def _as_naive_utc(value: datetime | str | None) -> datetime | None:
    """服务层给的时间有的还是 datetime，有的已经被 ``format_utc_datetime`` 转成带 Z 的字符串。"""
    if value is None or isinstance(value, datetime):
        return value
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is not None:
        return parsed.astimezone(UTC).replace(tzinfo=None)
    return parsed


def _local_time_text(value: datetime | str | None) -> str | None:
    """库里的 naive UTC 转成给人看的中文时间。"""
    naive_utc = _as_naive_utc(value)
    if naive_utc is None:
        return None
    from yuxi.services.reminder_service import to_shanghai

    local = to_shanghai(naive_utc)
    return f"{local.month}月{local.day}日({_WEEKDAY_LABELS[local.weekday()]}) {local:%H:%M}"


def _repeat_label(rule: dict | None) -> str:
    rule = rule or {}
    kind = str(rule.get("type") or "none")
    if kind == "daily":
        return "每天"
    if kind == "weekly":
        days = "、".join(
            _WEEKDAY_LABELS[int(day) - 1] for day in (rule.get("weekdays") or []) if 1 <= int(day) <= 7
        )
        return f"每周{days}" if days else "每周"
    if kind == "custom":
        interval = rule.get("interval")
        return f"每{interval}天" if interval else "定期"
    return "一次性"


def _occurrence_status_text(status: str | None) -> str:
    return _OCCURRENCE_STATUS_LABELS.get(str(status or ""), str(status or ""))


def _pick_person(item: dict[str, Any], person_uid: str) -> bool:
    return person_uid in {item.get("owner_uid"), item.get("target_uid")}


async def _collect_reminders(
    db,
    user: User,
    *,
    person: str | None = None,
    only_today: bool = False,
) -> dict[str, Any]:
    """查询与某人相关的提醒：设置人或被提醒人任意一侧命中都算。

    用户说"小李给我设置了什么提醒"时，小李是**设置人**；说"我妈今天有什么提醒"时，
    妈妈是**被提醒人**。一个 ``person`` 参数同时覆盖两种问法，模型不用挑参数。
    """
    from yuxi.services import reminder_service

    family_payload = await _collect_family(db, user)
    me = family_payload["me"]
    target = _resolve_person(me, family_payload["family"], person)
    viewable_targets = {me["uid"], *await reminder_service.visible_elder_uids(db, user)}

    if only_today:
        # 只有"被提醒的人"才能展开今日待办；传的是设置人（比如小李）时按我自己展开，
        # 再在下面用 person 过滤出他设的那几条。
        expand_uid = target["uid"] if target["uid"] in viewable_targets else me["uid"]
        today = await reminder_service.list_today(db, user, target_uid=expand_uid)
        raw_items = today.get("items", [])
        # list_today 只回 uid，人名要自己补，不然模型会把 uid 念给用户听
        involved_uids = {
            value
            for item in raw_items
            for value in (item.get("owner_uid"), item.get("target_uid"))
            if value
        }
        names = await _load_names(db, involved_uids)
        items = [
            {
                "title": item.get("title"),
                "category": item.get("category"),
                "content": item.get("content"),
                "time": _local_time_text(item.get("scheduled_at")),
                "status": _occurrence_status_text(item.get("status")),
                "set_by": names.get(item.get("owner_uid")) or item.get("owner_uid"),
                "set_for": names.get(item.get("target_uid")) or item.get("target_uid"),
                "owner_uid": item.get("owner_uid"),
                "target_uid": item.get("target_uid"),
                "repeat": _repeat_label(item.get("repeat_rule")),
            }
            for item in raw_items
        ]
        date_text = today.get("date")
    else:
        data = await reminder_service.list_reminders(db, user)
        items = [
            {
                "title": item.get("title"),
                "category": item.get("category"),
                "content": item.get("content"),
                "time": _local_time_text(item.get("remind_at")),
                "status": "已停用" if not item.get("enabled") else "启用中",
                "set_by": item.get("owner_name") or item.get("owner_uid"),
                "set_for": item.get("target_name") or item.get("target_uid"),
                "owner_uid": item.get("owner_uid"),
                "target_uid": item.get("target_uid"),
                "repeat": _repeat_label(item.get("repeat_rule")),
            }
            for item in data.get("reminders", [])
        ]
        date_text = None

    if person and target["uid"] != me["uid"]:
        items = [item for item in items if _pick_person(item, target["uid"])]

    matched = len(items)
    truncated = matched > _MAX_REMINDERS
    for item in items:
        item.pop("owner_uid", None)
        item.pop("target_uid", None)

    payload: dict[str, Any] = {
        "person": target["name"],
        "total": matched,
        "reminders": items[:_MAX_REMINDERS],
    }
    if date_text:
        payload["date"] = date_text
    if truncated:
        payload["note"] = f"只列出了前 {_MAX_REMINDERS} 条，还有 {matched - _MAX_REMINDERS} 条未列出。"
    if not items:
        payload["note"] = "没有查到符合条件的提醒。"
    return payload


async def _collect_messages(db, user: User, *, person: str, limit: int = _MAX_MESSAGES) -> dict[str, Any]:
    """读取我和某位家人的留言往来（只读，不改已读状态）。"""
    from yuxi.repositories.family_repository import FamilyRepository

    family_payload = await _collect_family(db, user)
    target = _resolve_person(family_payload["me"], family_payload["family"], person)
    if target["uid"] == user.uid:
        raise ValueError("留言是两个人之间的事，不能和自己查询留言。请指定一位家人。")

    repository = FamilyRepository()
    raw = await repository.list_messages_between(db, user.uid, target["uid"], limit=limit)
    names = {user.uid: user.username or user.uid, target["uid"]: target["name"]}

    messages = [
        {
            "from": names.get(item.from_uid, item.from_uid),
            "content": item.content,
            "time": _local_time_text(item.created_at),
            "read": item.read_at is not None,
        }
        for item in reversed(raw)
    ]

    return {
        "person": target["name"],
        "total": len(messages),
        "messages": messages,
        "note": "这里只是查看，不会把留言标成已读。",
    }


# ---------------------------------------------------------------------------
# 工具定义
#
# 这里**不要**给带 ``runtime: ToolRuntime`` 的工具手写 args_schema：
# 写了之后 langchain 不再把 runtime 当注入参数传进来，调用时会报
# "missing 1 required positional argument: 'runtime'"。
# 模型侧的参数 schema 由 ``tool_call_schema`` 自动剔除 runtime，
# 工具列表接口也改用 ``tool_call_schema`` 生成（见 toolkits/service.py）。
# ---------------------------------------------------------------------------


GET_FAMILY_MEMBERS_DESCRIPTION = """查询"我"的家庭成员清单。

返回当前登录用户自己，以及和他有绑定关系的家人：家人叫什么、对方是我的什么人
（"我的子女" / "我照护的老人"）、对方有几条我还没看的留言。

使用场景：
1. 用户提到某个称呼（"小李""我女儿""我妈"），需要先确认这个人是谁
2. 用户问"我家里都有谁""谁在照顾我""我绑定了哪些家人"
3. 调用 list_family_reminders / list_family_messages 之前，先确认家人的准确名字

注意：只返回和家人有关的信息，不包含账号、手机号等隐私字段。
"""


@tool(
    category="buildin",
    tags=["家庭", "家人"],
    display_name="查询家人清单",
    description=GET_FAMILY_MEMBERS_DESCRIPTION,
)
async def get_family_members(runtime: ToolRuntime) -> dict:
    """返回当前用户的家庭成员（自己 + 已绑定家人）。"""
    from yuxi.storage.postgres.manager import pg_manager

    uid = _runtime_uid(runtime)
    async with pg_manager.get_async_session_context() as db:
        user = await _load_current_user(db, uid)
        return await _collect_family(db, user)


LIST_FAMILY_REMINDERS_DESCRIPTION = """查询家庭范围内的提醒：谁给谁设了什么提醒、什么时候提醒、今天做了没有。

参数：
- person：家人姓名或 uid，可以是"设置提醒的人"也可以是"被提醒的人"，留空表示不限人。
- only_today：true 只看今天这一天（含是否已完成），false 看全部启用的提醒计划。

使用场景：
1. "小李给我设置了什么提醒" → person="小李"
2. "我今天有什么提醒" / "我药吃了没有" → only_today=true
3. "我妈都有哪些提醒" → person="我妈的准确名字"
4. 用户问某条提醒为什么没响、有没有做完

返回里 set_by 是设置人、set_for 是被提醒人、status 是今天的执行状态。
名字对不上会直接报错并列出真实家人名字，此时应先确认是谁，不要猜。
"""


@tool(
    category="buildin",
    tags=["家庭", "提醒"],
    display_name="查询家人提醒",
    description=LIST_FAMILY_REMINDERS_DESCRIPTION,
)
async def list_family_reminders(
    runtime: ToolRuntime,
    person: str | None = None,
    only_today: bool = False,
) -> dict:
    """查询与某位家人相关（或全部）的提醒。"""
    from yuxi.storage.postgres.manager import pg_manager

    uid = _runtime_uid(runtime)
    async with pg_manager.get_async_session_context() as db:
        user = await _load_current_user(db, uid)
        return await _collect_reminders(db, user, person=person, only_today=only_today)


LIST_FAMILY_MESSAGES_DESCRIPTION = """查询我和某位家人之间的关怀留言。

参数：
- person：家人姓名或 uid，必填
- limit：最多返回多少条，默认 20

使用场景：
1. "小李给我留言了吗" / "小李说了什么"
2. 用户想回顾和家人最近说过的话

返回按时间正序排列，read=false 表示我还没看过。这个工具只读，
不会把留言标记成已读，也不会替用户回复。
"""


@tool(
    category="buildin",
    tags=["家庭", "留言"],
    display_name="查询家人留言",
    description=LIST_FAMILY_MESSAGES_DESCRIPTION,
)
async def list_family_messages(
    runtime: ToolRuntime,
    person: str,
    limit: int = _MAX_MESSAGES,
) -> dict:
    """读取与某位家人的留言往来（只读）。"""
    from yuxi.storage.postgres.manager import pg_manager

    uid = _runtime_uid(runtime)
    safe_limit = max(1, min(int(limit or _MAX_MESSAGES), _MAX_MESSAGES))
    async with pg_manager.get_async_session_context() as db:
        user = await _load_current_user(db, uid)
        return await _collect_messages(db, user, person=person, limit=safe_limit)


__all__ = [
    "get_family_members",
    "list_family_messages",
    "list_family_reminders",
]
