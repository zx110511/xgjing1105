r"""
天机v9.1 统一指标API路由 (Metrics Routes)
==========================================
基于98分通用监控统计架构，提供:
- /api/metrics/latest — 所有最新指标快照
- /api/metrics/history/{name} — 指定指标时间序列
- /api/metrics/verify/{name} — 单指标锚定验证与重放
- /api/metrics/verify-all — 全量验证
- /api/metrics/status — 采集器状态
- /api/metrics/definitions — 已注册指标定义清单
"""

import time
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query

router = APIRouter(tags=["metrics"])


def _get_collector():
    try:
        from core.shared.stat_collector import get_collector

        return get_collector()
    except Exception:
        return None


def _snapshot_to_dict(snap) -> Dict[str, Any]:
    return {
        "name": snap.name,
        "timestamp": snap.timestamp,
        "value": snap.value,
        "metric_type": snap.metric_type.value
        if hasattr(snap.metric_type, "value")
        else str(snap.metric_type),
        "unit": snap.unit,
        "anchor_id": snap.anchor_id,
    }


def _metric_def_to_dict(md) -> Dict[str, Any]:
    return {
        "name": md.name,
        "display_name": md.display_name,
        "metric_type": md.metric_type.value
        if hasattr(md.metric_type, "value")
        else str(md.metric_type),
        "source_type": md.source_type.value
        if hasattr(md.source_type, "value")
        else str(md.source_type),
        "anchor_policy": md.anchor_policy.value
        if hasattr(md.anchor_policy, "value")
        else str(md.anchor_policy),
        "interval_seconds": md.interval_seconds,
        "unit": md.unit,
        "category": md.category,
        "description": md.description,
        "tags": md.tags,
    }


@router.get("/metrics/latest")
async def get_latest_metrics(
    category: Optional[str] = Query(None, description="按分类过滤"),
) -> Dict[str, Any]:
    collector = _get_collector()
    if not collector:
        return {
            "status": "unavailable",
            "detail": "StatCollector未初始化",
            "timestamp": time.time(),
        }

    collector.collect_all()
    all_latest = collector.registry.all_latest()
    metrics_defs = collector.registry.all_metrics()

    snapshots: Dict[str, Any] = {}
    by_category: Dict[str, List[Dict[str, Any]]] = {}

    for md in metrics_defs:
        if category and md.category != category:
            continue
        snap = all_latest.get(md.name)
        entry = {
            "definition": _metric_def_to_dict(md),
            "snapshot": _snapshot_to_dict(snap) if snap else None,
            "stale": snap is None
            or (time.time() - snap.timestamp) > (md.interval_seconds * 3)
            if snap
            else True,
        }
        snapshots[md.name] = entry
        by_category.setdefault(md.category, []).append(entry)

    return {
        "status": "ok",
        "timestamp": time.time(),
        "total_metrics": len(metrics_defs),
        "with_snapshots": len(all_latest),
        "by_category": by_category,
        "snapshots": snapshots,
    }


@router.get("/metrics/history/{name:path}")
async def get_metric_history(
    name: str,
    window_seconds: int = Query(600, description="时间窗口(秒)", ge=10, le=86400),
    limit: int = Query(200, description="最大返回点数", ge=1, le=2000),
) -> Dict[str, Any]:
    collector = _get_collector()
    if not collector:
        raise HTTPException(status_code=503, detail="StatCollector未初始化")

    md = collector.registry.get(name)
    if not md:
        raise HTTPException(status_code=404, detail=f"未注册的指标: {name}")

    history = collector.registry.get_history(name, window_seconds)
    if len(history) > limit:
        step = len(history) // limit
        history = history[:: max(1, step)]
        history = history[-limit:]

    points = [_snapshot_to_dict(s) for s in history]

    return {
        "status": "ok",
        "metric": name,
        "display_name": md.display_name,
        "unit": md.unit,
        "category": md.category,
        "window_seconds": window_seconds,
        "total_points": len(points),
        "points": points,
    }


@router.post("/metrics/verify/{name:path}")
async def verify_metric(name: str) -> Dict[str, Any]:
    collector = _get_collector()
    if not collector:
        raise HTTPException(status_code=503, detail="StatCollector未初始化")

    md = collector.registry.get(name)
    if not md:
        raise HTTPException(status_code=404, detail=f"未注册的指标: {name}")

    if md.anchor_policy.value == "none":
        return {"status": "skipped", "metric": name, "detail": "该指标未启用锚定"}

    result = collector.verify_metric(name)
    return result


@router.post("/metrics/verify-all")
async def verify_all_metrics() -> Dict[str, Any]:
    collector = _get_collector()
    if not collector:
        raise HTTPException(status_code=503, detail="StatCollector未初始化")

    result = collector.verify_all()
    return {"status": "ok", "timestamp": time.time(), **result}


@router.get("/metrics/status")
async def get_collector_status() -> Dict[str, Any]:
    collector = _get_collector()
    if not collector:
        return {"status": "not_initialized", "running": False}

    return {
        "status": "ok",
        **collector.get_status(),
    }


@router.get("/metrics/definitions")
async def get_metric_definitions(
    category: Optional[str] = Query(None),
) -> Dict[str, Any]:
    collector = _get_collector()
    if not collector:
        return {"status": "unavailable", "definitions": []}

    all_defs = collector.registry.all_metrics()
    if category:
        all_defs = [d for d in all_defs if d.category == category]

    return {
        "status": "ok",
        "total": len(all_defs),
        "categories": list({d.category for d in all_defs}),
        "definitions": [_metric_def_to_dict(d) for d in all_defs],
    }
