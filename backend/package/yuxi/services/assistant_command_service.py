"""问 AI 界面的自然语言指令：把"帮我做点事"落成一次真实操作或界面动作。

设计取舍（重要，改之前先读）：

1. **只用规则解析，不调用大模型**。指令类需求的句式高度收敛——给谁发消息、把哪条提醒
   标记完成、打开哪个页面——规则命中即执行，几十毫秒返回、零 token、可单测；未命中的
   自然语言原样交回原智能体对话，不影响正常问答。用大模型走 function calling 虽然泛化
   更好，但每次多一轮推理（老人等不起）、结果不确定（可能把"怎么给小李发消息"这种
   提问当成命令执行），对这类"改数据"的操作不合格。
2. **写操作全部在服务端完成**，复用 family_service / reminder_service 里已有的权限校验，
   前端只负责刷新界面和展示结果。前端自己拼请求会绕过 assert_can_view / assert_can_target
   这套单点权限。
3. **只操作本人**。提醒的确认/完成在业务上只能由被提醒的老人本人做（见
   reminder_service._load_occurrence_for_target），这里不开口子。

返回值协议（前端 useAssistantCommand 消费）::

    {
        "handled": bool,          # False 表示不是指令，交还给智能体对话
        "intent": str | None,     # family_message / reminder_create / reminder_change /
                                  # reminder_stop / reminder_done / reminder_confirm / navigate
        "reply": str,             # 直接展示给用户的助手回复
        "actions": list[dict],    # 界面动作：{"type": "refresh"|"navigate"|"notify", ...}
        "needs_input": bool,      # True 表示缺参数（例如没说发什么），reply 是追问
    },
"""

from __future__ import annotations

import re
from datetime import datetime, time, timedelta

from sqlalchemy.ext.asyncio import AsyncSession
from yuxi.services import family_service, reminder_service
from yuxi.storage.postgres.models_business import User
from yuxi.utils.datetime_utils import SHANGHAI_TZ

# 这些状态表示"时间已到、老人还没定性"，可以继续标记完成或确认。
REMINDER_SETTLED_STATUSES = {"delivered", "confirmed", "missed"}
# 老人说"收到"时还能确认的状态（pending 也允许，和 reminder_service 口径保持一致）。
REMINDER_CONFIRMABLE_STATUSES = {"pending", "delivered", "missed"}

# 匹配"给谁发消息"：给/跟/向/和 + 称呼 + 发/留/说/讲/转达 + 可选的量词与"消息"
_SEND_PATTERN = re.compile(
    r"(?:帮(?:我)?|请|麻烦)?\s*"
    r"(?:给|跟|向|和|对)\s*(?P<name>[\u4e00-\u9fa5A-Za-z0-9_]{1,12}?)\s*"
    r"(?:发|留|说|讲|转达)\s*(?:一|1)?\s*(?:条|个|句|下)?\s*"
    r"(?:消息|留言|话|微信|信息)?\s*"
    r"(?:[：:，,。]|说|讲|内容是|内容为|就是)?\s*"
    r"(?P<content>.*)$"
)

# "告诉小李明天来吃饭" 这种不带"发消息"字样的，只定位动词，人名和内容交给联系人表切分
# （用正则切分会被"小李小李"这类名字带偏，见 _split_name_and_content）
_TELL_PATTERN = re.compile(r"(?:帮(?:我)?|请|麻烦)?\s*(?:告诉|通知|转告)\s*(?P<rest>.+)$")

# 纯疑问句放行：用户在问方法（"怎么给小李发消息"），不是在发指令。
# 带"吗"和问号的句子也一并放行，否则"小李给我发消息了吗？"会被当成要发消息。
_QUESTION_PATTERN = re.compile(r"(怎么|如何|怎么样|为什么|为什么不能|能不能教|是什么意思|有什么区别)")

_DONE_PATTERN = re.compile(r"(做完|做了|完成|打卡|搞完|弄完)")
_CONFIRM_PATTERN = re.compile(r"(收到|确认|知道了|看到了|看见了)")
# 老人极简回应："我收到了""确认了"，没有说到哪一条，按"确认所有已到点的"处理
_CONFIRM_ALONE_PATTERN = re.compile(r"^(?:我)?(?:都)?(?:收到|确认)(?:了|啦|到了)?[!！。.]?$")

_NAVIGATE_PATTERN = re.compile(
    r"(?:打开|回到|返回|去|切到|切换到|看看|看一下|进入)\s*(?:我的)?\s*(?P<page>提醒|家人|首页|主页|问\s*AI|对话)"
)

# 提取提醒关键词时先剔掉这些虚词与动作词，剩下的才是"哪条提醒"
_KEYWORD_NOISE = re.compile(
    r"(帮我|帮忙|请|麻烦|把|将|给|的|提醒|标记|记录|记成|记为|改成|设置|为|成|完成|做完|做了|"
    r"已经|都|全部|所有|今天|今日|一下|这|那|条|个|件|事情|先|也|和|我|了|一下|吧|呢|啊|哦)"
)

_PAGE_LABELS = {
    "提醒": "我的提醒",
    "家人": "家人",
    "首页": "首页",
    "主页": "首页",
    "问ai": "问 AI",
    "对话": "问 AI",
}

# === 提醒管理（建/改/停）的中文时间解析 ====================================
# 只认约定好的口语形态：日期(今天/今晚/明天/明早/明晚/后天) × 时段(凌晨..晚上)
# × 时刻(八点/8点/三点半/3:30/14点/X点Y分) × 重复(每天/每周几)。
# 解析不出"确定"的时刻就返回 None，由调用方追问或放行——错时间对用药提醒是安全事故。

_CN_DIGITS = {"零": 0, "一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}
_CN_DIGIT_CHARS = "零一二两三四五六七八九十"

# 这些日期/重复说法本任务不支持。硬套规则会得到错误时刻（如"大后天"被当成
# "后天"、"每周一"丢掉"每"变成今天），宁可整句放行追问，也不猜。
_UNSUPPORTED_SCHEDULE = re.compile(
    r"(大后天|下周|下月|下个|每月|每隔|隔.{0,2}天|工作日"
    r"|\d\s*月|\d\s*[号日]|月\s*\d|(?<!每)(?:周|星期)[一二三四五六日天])"
)

_TIME_CHUNK = re.compile(
    r"(?P<date>后天|明天|明早|明晚|今天|今晚)?\s*"
    r"(?P<period>凌晨|早上|早晨|上午|中午|下午|傍晚|晚上)?\s*"
    r"(?:(?:(?P<hour>\d{1,2}|[零一二两三四五六七八九十]{1,3})\s*[点时]\s*"
    r"(?P<minute>半|(?P<minnum>\d{1,2}|[零一二两三四五六七八九十]{1,3})\s*分)?)"
    r"|(?:(?P<dhour>\d{1,2})\s*[:：]\s*(?P<dmin>\d{1,2})))"
)

_WEEKDAY_TO_ISO = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "日": 7, "天": 7}
_DATE_OFFSETS = {"后天": 2, "明天": 1, "明早": 1, "明晚": 1, "今天": 0, "今晚": 0}
_WEEKDAY_LABELS = {1: "一", 2: "二", 3: "三", 4: "四", 5: "五", 6: "六", 7: "日"}

# 创建指令句首锚定（可选礼貌词 + 可选重复词 + 可选时间前缀 + "提醒我"），
# 中间只放行"时间表达字符"（今明后/时段/数字/点半分等），
# 让"医生提醒我要按时吃药"这类第三方陈述天然不命中
_REMINDER_CREATE_PATTERN = re.compile(
    r"^(?:帮我|请|麻烦)?\s*(?:给我)?\s*"
    r"(?:每天|每日|每(?:周|星期)[一二三四五六日天])?\s*"
    r"[今明后天凌晨早晚夜间上下午傍晨时分半点中:：\d零一二两三四五六七八九十\s]{0,16}?"
    r"提醒我\s*(?P<rest>.+)$"
)
_REMINDER_CHANGE_PATTERN = re.compile(r"(改到|改成|改为|调整到|调整成|调整为|调整)")
_REMINDER_STOP_PATTERN = re.compile(r"(别再?提醒|不用提醒|不要了|不用了|停掉|停了|取消|删掉|删除)")

# 建改停三个 intent 抽关键词用的虚词表：在通用表基础上补充动作词、时段与重复词
_KEYWORD_MGMT_NOISE = re.compile(
    r"(帮我|帮忙|请|麻烦|把|将|给|的|提醒|标记|记录|记成|记为|改成|改到|改为|调整|设置|为|成|完成|做完|做了|"
    r"已经|都|全部|所有|今天|今日|明天|后天|明早|明晚|今晚|凌晨|早上|早晨|上午|中午|下午|傍晚|晚上|"
    r"每天|每日|每星期|每周|星期|周|一下|这|那|条|个|件|事情|先|也|和|我|了|吧|呢|啊|哦|们|"
    r"别再|别|不要|不用|停掉|停了|停|取消|删掉|删除)"
)


def _result(
    *,
    handled: bool,
    intent: str | None = None,
    reply: str = "",
    actions: list[dict] | None = None,
    needs_input: bool = False,
) -> dict:
    return {
        "handled": handled,
        "intent": intent,
        "reply": reply,
        "actions": actions or [],
        "needs_input": needs_input,
        "needsInput": needs_input,
    }


def _clean_content(raw: str) -> str:
    """去掉"说/内容是"这类引导词和首尾标点，得到真正要发出去的那句话。"""
    text = (raw or "").strip(" \t\r\n：:，,。;；、")
    for prefix in ("就说", "说一句", "内容是", "内容为", "说的是", "说", "讲"):
        if text.startswith(prefix):
            text = text[len(prefix) :].strip(" \t\r\n：:，,。;；、")
            break
    return text


def _extract_keyword(text: str) -> str:
    """从"把吃药的提醒标记为完成"里抽出"吃药"这类可用来匹配标题的核心词。"""
    stripped = _KEYWORD_NOISE.sub("", text)
    return re.sub(r"[\s，,。.！!？?：:；;、]", "", stripped)


def _match_score(keyword: str, title: str) -> float:
    """关键词与提醒标题的匹配度。

    连续子串直接给满分（"吃药" 命中 "吃药"）；否则按字符重合比例打分，
    让 "吃药" 也能对上 "吃降压药" 这种加了修饰的标题。
    """
    if not keyword or not title:
        return 0.0
    if keyword in title:
        return 1.0
    overlap = set(keyword) & set(title)
    if not overlap:
        return 0.0
    return len(overlap) / len(set(keyword))


def _chinese_number(text: str) -> int | None:
    """中文数字转整数。只覆盖小时会用到的 0-23，超界或写法不认识返回 None。"""
    if text == "十":
        return 10
    if text == "二十":
        return 20
    if len(text) == 3 and text.startswith("二十") and text[2] in _CN_DIGITS:
        return 20 + _CN_DIGITS[text[2]]
    if len(text) == 2 and text.startswith("十") and text[1] in _CN_DIGITS:
        return 10 + _CN_DIGITS[text[1]]
    if len(text) == 1 and text in _CN_DIGITS:
        return _CN_DIGITS[text]
    return None


def parse_when(text: str) -> tuple[datetime, dict] | None:
    """从中文口语句里解析提醒时刻与重复规则。

    Returns:
        (上海本地时间的 aware 时刻, repeat_rule)；解析不出确定时刻返回 None，
        由调用方追问或放行，绝不猜一个近似时间。
    """
    text = (text or "").strip()
    if not text or _UNSUPPORTED_SCHEDULE.search(text):
        return None

    rule: dict = {"type": "none"}
    if re.search(r"(每天|每日)", text):
        rule = {"type": "daily"}
    else:
        weekday = re.search(r"每(?:周|星期)([一二三四五六日天])", text)
        if weekday:
            rule = {"type": "weekly", "weekdays": [_WEEKDAY_TO_ISO[weekday.group(1)]]}

    match = _TIME_CHUNK.search(text)
    if not match:
        return None

    # "三点二十"这类没带"分"的分钟不猜：紧跟着数字却没解析出分钟，整句放弃
    tail = text[match.end() :]
    if tail and (tail[0] in _CN_DIGIT_CHARS or tail[0].isdigit()):
        return None

    if match.group("dhour") is not None:
        hour = int(match.group("dhour"))
        minute = int(match.group("dmin"))
    else:
        hour_raw = match.group("hour") or ""
        hour = int(hour_raw) if hour_raw.isdigit() else _chinese_number(hour_raw)
        minute_raw = match.group("minute")
        if minute_raw is None:
            minute = 0
        elif minute_raw == "半":
            minute = 30
        else:
            digits = minute_raw.rstrip("分")
            minute = int(digits) if digits.isdigit() else _chinese_number(digits)
    if hour is None or hour > 23 or minute > 59:
        return None

    period = match.group("period") or ""
    date_word = match.group("date") or ""
    offset = _DATE_OFFSETS.get(date_word, 0)

    if period == "晚上" or date_word in {"今晚", "明晚"}:
        # 晚上十二点是午夜零点，落到第二天；晚上八点补成 20 点
        if hour == 12:
            hour, offset = 0, offset + 1
        elif hour < 12:
            hour += 12
    elif period in {"下午", "傍晚", "中午"} and hour < 12:
        # 中午一点 = 13 点；中午/下午十二点保持 12 点
        hour += 12
    elif period == "凌晨" and hour == 12:
        hour = 0

    day = reminder_service.shanghai_now().date() + timedelta(days=offset)
    return datetime.combine(day, time(hour, minute), tzinfo=SHANGHAI_TZ), rule


def _strip_schedule(text: str) -> str:
    """去掉时间表达与指令虚词，剩下的就是提醒事项（或要定位的提醒关键词）。"""
    cleaned = _TIME_CHUNK.sub("", text or "")
    cleaned = _KEYWORD_MGMT_NOISE.sub("", cleaned)
    return re.sub(r"[\s，,。.！!？?：:；;、]", "", cleaned)


def _format_when(local: datetime, rule: dict) -> str:
    """给老人看的时刻描述：明天 08:00 / 每天 21:00 / 每周一 08:00。"""
    clock = local.strftime("%H:%M")
    kind = rule.get("type")
    if kind == "daily":
        return f"每天 {clock}"
    if kind == "weekly":
        days = "、".join(f"周{_WEEKDAY_LABELS.get(day, day)}" for day in rule.get("weekdays") or [])
        return f"每{days} {clock}"
    diff = (local.date() - reminder_service.shanghai_now().date()).days
    label = {0: "今天", 1: "明天", 2: "后天"}.get(diff) or local.strftime("%m月%d日")
    return f"{label} {clock}"


async def _load_contacts(db: AsyncSession, current_user: User) -> list[dict]:
    """当前用户能发留言的联系人（双向 active 绑定）。"""
    links = await family_service.list_links(db, current_user)
    contacts: list[dict] = []

    for link in links.get("as_elder", []):
        if link.get("child_name"):
            contacts.append(
                {
                    "uid": link["child_uid"],
                    "name": link["child_name"],
                    "relation": link.get("relation") or "子女",
                    "role": "child",
                }
            )

    for link in links.get("as_child", []):
        if link.get("elder_name"):
            contacts.append(
                {
                    "uid": link["elder_uid"],
                    "name": link["elder_name"],
                    "relation": link.get("relation") or "老人",
                    "role": "elder",
                }
            )

    return contacts


def _match_contact(contacts: list[dict], name: str) -> tuple[list[dict], str]:
    """按称呼找人，返回 (候选列表, 匹配方式)。"""
    target = (name or "").strip()
    if not target:
        return [], "none"

    exact = [c for c in contacts if c["name"] == target]
    if exact:
        return exact, "exact"

    # "小李" 对上 "小李子"、用户名 "xiaoli" 对上输入的 "xiaoli" 都已覆盖；
    # 用户也可能只输名字的一部分，所以再退一步做双向包含。
    partial = [c for c in contacts if target in c["name"] or c["name"] in target]
    if partial:
        return partial, "partial"

    # 称谓匹配："给儿子发消息"，同一称谓可能对应多人，交给调用方处理多候选
    by_relation = [c for c in contacts if target in (c.get("relation") or "")]
    if by_relation:
        return by_relation, "relation"

    return [], "none"


def _contact_list_text(contacts: list[dict]) -> str:
    return "、".join(dict.fromkeys(c["name"] for c in contacts))


def _split_name_and_content(rest: str, contacts: list[dict]) -> tuple[str, str]:
    """从"小李我今天血压130"里切出称呼和内容。

    只在已知联系人名字里找前缀（按长度降序，避免"小李"被"小李子"抢走），
    找不到就返回空称呼——宁可交还给智能体，也不要瞎猜着发出去。
    """
    text = (rest or "").strip()
    for contact in sorted(contacts, key=lambda c: len(c["name"]), reverse=True):
        name = contact["name"]
        if name and text.startswith(name):
            return name, text[len(name) :]
    return "", text


async def _handle_family_message(
    db: AsyncSession, current_user: User, *, name: str, content: str
) -> dict:
    content = _clean_content(content)

    contacts = await _load_contacts(db, current_user)
    if not contacts:
        return _result(
            handled=True,
            intent="family_message",
            reply="您还没有绑定家人，先到「我的家人」里同意家人的绑定申请，就能互相留言了。",
            actions=[{"type": "navigate", "path": "/elder/family", "label": "我的家人"}],
        )

    candidates, how = _match_contact(contacts, name)
    if not candidates:
        return _result(
            handled=True,
            intent="family_message",
            reply=f"没找到「{name}」。现在能发消息的是：{_contact_list_text(contacts)}。您想发给谁？",
            needs_input=True,
        )

    if len(candidates) > 1:
        names = _contact_list_text(candidates)
        return _result(
            handled=True,
            intent="family_message",
            reply=f"有几位都对得上「{name}」：{names}。您想发给哪一位？",
            needs_input=True,
        )

    contact = candidates[0]
    if not content:
        return _result(
            handled=True,
            intent="family_message",
            reply=f"要给{contact['name']}说什么？您可以直接说：给{contact['name']}发消息：明天降温多穿件衣服。",
            needs_input=True,
        )

    try:
        sent = await family_service.send_message(
            db, current_user, to_uid=contact["uid"], content=content
        )
    except Exception as error:  # noqa: BLE001 - 统一转成老人能看懂的提示
        detail = getattr(error, "detail", None) or str(error)
        return _result(
            handled=True,
            intent="family_message",
            reply=f"没能发给{contact['name']}：{detail}",
        )

    preview = sent.get("content") or content
    return _result(
        handled=True,
        intent="family_message",
        reply=f"已经给{contact['name']}发过去了：「{preview}」。",
        actions=[
            {"type": "notify", "level": "success", "message": f"已发给{contact['name']}"},
            {"type": "refresh", "target": "family"},
        ],
    )


def _resolve_reminder_targets(items: list[dict], keyword: str) -> tuple[list[dict], str]:
    """把"吃药"这类关键词映射到具体的提醒记录。"""
    if not keyword:
        return [], "no_keyword"

    scored = [(_match_score(keyword, item.get("title") or ""), item) for item in items]
    # 连续子串（满分）优先：关键词同时是"吃药"的子串、又与"吃降压药"字符重合时
    # 只认子串命中的，不然明明有精确匹配却打平成多候选、反问老人
    exact = [pair for pair in scored if pair[0] == 1.0]
    pool = exact or [pair for pair in scored if pair[0] >= 0.5]
    if not pool:
        return [], "no_match"

    best = max(score for score, _ in pool)
    top = [item for score, item in pool if score == best]
    if len(top) > 1:
        return top, "ambiguous"
    return top, "matched"


def _resolve_management_targets(items: list[dict], keyword: str) -> tuple[list[dict], str]:
    """建/改/停里定位目标提醒。没说哪一条时只有唯一候选才直接用，否则追问。"""
    if not items:
        return [], "no_match"
    if not keyword:
        return (items, "matched") if len(items) == 1 else (items, "ambiguous")
    return _resolve_reminder_targets(items, keyword)


async def _transfer_to_owner(
    db: AsyncSession, current_user: User, item: dict, raw: str, *, intent: str, verb: str
) -> dict:
    """老人想动子女建的提醒：不放宽权限，留言转达给设置人并告知老人已转达。"""
    owner_name = item.get("owner_name") or "家人"
    title = item.get("title") or "提醒"
    try:
        await family_service.send_message(
            db,
            current_user,
            to_uid=item["owner_uid"],
            content=f"{current_user.username}想{verb}提醒「{title}」：{raw}。请到家人页确认处理。",
        )
    except Exception as error:  # noqa: BLE001 - 统一转成老人能看懂的提示
        detail = getattr(error, "detail", None) or str(error)
        return _result(handled=True, intent=intent, reply=f"没能联系上{owner_name}：{detail}")

    return _result(
        handled=True,
        intent=intent,
        reply=f"「{title}」是{owner_name}设置的，我动不了；我已经留言请他帮您{verb}了，等他看到就好。",
        actions=[
            {"type": "notify", "level": "success", "message": f"已留言请{owner_name}{verb}「{title}」"},
            {"type": "refresh", "target": "family"},
        ],
    )


async def _handle_reminder_create(
    db: AsyncSession, current_user: User, raw: str, rest: str
) -> dict:
    """「提醒我明天早上八点吃药」：给自己建提醒。缺时间或缺事项时追问，不猜。"""
    parsed = parse_when(raw)
    title = _strip_schedule(rest)

    if parsed is None:
        prefix = f"「{title}」" if title else ""
        return _result(
            handled=True,
            intent="reminder_create",
            reply=f"{prefix}几点提醒您？您可以说：提醒我明天早上八点吃药。",
            needs_input=True,
        )

    when, rule = parsed
    if not title:
        return _result(
            handled=True,
            intent="reminder_create",
            reply="要提醒您做什么事？您可以说：提醒我明天早上八点吃药。",
            needs_input=True,
        )

    try:
        await reminder_service.create_reminder(
            db,
            current_user,
            target_uid=current_user.uid,
            title=title,
            content=None,
            category="other",
            remind_at=when,
            repeat_rule=rule,
        )
    except Exception as error:  # noqa: BLE001 - 统一转成老人能看懂的提示
        detail = getattr(error, "detail", None) or str(error)
        return _result(handled=True, intent="reminder_create", reply=f"没能设好提醒：{detail}")

    return _result(
        handled=True,
        intent="reminder_create",
        reply=f"「{title}」的提醒已设好：{_format_when(when, rule)}，到点我会提醒您。",
        actions=[
            {"type": "notify", "level": "success", "message": f"已设好「{title}」的提醒"},
            {"type": "refresh", "target": "reminders"},
        ],
    )


async def _handle_reminder_change(db: AsyncSession, current_user: User, raw: str) -> dict:
    """「把吃药提醒改到下午三点」：自己建的直接改；子女建的转达给设置人。"""
    keyword = _strip_schedule(raw)
    payload = await reminder_service.list_reminders(db, current_user)
    items = [item for item in payload["reminders"] if item.get("enabled")]

    if not items:
        return _result(
            handled=True,
            intent="reminder_change",
            reply="您现在没有提醒。先说一句「提醒我明天早上八点吃药」就能建一条。",
        )

    targets, status = _resolve_management_targets(items, keyword)
    if status == "ambiguous":
        names = "、".join(item.get("title") or "提醒" for item in targets)
        return _result(
            handled=True,
            intent="reminder_change",
            reply=f"有 {len(targets)} 条都对得上：{names}。您说的是哪一条？",
            needs_input=True,
        )
    if status == "no_match":
        return _result(
            handled=True,
            intent="reminder_change",
            reply=f"没有找到「{keyword}」的提醒，可以打开「我的提醒」看看现在有哪些。",
        )

    parsed = parse_when(raw)
    title = targets[0].get("title") or "提醒"
    if parsed is None:
        return _result(
            handled=True,
            intent="reminder_change",
            reply=f"「{title}」要改到几点？您可以说：把{title}提醒改到明天下午三点。",
            needs_input=True,
        )
    when, rule = parsed

    if not targets[0].get("is_mine"):
        return await _transfer_to_owner(db, current_user, targets[0], raw, intent="reminder_change", verb="调整")

    try:
        await reminder_service.update_reminder(
            db,
            current_user,
            targets[0]["id"],
            remind_at=when,
            # 只在明确说了"每天/每周几"时才动重复规则，否则保留原规则
            repeat_rule=rule if rule.get("type") != "none" else None,
        )
    except Exception as error:  # noqa: BLE001 - 统一转成老人能看懂的提示
        detail = getattr(error, "detail", None) or str(error)
        return _result(handled=True, intent="reminder_change", reply=f"没能改过来：{detail}")

    when_text = _format_when(when, rule)
    return _result(
        handled=True,
        intent="reminder_change",
        reply=f"「{title}」已经改到{when_text}了。",
        actions=[
            {"type": "notify", "level": "success", "message": f"「{title}」已改到{when_text}"},
            {"type": "refresh", "target": "reminders"},
        ],
    )


async def _handle_reminder_stop(db: AsyncSession, current_user: User, raw: str) -> dict:
    """「吃药提醒不要了」「别再提醒我吃药」：自己的停用；子女建的转达。"""
    keyword = _strip_schedule(raw)
    payload = await reminder_service.list_reminders(db, current_user)
    if not payload["reminders"]:
        return _result(handled=True, intent="reminder_stop", reply="您现在没有提醒。")

    enabled = [item for item in payload["reminders"] if item.get("enabled")]
    targets, status = _resolve_management_targets(enabled, keyword)

    if status == "no_match":
        # 可能早就停过了：明确说出现在的状态，免得老人以为没生效
        disabled = [item for item in payload["reminders"] if not item.get("enabled")]
        stopped, stopped_status = _resolve_management_targets(disabled, keyword)
        if stopped_status == "matched":
            return _result(
                handled=True,
                intent="reminder_stop",
                reply=f"「{stopped[0].get('title') or '提醒'}」的提醒之前就已经停了，不会再提醒您。",
            )
        return _result(handled=True, intent="reminder_stop", reply=f"没有找到「{keyword}」的提醒。")

    if status == "ambiguous":
        names = "、".join(item.get("title") or "提醒" for item in targets)
        return _result(
            handled=True,
            intent="reminder_stop",
            reply=f"有 {len(targets)} 条都对得上：{names}。您说的是哪一条？",
            needs_input=True,
        )

    target = targets[0]
    title = target.get("title") or "提醒"

    if not target.get("is_mine"):
        return await _transfer_to_owner(db, current_user, target, raw, intent="reminder_stop", verb="停用")

    try:
        # 停用优先于删除：数据保留，想恢复时还能找回来
        await reminder_service.update_reminder(db, current_user, target["id"], enabled=False)
    except Exception as error:  # noqa: BLE001 - 统一转成老人能看懂的提示
        detail = getattr(error, "detail", None) or str(error)
        return _result(handled=True, intent="reminder_stop", reply=f"没能停掉：{detail}")

    return _result(
        handled=True,
        intent="reminder_stop",
        reply=f"「{title}」的提醒已经停了，不会再提醒您。",
        actions=[
            {"type": "notify", "level": "success", "message": f"已停用「{title}」"},
            {"type": "refresh", "target": "reminders"},
        ],
    )


async def _handle_reminder_action(
    db: AsyncSession, current_user: User, text: str, *, want: str, batch: bool = False
) -> dict:
    """want="done" 标记完成；want="confirmed" 确认收到。batch=True 表示明确要处理全部。"""
    today = await reminder_service.list_today(db, current_user)
    items = today.get("items") or []
    if not items:
        # 子女端名下本来就没有提醒。提醒的完成/确认只能由老人本人做（见
        # reminder_service._load_occurrence_for_target），这里改成指路，别让子女以为成功了。
        links = await family_service.list_links(db, current_user)
        if links.get("as_child") and not links.get("as_elder"):
            return _result(
                handled=True,
                intent=f"reminder_{want}",
                reply="提醒得由老人本人确认才能记完成。您可以打开「家人」看看他今天的完成情况。",
                actions=[{"type": "navigate", "path": "/family", "label": "家人"}],
            )
        return _result(
            handled=True,
            intent=f"reminder_{want}",
            reply="今天没有安排提醒。",
        )

    keyword = _extract_keyword(text)
    targets, status = _resolve_reminder_targets(items, keyword)

    if status == "ambiguous":
        names = "、".join(item.get("title") or "提醒" for item in targets)
        return _result(
            handled=True,
            intent=f"reminder_{want}",
            reply=f"有 {len(targets)} 条都对得上：{names}。您说的是哪一条？",
            needs_input=True,
        )

    if status in {"no_keyword", "no_match"}:
        # 没指明哪一条：只有明确表示"全部"时才批量处理；
        # 其余情况（"我把饭吃完啦"这类日常话）原样交还智能体，不猜、不写数据。
        wants_all = batch or bool(re.search(r"(都|全部|所有|全都|每一条|每条)", text))
        if not wants_all:
            return _result(handled=False)
        targets = items

    allowed = (
        REMINDER_SETTLED_STATUSES if want == "done" else REMINDER_CONFIRMABLE_STATUSES
    )
    pending = [item for item in targets if item.get("status") in allowed]

    if not pending:
        if all(item.get("status") == "done" for item in targets):
            reply = "这些提醒之前就记成完成了，不用再记一次。"
        elif any(item.get("status") == "pending" for item in targets):
            reply = "还没到提醒的时间，到点我再提醒您，到时候再记完成。"
        else:
            reply = "这些提醒已经处理过了。"
        return _result(handled=True, intent=f"reminder_{want}", reply=reply)

    done_titles: list[str] = []
    for item in pending:
        if want == "done":
            await reminder_service.finish_occurrence(
                db, current_user, item["id"], done=True
            )
        else:
            await reminder_service.confirm_occurrence(db, current_user, item["id"])
        done_titles.append(item.get("title") or "提醒")

    await db.flush()

    if want == "done":
        if len(done_titles) == 1:
            reply = f"「{done_titles[0]}」已经记成完成了，做得很好。"
        else:
            reply = f"这 {len(done_titles)} 条都记成完成了：{'、'.join(done_titles)}。做得很好。"
    else:
        if len(done_titles) == 1:
            reply = f"「{done_titles[0]}」收到，已记下了。"
        else:
            reply = f"这 {len(done_titles)} 条都收到了：{'、'.join(done_titles)}。"

    return _result(
        handled=True,
        intent=f"reminder_{want}",
        reply=reply,
        actions=[
            {"type": "refresh", "target": "reminders"},
            {"type": "notify", "level": "success", "message": "已更新提醒状态"},
        ],
    )


async def _handle_navigate(
    db: AsyncSession, current_user: User, match: re.Match, *, current_page: str | None = None
) -> dict:
    key = (match.group("page") or "").replace(" ", "").lower()
    label = _PAGE_LABELS.get(key, key)

    if key == "提醒":
        path = "/elder"
    elif key == "家人":
        # 老人进「我的家人」（只能同意/拒绝绑定），子女进「家人」照护管理页
        links = await family_service.list_links(db, current_user)
        path = "/elder/family" if links.get("as_elder") else "/family"
    elif key in {"首页", "主页"}:
        path = "/"
    else:
        path = "/agent"

    # 已经在目标页时不要"跳转"到原地，刷新一下数据就好，否则老人会以为没反应
    if current_page and current_page.rstrip("/") == path.rstrip("/"):
        return _result(
            handled=True,
            intent="navigate",
            reply=f"您现在就在「{label}」页面，我帮您刷新一下。",
            actions=[{"type": "refresh", "target": "family" if "family" in path else "reminders"}],
        )

    return _result(
        handled=True,
        intent="navigate",
        reply=f"好的，这就带您去「{label}」。",
        actions=[{"type": "navigate", "path": path, "label": label}],
    )


async def handle(
    db: AsyncSession,
    current_user: User,
    text: str,
    *,
    page: str | None = None,
) -> dict:
    """解析并执行一条指令。不是指令就返回 handled=False，由原智能体对话接管。

    ``page`` 是前端当前所在路径，只用于判断"已经在目标页"这类措辞，不参与权限判断。
    """
    raw = (text or "").strip()
    if not raw:
        return _result(handled=False)

    # 问方法而不是下命令（"怎么给小李发消息"），交给 AI 正常回答
    if _QUESTION_PATTERN.search(raw) and not raw.startswith(("帮我", "请", "麻烦")):
        return _result(handled=False)

    # 带问号或以"吗"收尾的是询问（"小李给我发消息了吗？"），不是命令
    if ("？" in raw or "?" in raw or raw.endswith("吗")) and not raw.startswith(
        ("帮我", "请", "麻烦")
    ):
        return _result(handled=False)

    # 顺序有讲究：先说"给小李发消息说提醒做完了"，应当识别成发消息而不是完成提醒
    match = _SEND_PATTERN.search(raw)
    if match and match.group("name"):
        return await _handle_family_message(
            db, current_user, name=match.group("name"), content=match.group("content") or ""
        )

    match = _TELL_PATTERN.search(raw)
    if match:
        contacts = await _load_contacts(db, current_user)
        name, content = _split_name_and_content(match.group("rest"), contacts)
        if name and _clean_content(content):
            return await _handle_family_message(
                db, current_user, name=name, content=content
            )

    # 提醒管理（建/改/停）：排在发留言之后、完成/确认之前——
    # "给小李发消息说提醒改到三点"仍应识别成发消息；
    # 否定优先："别再提醒我吃药"先判停用，再考虑创建。
    if _REMINDER_STOP_PATTERN.search(raw) and "提醒" in raw:
        return await _handle_reminder_stop(db, current_user, raw)

    if _REMINDER_CHANGE_PATTERN.search(raw) and "提醒" in raw:
        return await _handle_reminder_change(db, current_user, raw)

    create_match = _REMINDER_CREATE_PATTERN.match(raw)
    if create_match:
        return await _handle_reminder_create(db, current_user, raw, create_match.group("rest"))

    if _DONE_PATTERN.search(raw):
        return await _handle_reminder_action(db, current_user, raw, want="done")

    if _CONFIRM_ALONE_PATTERN.match(raw):
        return await _handle_reminder_action(db, current_user, raw, want="confirmed", batch=True)

    if _CONFIRM_PATTERN.search(raw) and "提醒" in raw:
        return await _handle_reminder_action(db, current_user, raw, want="confirmed")

    match = _NAVIGATE_PATTERN.search(raw)
    if match:
        return await _handle_navigate(db, current_user, match, current_page=page)

    return _result(handled=False)
