r"""
事件接收API v6.0 — 统一记忆池
v6.0: 统一工具函数 (utils.py) + 消除重复代码
"""

import time
from typing import List

from core.shared.models import (
    HealthStatus,
    MemoryCreate,
    MemoryResponse,
    PlatformEvent,
)
from fastapi import APIRouter, HTTPException

from server.api.utils import run_sync as _run
from server.api.utils import safe_memory_response as _safe_memory_response
from server.deps import engine

router = APIRouter()


@router.get("/")
def platform_root():
    return {
        "status": "active",
        "adapters": 6,
        "message": "多平台适配层运行中",
        "routes": [
            "POST /event",
            "POST /remember",
            "GET /recall",
            "GET /stats",
            "GET /health",
        ],
    }


@router.post("/event")
async def receive_event(event: PlatformEvent):
    event.timestamp = event.timestamp or time.time()
    result = await _run(
        engine.remember,
        content=json_safe_dumps(event.payload),
        layer="sensory",
        tags=["event", f"type:{event.event_type}"],
        priority="low",
        metadata={
            "source": event.source,
            "event_type": event.event_type,
            "session_id": event.session_id,
            "received_at": event.timestamp,
        },
        use_llm=False,
    )
    return {
        "status": "received",
        "entry_id": result.get("id"),
        "actual_layer": result.get("actual_layer", "sensory"),
    }


@router.post("/remember", response_model=MemoryResponse, status_code=201)
async def platform_remember(item: MemoryCreate):
    result = await _run(
        engine.remember,
        content=item.content,
        layer=item.layer.value,
        tags=item.tags,
        priority=item.priority.value,
        metadata={**item.metadata, "session_id": item.session_id},
        use_llm=True,
    )
    entry_id = result.get("id")
    if entry_id is None:
        raise HTTPException(
            status_code=422, detail=f"记忆被拒绝: {result.get('reason', 'unknown')}"
        )
    # 从存储层获取完整条目
    response_data = None
    for layer_data in engine._layers.values():
        if entry_id in layer_data:
            response_data = _safe_memory_response(layer_data[entry_id].to_dict())
            break
    if response_data is None and hasattr(engine, "_store") and engine._store:
        stored = engine._store.get(entry_id)
        if stored:
            response_data = _safe_memory_response(stored)
    if response_data is None:
        raise HTTPException(status_code=500, detail="Entry created but not found")
    # 合体运行: 将策略D的asset_id和TCL的canonical_ids注入响应
    # response_data 是 MemoryResponse Pydantic模型，不是dict
    if result.get("asset_id"):
        response_data.asset_id = result["asset_id"]
    if result.get("actual_layer"):
        response_data.actual_layer = result["actual_layer"]
    if result.get("gate_verdict"):
        response_data.gate_verdict = result["gate_verdict"]
    return response_data


@router.get("/recall", response_model=List[MemoryResponse])
async def platform_recall(query: str, limit: int = 20):
    entries = await _run(engine.recall, query=query, limit=limit, min_score=0.0)
    return [
        _safe_memory_response(e if isinstance(e, dict) else e.to_dict())
        for e in entries
    ]


@router.get("/stats")
async def platform_stats():
    stats = await _run(engine.stats)
    return {"status": "success", "engine": stats}


@router.get("/health")
async def platform_health():
    from server.deps import embeddings_service

    capacity = await _run(engine.get_layer_capacity_info)
    return HealthStatus(
        status="healthy",
        version="9.1.0",
        engine_ready=True,
        embedding_ready=embeddings_service is not None,
        layers=capacity,
        uptime_seconds=round(time.time() - engine._stats["start_time"], 1),
    )


def json_safe_dumps(obj) -> str:
    import json

    return json.dumps(obj, ensure_ascii=False, default=str)
