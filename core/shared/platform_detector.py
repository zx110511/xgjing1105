r"""
天机平台自动检测器 v1.0 — 运行时自动识别当前IDE平台
====================================================
TVP: @天枢(tianshu) → @洞察(dongcha) | 任务: 平台感知 | 优先级: P0

核心功能:
- 运行时自动检测当前运行平台（Qoder / Trae / Cursor / Cline）
- 避免硬编码 "trae" 导致 Qoder 对话全被错误标记
- 检测顺序: Qoder → Trae → Cursor → Cline → unknown

检测策略:
  Qoder: 检查 QODER_WORKSPACE 环境变量 或 .qoder/ 目录存在
  Trae:  检查 Trae History 目录 或 .trae/ 目录存在
  Cursor: 检查 Cursor 特征路径
  Cline:  检查 Cline 特征路径

用法:
  from core.shared.platform_detector import get_platform, PLATFORM_QODER, PLATFORM_TRAE
  platform = get_platform()  # 返回 "qoder" / "trae" / "cursor" / "cline" / "unknown"
"""

import os
from pathlib import Path

# ─── 平台常量 ───────────────────────────────────────────────
PLATFORM_QODER = "qoder"
PLATFORM_TRAE = "trae"
PLATFORM_CURSOR = "cursor"
PLATFORM_CLINE = "cline"
PLATFORM_UNKNOWN = "unknown"

SUPPORTED_PLATFORMS = [PLATFORM_QODER, PLATFORM_TRAE, PLATFORM_CURSOR, PLATFORM_CLINE]

# ─── 缓存 ───────────────────────────────────────────────────
_cached_platform: str | None = None


def _detect_qoder() -> bool:
    """检测是否运行在 Qoder IDE 环境"""
    # 1. 检查环境变量
    if os.environ.get("QODER_WORKSPACE"):
        return True
    if os.environ.get("QODER_HOME"):
        return True

    # 2. 检查 .qoder 用户目录
    qoder_home = Path.home() / ".qoder"
    if qoder_home.exists():
        return True

    # 3. 检查 Qoder AppData 目录
    qoder_appdata = Path(os.environ.get("APPDATA", "")) / "Qoder"
    if qoder_appdata.exists():
        return True

    return False


def _detect_trae() -> bool:
    """检测是否运行在 Trae IDE 环境"""
    # 1. 检查 Trae History 目录
    trae_history = Path(os.environ.get("APPDATA", "")) / "Trae CN" / "User" / "History"
    if trae_history.exists():
        return True

    # 2. 检查 .trae 项目目录
    cwd = Path.cwd()
    if (cwd / ".trae").exists():
        return True

    # 向上搜索 .trae 目录
    current = cwd
    for _ in range(5):
        if (current / ".trae").exists():
            return True
        parent = current.parent
        if parent == current:
            break
        current = parent

    return False


def _detect_cursor() -> bool:
    """检测是否运行在 Cursor IDE 环境"""
    cursor_dir = Path(os.environ.get("APPDATA", "")) / "Cursor"
    return cursor_dir.exists()


def _detect_cline() -> bool:
    """检测是否运行在 Cline 环境"""
    cline_dir = Path.home() / ".cline"
    return cline_dir.exists()


def get_platform() -> str:
    """
    自动检测当前IDE平台。

    Returns:
        str: "qoder" | "trae" | "cursor" | "cline" | "unknown"

    注意:
        - 检测结果会被缓存，后续调用直接返回缓存值
        - 如需强制重新检测，调用 reset_platform_cache()
    """
    global _cached_platform
    if _cached_platform is not None:
        return _cached_platform

    # 检测顺序: Qoder → Trae → Cursor → Cline
    if _detect_qoder():
        _cached_platform = PLATFORM_QODER
    elif _detect_trae():
        _cached_platform = PLATFORM_TRAE
    elif _detect_cursor():
        _cached_platform = PLATFORM_CURSOR
    elif _detect_cline():
        _cached_platform = PLATFORM_CLINE
    else:
        _cached_platform = PLATFORM_UNKNOWN

    return _cached_platform


def reset_platform_cache() -> None:
    """重置平台检测缓存，下次调用 get_platform() 将重新检测"""
    global _cached_platform
    _cached_platform = None


def get_platform_display_name(platform: str | None = None) -> str:
    """获取平台的可读显示名称"""
    if platform is None:
        platform = get_platform()
    return {
        PLATFORM_QODER: "Qoder IDE",
        PLATFORM_TRAE: "Trae IDE",
        PLATFORM_CURSOR: "Cursor IDE",
        PLATFORM_CLINE: "Cline",
        PLATFORM_UNKNOWN: "Unknown Platform",
    }.get(platform, f"Unknown ({platform})")


def is_qoder() -> bool:
    """便捷方法: 当前是否为 Qoder 平台"""
    return get_platform() == PLATFORM_QODER


def is_trae() -> bool:
    """便捷方法: 当前是否为 Trae 平台"""
    return get_platform() == PLATFORM_TRAE


def get_qoder_history_path() -> Path | None:
    """获取 Qoder 对话历史缓存路径"""
    qoder_home = Path.home() / ".qoder" / "cache" / "projects"
    if qoder_home.exists():
        return qoder_home
    return None


def get_trae_history_path() -> Path | None:
    """获取 Trae 对话历史路径"""
    trae_history = Path(os.environ.get("APPDATA", "")) / "Trae CN" / "User" / "History"
    if trae_history.exists():
        return trae_history
    return None


def get_history_path_for_platform(platform: str | None = None) -> Path | None:
    """获取指定平台（或当前平台）的对话历史路径"""
    if platform is None:
        platform = get_platform()

    if platform == PLATFORM_QODER:
        return get_qoder_history_path()
    elif platform == PLATFORM_TRAE:
        return get_trae_history_path()
    return None


# ─── 模块加载时打印检测结果（调试用） ────────────────────────
if __name__ == "__main__":
    plat = get_platform()
    print(f"检测平台: {get_platform_display_name(plat)} ({plat})")
    print(f"  Qoder History: {get_qoder_history_path()}")
    print(f"  Trae History:  {get_trae_history_path()}")
    print(f"  is_qoder(): {is_qoder()}")
    print(f"  is_trae():  {is_trae()}")
