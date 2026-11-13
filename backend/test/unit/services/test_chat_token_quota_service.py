from __future__ import annotations

from datetime import datetime

import pytest
import pytest_asyncio
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from yuxi.services import chat_token_quota_service as quota
from yuxi.storage.postgres.models_business import AgentRun, Base, Conversation, Message
from yuxi.utils.datetime_utils import SHANGHAI_TZ

pytestmark = [pytest.mark.asyncio, pytest.mark.unit]

FIXED_NOW = datetime(2026, 10, 29, 12, 0, tzinfo=SHANGHAI_TZ)
TODAY_UTC = datetime(2026, 10, 29, 4, 0)
YESTERDAY_UTC = datetime(2026, 10, 28, 15, 59)


@pytest_asyncio.fixture()
async def session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as db:
        yield db
    await engine.dispose()


@pytest.fixture(autouse=True)
def fixed_today(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(quota, "shanghai_now", lambda: FIXED_NOW)


async def _seed_run(
    db,
    *,
    run_id: str,
    uid: str = "user-1",
    run_type: str = "chat",
    input_tokens: int | str = 0,
    output_tokens: int | str = 0,
    created_at: datetime = TODAY_UTC,
    thread_id: str | None = None,
    with_usage: bool = True,
) -> None:
    thread_id = thread_id or f"thread-{uid}"
    conversation = (
        await db.execute(select(Conversation).where(Conversation.thread_id == thread_id))
    ).scalar_one_or_none()
    if conversation is None:
        conversation = Conversation(thread_id=thread_id, uid=uid, agent_id="default-chatbot", status="active")
        db.add(conversation)
        await db.flush()

    run = AgentRun(
        id=run_id,
        conversation_thread_id=thread_id,
        agent_slug="default-chatbot",
        uid=uid,
        status="completed",
        request_id=f"req-{run_id}",
        conversation_id=conversation.id,
        run_type=run_type,
        input_payload={},
    )
    db.add(run)
    db.add(
        Message(
            conversation_id=conversation.id,
            role="assistant",
            content="answer",
            run_id=run_id,
            created_at=created_at,
            extra_metadata={"usage_metadata": {"input_tokens": input_tokens, "output_tokens": output_tokens}}
            if with_usage
            else {},
        )
    )
    await db.commit()


async def test_today_usage_only_counts_current_user_chat_runs(session):
    await _seed_run(session, run_id="chat-today", input_tokens=100, output_tokens=50)
    await _seed_run(session, run_id="resume-today", run_type="resume", input_tokens=20, output_tokens=10)
    await _seed_run(session, run_id="subagent-today", run_type="subagent", input_tokens=1000, output_tokens=1000)
    await _seed_run(session, run_id="other-user", uid="user-2", input_tokens=300, output_tokens=300)
    await _seed_run(
        session,
        run_id="chat-yesterday",
        input_tokens=999,
        output_tokens=999,
        created_at=YESTERDAY_UTC,
    )
    await _seed_run(session, run_id="chat-no-usage", with_usage=False)
    await _seed_run(
        session,
        run_id="chat-string-usage",
        input_tokens="7",
        output_tokens="3",
    )

    assert await quota.get_today_chat_token_usage(db=session, uid="user-1") == 190


async def test_quota_allows_below_limit_and_rejects_at_limit(session):
    await _seed_run(session, run_id="almost-full", input_tokens=1_999_999, output_tokens=0)
    await quota.ensure_daily_chat_token_quota(db=session, uid="user-1")

    await _seed_run(session, run_id="full", input_tokens=1, output_tokens=0)
    with pytest.raises(HTTPException) as exc_info:
        await quota.ensure_daily_chat_token_quota(db=session, uid="user-1")

    assert exc_info.value.status_code == 429
    assert "200 万 token" in exc_info.value.detail
