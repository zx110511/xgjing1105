"""灵犀探针 — 天机v9.1 代码智能分析工具集"""

from .dependency_scanner import (
    build_dependency_graph,
    calc_coupling,
    detect_cycles,
    find_dead_code,
    scan_and_report,
    scan_imports,
)
