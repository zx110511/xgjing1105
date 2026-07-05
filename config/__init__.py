"""
天机系统路径配置 v8.0
=====================
天机AI平台化研究独立体系 | 自进化闭环架构

使用方式:
    from config.paths import TIANJI_ROOT, DATA_DIR, LOG_DIR, ...

设计原则:
  - 自动检测：基于文件位置自动推断根目录
  - 可覆盖：支持环境变量 TIANJI_ROOT / AI_MEMORY_ROOT 覆盖
  - 类型安全：全部使用 pathlib.Path 对象
"""

import os
from pathlib import Path


def _detect_tianji_root() -> Path:
    env_root = os.environ.get("AI_MEMORY_ROOT") or os.environ.get("TIANJI_ROOT")
    if env_root:
        root = Path(env_root).resolve()
        if root.exists():
            return root

    this_file = Path(__file__).resolve()
    candidate = this_file.parent.parent
    if (candidate / "server" / "main.py").exists() or \
       (candidate / "tianji_launcher.py").exists():
        return candidate

    cwd = Path.cwd()
    return cwd


TIANJI_ROOT = _detect_tianji_root()
PROJECT_ROOT = TIANJI_ROOT
DATA_DIR = TIANJI_ROOT / "data" / ".memory"
LOG_DIR = TIANJI_ROOT / "logs"
BACKUP_DIR = TIANJI_ROOT / "backups"
DAEMON_DIR = TIANJI_ROOT / ".daemon"
DATABASE_PATH = DATA_DIR / "icme.db"
MCP_DIR = TIANJI_ROOT / "mcp"
SERVER_DIR = TIANJI_ROOT / "server"
CORE_DIR = TIANJI_ROOT / "core"
LLM_INTEGRATION_DIR = TIANJI_ROOT / "llm_integration"
ACTIVE_MEMORY_DIR = TIANJI_ROOT / "active_memory"
TESTS_DIR = TIANJI_ROOT / "tests"
TOOLS_DIR = TIANJI_ROOT / "tools"
AGENTS_DIR = TIANJI_ROOT / "agents"
ARCHIVE_DIR = TIANJI_ROOT / "archive"


def ensure_directories_exist(*dirs: Path) -> None:
    for d in dirs:
        d.mkdir(parents=True, exist_ok=True)


def initialize_paths() -> dict:
    status = {
        "tianji_root": str(TIANJI_ROOT),
        "data_dir_exists": DATA_DIR.exists(),
        "log_dir_exists": LOG_DIR.exists(),
        "database_exists": DATABASE_PATH.exists(),
    }
    ensure_directories_exist(DATA_DIR, LOG_DIR, BACKUP_DIR, DAEMON_DIR)
    status["initialized"] = True
    return status


def get_path_info() -> dict:
    import sys
    return {
        "python_executable": sys.executable,
        "tianji_root": str(TIANJI_ROOT),
        "project_root": str(PROJECT_ROOT),
        "data_dir": str(DATA_DIR),
        "log_dir": str(LOG_DIR),
        "backup_dir": str(BACKUP_DIR),
        "daemon_dir": str(DAEMON_DIR),
        "database_path": str(DATABASE_PATH),
        "environment_override": os.environ.get("TIANJI_ROOT", "None"),
        "all_dirs_exist": all([
            TIANJI_ROOT.exists(),
            DATA_DIR.exists(),
            LOG_DIR.exists(),
        ]),
    }
