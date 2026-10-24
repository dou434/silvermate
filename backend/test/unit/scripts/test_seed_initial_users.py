"""种子初始化脚本的安全回归测试。"""

from __future__ import annotations

import pytest

from scripts import seed_initial_users


def _clear_config_env(monkeypatch) -> None:
    for name in seed_initial_users.REQUIRED_ENV_VARS:
        monkeypatch.delenv(name, raising=False)


def test_load_seed_config_lists_all_missing_vars(monkeypatch):
    _clear_config_env(monkeypatch)

    with pytest.raises(seed_initial_users.SeedError) as exc_info:
        seed_initial_users.load_seed_config()

    message = str(exc_info.value)
    for name in seed_initial_users.REQUIRED_ENV_VARS:
        assert name in message


def test_load_seed_config_requires_each_var(monkeypatch):
    for name in seed_initial_users.REQUIRED_ENV_VARS:
        monkeypatch.setenv(name, "value")
    monkeypatch.delenv("YUXI_SUPER_ADMIN_PASSWORD", raising=False)

    with pytest.raises(seed_initial_users.SeedError) as exc_info:
        seed_initial_users.load_seed_config()

    assert "YUXI_SUPER_ADMIN_PASSWORD" in str(exc_info.value)


def test_main_missing_env_fails_before_initialization(monkeypatch, capsys):
    _clear_config_env(monkeypatch)
    monkeypatch.setattr(seed_initial_users, "load_project_env", lambda: None)

    def fail_if_initialized(*_args, **_kwargs):
        raise AssertionError("缺少配置时不应进入数据库初始化")

    monkeypatch.setattr(seed_initial_users, "seed_initial_users", fail_if_initialized)

    assert seed_initial_users.main() == 1
    assert "YUXI_SUPER_ADMIN_UID" in capsys.readouterr().err


def test_success_message_does_not_contain_secrets():
    config = {
        "superadmin_uid": "admin-uid",
        "superadmin_name": "测试管理员",
        "superadmin_phone_number": "13800000000",
        "superadmin_password": "super-secret-password",
        "default_user_password": "default-secret-password",
    }

    message = seed_initial_users.build_success_message(config)

    assert "13800000000" not in message
    assert "super-secret-password" not in message
    assert "default-secret-password" not in message
    assert "初始密码登录" in message
