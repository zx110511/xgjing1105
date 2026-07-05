# -*- coding: utf-8-sig -*-
import os
import subprocess
import sys
from pathlib import Path

TIANJI_ROOT = Path(__file__).resolve().parent
PORT = 8771

env = os.environ.copy()
env["AI_MEMORY_ROOT"] = str(TIANJI_ROOT)
env["AI_MEMORY_PORT"] = str(PORT)
env["PYTHONIOENCODING"] = "utf-8"
env["PYTHONUTF8"] = "1"                # 强制Python全局UTF-8模式
env["PYTHONPATH"] = str(TIANJI_ROOT)
env["TIANJI_V91_PROTOCOL_MODE"] = "true"
env["TIANJI_V91_EVENT_WIRING"] = "true"
env["EMBEDDING_ENGINE"] = "tfidf"      # 零网络阻塞启动
env["TRANSFORMERS_OFFLINE"] = "1"      # 禁止模型下载

LOG_DIR = TIANJI_ROOT / "logs"
LOG_DIR.mkdir(exist_ok=True)
SERVER_LOG = LOG_DIR / "tianji-server.log"
ERROR_LOG = LOG_DIR / "tianji-server.err.log"

print(f"Python: {sys.executable}")
print(f"ROOT: {TIANJI_ROOT}")
print("启动uvicorn服务...")

proc = subprocess.Popen(
    [
        sys.executable,
        "-X",
        "utf8",
        "-m",
        "uvicorn",
        "server.main:app",
        "--host",
        "0.0.0.0",
        "--port",
        str(PORT),
        "--workers",
        "1",
    ],
    cwd=str(TIANJI_ROOT),
    env=env,
    stdout=open(SERVER_LOG, "a", encoding="utf-8"),
    stderr=open(ERROR_LOG, "a", encoding="utf-8"),
    creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
)
print(f"服务已启动, PID: {proc.pid}")

PID_FILE = TIANJI_ROOT / ".daemon" / "tianji.pid"
PID_FILE.parent.mkdir(parents=True, exist_ok=True)
PID_FILE.write_text(str(proc.pid))
print(f"PID已写入: {PID_FILE}")
