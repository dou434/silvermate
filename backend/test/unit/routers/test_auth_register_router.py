"""自助注册端点的单元测试。

不依赖运行中的 Docker 服务：数据库用 sqlite in-memory，
仓储层用不落库的替身替换，只验证注册路径的校验与权限边界。
"""

from __future__ import annotations

import pytest
import pytest_asyncio
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from server.routers import auth_router
from server.routers.auth_router import RegisterRequest, register
from yuxi.storage.postgres.models_business import Base, User

pytestmark = [pytest.mark.asyncio, pytest.mark.unit]


@pytest_asyncio.fixture()
async def db_session():
    """提供仅用于写操作日志的 sqlite 会话。"""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as db:
        yield db
    await engine.dispose()


def _make_fake_repo(*, existing_uid: str | None = None, existing_phone: str | None = None):
    """构造 UserRepository 替身，只实现注册路径用到的方法。

    Returns:
        tuple: (替身实例, 记录 create() 入参的字典)
    """
    created: dict = {}

    class _FakeRepo:
        async def get_by_uid(self, uid: str):
            if existing_uid is not None and existing_uid == uid:
                return User(uid=existing_uid, username="existing", password_hash="$argon2id$placeholder")
            return None

        async def exists_by_phone(self, phone: str) -> bool:
            return existing_phone is not None and existing_phone == phone

        async def create(self, data: dict):
            created.update(data)
            user = User(**data)
            user.id = 99
            return user

    return _FakeRepo(), created


async def test_register_creates_normal_user_without_department(db_session, monkeypatch):
    repo, created = _make_fake_repo()
    monkeypatch.setattr(auth_router, "UserRepository", lambda: repo)

    result = await register(
        RegisterRequest(uid="elder_01", password="secret123", username="张阿姨"),
        db=db_session,
    )

    assert result["token_type"] == "bearer"
    assert result["access_token"]
    assert result["role"] == "user"
    assert result["department_id"] is None
    assert result["uid"] == "elder_01"
    assert result["username"] == "张阿姨"

    # 角色与部门强制由服务端决定，不接受客户端输入
    assert created["role"] == "user"
    assert created["department_id"] is None
    assert created["password_hash"].startswith("$argon2")


async def test_register_defaults_display_name_to_uid(db_session, monkeypatch):
    repo, created = _make_fake_repo()
    monkeypatch.setattr(auth_router, "UserRepository", lambda: repo)

    await register(RegisterRequest(uid="child_01", password="secret123"), db=db_session)

    assert created["username"] == "child_01"


async def test_register_rejects_duplicate_uid(db_session, monkeypatch):
    repo, _ = _make_fake_repo(existing_uid="elder_01")
    monkeypatch.setattr(auth_router, "UserRepository", lambda: repo)

    with pytest.raises(HTTPException) as exc_info:
        await register(RegisterRequest(uid="elder_01", password="secret123"), db=db_session)

    assert exc_info.value.status_code == 409


async def test_register_rejects_duplicate_phone(db_session, monkeypatch):
    repo, _ = _make_fake_repo(existing_phone="13800138000")
    monkeypatch.setattr(auth_router, "UserRepository", lambda: repo)

    with pytest.raises(HTTPException) as exc_info:
        await register(
            RegisterRequest(uid="elder_02", password="secret123", phone_number="138-0013-8000"),
            db=db_session,
        )

    assert exc_info.value.status_code == 409


async def test_register_rejects_invalid_uid_format(db_session, monkeypatch):
    repo, _ = _make_fake_repo()
    monkeypatch.setattr(auth_router, "UserRepository", lambda: repo)

    with pytest.raises(HTTPException) as exc_info:
        await register(RegisterRequest(uid="a b", password="secret123"), db=db_session)

    assert exc_info.value.status_code == 400


async def test_register_rejects_invalid_phone_format(db_session, monkeypatch):
    repo, _ = _make_fake_repo()
    monkeypatch.setattr(auth_router, "UserRepository", lambda: repo)

    with pytest.raises(HTTPException) as exc_info:
        await register(RegisterRequest(uid="elder_03", password="secret123", phone_number="12345"), db=db_session)

    assert exc_info.value.status_code == 400


async def test_register_request_rejects_short_password():
    with pytest.raises(ValidationError):
        RegisterRequest(uid="elder_04", password="123")


async def test_register_ignores_role_supplied_by_client(db_session, monkeypatch):
    """客户端即使传入 role，注册结果也必须是普通用户。"""
    repo, created = _make_fake_repo()
    monkeypatch.setattr(auth_router, "UserRepository", lambda: repo)

    payload = RegisterRequest.model_validate(
        {"uid": "child_02", "password": "secret123", "role": "superadmin"}
    )
    result = await register(payload, db=db_session)

    assert created["role"] == "user"
    assert result["role"] == "user"


async def test_register_defaults_identity_to_elder(db_session, monkeypatch):
    """不传身份时按长辈处理，兼容既有调用方。"""
    repo, created = _make_fake_repo()
    monkeypatch.setattr(auth_router, "UserRepository", lambda: repo)

    result = await register(RegisterRequest(uid="elder_05", password="secret123"), db=db_session)

    assert created["identity"] == "elder"
    assert result["identity"] == "elder"


async def test_register_persists_child_identity(db_session, monkeypatch):
    """选择子女身份时落库并原样返回。"""
    repo, created = _make_fake_repo()
    monkeypatch.setattr(auth_router, "UserRepository", lambda: repo)

    result = await register(
        RegisterRequest(uid="child_03", password="secret123", identity="child"),
        db=db_session,
    )

    assert created["identity"] == "child"
    assert result["identity"] == "child"


async def test_register_request_rejects_unknown_identity():
    """身份只允许 elder / child，其它取值直接 422。"""
    with pytest.raises(ValidationError):
        RegisterRequest(uid="elder_06", password="secret123", identity="admin")
