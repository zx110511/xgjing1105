# -*- coding: utf-8-sig -*-
"""main_health.py — health功能组 (SSS-PhaseB拆分+PhaseE修复)

从 main.py 拆分，补充缺失的app/engine导入。
"""

import os
import time

import server.main  # 直接引用模块变量, 避免 from X import Y 的 global 失效
from server.deps import engine
from server.main import _START_TIME, app


def _get_embedding_ready() -> bool:
    """动态检测embedding引擎是否就绪"""
    try:
        if hasattr(engine, "_embedding_model") and engine._embedding_model is not None:
            return True
        if hasattr(engine, "_embedder") and engine._embedder is not None:
            return True
        cap = engine.get_layer_capacity_info()
        return bool(cap)
    except Exception:
        return False


def _get_protocol_mode_active() -> bool:
    """动态检测Protocol模式是否激活"""
    if server.main._PROTOCOL_MODE_ACTIVE:
        return True
    try:
        from core.shared.config import TIANJI_V91_PROTOCOL_MODE

        if TIANJI_V91_PROTOCOL_MODE:
            from server.deps import get_memory_cores

            if get_memory_cores() is not None:
                return True
    except Exception:
        pass
    return False


def _get_event_wiring_active() -> bool:
    """动态检测Event Wiring是否激活"""
    if server.main._EVENT_WIRING_ACTIVE:
        return True
    try:
        from server.deps import get_event_bus

        eb = get_event_bus()
        if eb is not None and hasattr(eb, "_subscribers"):
            return len(getattr(eb, "_subscribers", {})) > 0
    except Exception:
        pass
    return False


def health_check():
    from core.shared.models import (
        HealthStatus,  # pyright: ignore[reportImplicitRelativeImport]
    )

    capacity = engine.get_layer_capacity_info()
    return HealthStatus(
        status="healthy",
        version="9.1.0",
        edition=os.environ.get("TIANJI_EDITION", "source-v9.1"),
        engine_ready=True,
        embedding_ready=_get_embedding_ready(),
        layers=capacity,
        uptime_seconds=round(time.time() - _START_TIME, 1),
        protocol_mode=_get_protocol_mode_active(),
        event_wiring=_get_event_wiring_active(),
    )


@app.get("/api/stats")
def get_stats():
    from core.shared.models import (
        MemoryStats,  # pyright: ignore[reportImplicitRelativeImport]
    )

    s = engine.stats()
    return MemoryStats(**s)


@app.get("/api/storage_health")
def storage_health():
    """v9.1 P1: 存储层健康检查端点

    检查项:
    - SQLite数据库是否存在、可连接
    - memories表是否存在、行数
    - FTS5索引是否正常
    - WAL文件大小
    - 磁盘剩余空间
    - 缓存命中率
    - SQLite→JSON回退状态
    """
    result = {
        "status": "unknown",
        "backend": "json",
        "db_path": None,
        "db_exists": False,
        "db_size_mb": 0,
        "wal_size_mb": 0,
        "disk_free_mb": 0,
        "tables": {},
        "issues": [],
        "written_since_start": 0,
        "errors_since_start": 0,
        "fallback_count": 0,
        "uptime_seconds": round(time.time() - _START_TIME, 1),
    }

    # 检查是否使用SQLite后端
    if hasattr(engine, "_use_sqlite") and engine._use_sqlite:
        result["backend"] = "sqlite"

        # 获取SQLiteStore的健康信息
        if hasattr(engine, "_store") and hasattr(engine._store, "get_db_health"):
            try:
                db_health = engine._store.get_db_health()
                result["db_path"] = db_health.get("db_path")
                result["db_exists"] = db_health.get("db_exists", False)
                result["db_size_mb"] = db_health.get("db_size_mb", 0)
                result["wal_size_mb"] = db_health.get("wal_size_mb", 0)
                result["disk_free_mb"] = db_health.get("disk_free_mb", 0)
                result["table_stats"] = db_health.get("table_stats", {})
                result["written_since_start"] = db_health.get("total_writes", 0)
                result["errors_since_start"] = db_health.get("errors", 0)
                result["cache_hit_rate"] = db_health.get("cache_hit_rate", 0)

                # 判断健康状态
                if not db_health.get("db_exists"):
                    result["status"] = "critical"
                    result["issues"].append("数据库文件不存在")
                elif db_health.get("db_connect_error"):
                    result["status"] = "critical"
                    result["issues"].append(
                        f"无法连接: {db_health['db_connect_error']}"
                    )
                else:
                    mem_tbl = db_health.get("table_stats", {}).get("memories", {})
                    if not mem_tbl.get("ok"):
                        result["status"] = "degraded"
                        result["issues"].append(
                            f"memories表异常: {mem_tbl.get('error', 'unknown')}"
                        )
                    elif result["disk_free_mb"] > 0 and result["disk_free_mb"] < 50:
                        result["status"] = "degraded"
                        result["issues"].append(
                            f"磁盘空间不足: {result['disk_free_mb']}MB"
                        )
                    else:
                        result["status"] = "healthy"
            except Exception as e:
                result["status"] = "error"
                result["issues"].append(f"get_db_health()异常: {e}")
        else:
            # 回退: 直接检查数据库
            try:
                db_path = engine._data_path / "icme.db"
                result["db_path"] = str(db_path)
                result["db_exists"] = db_path.exists()
                if db_path.exists():
                    result["db_size_mb"] = round(
                        db_path.stat().st_size / (1024 * 1024), 2
                    )
                    import sqlite3

                    conn = sqlite3.connect(str(db_path), timeout=5)
                    cnt = conn.execute("SELECT COUNT(*) FROM memories").fetchone()[0]
                    result["table_stats"]["memories"] = {"rows": cnt, "ok": True}
                    conn.close()
                    result["status"] = "healthy"
                else:
                    result["status"] = "degraded"
                    result["issues"].append("数据库文件不存在，使用JSON回退")
            except Exception as e:
                result["status"] = "error"
                result["issues"].append(str(e))
    else:
        result["backend"] = "json"
        result["status"] = "healthy"

    # 回退计数
    if hasattr(engine, "_errors"):
        result["fallback_count"] = engine._errors

    return result
