"""worker 健康检查脚本的退出码：心跳存在返回 0，缺失返回 1。"""

from __future__ import annotations

import pytest

from scripts import worker_health

pytestmark = [pytest.mark.unit]


class _FakeRedis:
    def __init__(self, heartbeat: str | None) -> None:
        self.heartbeat = heartbeat
        self.closed = False

    def get(self, key: str) -> str | None:
        assert key == worker_health.HEALTH_CHECK_KEY
        return self.heartbeat

    def close(self) -> None:
        self.closed = True


def _patch_client(monkeypatch: pytest.MonkeyPatch, heartbeat: str | None) -> _FakeRedis:
    client = _FakeRedis(heartbeat)
    monkeypatch.setattr(worker_health, "create_sync_redis_client", lambda _config: client)
    return client


def test_health_check_passes_with_heartbeat(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _patch_client(monkeypatch, "j_complete=1")

    assert worker_health.main() == 0
    assert client.closed


def test_health_check_fails_without_heartbeat(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _patch_client(monkeypatch, None)

    assert worker_health.main() == 1
    assert client.closed
