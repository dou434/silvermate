"""本地 TCP 端口转发：172.24.64.1:7898 -> 127.0.0.1:7897

用途：
    Docker Desktop 的 Linux 虚拟机无法直接访问宿主机回环地址（127.0.0.1）上的
    HTTP 代理。本脚本把 WSL 虚拟网卡地址上的 7898 端口转发到宿主机回环的 7897，
    使 Docker 守护进程能够通过它拉取镜像。

设计说明：
    - 不使用 netsh portproxy：它需要管理员权限，且依赖 IP Helper 服务。
    - 只绑定 172.24.64.1（WSL 虚拟网卡），不对外暴露到局域网。
    - 纯 asyncio 双向转发，无第三方依赖。

用法：
    python tools/proxy_forward.py

停止：
    Ctrl+C 或结束该进程
"""

from __future__ import annotations

import asyncio

LISTEN_HOST = "172.24.64.1"
LISTEN_PORT = 7898
TARGET_HOST = "127.0.0.1"
TARGET_PORT = 7897

BUFFER_SIZE = 65536


async def pipe(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
    """单向搬运数据，任一端关闭即停止。"""
    try:
        while True:
            data = await reader.read(BUFFER_SIZE)
            if not data:
                break
            writer.write(data)
            await writer.drain()
    except (ConnectionResetError, BrokenPipeError, asyncio.CancelledError):
        pass
    finally:
        try:
            writer.close()
        except Exception:
            pass


async def handle_client(
    client_reader: asyncio.StreamReader, client_writer: asyncio.StreamWriter
) -> None:
    """为一个客户端连接建立到目标的隧道，双向并发搬运。"""
    try:
        target_reader, target_writer = await asyncio.open_connection(TARGET_HOST, TARGET_PORT)
    except OSError as exc:
        print(f"[warn] 连接目标代理失败: {exc}", flush=True)
        client_writer.close()
        return

    await asyncio.gather(
        pipe(client_reader, target_writer),
        pipe(target_reader, client_writer),
    )


async def main() -> None:
    server = await asyncio.start_server(handle_client, LISTEN_HOST, LISTEN_PORT)
    print(f"[ok] {LISTEN_HOST}:{LISTEN_PORT} -> {TARGET_HOST}:{TARGET_PORT}", flush=True)
    async with server:
        await server.serve_forever()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("[stop] 已停止", flush=True)
