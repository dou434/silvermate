"""轮换全部超级管理员密码。

新密码从本地 `.env` 的 ``YUXI_SUPER_ADMIN_PASSWORD`` 读取，脚本不会输出密码内容。
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import select

APP_ROOT = Path(__file__).resolve().parents[1]
for import_path in (APP_ROOT, APP_ROOT / "package"):
    if str(import_path) not in sys.path:
        sys.path.insert(0, str(import_path))

ENV_VAR_NAME = "YUXI_SUPER_ADMIN_PASSWORD"


def load_project_env() -> None:
    load_dotenv(APP_ROOT / ".env", override=False)


async def rotate_superadmin_passwords(password: str) -> int:
    from yuxi.storage.postgres.manager import pg_manager
    from yuxi.storage.postgres.models_business import User
    from yuxi.utils.auth_utils import AuthUtils

    try:
        pg_manager.initialize()
        async with pg_manager.get_async_session_context() as db:
            users = (
                await db.execute(select(User).where(User.role == "superadmin"))
            ).scalars().all()
            if not users:
                print("未找到超级管理员，无需轮换。", file=sys.stderr)
                return 1
            for user in users:
                user.password_hash = AuthUtils.hash_password(password)
            if not all(AuthUtils.verify_password(user.password_hash, password) for user in users):
                print("轮换后密码校验失败，本次变更未提交。", file=sys.stderr)
                raise RuntimeError("password verification failed")
    finally:
        await pg_manager.close()
    return 0


def main() -> int:
    load_project_env()
    password = os.getenv(ENV_VAR_NAME)
    if not password:
        print(f"缺少环境变量 {ENV_VAR_NAME}，请在 .env 中设置新密码后重试。", file=sys.stderr)
        return 1
    try:
        result = asyncio.run(rotate_superadmin_passwords(password))
    except Exception as exc:
        print(f"轮换管理员密码失败：{exc}", file=sys.stderr)
        return 1
    if result == 0:
        print("管理员密码轮换完成并校验通过。")
    return result


if __name__ == "__main__":
    raise SystemExit(main())
