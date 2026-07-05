# -*- coding: utf-8-sig -*-
"""status_routes_engine_helpers.py — 从 status_routes.py 拆分 (SSS-PhaseB)

engine_helpers功能组
源文件: status_routes.py
"""

import json
import os
import sys
import threading
import time
from typing import Any, Dict, List
from fastapi import APIRouter


def _get_engine():
    try:
        from server.deps import get_engine

        return get_engine()
    except Exception:
        return None


def _get_container():
    try:
        from server.api.container_routes import get_container

        c = get_container()
        if c:
            return c
    except Exception:
        pass
    return None


def _get_engine_stats() -> Dict[str, Any]:
    engine = _get_engine()
    if engine:
        try:
            return engine.stats()
        except Exception:
            pass
    try:
        import json
        import urllib.request

        r = urllib.request.urlopen("http://127.0.0.1:8771/api/health", timeout=3)
        h = json.loads(r.read())
        result = {}
        if h.get("total_entries") is not None:
            result["total_entries"] = h["total_entries"]
        if h.get("uptime_seconds") is not None:
            result["uptime_seconds"] = h["uptime_seconds"]
        if h.get("layers"):
            result["layers"] = {
                k: {"entry_count": v.get("entry_count", 0)}
                for k, v in h["layers"].items()
                if isinstance(v, dict)
            }
        if result:
            return result
    except Exception:
        pass
    return {"total_entries": 0, "uptime_seconds": 0}


def _get_layer_capacity() -> Dict[str, Any]:
    engine = _get_engine()
    if engine:
        try:
            cap = engine.get_layer_capacity_info()
            if cap:
                return cap
        except Exception:
            pass
    return {}


# ── 全局污染字段黑名单：禁止从模块 stats 中泄漏到 key_metrics ──
_GLOBAL_POLLUTION_FIELDS = {
    "total_entries",
    "total_accesses",
    "archive_entries",
    "data_path",
    "start_time",
    "layers",
}

