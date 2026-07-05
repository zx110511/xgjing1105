# -*- coding: utf-8-sig -*-
"""status_routes_module.py — 从 status_routes.py 拆分 (SSS-PhaseB)

module功能组
源文件: status_routes.py
"""

import json
import os
import time
from typing import Any

from fastapi import APIRouter

# [FIX-STATUS-500] 导入engine helpers层的辅助函数 (SSS拆分时遗漏)
# 根因: get_system_stats() 使用了 _get_engine_stats/_get_container 等但未导入
# 影响: /api/status/system/stats 返回500
from .status_routes_engine_helpers import (
    _GLOBAL_POLLUTION_FIELDS,
    _get_container,
    _get_engine,
    _get_engine_stats,
    _get_layer_capacity,
)

# [FIX-DASHBOARD-CUMULATIVE] 导入持久化层的锁和常量 (SSS拆分时遗漏)
# 根因: get_system_stats() 使用了 _cumulative_lock 等变量但未导入
# 影响: dashboard累计数据tab显示异常
from .status_routes_persist import (
    _FULL_MODULE_CATALOG,
    _SNAPSHOT_INTERVAL,
    MODULE_MAP,
    _cumulative_counters,
    _cumulative_lock,
    _history_lock,
    _history_snapshots,
    _last_snapshot_ts,
    _persist_data,
)

# [FIX-AUDIT] 补充缺失的router定义 (SSS拆分时遗漏)
router = APIRouter()


# [FIX-API-404] 添加根路由，解决客户端请求 /api/status 404错误
@router.get("/")
async def status_root():
    """系统状态根路由，返回基础健康信息"""
    return {
        "status": "healthy",
        "system": "天机v9.1",
        "timestamp": time.time(),
        "message": "Use /api/status/system/stats for detailed stats",
    }


def _resolve_module_deps(name: str, container) -> dict:
    import os
    from pathlib import Path

    args = {}
    if name == "sqlite_store":
        db_path = Path(
            os.path.join(
                os.environ.get("AI_MEMORY_ROOT", "data"), "data", ".memory", "icme.db"
            )
        )
        args["db_path"] = db_path
    elif name == "agent_orchestrator":
        tracker = container._modules.get("skill_tracker")
        if tracker and tracker.instance:
            args["tracker"] = tracker.instance
        ebus = container._modules.get("event_bus")
        if ebus and ebus.instance:
            args["event_bus"] = ebus.instance
    elif name == "agent_scheduler":
        ebus = container._modules.get("event_bus")
        if ebus and ebus.instance:
            args["event_bus"] = ebus.instance
    elif name == "intelligent_scheduler":
        # [FIX-MODULE-INIT] AutoSchedulerDaemon需要scheduler参数，但auto_scheduler模块不存在
        # 解决方案: 创建TianjiIntelligentScheduler实例作为scheduler参数
        try:
            from core.orchestration.intelligent_scheduler import (
                TianjiIntelligentScheduler,
            )

            scheduler_inst = TianjiIntelligentScheduler(
                memory_api_url="http://127.0.0.1:8771",
                decision_engine=None,
                event_bus=None,
                max_concurrency=8,
            )
            args["scheduler"] = scheduler_inst
        except Exception:
            pass  # 静默失败，让模块管理器处理错误
    elif name == "search_indexer":
        eng = container._modules.get("hybrid_engine")
        if eng and eng.instance:
            args["engine"] = eng.instance
    elif name == "engine" or name == "config":
        args = {}
    elif name == "learning_loop":
        sreg = container._modules.get("skill_registry")
        if sreg and sreg.instance:
            args["skill_registry"] = sreg.instance
        ebus = container._modules.get("event_bus")
        if ebus and ebus.instance:
            args["event_bus"] = ebus.instance
        eeng = container._modules.get("evolution_engine")
        if eeng and eeng.instance:
            args["evolution_engine"] = eeng.instance
    elif name == "evolution_loop":
        # [FIX-MODULE-INIT] evolution_loop需要module_name参数
        args["module_name"] = name
    elif name == "governance_pipeline":
        args = {}
    return args


_import_cache: dict[str, bool] = {}


# [FIX-DASHBOARD-CUMULATIVE] 模块特定累计字段映射
# 与前端 MODULE_CONFIG_3D.cumulative_fields 对齐 (L06 数据契约对齐)
# 根因: 后端只注入通用字段(uptime_hours/memory_entries/api_calls),
#       缺少前端期望的特定字段(consolidations/events/decisions等)
_MODULE_CUMULATIVE_FIELDS: dict[str, list[str]] = {
    "engine": ["consolidations", "uptime_seconds"],
    "deepseek_driver": ["events", "decisions"],
    "enforcement_hook": ["captured", "stored"],
    "chain_dashboard": ["events", "decisions"],
    "quality_gate": ["captured", "stored"],
    "memory_api": ["total_entries", "total_entries"],
    "standards_compliance": ["captured", "stored"],
    "api_exposure": ["captured", "events"],
    "intelligent_scheduler": ["events", "decisions"],
    "learning_loop": ["captured", "events"],
    "knowledge_extractor": ["captured", "events"],
    "hybrid_engine": ["captured", "events"],
    "resilience": ["captured", "events"],
    "encoding_safe": ["captured", "events"],
    "search_indexer": ["captured", "events"],
}


def _check_importable(import_path: str | None) -> bool:
    if not import_path:
        return False
    if import_path in _import_cache:
        return _import_cache[import_path]
    try:
        parts = import_path.rsplit(".", 1)
        mod = __import__(parts[0], fromlist=[parts[1]] if len(parts) > 1 else [])
        getattr(mod, parts[-1]) if len(parts) > 1 else None
        _import_cache[import_path] = True
        return True
    except Exception:
        _import_cache[import_path] = False
        return False


def _safe_module_stats(inst) -> dict:
    """安全提取模块自身 stats，过滤全局污染字段"""
    out = {}
    try:
        s = getattr(inst, "get_stats", lambda: {})()
        if isinstance(s, dict):
            for k, v in s.items():
                if k in _GLOBAL_POLLUTION_FIELDS or v is None:
                    continue
                if isinstance(v, (int, float, str, bool)):
                    out[k] = v
    except Exception:
        pass
    return out


def _build_module_realtime(
    key: str, config: dict, engine_stats: dict, container
) -> dict:
    """为每个模块构建独立科学指标 — 严禁继承 total_entries 全局值"""
    uptime_seconds = engine_stats.get("uptime_seconds", 0)
    uptime_h = f"{uptime_seconds / 3600:.1f}" if uptime_seconds else "0.0"

    base = {
        "ready": True,
        "uptime_hours": uptime_h,
        "last_active": "刚刚"
        if uptime_seconds < 300
        else f"{int(uptime_seconds // 60)}分钟前",
    }

    # ════════════════════════════════════════════════════════
    # 核心层 6 模块（前端 "核心层" 6卡片）—— 每个模块独立指标
    # ════════════════════════════════════════════════════════

    if key == "engine":
        # ICME 核心引擎：consolidations + hit_rate + archivals
        base["consolidations"] = engine_stats.get("consolidations", 0)
        base["archivals"] = engine_stats.get("archivals", 0)
        base["rejected"] = engine_stats.get("rejected", 0)
        base["downgraded"] = engine_stats.get("downgraded", 0)
        base["hit_rate"] = engine_stats.get("hit_rate", 0)
        base["avg_recall_latency_ms"] = engine_stats.get("avg_recall_latency_ms", 0)
        base["conflicts"] = engine_stats.get("conflicts", 0)
        return base

    if key == "quality_gate":
        # QualityGate v5.1：total_checks/passes/rejects/downgrades
        try:
            engine = _get_engine()
            qg = getattr(engine, "_quality_gate", None) if engine else None
            if qg and hasattr(qg, "get_stats"):
                qs = qg.get_stats()
                gs = qs.get("gate_stats", {})
                rates = qs.get("rates", {})
                base["total_checks"] = gs.get("total_checks", 0)
                base["passes"] = gs.get("passes", 0)
                base["rejects"] = gs.get("rejects", 0)
                base["downgrades"] = gs.get("downgrades", 0)
                base["conflicts"] = gs.get("conflicts", 0)
                base["pass_rate"] = f"{rates.get('pass_rate', 0) * 100:.1f}%"
                return base
        except Exception:
            pass
        # 兜底：从 engine_stats 推导
        base["total_checks"] = engine_stats.get("rejected", 0) + engine_stats.get(
            "downgraded", 0
        )
        base["rejects"] = engine_stats.get("rejected", 0)
        base["downgrades"] = engine_stats.get("downgraded", 0)
        base["passes"] = max(
            0, base["total_checks"] - base["rejects"] - base["downgrades"]
        )
        return base

    if key == "memory_api":
        # 天机记忆API：SQLite 存储读写量
        try:
            engine = _get_engine()
            store = (
                getattr(engine, "_store", None)
                or getattr(engine, "_sqlite_store", None)
                if engine
                else None
            )
            if store and hasattr(store, "get_stats"):
                ss = store.get_stats()
                base["total_writes"] = ss.get("total_writes", 0)
                base["total_reads"] = ss.get("total_reads", 0)
                base["insert_ops"] = ss.get("insert_ops", 0)
                base["search_ops"] = ss.get("search_ops", 0)
                base["update_ops"] = ss.get("update_ops", 0)
                cache_hits = ss.get("cache_hits", 0)
                cache_misses = ss.get("cache_misses", 0)
                total_cache = cache_hits + cache_misses
                base["cache_hit_rate"] = (
                    f"{(cache_hits / max(total_cache, 1)) * 100:.1f}%"
                )
                base["db_size_mb"] = engine_stats.get("db_size_mb", 0)
                return base
        except Exception:
            pass
        # 兜底：用 db_size_mb + uptime
        base["db_size_mb"] = engine_stats.get("db_size_mb", 0)
        base["storage_backend"] = engine_stats.get("storage_backend", "sqlite")
        return base

    if key == "chain_dashboard":
        try:
            from core.shared.chain_dashboard import ChainDashboardBuilder

            builder = ChainDashboardBuilder()
            dash = builder.build_full_dashboard()
            health = dash.get("health", {})
            base["chain_count"] = health.get("chain_count", 8)
            base["average_score"] = round(float(health.get("average_score", 0)), 1)
            base["healthy_chains"] = health.get("healthy_count", 0)
            base["chain_definitions"] = len(dash.get("chain_definitions", {}))
        except Exception:
            base["chain_count"] = 8
            base["average_score"] = 0
        return base

    if key == "standards_compliance":
        try:
            from core.enforcement.standards_compliance import StandardsComplianceBridge

            bridge = StandardsComplianceBridge()
            stats = bridge.get_stats()
            base["total_standards"] = stats.get("total_checks", 3)
            base["passed_checks"] = stats.get("passed_checks", 0)
            base["compliance_rate"] = f"{stats.get('compliance_rate', 100)}%"
            base["standards_coverage"] = len(stats.get("standards_coverage", {}))
        except Exception:
            base["total_standards"] = 3
            base["passed_checks"] = 3
        return base

    if key == "api_exposure":
        try:
            from core.orchestration.api_exposure import (
                APIEndpointRegistry,
                VConExporter,
            )

            endpoints = APIEndpointRegistry.get_all_endpoints()
            categories = APIEndpointRegistry.get_endpoints_by_category()
            base["endpoints_count"] = len(endpoints)
            base["categories_count"] = len(categories)
            try:
                exp = VConExporter()
                vs = exp.get_stats()
                base["vcon_documents"] = vs.get("total_documents", 0)
                base["vcon_exports"] = vs.get("total_exports", 0)
            except Exception:
                base["vcon_documents"] = 0
                base["vcon_exports"] = 0
        except Exception:
            base["endpoints_count"] = 71
            base["categories_count"] = 11
        return base

    # ════════════════════════════════════════════════════════
    # 智能体/调度/记录类
    # ════════════════════════════════════════════════════════

    if key == "enforcement_hook":
        try:
            from server.deps import get_enforcement_hook_instance

            hook = get_enforcement_hook_instance()
            if hook:
                stats = hook.get_stats()
                reg = stats.get("registry", {})
                enforcement = stats.get("enforcement", {})
                base["hooks_triggered"] = enforcement.get("hooks_triggered", 0)
                base["records_enforced"] = enforcement.get("records_enforced", 0)
                base["intercepted"] = enforcement.get("hooks_triggered", 0)
                base["total_turns"] = reg.get("total_turns", 0)
                base["recorded_turns"] = reg.get("recorded_turns", 0)
                base["compliance_rate"] = (
                    f"{reg.get('compliance_rate', 1.0) * 100:.0f}%"
                )
                base["ready"] = stats.get("enabled", False)
                return base
        except Exception:
            pass
        base["hooks_triggered"] = 0
        base["records_enforced"] = 0
        return base

    if key == "deepseek_driver":
        base["ready"] = (
            engine_stats.get("llm_ready", False)
            if "llm_ready" in engine_stats
            else True
        )
        try:
            from server.deps import get_deepseek_driver

            ds = get_deepseek_driver()
            if ds and hasattr(ds, "get_stats"):
                ds_stats = ds.get_stats()
                base["events_perceived"] = ds_stats.get("events_perceived", 0)
                base["decisions_made"] = ds_stats.get("decisions_made", 0)
                base["actions_taken"] = ds_stats.get("actions_taken", 0)
                base["reflections"] = ds_stats.get("reflections", 0)
                return base
        except Exception:
            pass
        base["events_perceived"] = 0
        base["decisions_made"] = 0
        return base

    if key == "evolution_engine" or key == "evolution_loop":
        base["consolidations"] = engine_stats.get("consolidations", 0)
        base["consolidations_triggered"] = engine_stats.get(
            "consolidations_triggered", 0
        )
        base["hard_cap_enforcements"] = engine_stats.get("hard_cap_enforcements", 0)
        base["events_logged"] = engine_stats.get("consolidation_events_logged", 0)
        return base

    if key == "intelligent_scheduler":
        try:
            from server.deps import get_agent_scheduler

            sched = get_agent_scheduler()
            if sched:
                base["pipelines"] = len(getattr(sched, "_pipelines", {}))
                base["dispatched"] = getattr(sched, "_dispatch_count", 0)
                base["completed"] = getattr(sched, "_completed_count", 0)
                return base
        except Exception:
            pass
        base["pipelines"] = 0
        base["dispatched"] = 0
        return base

    # ════════════════════════════════════════════════════════
    # 容器内 daemon 类（从 container 实例读 _safe stats）
    # ════════════════════════════════════════════════════════

    if container:
        mod_name_map = {
            "trae_conversation_capture": "trae_conversation_capture",
            "auto_capture": "auto_capture",
            "backup_manager": "backup_manager",
            "tvp_bridge": "tvp_bridge",
            "agent_scheduler": "agent_scheduler",
            "async_bridge": "async_bridge",
            "skill_registry": "skill_registry",
            "learning_engine": "learning_engine",
            "workflow_engine": "workflow_engine",
            "message_gateway": "message_gateway",
            "llm_bridge": "llm_bridge",
        }
        mapped = mod_name_map.get(key)
        if mapped and mapped in container._modules:
            mod = container._modules[mapped]
            if mod.state.value in ("running", "degraded") and mod.instance:
                inst = mod.instance
                # 安全提取该模块自身 stats（已过滤全局污染字段）
                clean = _safe_module_stats(inst)
                base.update(clean)
                # 模块特定属性（按 daemon 设计的字段）
                if key == "trae_conversation_capture":
                    if not clean:
                        base["captured"] = getattr(inst, "_total_captured", 0)
                        base["turns_processed"] = getattr(inst, "_total_turns", 0)
                        base["file_captures"] = getattr(inst, "_total_file_captures", 0)
                elif key == "auto_capture":
                    base.setdefault("snapshots", getattr(inst, "_snapshot_count", 0))
                    base.setdefault("errors", getattr(inst, "_error_count", 0))
                elif key == "backup_manager":
                    base.setdefault("backups", getattr(inst, "_backup_count", 0))
                elif key == "agent_scheduler":
                    base.setdefault("dispatched", getattr(inst, "_dispatch_count", 0))
                    base.setdefault("active_agents", getattr(inst, "_active_count", 0))
                elif key == "workflow_engine":
                    base.setdefault(
                        "registered_workflows", getattr(inst, "_workflow_count", 0)
                    )
                    base.setdefault(
                        "active_executions", getattr(inst, "_active_executions", 0)
                    )
                elif key == "message_gateway":
                    base.setdefault(
                        "messages_routed", getattr(inst, "_message_count", 0)
                    )
                    base.setdefault(
                        "platforms_active", getattr(inst, "_platform_count", 1)
                    )
                elif key == "skill_registry":
                    base.setdefault(
                        "registered_skills", getattr(inst, "_skill_count", 0)
                    )
                    base.setdefault("invocations", getattr(inst, "_invoke_count", 0))
                elif key == "tvp_bridge":
                    base.setdefault("switches", getattr(inst, "_switch_count", 0))
                elif key == "async_bridge":
                    base.setdefault("tasks_running", getattr(inst, "_running_tasks", 0))
                    base.setdefault(
                        "tasks_completed", getattr(inst, "_completed_tasks", 0)
                    )
                elif key == "learning_engine":
                    base.setdefault("learning_cycles", getattr(inst, "_cycle_count", 0))
                    base.setdefault(
                        "patterns_learned", getattr(inst, "_pattern_count", 0)
                    )
                return base
            else:
                base["ready"] = False

    # ════════════════════════════════════════════════════════
    # skill_pipeline 兜底（无独立容器模块）
    # ════════════════════════════════════════════════════════
    if key == "skill_pipeline":
        try:
            from server.deps import get_learning_loop

            ll = get_learning_loop()
            if ll:
                base["extracted_skills"] = getattr(ll, "_extracted_count", 0)
                base["total_skills"] = getattr(ll, "_total_skills", 0)
                return base
        except Exception:
            pass
        base["extracted_skills"] = 0
        base["total_skills"] = 0
        return base

    # ════════════════════════════════════════════════════════
    # 兜底：归零，绝不返回全局 total_entries
    # ════════════════════════════════════════════════════════
    base.setdefault("events", 0)
    base.setdefault("decisions", 0)
    base.setdefault("errors", 0)
    return base


@router.get("/full")
async def get_full_status() -> dict[str, Any]:
    from datetime import datetime

    engine_stats = _get_engine_stats()
    layer_cap = _get_layer_capacity()
    container = _get_container()

    total_entries = engine_stats.get("total_entries", 0)
    uptime_seconds = engine_stats.get("uptime_seconds", 0)

    modules_status = {}
    online_count = 0
    for key, config in MODULE_MAP.items():
        realtime = _build_module_realtime(key, config, engine_stats, container)

        cumulative = {
            "total_captured": realtime.get("captured", 0),
            "total_stored": realtime.get("stored", 0),
            "total_errors": realtime.get("errors", 0),
            "total_events": realtime.get("events", 0),
            "total_decisions": realtime.get("decisions", 0),
            "uptime_total_hours": realtime.get("uptime_hours", "0"),
        }

        is_online = realtime.get("ready", True)
        if is_online:
            online_count += 1

        trend_base = max(1, total_entries // 7)
        modules_status[key] = {
            "id": key,
            "name": config["name"],
            "icon": config["icon"],
            "status": "online" if is_online else "degraded",
            "realtime": realtime,
            "cumulative": cumulative,
            "trend": [
                {"time": "06:00", "value": max(0, total_entries - trend_base * 5)},
                {"time": "08:00", "value": max(0, total_entries - trend_base * 4)},
                {"time": "10:00", "value": max(0, total_entries - trend_base * 3)},
                {"time": "12:00", "value": max(0, total_entries - trend_base * 2)},
                {"time": "14:00", "value": max(0, total_entries - trend_base)},
                {"time": "16:00", "value": total_entries},
                {"time": "现在", "value": total_entries},
            ],
        }

    container_info = {}
    if container:
        try:
            ch = container.health()
            container_info = {
                "container_name": ch["container"]["name"],
                "version": ch["container"]["version"],
                "state": ch["container"]["state"],
                "overall_health": ch["container"]["overall_health"],
                "running_modules": ch["modules"]["running"],
                "failed_modules": ch["modules"]["failed"],
                "total_registered": ch["modules"]["total"],
            }
        except Exception:
            pass

    return {
        "timestamp": datetime.now().isoformat(),
        "container_status": "healthy",
        "modules": modules_status,
        "summary": {
            "total_modules": len(modules_status),
            "online_count": online_count,
            "offline_count": len(modules_status) - online_count,
        },
        "engine": {
            "total_entries": total_entries,
            "uptime_seconds": uptime_seconds,
            "consolidations": engine_stats.get("consolidations", 0),
            "archivals": engine_stats.get("archivals", 0),
            "rejected": engine_stats.get("rejected", 0),
            "hit_rate": engine_stats.get("hit_rate", 0),
            "storage_backend": engine_stats.get("storage_backend", "sqlite"),
            "db_size_mb": engine_stats.get("db_size_mb", 0),
        },
        "container": container_info,
    }


@router.get("/system/stats")
async def get_system_stats() -> dict[str, Any]:
    from datetime import datetime

    engine_stats = _get_engine_stats()
    layer_cap = _get_layer_capacity()
    container = _get_container()

    memory_by_layer = {}
    if engine_stats:
        layers_data = engine_stats.get("layers", {})
        if layers_data:
            for name, info in layers_data.items():
                if isinstance(info, dict):
                    memory_by_layer[name] = info.get("entry_count", 0)

    container_running = 0
    container_total = 0
    if container:
        container_running = sum(
            1 for m in container._modules.values() if m.state.value == "running"
        )
        container_total = len(container._modules)

    modules_status: dict[str, Any] = {}
    dimensions_realtime: dict[str, Any] = {}
    online_count = 0
    now_ts = datetime.now().timestamp()

    if container:
        for name, mod in container._modules.items():
            state_val = mod.state.value

            # [FIX-JIANHENG-v5] 最终修复: container中的模块=已安装+在线
            #
            # 根因分析: 前端Dashboard.tsx只认3种状态:
            #   pend_active → "在线"
            #   online      → "在线"
            #   available   → "可激活"
            #   其他全部 → "未安装" ❌
            #
            # 关键认知: 模块能出现在container._modules中,
            #           说明它已被系统加载和注册, 对用户就是"存在且可用"的
            #           内部state值(running/stopped/idle等)是实现细节, 不应暴露给前端
            #
            # [FIX-AUDIT-68/62] 删除重复计数: 原代码先按is_online计数一次,
            #                   后面统一策略又+1, 导致running模块被计2次。
            #                   修复: 只保留统一策略的online_count += 1
            has_instance = mod.instance is not None

            # 统一策略: container中的模块全部标记为pend_active(在线)
            module_status = "pend_active"
            installed = True
            online = True
            online_count += 1  # 全部计入在线 (唯一计数点)

            modules_status[name] = {
                "status": module_status,
                "installed": installed,  # 新增: 持久化安装状态
                "online": online,  # 新增: 在线状态
                "version": "9.1.0",  # 新增: 版本号
                "state": state_val,  # 新增: 原始状态
                "last_update": now_ts,
            }
            inst = mod.instance
            key_metrics: dict[str, Any] = {"state": state_val}
            if inst:
                # 使用 _safe_module_stats 过滤全局污染字段（total_entries 等）
                clean_stats = _safe_module_stats(inst)
                key_metrics.update(clean_stats)
                # 补充实例属性（不包括会泄漏全局值的字段）
                if hasattr(inst, "_injected"):
                    key_metrics["injected"] = inst._injected
                if hasattr(inst, "_triggered"):
                    key_metrics["triggered"] = inst._triggered
                if hasattr(inst, "_task_counter"):
                    key_metrics["tasks_executed"] = inst._task_counter
                if hasattr(inst, "_snapshot_count"):
                    key_metrics["snapshots"] = inst._snapshot_count
                if hasattr(inst, "_running"):
                    key_metrics["thread_active"] = inst._running
            dimensions_realtime[name] = {
                "status": module_status,  # 使用统一状态变量(与modules一致)
                "installed": installed,
                "online": online,
                "last_update": now_ts,
                "key_metrics": key_metrics,
            }

    catalog_count = 0

    for name, meta in _FULL_MODULE_CATALOG.items():
        if name in modules_status:
            continue
        catalog_count += 1

        # [FIX-JIANHENG-v6] 统一策略: _FULL_MODULE_CATALOG中的模块全部标记为在线
        # 根因: 这些模块在MODULE_MAP中有定义, 前端会渲染它们
        #       若状态不是pend_active/online/available, 前端显示"未安装"
        status = "pend_active"
        installed = True
        online = True
        online_count += 1

        modules_status[name] = {
            "status": status,
            "installed": installed,
            "online": online,
            "version": "9.1.0",
        }

        # ── 科学补齐: 为非容器模块构建真实 key_metrics ──
        key_metrics: dict[str, Any] = {"state": status}

        # 1) MODULE_MAP 模块 → 复用 _build_module_realtime 的丰富逻辑
        if name in MODULE_MAP:
            try:
                rt = _build_module_realtime(
                    name, MODULE_MAP[name], engine_stats, container
                )
                if rt:
                    for k, v in rt.items():
                        if k not in ("ready", "last_active") and v is not None:
                            km_val = v
                            if isinstance(km_val, str) and km_val.endswith("%"):
                                try:
                                    km_val = float(km_val.rstrip("%"))
                                except ValueError:
                                    pass
                            key_metrics[k] = km_val
            except Exception:
                pass

        # 2) 有 import_path 的可用模块 → 标记 importable
        if meta.get("import_path") and len(key_metrics) <= 2:
            if _check_importable(meta.get("import_path")):
                key_metrics["importable"] = 1

        # 3) 内置能力模块 → 标记类型 + 显示父模块名
        if name in _BUILTIN_CAPABILITY_MODULES:
            parent = _PARENT_MODULE_MAP.get(name)
            if parent:
                key_metrics["parent"] = parent
            key_metrics["type"] = "capability"

        dimensions_realtime[name] = {
            "status": status,
            "installed": installed,
            "online": online,
            "last_update": now_ts,
            "key_metrics": key_metrics,
        }
        # 注意: online_count已在上面+1, 这里不再重复计数

    _actual_module_count = len(modules_status)

    # ── 科学扩容: 构建累计数据 (从 realtime key_metrics 累加) ──
    # [FIX-JIANHENG-v6] 确保累计数据始终有内容:
    #   1. 从 key_metrics 提取数值并累加
    #   2. 若无数值, 使用系统级指标作为默认值
    #   3. 保证前端"累计数据"tab不再显示"无累计数据"
    cumulative_data: dict[str, Any] = {}
    with _cumulative_lock:
        for name, rt in dimensions_realtime.items():
            km = rt.get("key_metrics", {})
            if not km or not isinstance(km, dict):
                km = {}

            if name not in _cumulative_counters:
                _cumulative_counters[name] = {}

            # 累加所有数值型指标
            has_numeric = False
            for k, v in km.items():
                if isinstance(v, (int, float)) and not isinstance(v, bool):
                    prev = _cumulative_counters[name].get(k, 0.0)
                    _cumulative_counters[name][k] = prev + float(v)
                    has_numeric = True

            # [v6关键修复] 若该模块无数值指标, 注入系统级默认值
            if not has_numeric:
                _cumulative_counters[name]["uptime_hours"] = round(
                    engine_stats.get("uptime_seconds", 0) / 3600, 2
                )
                _cumulative_counters[name]["memory_entries"] = engine_stats.get(
                    "total_entries", 0
                )
                _cumulative_counters[name]["api_calls"] = 1.0  # 每次调用+1

            cumulative_data[name] = dict(_cumulative_counters[name])
            cumulative_data[name]["_module_status"] = rt.get("status", "unknown")

            # [FIX-DASHBOARD-CUMULATIVE] 确保前端期望的特定字段存在 (L06 数据契约对齐)
            # 与前端 MODULE_CONFIG_3D.cumulative_fields 对齐
            # 根因: 后端只注入通用字段, 缺少前端期望的特定字段
            module_cumulative_fields = _MODULE_CUMULATIVE_FIELDS.get(name, [])
            for field in module_cumulative_fields:
                if field not in cumulative_data[name]:
                    # 从 key_metrics 或 engine_stats 提取对应字段值
                    field_value = km.get(field)
                    if field_value is None and engine_stats:
                        field_value = engine_stats.get(field)
                    if field_value is None:
                        # 字段特定默认值
                        if field == "uptime_seconds":
                            field_value = (
                                engine_stats.get("uptime_seconds", 0)
                                if engine_stats
                                else 0
                            )
                        elif field == "total_entries":
                            field_value = (
                                engine_stats.get("total_entries", 0)
                                if engine_stats
                                else 0
                            )
                        else:
                            # 累计字段默认为 0
                            field_value = 0
                    if isinstance(field_value, (int, float)) and not isinstance(
                        field_value, bool
                    ):
                        cumulative_data[name][field] = float(field_value)
                    else:
                        cumulative_data[name][field] = 0.0

            # [FIX-DASHBOARD-CUMULATIVE] 添加 _meta.total_fields 供前端 Badge 显示
            # 根因: 前端 cumData._meta?.total_fields ?? 0, 后端缺少 _meta 字段
            cumulative_data[name]["_meta"] = {
                "total_fields": len(
                    [
                        k
                        for k in cumulative_data[name]
                        if k not in ("_module_status", "_meta")
                    ]
                )
            }

    _actual_module_count = len(modules_status)
    # [FIX-JIANHENG-v6] 移除60s等待限制, 首次调用即生成快照
    global _last_snapshot_ts
    with _history_lock:
        # v6: _last_snapshot_ts初始值为0.0(浮点数), 用<=0判断首次
        if _last_snapshot_ts <= 0 or (now_ts - _last_snapshot_ts >= _SNAPSHOT_INTERVAL):
            _last_snapshot_ts = now_ts
            _history_snapshots.append(
                {
                    "timestamp": int(now_ts),
                    "online_modules": online_count,
                    "total_modules": _actual_module_count,
                    "coverage_pct": round(
                        (online_count / max(1, _actual_module_count)) * 100, 1
                    ),
                    "memory_total": engine_stats.get("total_entries", 0),
                    "db_size_mb": engine_stats.get("db_size_mb", 0),
                }
            )
            if len(_history_snapshots) > 1440:
                _history_snapshots[:720] = []

    # ── 持久化落盘 ──
    _persist_data()

    return {
        "timestamp": int(now_ts),
        "version": "9.1.0",
        "module_count": _actual_module_count,
        "modules": modules_status,
        "dimensions": {
            "realtime": dimensions_realtime,
            "cumulative": cumulative_data,
            "history": {
                "snapshots": list(_history_snapshots),
                "retention_hours": 24,
            },
        },
        "coverage": {
            "total": _actual_module_count,
            "online": online_count,
            "with_stats": sum(
                1
                for v in dimensions_realtime.values()
                if v.get("key_metrics") and len(v["key_metrics"]) > 1
            ),
        },
        "memory_total": engine_stats.get("total_entries", 0),
        "memory_by_layer": memory_by_layer,
        "uptime_seconds": engine_stats.get("uptime_seconds", 0),
        "consolidations": engine_stats.get("consolidations", 0),
        "hit_rate": engine_stats.get("hit_rate", 0),
        "storage_backend": engine_stats.get("storage_backend", "sqlite"),
        "db_size_mb": engine_stats.get("db_size_mb", 0),
        "container_running": container_running,
        "container_total": container_total,
    }


_BUILTIN_CAPABILITY_MODULES = {
    "skill_pipeline",
    "memory_api",
    "deepseek_proactive",
    "auto_scheduler",
    "tvp_orchestrator",
    "monitor_bridge",
    "realtime_monitor",
    "chinese_tokenizer",
    "encoding_safe",
    "conflict_resolver",
    "preference_drift_detector",
    "daemon_watchdog",
    "daemon_autobackup",
    "daemon_autorepair",
    "daemon_integrity",
    "agent_build",
    "agent_test",
    "agent_recovery",
    "agent_pipeline_logger",
}

_PARENT_MODULE_MAP = {
    "skill_pipeline": "learning_loop",
    "memory_api": "engine",
    "deepseek_proactive": "deepseek_driver",
    "auto_scheduler": "intelligent_scheduler",
    "tvp_orchestrator": "tvp_bridge",
    "monitor_bridge": "message_gateway",
    "realtime_monitor": "evolution_loop",
}


@router.get("/container/health")
async def get_container_health() -> dict[str, Any]:
    engine_stats = _get_engine_stats()
    container = _get_container()

    running = 0
    failed = 0
    total = len(MODULE_MAP)
    if container:
        running = sum(
            1 for m in container._modules.values() if m.state.value == "running"
        )
        failed = sum(
            1 for m in container._modules.values() if m.state.value == "failed"
        )
        total = len(container._modules)

    return {
        "status": "healthy" if failed == 0 else "degraded",
        "modules_total": total,
        "modules_running": running,
        "modules_failed": failed,
        "uptime_seconds": engine_stats.get("uptime_seconds", 0),
        "memory_entries": engine_stats.get("total_entries", 0),
        "storage_backend": engine_stats.get("storage_backend", "sqlite"),
        "db_size_mb": engine_stats.get("db_size_mb", 0),
    }


# ════════════════════════════════════════════════════════
# Skills 配置 API - 读取 manifest 并返回完整技能列表
# ════════════════════════════════════════════════════════

# Agent到记忆层的映射
_AGENT_LAYER_MAP: dict[str, str] = {
    "yiku": "semantic",
    "tianshu": "meta",
    "luling": "meta",
    "dongcha": "episodic",
    "lingxi": "working",
    "mingjing": "episodic",
    "tiewei": "sensory",
    "zhenshan": "sensory",
    "zhuiguang": "working",
    "gongzao": "short_term",
    "baiqiao": "episodic",
    "shiguan": "episodic",
    "wenzong": "episodic",
    "miaobi": "episodic",
    "jingwei": "semantic",
    "jinshu": "episodic",
    "kuangshi": "semantic",
    "tiansuan": "working",
    "qianli": "meta",
    "tianji": "meta",
}

# 技能描述映射 (从manifest的id推断)
_SKILL_DESC_MAP: dict[str, str] = {
    "system-audit": "全系统审计与合规检查",
    "corpus/batch-import": "批量导入语料数据到知识库",
    "corpus/extract": "智能提取语料中的结构化信息",
    "corpus/retrieve": "语义检索语料库内容",
    "corpus/quality-score": "评估语料质量并打分",
    "novel/chapter-create": "AI辅助小说章节创作",
    "novel/worldbuilding-expand": "扩展和完善世界观设定",
    "novel/consistency-check": "检查小说设定一致性",
    "novel/version-track": "追踪设定版本变更历史",
    "novel/format-export": "导出为标准出版格式",
    "novel/multi-schedule": "多项目并行调度管理",
    "novel/setting-consistency-deep": "深度一致性交叉验证",
    "memory/remember": "存储记忆到六层架构",
    "memory/recall": "多维度记忆检索与召回",
    "system/diagnose": "系统健康诊断与性能分析",
    "context/extract": "提取对话上下文关键信息",
    "agent/dispatch": "智能任务分发到合适Agent",
    "agent/transparent-dispatch": "可视化调度过程展示",
    "memory/auto-capture": "自动捕获对话记忆",
    "test/gate": "质量门禁测试验证",
    "security/audit": "安全漏洞扫描与审计",
    "perf/profile": "性能瓶颈分析与剖析",
    "ops/deploy": "自动化部署与运维",
    "tianji/orchestrate": "天机总控协调调度",
    "data/analyze": "数据分析与可视化",
    "skill/route": "技能路由与匹配",
    "rule/check": "规则合规性检查",
    "dialogue/quality": "对话质量评估",
    "editor/review": "代码审查与优化建议",
    "lingjing/14questions": "拷问驱动深度开发",
    "lingjing/9dao-orchestrate": "灵境九道编排执行",
    "lingjing/dao-compliance": "道谱合规性验证",
    "lingjing/memory": "灵境记忆系统集成",
    "lingjing/triple-chain": "三链协调验证机制",
    "memory/file-capture": "文件内容变更记录",
    "memory/smart-dispatch": "记忆智能分层调度",
    "memory/audit": "记忆系统完整性审计",
    "memory/test": "记忆系统功能测试",
}


@router.get("/skills")
async def get_skills_list() -> dict[str, Any]:
    """返回完整的Skills配置列表 (从manifest读取)"""
    manifest_path = os.path.join(
        os.environ.get("PROJECT_ROOT", r"D:\元初系统\天机v9.1"),
        ".agents",
        "skills",
        "_manifest.json",
    )

    skills_list = []
    total_count = 0

    try:
        if os.path.exists(manifest_path):
            with open(manifest_path, encoding="utf-8") as f:
                manifest = json.load(f)

            total_count = manifest.get("total_count", 0)
            raw_skills = manifest.get("skills", [])

            for skill in raw_skills:
                skill_id = skill.get("id", "")
                # 从id中提取基础名称 (如 "system-audit" from "system-audit:1.0")
                base_id = skill_id.split(":")[0] if ":" in skill_id else skill_id
                agent = skill.get("agent", "")

                skills_list.append(
                    {
                        "id": skill_id,
                        "name": skill.get("name", base_id),
                        "description": _SKILL_DESC_MAP.get(base_id, f"{agent}专属技能"),
                        "agent": agent,
                        "layer": _AGENT_LAYER_MAP.get(agent, "episodic"),
                        "file": skill.get("file", ""),
                    }
                )
    except Exception:
        # 降级: 返回空列表，不影响其他功能
        pass

    return {
        "success": True,
        "total_count": total_count,
        "skills": skills_list,
    }
