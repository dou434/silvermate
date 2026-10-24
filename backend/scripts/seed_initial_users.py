from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path
from typing import TypedDict

from dotenv import load_dotenv
from sqlalchemy import func, select


APP_ROOT = Path(__file__).resolve().parents[1]
for import_path in (APP_ROOT, APP_ROOT / "package"):
    import_path_str = str(import_path)
    if import_path_str not in sys.path:
        sys.path.insert(0, import_path_str)

# 初始账号全部来自环境变量，仓库里不保留任何真实手机号或明文密码。
REQUIRED_ENV_VARS = (
    "YUXI_SUPER_ADMIN_UID",
    "YUXI_SUPER_ADMIN_NAME",
    "YUXI_SUPER_ADMIN_PHONE_NUMBER",
    "YUXI_SUPER_ADMIN_PASSWORD",
    "YUXI_DEFAULT_USER_PASSWORD",
)


class DepartmentSeed(TypedDict):
    name: str
    description: str
    prefix: str
    normal_count: int


class SeedConfig(TypedDict):
    superadmin_uid: str
    superadmin_name: str
    superadmin_phone_number: str
    superadmin_password: str
    default_user_password: str


DEPARTMENTS: list[DepartmentSeed] = [
    {"name": "研发部", "description": "负责产品研发与技术平台建设", "prefix": "dev", "normal_count": 5},
    {"name": "产品部", "description": "负责产品规划、需求分析与项目推进", "prefix": "prod", "normal_count": 5},
    {"name": "运营部", "description": "负责业务运营、用户支持与内容维护", "prefix": "ops", "normal_count": 4},
]


class SeedError(Exception):
    pass


def load_project_env() -> None:
    load_dotenv(APP_ROOT / ".env", override=False)
    load_dotenv(APP_ROOT.parent / ".env", override=False)
    load_dotenv(Path.cwd() / ".env", override=False)


def load_seed_config() -> SeedConfig:
    """读取初始账号配置。缺变量时立刻失败，报错只暴露变量名，不暴露任何取值。"""
    missing = [name for name in REQUIRED_ENV_VARS if not (os.getenv(name) or "").strip()]
    if missing:
        raise SeedError(f"缺少必需的环境变量：{', '.join(missing)}。请在 .env 中补齐后重试。")

    return SeedConfig(
        superadmin_uid=os.environ["YUXI_SUPER_ADMIN_UID"].strip(),
        superadmin_name=os.environ["YUXI_SUPER_ADMIN_NAME"].strip(),
        superadmin_phone_number=os.environ["YUXI_SUPER_ADMIN_PHONE_NUMBER"].strip(),
        superadmin_password=os.environ["YUXI_SUPER_ADMIN_PASSWORD"],
        default_user_password=os.environ["YUXI_DEFAULT_USER_PASSWORD"],
    )


async def ensure_uninitialized(session) -> None:
    from yuxi.storage.postgres.models_business import User

    user_count = await session.scalar(select(func.count(User.id)))
    if user_count:
        raise SeedError(f"系统已初始化：users 表已有 {user_count} 个用户，脚本已退出。")

    superadmin_count = await session.scalar(select(func.count(User.id)).where(User.role == "superadmin"))
    if superadmin_count:
        raise SeedError("系统已初始化：已存在超级管理员，脚本已退出。")


async def seed_initial_users(config: SeedConfig) -> None:
    from yuxi.utils.auth_utils import AuthUtils
    from yuxi.storage.postgres.manager import pg_manager
    from yuxi.storage.postgres.models_business import Department, User
    from yuxi.utils.datetime_utils import utc_now_naive

    try:
        pg_manager.initialize()
        await pg_manager.create_business_tables()
        await pg_manager.ensure_business_schema()

        async with pg_manager.get_async_session_context() as session:
            await ensure_uninitialized(session)

            departments: dict[str, Department] = {}
            for department_seed in DEPARTMENTS:
                department = Department(
                    name=department_seed["name"],
                    description=department_seed["description"],
                )
                session.add(department)
                departments[department_seed["prefix"]] = department

            await session.flush()

            users = [
                User(
                    username=config["superadmin_name"],
                    uid=config["superadmin_uid"],
                    phone_number=config["superadmin_phone_number"],
                    password_hash=AuthUtils.hash_password(config["superadmin_password"]),
                    role="superadmin",
                    department_id=departments["dev"].id,
                    last_login=utc_now_naive(),
                )
            ]

            for department_seed in DEPARTMENTS:
                department = departments[department_seed["prefix"]]
                for index in range(1, 3):
                    users.append(
                        User(
                            username=f"{department_seed['name']}管理员{index}",
                            uid=f"{department_seed['prefix']}_admin_{index}",
                            password_hash=AuthUtils.hash_password(config["default_user_password"]),
                            role="admin",
                            department_id=department.id,
                        )
                    )
                for index in range(1, department_seed["normal_count"] + 1):
                    users.append(
                        User(
                            username=f"{department_seed['name']}用户{index}",
                            uid=f"{department_seed['prefix']}_user_{index:02d}",
                            password_hash=AuthUtils.hash_password(config["default_user_password"]),
                            role="user",
                            department_id=department.id,
                        )
                    )

            session.add_all(users)
    finally:
        await pg_manager.close()


def main() -> int:
    load_project_env()
    try:
        config = load_seed_config()
        asyncio.run(seed_initial_users(config))
    except SeedError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"初始化种子用户失败：{exc}", file=sys.stderr)
        return 1

    print(build_success_message(config))
    return 0


def build_success_message(config: SeedConfig) -> str:
    """生成成功提示文案，不包含密码、手机号等敏感值。"""
    return (
        f"初始化完成：已创建超级管理员 {config['superadmin_name']}（{config['superadmin_uid']}）、"
        "3 个部门、6 个部门管理员和 14 个普通用户。\n"
        "请使用环境变量中配置的初始密码登录，并立即修改密码。"
    )


if __name__ == "__main__":
    raise SystemExit(main())
