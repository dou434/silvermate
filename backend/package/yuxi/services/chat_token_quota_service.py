"""AI 聊天问答的每日 token 额度。

额度按账号、按 Asia/Shanghai 自然日计算，只统计聊天问答（chat/resume）主运行
写入消息的 input+output tokens；知识库 embedding、OCR、评估、子智能体等内部调用
不计入。
"""

from __future__ import annotations

from datetime import datetime, time, timedelta

from fastapi import HTTPException
from sqlalchemy import Integer, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from yuxi.storage.postgres.models_business import AgentRun, Message
from yuxi.utils.datetime_utils import SHANGHAI_TZ, UTC, shanghai_now

DAILY_CHAT_TOKEN_QUOTA = 2_000_000
CHAT_RUN_TYPES = ("chat", "resume")


def _today_range_utc() -> tuple[datetime, datetime]:
    """返回 Asia/Shanghai 今天对应的 UTC 左闭右开区间（naive UTC）。"""
    day = shanghai_now().date()
    start_local = datetime.combine(day, time.min, tzinfo=SHANGHAI_TZ)
    end_local = start_local + timedelta(days=1)
    return (
        start_local.astimezone(UTC).replace(tzinfo=None),
        end_local.astimezone(UTC).replace(tzinfo=None),
    )


async def get_today_chat_token_usage(*, db: AsyncSession, uid: str) -> int:
    """统计账号今天 AI 聊天问答消耗的 input+output tokens。"""
    start, end = _today_range_utc()
    input_tokens = cast(Message.extra_metadata["usage_metadata"]["input_tokens"].as_string(), Integer)
    output_tokens = cast(Message.extra_metadata["usage_metadata"]["output_tokens"].as_string(), Integer)
    result = await db.execute(
        select(
            func.coalesce(
                func.sum(func.coalesce(input_tokens, 0) + func.coalesce(output_tokens, 0)),
                0,
            )
        )
        .select_from(Message)
        .join(AgentRun, Message.run_id == AgentRun.id)
        .where(
            AgentRun.uid == uid,
            AgentRun.run_type.in_(CHAT_RUN_TYPES),
            Message.created_at >= start,
            Message.created_at < end,
            Message.extra_metadata["usage_metadata"].isnot(None),
        )
    )
    return int(result.scalar() or 0)


async def ensure_daily_chat_token_quota(*, db: AsyncSession, uid: str) -> None:
    """额度用尽时拒绝新的聊天 run，由前端展示额度提示。"""
    used = await get_today_chat_token_usage(db=db, uid=uid)
    if used < DAILY_CHAT_TOKEN_QUOTA:
        return
    raise HTTPException(
        status_code=429,
        detail=f"今日 AI 问答额度已用完（{DAILY_CHAT_TOKEN_QUOTA // 10_000} 万 token），请明天再来。",
    )
