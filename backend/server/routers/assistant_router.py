"""问 AI 界面的界面指令路由。

前端在把一句话发给智能体之前先问一次这里：如果能识别成指令（给家人发留言、
把提醒标记完成、打开某个页面），就由服务端直接执行并返回结果；识别不了就返回
``handled=false``，前端继续走原来的智能体对话，不影响正常问答。
"""

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from yuxi.services import assistant_command_service
from yuxi.storage.postgres.models_business import User

from server.utils.auth_middleware import get_db, get_required_user

assistant = APIRouter(prefix="/assistant", tags=["assistant"])


class CommandRequest(BaseModel):
    text: str = Field(min_length=1, max_length=500, description="用户原话")
    page: str | None = Field(default=None, description="当前页面路径，可选，用于回复措辞")


@assistant.post("/command")
async def run_assistant_command(
    payload: CommandRequest,
    current_user: User = Depends(get_required_user),
    db: AsyncSession = Depends(get_db),
):
    """尝试把一句话当成界面指令执行；不是指令时返回 handled=false。"""
    return await assistant_command_service.handle(
        db, current_user, payload.text, page=payload.page
    )
