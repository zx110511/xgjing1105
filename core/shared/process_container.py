"""
天机v9.1 多进程容器管理器 (TianjiV9-ProcessContainer)
===========================================================
《天机·星枢运转》— 容器化进程树架构

架构:
    天机.exe (主进程 / PID-0)
    ├── 忆库子进程 (Memory Engine)     — ICME六层记忆 + 知识图谱
    ├── 调度子进程 (Scheduler Engine)   — Agent任务编排 + TVP调度
    ├── 执行子进程 (Executor Engine)    — Agent执行器 (LLM推理池)
    ├── 运维子进程 (Ops Engine)         — 监控/自愈/审计
    ├── 安全子进程 (Security Engine)    — 合规扫描/权限/加密
    └── 性能子进程 (Performance Engine) — profiler/优化器

特性:
    - 子进程隔离 (每个引擎独立 pythonw.exe 进程)
    - stdin/stdout 管道通信 (JSON-line 协议)
    - 健康心跳 (5s 间隔)
    - 崩溃自动重启 (指数退避, 最多5次)
    - 优雅关闭 (SIGTERM → 30s → SIGKILL)
    - 资源限制 (CPU affinity + memory limit)

通信协议:
    → {"cmd": "start", "engine": "memory", "config": {...}}
    ← {"status": "ok", "pid": 12345, "port": 9001}
    ← {"status": "heartbeat", "stats": {...}}
    ← {"status": "error", "message": "..."}

设计阶段: v9.1 — 基础架构, 待 v9.1 完整实现主子进程通信
"""

import json
import os
import signal
import subprocess
import sys
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

# ──────────────────────────────────────────────
# 路径配置
# ──────────────────────────────────────────────
MODULE_DIR = Path(__file__).resolve().parent
APP_DIR = MODULE_DIR.parent
LOG_DIR = APP_DIR / "logs"
DAEMON_DIR = APP_DIR / ".daemon"
LOG_DIR.mkdir(parents=True, exist_ok=True)
DAEMON_DIR.mkdir(parents=True, exist_ok=True)

CONTAINER_LOG = LOG_DIR / "container.log"

_V81_PYTHON_DIR = APP_DIR / "python"
_PYTHONW = _V81_PYTHON_DIR / "pythonw.exe"
_PYTHON = _V81_PYTHON_DIR / "python.exe"


# ──────────────────────────────────────────────
# 数据模型
# ──────────────────────────────────────────────


class EngineType(Enum):
    MEMORY = "memory"  # 忆库引擎
    SCHEDULER = "scheduler"  # 调度引擎
    EXECUTOR = "executor"  # 执行引擎
    OPS = "ops"  # 运维引擎
    SECURITY = "security"  # 安全引擎
    PERFORMANCE = "performance"  # 性能引擎


class EngineStatus(Enum):
    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    DEGRADED = "degraded"
    STOPPING = "stopping"
    CRASHED = "crashed"


@dataclass
class EngineConfig:
    engine_type: EngineType
    entry_module: str  # 入口模块路径 (如 "core.memory_engine")
    port: int = 0  # 分配端口 (0=不绑定)
    max_restarts: int = 5  # 最大重启次数
    restart_delay: float = 5.0  # 重启延迟 (秒)
    memory_limit_mb: int = 512  # 内存限制 (MB)
    env_vars: dict[str, str] = field(default_factory=dict)


@dataclass
class EngineInstance:
    config: EngineConfig
    process: subprocess.Popen | None = None
    pid: int | None = None
    status: EngineStatus = EngineStatus.STOPPED
    started_at: float | None = None
    restart_count: int = 0
    last_heartbeat: float | None = None
    last_error: str | None = None
    stats: dict[str, Any] = field(default_factory=dict)


# ──────────────────────────────────────────────
# 默认引擎配置
# ──────────────────────────────────────────────

DEFAULT_ENGINES = [
    EngineConfig(
        engine_type=EngineType.MEMORY,
        entry_module="core.memory_engine",
        port=9001,
        memory_limit_mb=1024,
        env_vars={"TIANJI_ROLE": "memory", "TIANJI_PORT": "9001"},
    ),
    EngineConfig(
        engine_type=EngineType.SCHEDULER,
        entry_module="core.scheduler_engine",
        port=9002,
        memory_limit_mb=256,
        env_vars={"TIANJI_ROLE": "scheduler", "TIANJI_PORT": "9002"},
    ),
    EngineConfig(
        engine_type=EngineType.EXECUTOR,
        entry_module="core.executor_engine",
        port=9003,
        memory_limit_mb=2048,
        env_vars={"TIANJI_ROLE": "executor", "TIANJI_PORT": "9003"},
    ),
    EngineConfig(
        engine_type=EngineType.OPS,
        entry_module="core.ops_engine",
        port=9004,
        memory_limit_mb=256,
        env_vars={"TIANJI_ROLE": "ops", "TIANJI_PORT": "9004"},
    ),
    EngineConfig(
        engine_type=EngineType.SECURITY,
        entry_module="core.security_engine",
        port=9005,
        memory_limit_mb=256,
        env_vars={"TIANJI_ROLE": "security", "TIANJI_PORT": "9005"},
    ),
    EngineConfig(
        engine_type=EngineType.PERFORMANCE,
        entry_module="core.performance_engine",
        port=9006,
        memory_limit_mb=128,
        env_vars={"TIANJI_ROLE": "performance", "TIANJI_PORT": "9006"},
    ),
]


# ──────────────────────────────────────────────
# 容器管理器
# ──────────────────────────────────────────────


class ProcessContainer:
    """天机多进程容器管理器"""

    def __init__(self, engines: list[EngineConfig] = None):
        self._engines: dict[EngineType, EngineInstance] = {}
        self._lock = threading.RLock()
        self._running = False
        self._monitor_thread: threading.Thread | None = None
        self._on_engine_crash: Callable | None = None

        # 注册引擎
        for config in engines or DEFAULT_ENGINES:
            self._engines[config.engine_type] = EngineInstance(config=config)

        self._python_exe = str(_PYTHONW) if _PYTHONW.exists() else sys.executable

    # ──────────────── 公开 API ────────────────

    def start_all(self) -> dict[str, Any]:
        """启动所有引擎"""
        results = {}
        for engine_type in self._engines:
            results[engine_type.value] = self.start_engine(engine_type)
        self._running = True
        self._start_monitor()
        return results

    def stop_all(self, timeout: int = 30) -> dict[str, Any]:
        """停止所有引擎"""
        self._running = False
        results = {}
        threads = []

        for engine_type, instance in list(self._engines.items()):
            t = threading.Thread(
                target=lambda et=engine_type, ins=instance: results.update(
                    {et.value: self.stop_engine(et, timeout)}
                )
            )
            t.start()
            threads.append(t)

        for t in threads:
            t.join(timeout=timeout + 5)

        return results

    def start_engine(self, engine_type: EngineType) -> dict[str, Any]:
        """启动单个引擎"""
        with self._lock:
            instance = self._engines.get(engine_type)
            if not instance:
                return {
                    "status": "error",
                    "message": f"Unknown engine: {engine_type.value}",
                }

            if instance.status == EngineStatus.RUNNING:
                return {
                    "status": "ok",
                    "message": "Already running",
                    "pid": instance.pid,
                }

            try:
                instance.status = EngineStatus.STARTING
                env = os.environ.copy()
                env.update(instance.config.env_vars)
                env["TIANJI_ENGINE"] = engine_type.value

                process = subprocess.Popen(
                    [self._python_exe, "-m", instance.config.entry_module],
                    cwd=str(APP_DIR),
                    env=env,
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    creationflags=subprocess.CREATE_NO_WINDOW
                    | subprocess.CREATE_NEW_PROCESS_GROUP
                    if sys.platform == "win32"
                    else 0,
                )

                instance.process = process
                instance.pid = process.pid
                instance.started_at = time.time()
                instance.status = EngineStatus.RUNNING
                instance.restart_count = 0
                instance.last_error = None

                self._log(
                    f"引擎启动: {engine_type.value}, PID={process.pid}, 端口={instance.config.port}"
                )
                return {
                    "status": "ok",
                    "pid": process.pid,
                    "port": instance.config.port,
                }

            except Exception as e:
                instance.status = EngineStatus.CRASHED
                instance.last_error = str(e)
                self._log(f"引擎启动失败: {engine_type.value}, 错误: {e}")
                return {"status": "error", "message": str(e)}

    def stop_engine(self, engine_type: EngineType, timeout: int = 30) -> dict[str, Any]:
        """停止单个引擎"""
        with self._lock:
            instance = self._engines.get(engine_type)
            if not instance or not instance.process:
                return {"status": "ok", "message": "Not running"}

            instance.status = EngineStatus.STOPPING

            try:
                # 优雅关闭
                if sys.platform == "win32":
                    instance.process.send_signal(signal.CTRL_BREAK_EVENT)
                else:
                    instance.process.send_signal(signal.SIGTERM)

                try:
                    instance.process.wait(timeout=timeout)
                except subprocess.TimeoutExpired:
                    self._log(f"引擎未响应, 强制终止: {engine_type.value}")
                    instance.process.kill()
                    instance.process.wait(timeout=5)

                instance.status = EngineStatus.STOPPED
                instance.process = None
                instance.pid = None
                self._log(f"引擎已停止: {engine_type.value}")
                return {"status": "ok", "message": "Stopped"}

            except Exception as e:
                instance.status = EngineStatus.STOPPED
                instance.process = None
                instance.pid = None
                return {"status": "error", "message": str(e)}

    def restart_engine(self, engine_type: EngineType) -> dict[str, Any]:
        """重启单个引擎"""
        stop_result = self.stop_engine(engine_type)
        time.sleep(1)
        start_result = self.start_engine(engine_type)
        return {"stop": stop_result, "start": start_result}

    def get_status(self) -> dict[str, Any]:
        """获取所有引擎状态"""
        with self._lock:
            engines_status = {}
            for engine_type, instance in self._engines.items():
                engines_status[engine_type.value] = {
                    "status": instance.status.value,
                    "pid": instance.pid,
                    "port": instance.config.port,
                    "started_at": datetime.fromtimestamp(
                        instance.started_at
                    ).isoformat()
                    if instance.started_at
                    else None,
                    "restart_count": instance.restart_count,
                    "last_error": instance.last_error,
                    "last_heartbeat": datetime.fromtimestamp(
                        instance.last_heartbeat
                    ).isoformat()
                    if instance.last_heartbeat
                    else None,
                    "memory_limit_mb": instance.config.memory_limit_mb,
                }

            running = sum(
                1 for e in self._engines.values() if e.status == EngineStatus.RUNNING
            )

            return {
                "total_engines": len(self._engines),
                "running_engines": running,
                "stopped_engines": len(self._engines) - running,
                "engines": engines_status,
            }

    def set_crash_handler(self, handler: Callable):
        """设置崩溃回调"""
        self._on_engine_crash = handler

    # ──────────────── 内部实现 ────────────────

    def _start_monitor(self):
        """启动监控线程"""

        def _monitor_loop():
            while self._running:
                time.sleep(5)
                with self._lock:
                    for engine_type, instance in list(self._engines.items()):
                        if instance.process and instance.status == EngineStatus.RUNNING:
                            poll = instance.process.poll()
                            if poll is not None:
                                # 进程已退出
                                self._log(
                                    f"引擎崩溃: {engine_type.value}, 退出码={poll}"
                                )
                                instance.status = EngineStatus.CRASHED
                                instance.last_error = f"Exit code: {poll}"

                                # 自动重启
                                if (
                                    instance.restart_count
                                    < instance.config.max_restarts
                                ):
                                    delay = instance.config.restart_delay * (
                                        2**instance.restart_count
                                    )
                                    self._log(
                                        f"自动重启: {engine_type.value}, 重试#{instance.restart_count + 1}, 延迟{delay}s"
                                    )
                                    time.sleep(delay)
                                    result = self.start_engine(engine_type)
                                    if result.get("status") == "ok":
                                        instance.restart_count += 1
                                    else:
                                        self._log(f"重启失败: {engine_type.value}")

                                if self._on_engine_crash:
                                    try:
                                        self._on_engine_crash(engine_type, poll)
                                    except Exception:
                                        pass

        self._monitor_thread = threading.Thread(target=_monitor_loop, daemon=True)
        self._monitor_thread.start()

    def _log(self, msg: str):
        """写入容器日志"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        line = f"[{timestamp}] [CONTAINER] {msg}"
        print(line, flush=True)
        try:
            with open(CONTAINER_LOG, "a", encoding="utf-8") as f:
                f.write(line + "\n")
        except OSError:
            pass


# ──────────────────────────────────────────────
# 便捷函数
# ──────────────────────────────────────────────


def launch_container_mode():
    """快速启动容器模式 — 所有引擎独立进程"""
    container = ProcessContainer()
    container._log("启动天机v9.1 多进程容器模式...")
    results = container.start_all()
    container._log(f"启动完成: {json.dumps(results, ensure_ascii=False)}")

    try:
        while True:
            time.sleep(30)
            status = container.get_status()
            container._log(
                f"容器状态: {status['running_engines']}/{status['total_engines']} 运行中"
            )
    except KeyboardInterrupt:
        container._log("容器关闭中...")
        container.stop_all()
        container._log("容器已停止")


if __name__ == "__main__":
    launch_container_mode()
