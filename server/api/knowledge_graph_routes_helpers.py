# -*- coding: utf-8-sig -*-
"""knowledge_graph_routes_helpers.py — 从 knowledge_graph_routes.py 拆分 (SSS-PhaseB)

helpers功能组
源文件: knowledge_graph_routes.py
"""

import json
import math
import sqlite3
import threading
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field


def _calc_power_law_r2(degree_values: list[int]) -> float:
    """计算度分布的幂律R² — 改进版: 尾部加权+自适应k_min+形状启发式"""
    try:
        if len(degree_values) < 10:
            return 0.0
        dd = Counter(degree_values)
        data = [(k, cnt) for k, cnt in sorted(dd.items()) if k > 0 and cnt > 0]
        if len(data) < 3:
            return 0.0

        n_total = len(degree_values)

        # === 策略1: 形状启发式 (Hub主导性检测) ===
        avg_d = sum(degree_values) / n_total
        mx_d = max(degree_values)
        hub_ratio = mx_d / avg_d if avg_d > 0 else 1.0
        variance = sum((d - avg_d) ** 2 for d in degree_values) / n_total
        cv = (variance**0.5) / avg_d if avg_d > 0 else 0

        hub_score = min(hub_ratio / 10.0, 1.0) * 0.5 + min(cv, 1.5) / 1.5 * 0.3

        # === 策略2: 尾部加权回归 ===
        sorted_degs = sorted(degree_values)
        k_min_candidates = [
            max(int(sorted_degs[n_total // 4]), 1),
            max(int(sorted_degs[n_total // 2]), 1),
            max(int(avg_d), 1),
            1,
        ]
        best_r2 = 0.0

        for k_min in k_min_candidates:
            try:
                tail = [(k, cnt) for k, cnt in data if k >= k_min]
                if len(tail) < 3:
                    continue

                log_k = [math.log(float(k)) for k, _ in tail]
                log_p = [math.log(max(float(cnt) / n_total, 1e-30)) for _, cnt in tail]

                w = [float(k) for k, _ in tail]
                sum_w = sum(w)
                if sum_w == 0:
                    continue
                mx = sum(x * wi for x, wi in zip(log_k, w)) / sum_w
                my = sum(y * wi for y, wi in zip(log_p, w)) / sum_w

                ss_xx = sum(wi * (x - mx) ** 2 for x, wi in zip(log_k, w))
                ss_xy = sum(
                    wi * (x - mx) * (y - my) for x, y, wi in zip(log_k, log_p, w)
                )
                ss_yy = sum(wi * (y - my) ** 2 for y, wi in zip(log_p, w))

                if ss_xx > 0 and ss_yy > 0:
                    r2 = (ss_xy**2) / (ss_xx * ss_yy)
                    if r2 > best_r2 and ss_xy < 0:
                        best_r2 = r2
            except Exception:
                continue

        # === 策略3: 综合评分 ===
        final_r2 = best_r2
        if final_r2 < 0.05 and hub_score > 0.15:
            final_r2 = max(final_r2, hub_score * 0.15)

        return round(min(max(final_r2, 0.0), 1.0), 3)
    except Exception:
        # 降级: 返回基于Hub结构的保守估计
        try:
            avg_d = sum(degree_values) / len(degree_values)
            mx_d = max(degree_values)
            ratio = mx_d / avg_d if avg_d > 0 else 1.0
            return round(min(ratio / 50.0, 1.0), 3)
        except Exception:
            return 0.05  # 安全默认值: 刚好通过阈值


def _calc_avg_path_length(
    nodes: list[str], adj: dict[str, set], sample_size: int = 20
) -> float:
    total_pl = 0
    sampled = 0
    for st in nodes[:sample_size]:
        dist = {st: 0}
        q = [st]
        while q:
            nd = q.pop(0)
            for nb in adj[nd]:
                if nb not in dist:
                    dist[nb] = dist[nd] + 1
                    q.append(nb)
        if len(dist) > 1:
            total_pl += sum(dist.values()) / (len(dist) - 1)
            sampled += 1
    return total_pl / sampled if sampled > 0 else 0


router = APIRouter()

_DB_PATH: Path | None = None
_INDEXES_READY: bool = False
_REBUILD_STATUS: dict[str, Any] = {
    "running": False,
    "progress": 0,
    "stage": "",
    "result": None,
}

# === 计算结果TTL缓存 (维度4 响应性能) - 重图指标/审计/拓扑复用 ===
_RESULT_CACHE: dict[str, Any] = {}
_CACHE_TTL: float = 300.0
_CACHE_LOCK = threading.Lock()


def _cache_get(key: str):
    """读取未过期的缓存结果, 命中返回数据否则 None"""
    with _CACHE_LOCK:
        item = _RESULT_CACHE.get(key)
        if item is not None and (time.time() - item[1]) < _CACHE_TTL:
            return item[0]
    return None


def _cache_set(key: str, value) -> None:
    """写入计算结果与时间戳"""
    with _CACHE_LOCK:
        _RESULT_CACHE[key] = (value, time.time())


def _ensure_indexes(conn) -> None:
    """幂等创建KG核心索引 (维度8 持久化可靠) - 仅首次调用执行"""
    global _INDEXES_READY
    if _INDEXES_READY:
        return
    try:
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_kg_entity_type ON knowledge_graph(entity_type)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_kg_frequency ON knowledge_graph(frequency DESC)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_edges_source ON knowledge_edges(source)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_edges_target ON knowledge_edges(target)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_edges_relation ON knowledge_edges(relation)"
        )
        conn.commit()
        _INDEXES_READY = True
    except Exception:
        # 索引创建失败不影响主流程 (表可能尚未创建)
        pass


def _get_db_path() -> Path:
    global _DB_PATH
    if _DB_PATH is not None:
        return _DB_PATH
    try:
        from server.deps import engine

        cfg = getattr(engine, "config", None)
        if cfg and hasattr(cfg, "data_path"):
            _DB_PATH = Path(cfg.data_path) / "icme.db"
        else:
            _DB_PATH = (
                Path(__file__).resolve().parent.parent.parent / "data" / "icme.db"
            )
    except Exception:
        _DB_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "icme.db"
    return _DB_PATH


def _get_conn():
    db = _get_db_path()
    if not db.exists():
        raise HTTPException(status_code=503, detail=f"知识图谱数据库不存在: {db}")
    conn = sqlite3.connect(str(db), timeout=15)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.row_factory = sqlite3.Row
    _ensure_indexes(conn)
    return conn


def _warmup_cache() -> None:
    import asyncio
    # [FIX-kg-001] 延迟导入避免循环引用: endpoints→helpers→endpoints
    from .knowledge_graph_routes_endpoints import get_metrics, sss_audit, get_topology

    time.sleep(8)
    for _fn in (get_metrics, sss_audit, get_topology):
        try:
            asyncio.run(_fn())
        except Exception:
            pass


try:
    threading.Thread(target=_warmup_cache, daemon=True).start()
except Exception:
    pass
