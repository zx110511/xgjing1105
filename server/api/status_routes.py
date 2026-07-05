# -*- coding: utf-8-sig -*-
"""status_routes.py — re-export兼容层 (SSS-PhaseB拆分后)

实际定义已拆分至子模块，本文件保持导入路径兼容。
"""

from .status_routes_persist import *
from .status_routes_module import *
from .status_routes_engine_helpers import *

# [FIX-AUDIT] import * 不导出下划线开头的名称，需显式导入
from .status_routes_persist import (
    _PERSIST_DIR, _CUMULATIVE_FILE, _HISTORY_FILE,
    _cumulative_counters, _history_snapshots, _last_snapshot_ts,
    _FULL_MODULE_CATALOG, _MODULE_ICONS,
)
from .status_routes_module import (
    _resolve_module_deps, _check_importable, _import_cache,
    get_system_stats, router,
)

