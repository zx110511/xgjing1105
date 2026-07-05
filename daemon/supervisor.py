"""
天机v9.1 轻量级守护进程监督器 (TianjiV9-Supervisor)
===========================================================
《天机·星枢运转》— 守护进程自恢复机制

功能:
    - 心跳检测 (heartbeat file / PID存活)
    - 崩溃自动拉起 (指数退避重试)
    - 最大重试次数保护 (防止无限重启循环)
    - 恢复事件记录 (logs/supervisor.log)

架构:
    独立子进程 (与主守护进程同级)
    ├── 心跳轮询 (每10s检查 daemon heartbeat)
    ├── 进程存活检测 (PID文件 + OS进程查询)
    ├── 自动拉起 (subprocess 重启 daemon)
    └── 日志审计 (每次恢复记录详细信息)

用法:
    python daemon/supervisor.py                    # 前台运行
    pythonw daemon/supervisor.py                   # 后台无窗口运行
    python daemon/supervisor.py --oneshot          # 单次检查后退出

集成:
    托盘启动器自动检测并启动 supervisor (通过 tianji_launcher.py)
"""

import json
import os
import signal
import subprocess
import sys
import time
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any

# ──────────────────────────────────────────────
# 路径配置
# ──────────────────────────────────────────────
SUPERVISOR_DIR = Path(__file__).resolve().parent
APP_DIR = SUPERVISOR_DIR.parent  # 天机v9.1 根目录
os.chdir(str(APP_DIR))
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

LOG_DIR = APP_DIR / "logs"
DAEMON_DIR = APP_DIR / ".daemon"
LOG_DIR.mkdir(parents=True, exist_ok=True)
DAEMON_DIR.mkdir(parents=True, exist_ok=True)

SUPERVISOR_LOG = LOG_DIR / "supervisor.log"
SUPERVISOR_PID = DAEMON_DIR / "supervisor.pid"
DAEMON_PID_FILE = DAEMON_DIR / "tianji_launcher.pid"
DAEMON_HEARTBEAT = DAEMON_DIR / ".scheduler_heartbeat"

# 守护进程启动命令
_V81_PYTHON_DIR = APP_DIR / "python"
_PYTHONW = _V81_PYTHON_DIR / "pythonw.exe"
_PYTHON = _V81_PYTHON_DIR / "python.exe"
LAUNCHER_SCRIPT = APP_DIR / "launcher" / "tianji_launcher.py"

# ──────────────────────────────────────────────
# 配置常量
# ──────────────────────────────────────────────
HEARTBEAT_INTERVAL = 10  # 心跳检查间隔 (秒)
HEARTBEAT_TIMEOUT = 60  # 心跳超时 (秒) — 超过此时间未更新视为失联
STARTUP_GRACE = 30  # 启动宽限期 (秒) — 刚启动时不触发恢复
MAX_RETRIES = 5  # 最大连续重试次数
RETRY_BASE_DELAY = 5  # 基础重试延迟 (秒)
RETRY_MAX_DELAY = 300  # 最大重试延迟 (秒, 指数退避上限)
COOLDOWN_PERIOD = 600  # 冷却周期 (秒) — 连续失败超过MAX_RETRIES后冷却
STABILITY_WINDOW = 300  # 稳定窗口 (秒) — 运行超过此时间重置重试计数


def supervisor_log(msg: str):
    """写入监督器日志"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{timestamp}] [SUPERVISOR] {msg}"
    print(line, flush=True)
    try:
        with open(SUPERVISOR_LOG, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError:
        pass


def is_process_alive(pid: int) -> bool:
    """检查指定PID的进程是否存活"""
    try:
        import psutil

        return psutil.pid_exists(pid)
    except ImportError:
        # Fallback: 使用 tasklist
        try:
            result = subprocess.run(
                ["tasklist", "/FI", f"PID eq {pid}"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            return f"{pid}" in result.stdout and "No tasks" not in result.stdout
        except Exception:
            return False


def read_pid_file(pid_file: Path) -> int | None:
    """读取PID文件"""
    try:
        if pid_file.exists():
            content = pid_file.read_text().strip()
            return int(content)
    except (ValueError, OSError):
        pass
    return None


def get_heartbeat_age() -> float | None:
    """获取心跳文件的年龄 (秒), None 表示文件不存在"""
    try:
        if DAEMON_HEARTBEAT.exists():
            mtime = DAEMON_HEARTBEAT.stat().st_mtime
            return time.time() - mtime
    except OSError:
        pass
    return None


def start_daemon() -> subprocess.Popen | None:
    """启动守护进程"""
    supervisor_log("正在启动天机守护进程...")

    python_exe = (
        str(_PYTHONW)
        if _PYTHONW.exists()
        else sys.executable.replace("python.exe", "pythonw.exe")
    )
    launcher = str(LAUNCHER_SCRIPT)

    try:
        process = subprocess.Popen(
            [python_exe, launcher],
            cwd=str(APP_DIR),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW | subprocess.DETACHED_PROCESS
            if sys.platform == "win32"
            else 0,
        )
        supervisor_log(f"守护进程已启动, PID={process.pid}")
        return process
    except Exception as e:
        supervisor_log(f"守护进程启动失败: {e}")
        return None


def stop_daemon(pid: int):
    """优雅停止守护进程"""
    supervisor_log(f"正在停止守护进程 PID={pid}...")
    try:
        if sys.platform == "win32":
            subprocess.run(
                ["taskkill", "/PID", str(pid)], capture_output=True, timeout=10
            )
        else:
            os.kill(pid, signal.SIGTERM)
        time.sleep(2)
        if is_process_alive(pid):
            if sys.platform == "win32":
                subprocess.run(
                    ["taskkill", "/F", "/PID", str(pid)], capture_output=True, timeout=5
                )
            else:
                os.kill(pid, signal.SIGKILL)
    except Exception as e:
        supervisor_log(f"停止守护进程异常: {e}")


def run_supervisor_loop():
    """监督器主循环"""
    supervisor_log("=" * 60)
    supervisor_log("天机v9.1 守护进程监督器启动")
    supervisor_log(f"工作目录: {APP_DIR}")
    supervisor_log(f"心跳检查间隔: {HEARTBEAT_INTERVAL}s")
    supervisor_log(f"最大重试次数: {MAX_RETRIES}")
    supervisor_log(f"冷却周期: {COOLDOWN_PERIOD}s")
    supervisor_log("=" * 60)

    # 写入自己的PID
    SUPERVISOR_PID.write_text(str(os.getpid()))

    retry_count = 0
    last_start_time: float | None = None
    daemon_pid: int | None = None

    try:
        while True:
            try:
                # 1. 检查守护进程是否存活
                daemon_pid = read_pid_file(DAEMON_PID_FILE)
                heartbeat_age = get_heartbeat_age()

                is_alive = False
                if daemon_pid and is_process_alive(daemon_pid):
                    if heartbeat_age is not None and heartbeat_age <= HEARTBEAT_TIMEOUT:
                        is_alive = True
                        # 稳定运行 — 重置重试计数
                        if (
                            last_start_time
                            and (time.time() - last_start_time) > STABILITY_WINDOW
                        ):
                            if retry_count > 0:
                                supervisor_log(
                                    f"守护进程稳定运行 {STABILITY_WINDOW}s, 重置重试计数 (原={retry_count})"
                                )
                                retry_count = 0
                    elif (
                        heartbeat_age is not None and heartbeat_age > HEARTBEAT_TIMEOUT
                    ):
                        supervisor_log(
                            f"警告: 守护进程心跳超时 ({heartbeat_age:.0f}s > {HEARTBEAT_TIMEOUT}s)"
                        )
                else:
                    if daemon_pid:
                        supervisor_log(f"警告: 守护进程 PID={daemon_pid} 不存在")
                    # 检查是否在启动宽限期内
                    if (
                        last_start_time
                        and (time.time() - last_start_time) < STARTUP_GRACE
                    ):
                        pass  # 继续等待
                    else:
                        is_alive = False

                if not is_alive and (
                    last_start_time is None
                    or (time.time() - last_start_time) > STARTUP_GRACE
                ):
                    # 2. 需要恢复
                    if retry_count >= MAX_RETRIES:
                        # 冷却期
                        supervisor_log(
                            f"错误: 已达最大重试次数 ({MAX_RETRIES}), 进入冷却期 {COOLDOWN_PERIOD}s"
                        )
                        time.sleep(COOLDOWN_PERIOD)
                        retry_count = 0
                        supervisor_log("冷却期结束, 重置重试计数")
                        continue

                    # 计算指数退避延迟
                    delay = min(RETRY_BASE_DELAY * (2**retry_count), RETRY_MAX_DELAY)
                    supervisor_log(
                        f"守护进程失联! 重试 #{retry_count + 1}/{MAX_RETRIES}, 延迟 {delay}s"
                    )

                    time.sleep(delay)

                    # 启动守护进程
                    process = start_daemon()
                    if process:
                        last_start_time = time.time()
                        retry_count += 1
                        supervisor_log(
                            f"重启完成, 新PID={process.pid}, 重试计数={retry_count}"
                        )
                    else:
                        retry_count += 1
                        supervisor_log(f"重启失败! 重试计数={retry_count}")

            except Exception as e:
                supervisor_log(f"监督循环异常: {e}")
                traceback.print_exc()

            time.sleep(HEARTBEAT_INTERVAL)

    except KeyboardInterrupt:
        supervisor_log("收到中断信号, 监督器退出")
    finally:
        if SUPERVISOR_PID.exists():
            SUPERVISOR_PID.unlink()
        supervisor_log("监督器已停止")


def run_oneshot() -> dict[str, Any]:
    """单次检查模式 — 返回状态供外部调用"""
    daemon_pid = read_pid_file(DAEMON_PID_FILE)
    heartbeat_age = get_heartbeat_age()

    result = {
        "timestamp": datetime.now().isoformat(),
        "supervisor_running": SUPERVISOR_PID.exists(),
        "daemon": {
            "pid": daemon_pid,
            "alive": daemon_pid and is_process_alive(daemon_pid)
            if daemon_pid
            else False,
            "heartbeat_age_seconds": round(heartbeat_age, 1) if heartbeat_age else None,
            "heartbeat_ok": heartbeat_age is not None
            and heartbeat_age <= HEARTBEAT_TIMEOUT,
        },
    }

    supervisor_log(f"单次检查: {json.dumps(result, ensure_ascii=False)}")
    return result


# ──────────────────────────────────────────────
# 入口
# ──────────────────────────────────────────────
if __name__ == "__main__":
    if "--oneshot" in sys.argv:
        result = run_oneshot()
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        run_supervisor_loop()
