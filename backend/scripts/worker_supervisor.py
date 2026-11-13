"""开发环境 worker supervisor：arq 退出后自动拉起，源码变化时热重载。

为什么不用 `watchfiles ... arq ...`：watchfiles 只会在文件变化时重跑子进程，
arq 自己退出（例如数据库还没就绪、代码异常）后容器仍然是 Up，任务全堆在
Redis 队列里，前端表现就是「问 AI 一直没有回应」。这里由 supervisor 持有
arq 子进程：子进程退出立即重启，收到 SIGTERM 时先让 arq 优雅退出；
supervisor 自己退出则容器退出，交给 compose 的 restart 策略。
"""

from __future__ import annotations

import asyncio
import signal
import sys

from watchfiles import PythonFilter, awatch

WORKER_COMMAND = ("arq", "server.worker_main.WorkerSettings")
WATCH_DIRS = ("/app/server", "/app/package")
RESTART_DELAY_SECONDS = 2
STOP_TIMEOUT_SECONDS = 8


async def _stop_worker(process: asyncio.subprocess.Process, exit_task: asyncio.Task) -> None:
    if exit_task.done():
        return

    process.terminate()
    done, _ = await asyncio.wait({exit_task}, timeout=STOP_TIMEOUT_SECONDS)
    if not done:
        print("worker 未在时限内退出，强制结束", flush=True)
        process.kill()
        await exit_task


async def _watch_changes(changed: asyncio.Event) -> None:
    # 注意不要把外层的 stop 事件传给 awatch：它在被取消时会 set(stop_event)，
    # 会让 supervisor 把「正常重启子进程」误判成「收到停止信号」而直接退出。
    async for _ in awatch(*WATCH_DIRS, watch_filter=PythonFilter()):
        changed.set()
        return


async def _run_worker(stop: asyncio.Event) -> str:
    """跑一轮 worker，返回本轮结束原因：stop / changed / exited。"""
    process = await asyncio.create_subprocess_exec(*WORKER_COMMAND)
    exit_task = asyncio.create_task(process.wait())
    changed = asyncio.Event()
    changed_task = asyncio.create_task(changed.wait())
    stop_task = asyncio.create_task(stop.wait())
    watch_task = asyncio.create_task(_watch_changes(changed))

    done, _ = await asyncio.wait(
        {exit_task, changed_task, stop_task, watch_task},
        return_when=asyncio.FIRST_COMPLETED,
    )

    for task in (changed_task, stop_task, watch_task):
        task.cancel()
    await asyncio.gather(changed_task, stop_task, watch_task, return_exceptions=True)

    if stop.is_set():
        reason = "stop"
    elif changed.is_set():
        reason = "changed"
        print("检测到代码变化，重启 worker", flush=True)
    elif exit_task in done:
        reason = "exited"
        print(f"worker 已退出（code={process.returncode}），{RESTART_DELAY_SECONDS} 秒后重启", flush=True)
    else:
        # watcher 自己挂了（例如 inotify 资源不足），继续跑会悄悄失去热重载能力，
        # 直接退出交给容器重启更诚实。
        error = watch_task.exception()
        print(f"文件监听异常退出（{error!r}），容器将重启", flush=True)
        await _stop_worker(process, exit_task)
        raise SystemExit(1)

    await _stop_worker(process, exit_task)
    return reason


async def _sleep_unless_stopped(stop: asyncio.Event, seconds: float) -> None:
    try:
        await asyncio.wait_for(stop.wait(), timeout=seconds)
    except TimeoutError:
        pass


async def main() -> None:
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()

    def request_stop(signum: int) -> None:
        print(f"收到信号 {signum}，准备退出", flush=True)
        stop.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, request_stop, sig)

    while not stop.is_set():
        reason = await _run_worker(stop)
        if reason == "stop":
            break
        if reason == "exited":
            await _sleep_unless_stopped(stop, RESTART_DELAY_SECONDS)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        sys.exit(0)
