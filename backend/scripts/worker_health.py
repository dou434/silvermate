"""worker 容器健康检查：ARQ 心跳键存在即认为 worker 活着。

只做一次 Redis 查询，不初始化应用运行时；进程退出后的自动拉起由
worker_supervisor 负责，这里只负责让 `docker ps` 看到真实状态。
"""

from __future__ import annotations

import sys

from arq.constants import default_queue_name, health_check_key_suffix
from yuxi.storage.redis.manager import RedisConfig, create_sync_redis_client

HEALTH_CHECK_KEY = f"{default_queue_name}{health_check_key_suffix}"


def main() -> int:
    client = create_sync_redis_client(RedisConfig.from_env())
    try:
        heartbeat = client.get(HEALTH_CHECK_KEY)
    finally:
        client.close()

    if not heartbeat:
        print("worker health check failed: no heartbeat in Redis")
        return 1

    print(f"worker health check ok: {heartbeat}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
