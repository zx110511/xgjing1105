r"""
记忆CRUD路由 - REST API v6.0
==============================
v6.0: 统一工具函数 (utils.py) + 消除重复代码
"""

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel

from core.shared.models import MemoryCreate, MemoryLayer, MemoryResponse, MemoryStats
from server.api.utils import run_sync as _run
from server.api.utils import safe_memory_response as _safe_memory_response
from server.deps import engine

router = APIRouter()

# P0-3: storage/management 结果缓存 (30s TTL)，避免大数据库重复计算超时
_STORAGE_CACHE: dict = {"data": None, "time": 0.0}
_STORAGE_CACHE_TTL = 30.0


def _op_log(action: str, detail: str, result: str = "ok"):
    try:
        from server.main import _log_operation

        _log_operation("memory", action, detail, result)
    except Exception:
        pass


class ConsolidateRequest(BaseModel):
    entry_id: str
    from_layer: str
    to_layer: str


class ConsolidateAllRequest(BaseModel):
    from_layer: str = "working"
    to_layer: str | None = None


class ImportRequest(BaseModel):
    data: list = []
    format: str = "json"


class BatchDeleteRequest(BaseModel):
    ids: list[str]


def _find_entry(entry_id: str):
    for layer_data in engine._layers.values():
        if entry_id in layer_data:
            return layer_data[entry_id]
    if hasattr(engine, "_store") and engine._store:
        stored = engine._store.get(entry_id)
        if stored:
            return stored
    return None


def _get_accumulated_entries(from_layer: str) -> list:
    layer_data = engine._layers.get(from_layer, {})
    accumulated = []
    for entry_id, entry in layer_data.items():
        if hasattr(entry, "accumulated_count") and entry.accumulated_count > 0:
            accumulated.append(entry_id)
    if not accumulated:
        accumulated = list(layer_data.keys())[: min(50, len(layer_data))]
    return accumulated


@router.get("/", response_model=list[MemoryResponse])
async def list_memories(
    layer: str | None = Query(None),
    tags: str | None = Query(None),
    priority: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
):
    tag_list = [t.strip() for t in tags.split(",")] if tags else None
    priority_list = [priority] if priority else None
    valid_layers = [l.name for l in engine.config.layers]
    if layer and layer not in valid_layers:
        raise HTTPException(status_code=400, detail=f"Invalid layer: {layer}")
    entries = await _run(
        engine.recall,
        layers=[layer] if layer else None,
        tags=tag_list,
        priority=priority_list,
        limit=limit,
        min_score=0.0,
    )
    _op_log("list", f"layer={layer or 'all'} limit={limit} count={len(entries)}")
    return [
        _safe_memory_response(e if isinstance(e, dict) else e.to_dict())
        for e in entries
    ]


# [FIX-API-404] 添加 /list 别名路由，解决客户端请求路径错误
@router.get("/list", response_model=list[MemoryResponse])
async def list_memories_alias(
    layer: str | None = Query(None),
    tags: str | None = Query(None),
    priority: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
):
    """别名路由，兼容客户端请求 /api/memory/list"""
    return await list_memories(layer=layer, tags=tags, priority=priority, limit=limit)


@router.get("/stats", response_model=MemoryStats)
async def memory_stats():
    result = await _run(engine.stats)
    _op_log("stats", f"total={result.get('total_entries', 0)}")
    return MemoryStats(**result)


@router.get("/layers/info")
async def layer_capacity():
    result = await _run(engine.get_layer_capacity_info)
    _op_log("capacity", f"layers={len(result) if isinstance(result, dict) else '?'}")

    import os
    from pathlib import Path

    data_root = Path(os.environ.get("AI_MEMORY_ROOT") or r"D:\元初系统\天机v9.1")

    physical = {}
    for pattern in [
        "data/.memory/icme.db",
        "data/.memory/metrics/anchors.db",
        "data/.memory/metrics/anchors.db-wal",
        "data/.memory/working",
        "data/.memory/evolution_history",
    ]:
        p = data_root / pattern
        if p.exists():
            if p.is_dir():
                files = list(p.glob("*"))
                total_kb = sum(f.stat().st_size for f in files if f.is_file()) // 1024
                physical[pattern] = {
                    "type": "directory",
                    "files": len(files),
                    "size_kb": total_kb,
                }
            else:
                physical[pattern] = {
                    "type": "file",
                    "size_kb": p.stat().st_size // 1024,
                    "modified": p.stat().st_mtime,
                }

    return {
        "layers": result,
        "physical_storage": physical,
        "total_physical_kb": sum(v.get("size_kb", 0) for v in physical.values()),
        "timestamp": __import__("time").time(),
    }


@router.post("/export")
async def export_data():
    result = await _run(engine.build_export_data)
    _op_log("export", f"entries={len(result) if isinstance(result, list) else '?'}")
    return result


@router.get("/storage/management")
async def storage_management(auto_manage: bool = Query(False)):
    import json
    import os
    import time
    from pathlib import Path

    # P0-3: 缓存命中 (只读快照; auto_manage=true 时绕过缓存并执行管理动作)
    _now = time.time()
    if (
        not auto_manage
        and _STORAGE_CACHE["data"] is not None
        and (_now - _STORAGE_CACHE["time"]) < _STORAGE_CACHE_TTL
    ):
        cached = dict(_STORAGE_CACHE["data"])
        cached["_cache"] = {
            "hit": True,
            "age_seconds": round(_now - _STORAGE_CACHE["time"], 1),
            "ttl_seconds": _STORAGE_CACHE_TTL,
        }
        return cached

    stats = await _run(engine.stats)
    capacity = await _run(engine.get_layer_capacity_info)

    data_root = Path(os.environ.get("AI_MEMORY_ROOT") or r"D:\元初系统\天机v9.1")
    # 与engine一致的权威记忆目录 (data/.memory)，避免物理文件路径与engine不一致
    mem_root = Path(
        getattr(engine, "_data_path", None) or (data_root / "data" / ".memory")
    )

    snapshot_path = mem_root / "storage_snapshots.json"

    def _load_prev_snapshot() -> dict:
        try:
            if snapshot_path.exists():
                return json.loads(snapshot_path.read_text("utf-8"))
        except Exception:
            pass
        return {}

    def _save_snapshot(data: dict):
        try:
            snapshot_path.parent.mkdir(parents=True, exist_ok=True)
            snapshot_path.write_text(json.dumps(data, ensure_ascii=False), "utf-8")
        except Exception:
            pass

    prev = _load_prev_snapshot()
    prev_layers = prev.get("layers", {})
    prev_time = prev.get("timestamp", 0)
    elapsed_min = (time.time() - prev_time) / 60.0 if prev_time > 0 else 0

    THRESHOLDS = {
        "sensory": {"warn_k": 1.5, "critical_k": 1.9, "growth_rate_warn": 0.5},
        "working": {"warn_k": 0.35, "critical_k": 0.45, "growth_rate_warn": 2.0},
        "short_term": {"warn_k": 3.5, "critical_k": 4.5, "growth_rate_warn": 1.0},
        "episodic": {"warn_k": 1.5, "critical_k": 1.9, "growth_rate_warn": 0.3},
        "semantic": {"warn_k": 7.0, "critical_k": 9.0, "growth_rate_warn": 0.2},
        "meta": {"warn_k": 80.0, "critical_k": 95.0, "growth_rate_warn": 5.0},
    }

    layer_breakdown = {}
    total_size_bytes = 0
    current_snapshot_layers = {}
    all_alerts = []

    for lname, linfo in (capacity or {}).items():
        entry_count = linfo.get("entry_count", 0)
        size_mb = linfo.get("size_bytes", 0) / (1024 * 1024)
        max_entries = linfo.get("max_entries", 2000)
        max_size_mb = linfo.get("max_size_bytes", 0) / (1024 * 1024)
        usage_pct = linfo.get("usage_ratio", 0) * 100
        needs_consolidation = linfo.get("needs_consolidation", False)
        at_hard_cap = linfo.get("at_hard_cap", False)

        total_size_bytes += linfo.get("size_bytes", 0)

        entries_k = round(entry_count / 1000.0, 2)
        max_entries_k = round(max_entries / 1000.0, 2)

        prev_entry_k = prev_layers.get(lname, {}).get("entries_k", entries_k)
        delta_k = round(entries_k - prev_entry_k, 3)
        rate_k_per_min = round(delta_k / elapsed_min, 4) if elapsed_min > 0.01 else 0.0

        thresh = THRESHOLDS.get(
            lname,
            {
                "warn_k": max_entries_k * 0.75,
                "critical_k": max_entries_k * 0.95,
                "growth_rate_warn": 1.0,
            },
        )
        status = "OK"
        if at_hard_cap or entries_k >= thresh["critical_k"]:
            status = "CRITICAL"
        elif needs_consolidation or entries_k >= thresh["warn_k"]:
            status = "WARNING"
        elif abs(rate_k_per_min) > thresh["growth_rate_warn"]:
            status = "GROWTH_ALERT" if rate_k_per_min > 0 else "SHRINK_ALERT"

        if status != "OK":
            alert_msg = f"{lname}: {entries_k}k/{max_entries_k}k ({usage_pct:.1f}%)"
            if abs(delta_k) > 0.001:
                alert_msg += f" | delta={delta_k:+.3f}k ({rate_k_per_min:+.2f}k/min)"
            all_alerts.append(
                {
                    "level": "error"
                    if status == "CRITICAL"
                    else ("warn" if status == "WARNING" else "info"),
                    "layer": lname,
                    "status": status,
                    "message": alert_msg,
                    "entries_k": entries_k,
                    "delta_k": delta_k,
                    "rate_k_per_min": rate_k_per_min,
                }
            )

        layer_data = {
            "entries": entry_count,
            "entries_k": entries_k,
            "max_entries": max_entries,
            "max_entries_k": max_entries_k,
            "size_mb": round(size_mb, 2),
            "max_size_mb": round(max_size_mb, 2),
            "usage_pct": round(usage_pct, 1),
            "delta_k": delta_k,
            "rate_k_per_min": rate_k_per_min,
            "elapsed_min": round(elapsed_min, 1),
            "needs_consolidation": needs_consolidation,
            "at_hard_cap": at_hard_cap,
            "thresholds": {
                "warn_k": thresh["warn_k"],
                "critical_k": thresh["critical_k"],
                "growth_rate_warn_k_per_min": thresh["growth_rate_warn"],
            },
            "status": status,
        }
        layer_breakdown[lname] = layer_data
        current_snapshot_layers[lname] = {
            "entries_k": entries_k,
            "timestamp": time.time(),
        }

    _save_snapshot(
        {
            "timestamp": time.time(),
            "layers": current_snapshot_layers,
            "total_entries_k": round((stats.get("total_entries", 0) or 0) / 1000.0, 2),
        }
    )

    db_path = mem_root / "icme.db"
    anchors_path = mem_root / "metrics" / "anchors.db"
    wal_path = mem_root / "metrics" / "anchors.db-wal"

    def _rel(p: Path) -> str:
        try:
            return str(p.relative_to(data_root))
        except Exception:
            return str(p)

    physical_files = []
    for label, p in [
        ("icme.db", db_path),
        ("anchors.db (FTS5)", anchors_path),
        ("WAL日志", wal_path),
    ]:
        if p.exists():
            st = p.stat()
            physical_files.append(
                {
                    "name": label,
                    "path": _rel(p),
                    "size_kb": round(st.st_size / 1024, 1),
                    "size_mb": round(st.st_size / (1024 * 1024), 2),
                    "modified": time.strftime(
                        "%Y-%m-%d %H:%M:%S", time.localtime(st.st_mtime)
                    ),
                }
            )

    working_dir = mem_root / "working"
    working_stats = None
    if working_dir.exists():
        files = list(working_dir.glob("*"))
        working_stats = {
            "files_count": len(files),
            "total_kb": round(
                sum(f.stat().st_size for f in files if f.is_file()) / 1024, 1
            ),
            "oldest": min((f.stat().st_mtime for f in files if f.is_file()), default=0),
            "newest": max((f.stat().st_mtime for f in files if f.is_file()), default=0),
        }

    total_entries = stats.get("total_entries", 0) if stats else 0
    prev_total_k = prev.get("total_entries_k", total_entries / 1000.0)

    # P0-2: 数据一致性校验 — layers条目总和 vs stats.total_entries
    layers_entry_sum = sum(ld.get("entries", 0) for ld in layer_breakdown.values())
    archive_entries_val = stats.get("archive_entries", 0) if stats else 0
    diff = layers_entry_sum - total_entries
    consistency_check = {
        "layers_entry_sum": layers_entry_sum,
        "total_entries": total_entries,
        "diff": diff,
        "consistent": diff == 0,
        "archive_entries": archive_entries_val,
        "note": (
            "layers总和=total_entries，一致"
            if diff == 0
            else (
                f"偏差{diff:+d}条: archive归档条目({archive_entries_val})独立计数，"
                "不计入六层活跃总和"
            )
        ),
    }

    response = {
        "unit_system": {
            "capacity_unit": "k",
            "capacity_unit_label": "thousand entries",
            "rate_unit": "k/min",
            "base": 1000,
        },
        "timestamp": time.time(),
        "uptime_seconds": stats.get("uptime_seconds", 0) if stats else 0,
        "summary": {
            "total_entries": total_entries,
            "total_entries_k": round(total_entries / 1000.0, 2),
            "prev_total_k": round(prev_total_k, 2),
            "delta_total_k": round(total_entries / 1000.0 - prev_total_k, 3),
            "total_layers": len(layer_breakdown),
            "total_db_size_mb": round(total_size_bytes / (1024 * 1024), 2),
            "physical_total_kb": sum(pf["size_kb"] for pf in physical_files)
            + (working_stats["total_kb"] if working_stats else 0),
            "physical_total_mb": round(
                (
                    sum(pf["size_kb"] for pf in physical_files)
                    + (working_stats["total_kb"] if working_stats else 0)
                )
                / 1024,
                2,
            ),
            "archive_entries": stats.get("archive_entries", 0) if stats else 0,
            "consolidations": stats.get("consolidations", 0) if stats else 0,
        },
        "consistency_check": consistency_check,
        "layers": layer_breakdown,
        "physical_storage": physical_files,
        "working_directory": working_stats,
        "threshold_config": THRESHOLDS,
        "alerts": all_alerts,
        "change_mechanism": {
            "snapshot_enabled": True,
            "snapshot_path": _rel(snapshot_path) if snapshot_path.exists() else None,
            "prev_snapshot_age_min": round(elapsed_min, 1),
            "auto_cleanup_wal": wal_path.exists(),
        },
        "orchestration": {
            "auto_manage_enabled": auto_manage,
            "actions_taken": [],
        },
    }

    management_actions = []
    for alert in all_alerts if auto_manage else []:
        layer = alert["layer"]
        status = alert["status"]
        if status in ("CRITICAL", "WARNING"):
            try:
                action_type = (
                    "emergency_consolidate"
                    if status == "CRITICAL"
                    else "preventive_consolidate"
                )
                max_to_consolidate = 100 if status == "CRITICAL" else 50
                threshold_score = 0.5 if status == "CRITICAL" else 0.6

                result = await _run(
                    engine.consolidate_batch,
                    from_layer=layer,
                    threshold=threshold_score,
                    max_entries=max_to_consolidate,
                )

                consolidated_count = result.get("consolidated", 0)
                action_record = {
                    "timestamp": time.time(),
                    "layer": layer,
                    "trigger": status,
                    "action": action_type,
                    "consolidated": consolidated_count,
                    "from_layer": result.get("from_layer"),
                    "to_layer": result.get("to_layer"),
                    "threshold_used": threshold_score,
                    "status": result.get("status", "unknown"),
                }
                management_actions.append(action_record)
                _op_log(
                    "auto_orchestrate",
                    f"{action_type}:{layer}→{result.get('to_layer')} x{consolidated_count}",
                )

                if status == "CRITICAL":
                    layer_info = (capacity or {}).get(layer, {})
                    max_entries = layer_info.get("max_entries", 2000)
                    max_k = max_entries / 1000.0

                    post_consolidation_stats = await _run(engine.stats)
                    post_capacity = await _run(engine.get_layer_capacity_info)
                    post_layer_info = (post_capacity or {}).get(layer, {})
                    post_entry_count = post_layer_info.get("entry_count", 0)
                    post_entries_k = post_entry_count / 1000.0

                    still_critical = post_entries_k > max_k * 1.1
                    still_overcap = post_entries_k > max_k * 1.3

                    if still_overcap or (still_critical and consolidated_count < 20):
                        evict_target_ratio = 0.85 if still_overcap else 0.9
                        evict_max = 200 if still_overcap else 150

                        evict_result = await _run(
                            engine.force_evict_overcapacity,
                            layer=layer,
                            target_ratio=evict_target_ratio,
                            max_evict=evict_max,
                        )
                        evicted_count = evict_result.get("evicted", 0)

                        evict_action = {
                            "timestamp": time.time(),
                            "layer": layer,
                            "trigger": "POST_CONSOLIDATION_CLEANUP",
                            "action": "force_evict",
                            "evicted": evicted_count,
                            "before": evict_result.get("before"),
                            "after": evict_result.get("after"),
                            "max_entries": evict_result.get("max_entries"),
                            "reason": f"still_overcap={still_overcap}, was_{post_entries_k:.1f}k",
                            "previous_consolidation": consolidated_count,
                        }
                        management_actions.append(evict_action)
                        _op_log(
                            "auto_orchestrate",
                            f"post_consolidation_evict:{layer} x{evicted_count} (was {post_entries_k:.1f}k)",
                        )

            except Exception as e:
                management_actions.append(
                    {
                        "timestamp": time.time(),
                        "layer": layer,
                        "trigger": status,
                        "action": "failed",
                        "error": str(e),
                        "consolidated": 0,
                    }
                )
                _op_log("auto_orchestrate_error", f"{layer}:{e}")

    if management_actions:
        log_path = mem_root / "storage_management_log.jsonl"
        try:
            log_path.parent.mkdir(parents=True, exist_ok=True)
            with open(log_path, "a", encoding="utf-8") as f:
                for action in management_actions:
                    f.write(json.dumps(action, ensure_ascii=False) + "\n")
        except Exception:
            pass
        response["orchestration"]["actions_taken"] = management_actions
        response["alerts_post_action"] = [
            {
                "level": "info",
                "message": f"Auto-managed: {len(management_actions)} action(s) taken",
            }
        ]

    # P0-3: 只读快照写入缓存 (仅当未执行管理动作时，保证缓存为纯只读结果)
    if not auto_manage:
        _STORAGE_CACHE["data"] = response
        _STORAGE_CACHE["time"] = time.time()
    response["_cache"] = {"hit": False, "ttl_seconds": _STORAGE_CACHE_TTL}

    return response


@router.post("/storage/manage")
async def storage_manual_manage(request: Request):
    import json
    import os
    import time
    from pathlib import Path

    data_root = Path(os.environ.get("AI_MEMORY_ROOT") or r"D:\元初系统\天机v9.1")
    mem_root = Path(
        getattr(engine, "_data_path", None) or (data_root / "data" / ".memory")
    )
    try:
        body = await request.json()
    except Exception:
        body = {}
    target_layer = body.get("layer")
    action = body.get("action", "consolidate")
    force = body.get("force", False)

    capacity = await _run(engine.get_layer_capacity_info)
    actions_performed = []

    if action == "consolidate_all":
        result = await _run(
            engine.consolidate_all_layers, threshold=0.5, max_per_layer=50
        )
        actions_performed.append({"action": "consolidate_all", "result": result})

    elif action == "auto_promote":
        max_per_layer = body.get("max_per_layer", 50)
        result = await _run(engine.auto_promote_sweep, max_per_layer=max_per_layer)
        actions_performed.append({"action": "auto_promote", "result": result})

    elif target_layer and action in ("consolidate", "emergency_consolidate"):
        layer_info = (capacity or {}).get(target_layer, {})
        is_critical = layer_info.get("at_hard_cap", False) or (
            layer_info.get("usage_ratio", 0) > 0.9
        )
        threshold = 0.4 if (is_critical or force) else 0.6
        # 用户传入max_entries优先，否则使用默认值
        default_max = 150 if (is_critical or force) else 80
        user_max = body.get("max_entries", 0)
        max_entries = user_max if user_max and user_max > 0 else default_max

        # 动态阈值: 根据层使用率调整，使用率越高阈值越低
        usage_ratio = layer_info.get("usage_ratio", 0)
        _ec = layer_info.get("entry_count", 0)
        _me = layer_info.get("max_entries", 1)
        entry_ratio = _ec / max(_me, 1)
        effective_usage = max(usage_ratio, entry_ratio)
        if not (is_critical or force):
            if effective_usage > 0.85:
                threshold = 0.2
            elif effective_usage > 0.75:
                threshold = 0.3
            elif effective_usage > 0.65:
                threshold = 0.4

        result = await _run(
            engine.consolidate_batch,
            from_layer=target_layer,
            threshold=threshold,
            max_entries=max_entries,
            use_quality_promotion=not (is_critical or force),
        )
        actions_performed.append(
            {
                "action": action,
                "target": target_layer,
                "threshold": threshold,
                "max_entries": max_entries,
                "effective_usage": effective_usage,
                **result,
            }
        )

        if result.get("consolidated", 0) == 0 and (is_critical or force):
            evict_result = await _run(
                engine.force_evict_overcapacity,
                layer=target_layer,
                target_ratio=0.8,
                max_evict=200,
            )
            actions_performed.append(
                {
                    "action": "force_evict",
                    "target": target_layer,
                    **evict_result,
                }
            )

    elif target_layer and action == "force_evict":
        evict_result = await _run(
            engine.force_evict_overcapacity,
            layer=target_layer,
            target_ratio=body.get("target_ratio", 0.8),
            max_evict=body.get("max_evict", 200),
        )
        actions_performed.append(
            {"action": "force_evict", "target": target_layer, **evict_result}
        )

    elif action == "cleanup_wal":
        wal_path = mem_root / "metrics" / "anchors.db-wal"
        if wal_path.exists():
            try:
                import sqlite3

                db_path = mem_root / "metrics" / "anchors.db"
                # 先记录checkpoint前的WAL大小 (TRUNCATE后文件可能被移除, 避免stat失败)
                size_before = wal_path.stat().st_size
                conn = sqlite3.connect(str(db_path))
                conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
                conn.close()
                size_after = wal_path.stat().st_size if wal_path.exists() else 0
                actions_performed.append(
                    {
                        "action": "cleanup_wal",
                        "freed_kb": round((size_before - size_after) / 1024, 1),
                        "status": "ok",
                    }
                )
            except Exception as e:
                actions_performed.append(
                    {"action": "cleanup_wal", "error": str(e), "status": "error"}
                )
        else:
            actions_performed.append({"action": "cleanup_wal", "status": "no_wal_file"})

    elif action == "get_logs":
        log_path = mem_root / "storage_management_log.jsonl"
        logs = []
        limit = body.get("limit", 50)
        if log_path.exists():
            with open(log_path, encoding="utf-8") as f:
                for line in f:
                    try:
                        logs.append(json.loads(line.strip()))
                    except Exception:
                        pass
        logs = logs[-limit:]
        return {"logs": logs, "total": len(logs), "log_path": str(log_path)}

    # item#8: 手动统筹操作写入日志, 确保 get_logs 可追溯管理操作记录
    if actions_performed:
        log_path = mem_root / "storage_management_log.jsonl"
        try:
            log_path.parent.mkdir(parents=True, exist_ok=True)
            with open(log_path, "a", encoding="utf-8") as f:
                for _act in actions_performed:
                    _record = {"timestamp": time.time(), "trigger": "MANUAL", **_act}
                    f.write(json.dumps(_record, ensure_ascii=False) + "\n")
        except Exception:
            pass
        _op_log("manual_manage", f"{action}:{target_layer} x{len(actions_performed)}")

    new_capacity = (
        await _run(engine.get_layer_capacity_info) if actions_performed else capacity
    )

    return {
        "timestamp": time.time(),
        "requested": body,
        "actions_performed": actions_performed,
        "layers_after": new_capacity,
        "total_actions": len(actions_performed),
    }


@router.post("/import")
async def import_data(req: ImportRequest):
    imported = 0
    errors = []
    for item in req.data:
        try:
            if isinstance(item, dict) and item.get("content"):
                await _run(
                    engine.remember,
                    content=item["content"],
                    layer=item.get("layer", "working"),
                    tags=item.get("tags", []),
                    priority=item.get("priority", "medium"),
                    metadata=item.get("metadata", {}),
                    use_llm=False,
                )
                imported += 1
            else:
                errors.append(f"跳过无效条目: {str(item)[:50]}")
        except Exception as e:
            errors.append(str(e)[:100])
    _op_log("import", f"total={len(req.data)} imported={imported} errors={len(errors)}")
    return {
        "status": "completed",
        "imported": imported,
        "errors": errors,
        "total": len(req.data),
    }


@router.post("/batch-delete")
async def batch_delete(req: BatchDeleteRequest):
    deleted = 0
    not_found = 0
    for entry_id in req.ids:
        try:
            success = await _run(engine.forget, entry_id)
            if success:
                deleted += 1
            else:
                not_found += 1
        except Exception:
            not_found += 1
    _op_log(
        "batch_delete", f"total={len(req.ids)} deleted={deleted} not_found={not_found}"
    )
    return {
        "status": "completed",
        "deleted": deleted,
        "not_found": not_found,
        "total": len(req.ids),
    }


@router.post("/", response_model=MemoryResponse, status_code=201)
async def create_memory(item: MemoryCreate):
    # [FIX-COUNTER-AUDIT] 启用LLM增强: 原use_llm=False导致分类/摘要/知识提取计数器永远为0
    # 修复: 当content长度>50字符时启用LLM增强，触发classify/summarize/extract_knowledge
    # 短内容(<50字符)跳过LLM增强以优化性能
    # [FIX-TIMEOUT] 支持客户端通过 use_llm=False 强制关闭LLM增强，避免30s超时
    if item.use_llm is not None:
        use_llm_flag = item.use_llm
    else:
        use_llm_flag = len(item.content) > 50
    result = await _run(
        engine.remember,
        content=item.content,
        layer=item.layer.value,
        tags=item.tags,
        priority=item.priority.value,
        metadata=item.metadata,
        use_llm=use_llm_flag,
    )
    entry_id = result.get("id")
    _op_log(
        "create",
        f"layer={item.layer.value} id={entry_id} tags={item.tags}",
        "ok" if entry_id else "rejected",
    )
    if entry_id is None:
        s = result.get("status", "rejected")
        raise HTTPException(
            status_code=422,
            detail=f"记忆被拒绝({s}): {result.get('reason', 'unknown')}",
        )
    entry_dict = _find_entry(entry_id)
    if entry_dict:
        return _safe_memory_response(entry_dict)
    raise HTTPException(status_code=500, detail="Created but not found")


@router.get("/{entry_id}", response_model=MemoryResponse)
async def get_memory(entry_id: str):
    entry_dict = _find_entry(entry_id)
    if entry_dict:
        _op_log("read", f"id={entry_id}")
        return _safe_memory_response(entry_dict)
    raise HTTPException(status_code=404, detail="Entry not found")


@router.put("/{entry_id}")
async def update_memory(
    entry_id: str,
    request: Request,
):
    """更新记忆条目

    [FIX-PUT-422] 支持JSON和form两种格式，避免list[str]参数解析422错误
    [FIX-PUT-UPDATE] 通过engine.update_entry持久化更新，避免引用对象未保存
    """
    entry_dict = _find_entry(entry_id)
    if not entry_dict:
        raise HTTPException(status_code=404, detail="Entry not found")

    # 兼容JSON和form-urlencoded
    content_type = request.headers.get("content-type", "")
    if "application/json" in content_type:
        try:
            body = await request.json()
        except Exception:
            body = {}
    else:
        try:
            form = await request.form()
            body = dict(form)
            # form中tags可能多次出现，合并为list
            tags_list = form.getlist("tags") if hasattr(form, "getlist") else None
            if tags_list:
                body["tags"] = tags_list
        except Exception:
            body = {}

    updates = {}
    if "content" in body and body["content"] is not None:
        updates["content"] = body["content"]
    if "tags" in body and body["tags"] is not None:
        tags = body["tags"]
        if isinstance(tags, str):
            tags = [t.strip() for t in tags.split(",") if t.strip()]
        updates["tags"] = tags
    if "priority" in body and body["priority"] is not None:
        updates["priority"] = body["priority"]

    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")

    # 优先通过engine持久化
    updated = False
    if hasattr(engine, "update_entry"):
        try:
            updated = await _run(engine.update_entry, entry_id, updates)
        except Exception:
            updated = False
    if not updated and hasattr(engine, "_store") and engine._store:
        try:
            updated = engine._store.update(entry_id, updates)
        except Exception:
            updated = False
    # 兜底: 直接修改内存对象
    if not updated:
        if "content" in updates and hasattr(entry_dict, "content"):
            entry_dict.content = updates["content"]
        if "tags" in updates and hasattr(entry_dict, "tags"):
            entry_dict.tags = updates["tags"]
        if "priority" in updates and hasattr(entry_dict, "priority"):
            entry_dict.priority = updates["priority"]

    # 重新读取以返回最新状态
    entry_after = _find_entry(entry_id) or entry_dict
    _op_log("update", f"id={entry_id} fields={list(updates.keys())}")
    return _safe_memory_response(entry_after)


@router.delete("/{entry_id}")
async def delete_memory(entry_id: str):
    success = await _run(engine.forget, entry_id)
    if not success:
        raise HTTPException(status_code=404, detail="Entry not found")
    _op_log("delete", f"id={entry_id}")
    return {"status": "deleted", "entry_id": entry_id}


@router.post("/consolidate")
async def consolidate_entry(req: ConsolidateRequest):
    result = await _run(engine.consolidate, req.from_layer, req.to_layer, req.entry_id)
    if result is None:
        raise HTTPException(status_code=400, detail="Consolidation failed")
    _op_log("consolidate", f"id={req.entry_id} {req.from_layer}→{req.to_layer}")
    return {"status": "consolidated", "entry_id": result, "to_layer": req.to_layer}


@router.post("/consolidate_all")
async def consolidate_all(req: ConsolidateAllRequest):
    layer_names = [l.value for l in MemoryLayer]
    if req.from_layer not in layer_names:
        raise HTTPException(status_code=400, detail=f"Invalid layer: {req.from_layer}")
    from_idx = layer_names.index(req.from_layer)
    if from_idx >= len(layer_names) - 1:
        return {
            "status": "ok",
            "consolidated_count": 0,
            "message": "Already at top layer",
        }
    to_layer = req.to_layer if req.to_layer else layer_names[from_idx + 1]
    if to_layer not in layer_names:
        raise HTTPException(status_code=400, detail=f"Invalid target layer: {to_layer}")
    accumulated = await _run(_get_accumulated_entries, req.from_layer)
    consolidated = 0
    for entry_id in accumulated:
        try:
            if await _run(engine.consolidate, req.from_layer, to_layer, entry_id):
                consolidated += 1
        except Exception:
            pass
    _op_log(
        "consolidate_all",
        f"{req.from_layer}→{to_layer} count={consolidated}/{len(accumulated)}",
    )
    return {
        "status": "ok",
        "from_layer": req.from_layer,
        "to_layer": to_layer,
        "total_accumulated": len(accumulated),
        "consolidated_count": consolidated,
    }
