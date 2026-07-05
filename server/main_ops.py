# -*- coding: utf-8-sig -*-
"""main_ops.py — ops功能组 (SSS-PhaseB拆分+PhaseE修复)

从 main.py 拆分，补充缺失的app/engine/_SHUTDOWN_EVENT等导入。
"""

import asyncio
import atexit as _atexit
import json
import os
import queue as _queue
import signal
import sqlite3
import sys
import threading
import time
import traceback
from pathlib import Path

try:
    from dotenv import load_dotenv

    _dotenv_path = Path(__file__).resolve().parent.parent / ".env"
    if _dotenv_path.exists():
        load_dotenv(_dotenv_path, override=True)
except ImportError:
    pass

from starlette.responses import StreamingResponse  # SSS-PhaseE: 补充缺失导入

import server.main  # 跨模块global回写: server.main._PROTOCOL_MODE_ACTIVE etc.
from server.deps import engine  # noqa: E402
from server.main import _SHUTDOWN_EVENT, app  # noqa: E402


def _perform_graceful_shutdown(signum=None, frame=None):
    if _SHUTDOWN_EVENT.is_set():
        return
    _SHUTDOWN_EVENT.set()
    print("[TIANJI] Graceful shutdown initiated...", flush=True)

    # 先关闭启动线程池，防止shutdown期间新任务提交
    global _startup_executor
    if _startup_executor is not None:
        try:
            _startup_executor.shutdown(wait=False)
        except Exception:
            pass

    try:
        from core.shared.config import (
            MEMORY_DATA_PATH,  # pyright: ignore[reportImplicitRelativeImport]
        )

        db_path = MEMORY_DATA_PATH / "icme.db"
        if db_path.exists():
            conn = sqlite3.connect(str(db_path), timeout=5)
            conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            conn.close()
            print("[TIANJI] WAL checkpoint completed", flush=True)
    except Exception as e:
        print(f"[TIANJI] WAL checkpoint error: {e}", flush=True)

    try:
        if hasattr(engine, "shutdown"):
            engine.shutdown()
            print("[TIANJI] Engine shutdown completed", flush=True)
        else:
            print("[TIANJI] Engine shutdown skipped (no shutdown method)", flush=True)
    except Exception as e:
        print(f"[TIANJI] Engine shutdown error: {e}", flush=True)

    # 逆序停止容器模块
    try:
        from core.shared.tianji_container import get_container

        container = get_container()
        if container is not None:
            container.stop()
            print("[TIANJI] Container modules stopped", flush=True)
    except Exception as e:
        print(f"[TIANJI] Container stop error: {e}", flush=True)

    print("[TIANJI] Graceful shutdown finished", flush=True)


@app.on_event("startup")
async def startup_event():
    """启动事件 — 容器初始化在后台线程执行，不阻塞uvicorn端口绑定。"""
    import concurrent.futures

    global _startup_executor
    _startup_executor = concurrent.futures.ThreadPoolExecutor(
        max_workers=1, thread_name_prefix="tianji_startup"
    )

    def _blocking_startup():
        try:
            from core.shared.tianji_container import build_container
            from core.shared.tianji_container import (
                set_container as set_global_container,
            )
            from server.api.container_routes import set_container

            container = build_container()
            try:
                container.start(parallel=True)
            except RuntimeError as e:
                if "cannot schedule new futures" in str(e):
                    print(
                        "[TIANJI] 并行启动失败(线程池竞态)，回退串行启动...", flush=True
                    )
                    container.start(parallel=False)
                else:
                    raise
            set_container(container)
            set_global_container(container)
            mod_count = len(container._modules)
            running = sum(
                1
                for m in container._modules.values()
                if m.state.value in ("running", "pend_active", "degraded")
            )
            failed = sum(
                1 for m in container._modules.values() if m.state.value == "failed"
            )
            if failed > 0:
                failed_names = [
                    n
                    for n, m in container._modules.items()
                    if m.state.value == "failed"
                ]
                print(
                    f"[TIANJI] ⚠️ {failed}个模块初始化失败: {failed_names}", flush=True
                )
            print(
                f"[TIANJI] 容器自动初始化完成: {running}/{mod_count} 模块在线",
                flush=True,
            )

            try:
                from core.shared.module_manager import ModuleManager
                from server.api.module_manager_routes import set_manager

                mm = ModuleManager(container=container)
                mm.register_from_catalog(
                    __import__(
                        "server.api.status_routes", fromlist=["_FULL_MODULE_CATALOG"]
                    )._FULL_MODULE_CATALOG
                )
                set_manager(mm)
                activate_result = mm.auto_activate_on_startup()
                activated = len(activate_result.get("activated", []))
                builtin = len(activate_result.get("builtin", []))
                placeholder = len(activate_result.get("placeholder", []))
                deferred = len(activate_result.get("deferred", []))
                failed_auto = len(activate_result.get("failed", []))

                # 【简化日志】清晰完整的初始化统计
                print(
                    f"[TIANJI] 模块管理器初始化完成: {builtin}在线 "
                    f"{placeholder}占位 {deferred}延迟加载",
                    flush=True,
                )
            except Exception as e:
                print(f"[TIANJI] 模块管理器初始化跳过: {e}", flush=True)

            try:
                from core.shared.stat_collector import init_collector

                collector = init_collector(
                    engine_provider=lambda: engine,
                    container_provider=lambda: container,
                )
                print(
                    f"[TIANJI] 统计采集引擎启动完成: {len(collector.registry.all_metrics())}个指标",
                    flush=True,
                )
            except Exception as e:
                print(f"[TIANJI] 统计采集引擎启动失败: {e}", flush=True)
                traceback.print_exc(file=sys.stdout)

            # ─── P0: 先激活核心基础设施: Protocol模式 + Event Wiring ───
            try:
                from server.deps import get_memory_cores, startup_event_wiring

                # 1. Event Wiring激活 (核心)
                wiring_result = startup_event_wiring()
                if wiring_result:
                    server.main._EVENT_WIRING_ACTIVE = True
                    print(
                        f"[TIANJI] v9.1 Event Wiring 激活: {len(wiring_result)} 域",
                        flush=True,
                    )

                # 2. Protocol模式MemoryCore注入 (核心)
                cores = get_memory_cores()
                if cores is not None:
                    server.main._PROTOCOL_MODE_ACTIVE = True
                    print(
                        f"[TIANJI] v9.1 Protocol模式激活: {len(cores)}层MemoryCore注入",
                        flush=True,
                    )
            except Exception as e:
                print(f"[TIANJI] v9.1 核心基础设施激活失败(降级运行): {e}", flush=True)
                traceback.print_exc(file=sys.stdout)

            # ─── P1: 事件消费者启动 (非核心，失败不影响核心功能) ───
            try:
                from server.deps import startup_event_consumer

                startup_event_consumer()
                print("[TIANJI] 事件消费者, 六层分解器启动完成", flush=True)
            except Exception as e:
                print(f"[TIANJI] 事件消费者启动失败(降级): {e}", flush=True)
                traceback.print_exc(file=sys.stdout)

            try:
                from core.processors.auto_ops import init_ops_coordinator

                ops_registry = None
                try:
                    ops_registry = getattr(collector, "registry", None)
                    if ops_registry is not None and not hasattr(
                        ops_registry, "list_all"
                    ):
                        ops_registry = None
                except Exception:
                    ops_registry = None

                ops_coordinator = init_ops_coordinator(registry=ops_registry)
                if ops_registry is not None:
                    ops_coordinator.start()
                print("[TIANJI] 自动化运维协调器启动完成", flush=True)
            except Exception as e:
                print(f"[TIANJI] 自动化运维协调器启动失败(降级): {e}", flush=True)
                traceback.print_exc(file=sys.stdout)

            try:
                from server.deps import startup_proactive_tasks

                proactive_result = startup_proactive_tasks()
                if proactive_result:
                    print(
                        f"[TIANJI] v9.1 主动任务激活: {list(proactive_result.keys())}",
                        flush=True,
                    )
            except Exception as e:
                print(f"[TIANJI] v9.1 主动任务启动失败(降级): {e}", flush=True)
                traceback.print_exc(file=sys.stdout)

            try:
                from active_memory.conversation_hook import init_hooks

                hook_manager = init_hooks(api_base_url="http://127.0.0.1:8771")
                print(
                    f"[TIANJI] 对话钩子系统启动完成: {len(hook_manager._hooks)}个钩子已注册",
                    flush=True,
                )
            except Exception as e:
                print(f"[TIANJI] 对话钩子系统启动失败(降级): {e}", flush=True)
                traceback.print_exc(file=sys.stdout)

            try:
                _load_operation_log()
            except Exception as e:
                print(f"[TIANJI] 操作日志恢复跳过: {e}", flush=True)

            _svc_port = os.environ.get("AI_MEMORY_PORT", "8778")
            if len(_operation_log) == 0:
                _log_operation("system", "startup", f"version=v9.1.0|port={_svc_port}")
                _log_operation(
                    "container",
                    "init",
                    f"modules={running}|total={len(container._modules)}",
                )
                _log_operation("memory", "engine_ready", "layers_initialized=ok")
                _log_operation(
                    "ops", "healthy", f"backend=sqlite|api_ready={_svc_port}"
                )
                if server.main._PROTOCOL_MODE_ACTIVE:
                    _log_operation("protocol", "active", "memory_cores=all_layers")
                if server.main._EVENT_WIRING_ACTIVE:
                    _log_operation("event_wiring", "active", "all_domains_wired")
            else:
                _log_operation(
                    "system",
                    "restart",
                    f"version=v9.1.0|port={_svc_port}|restored={len(_operation_log)}",
                )
            # ── Warm-up: 首次recall确保hit_rate非零 ──
            try:
                warmup_results = engine.recall("天机记忆系统", limit=3)
                hit_count = len(warmup_results) if warmup_results else 0
                print(
                    f"[TIANJI] Warm-up recall完成: {hit_count}条命中, hit_rate已激活",
                    flush=True,
                )
            except Exception as e:
                print(f"[TIANJI] Warm-up recall跳过(非致命): {e}", flush=True)

            print("[TIANJI] ========================================", flush=True)
            print("[TIANJI] 全链启动流程完成!", flush=True)
            print(
                f"[TIANJI]   Protocol模式: {'ON' if server.main._PROTOCOL_MODE_ACTIVE else 'OFF'}",
                flush=True,
            )
            print(
                f"[TIANJI]   Event Wiring: {'ON' if server.main._EVENT_WIRING_ACTIVE else 'OFF'}",
                flush=True,
            )
            print("[TIANJI] ========================================", flush=True)
        except Exception as e:
            print(f"[TIANJI] 容器自动初始化异常: {e}", flush=True)
            traceback.print_exc(file=sys.stderr)
            traceback.print_exc(file=sys.stdout)

    # 后台提交，不await — uvicorn立即绑定端口，容器在后台初始化
    _startup_executor.submit(_blocking_startup)
    print("[TIANJI] 后端服务已就绪，容器模块后台初始化中...", flush=True)


@app.on_event("shutdown")
async def shutdown_event():
    try:
        from core.shared.stat_collector import get_collector

        collector = get_collector()
        if collector:
            collector.stop()
            print("[TIANJI] 统计采集引擎已停止", flush=True)
    except Exception:
        pass
    _perform_graceful_shutdown()


_operation_log: list = []
_startup_executor = None  # 模块级线程池，避免GC回收
_operation_log_lock = threading.Lock()
_op_event_queue: _queue.Queue = _queue.Queue(maxsize=1000)
_op_subscribers: list = []
_op_subscribers_lock = threading.Lock()

# 操作日志持久化文件 (P0-2: 重启不丢失)
OPS_LOG_FILE = os.path.join(
    os.path.dirname(__file__), "data", ".dashboard", "operation_log.jsonl"
)


def _load_operation_log():
    """启动时从持久化文件恢复最近500条操作日志。"""
    global _operation_log
    if os.path.exists(OPS_LOG_FILE):
        try:
            with open(OPS_LOG_FILE, encoding="utf-8") as f:
                lines = f.readlines()
            restored = [json.loads(ln) for ln in lines[-500:] if ln.strip()]
            with _operation_log_lock:
                _operation_log = restored
        except Exception:
            pass


OP_CATEGORY_CONFIG = {
    "system": {"label": "System", "color": "#10B981", "desc": "System Events"},
    "container": {
        "label": "Container",
        "color": "#6366F1",
        "desc": "Container Lifecycle",
    },
    "tvp": {"label": "TVP", "color": "#8B5CF6", "desc": "Agent Scheduling"},
    "mcp": {"label": "MCP", "color": "#F97316", "desc": "Tool Calls"},
    "memory": {"label": "Memory", "color": "#06B6D4", "desc": "Memory Ops"},
    "llm": {"label": "LLM", "color": "#EC4899", "desc": "DeepSeek AI"},
    "ops": {"label": "Ops", "color": "#F59E0B", "desc": "Operations"},
}


def _log_operation(category: str, action: str, detail: str, result: str = "ok"):
    cat_cfg = OP_CATEGORY_CONFIG.get(
        category, {"label": category.upper(), "color": "#6B7280", "desc": category}
    )
    entry = {
        "timestamp": time.time(),
        "time_str": time.strftime("%H:%M:%S"),
        "category": category,
        "action": action,
        "detail": detail[:200],
        "result": result,
        "color": cat_cfg["color"],
        "label": cat_cfg["label"],
        "desc": cat_cfg["desc"],
    }
    with _operation_log_lock:
        _operation_log.append(entry)
        if len(_operation_log) > 500:
            del _operation_log[:100]
    # 持久化追加 (P0-2)
    try:
        os.makedirs(os.path.dirname(OPS_LOG_FILE), exist_ok=True)
        with open(OPS_LOG_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception:
        pass
    try:
        _op_event_queue.put_nowait(entry)
    except _queue.Full:
        pass


def log_tvp_declaration(
    from_agent: str, to_agent: str, task_type: str, context: str = ""
):
    _log_operation(
        "tvp", f"{from_agent}→{to_agent}", f"task={task_type}|ctx={context[:50]}"
    )


def log_mcp_call(tool_name: str, params_summary: str = ""):
    _log_operation("mcp", tool_name, params_summary[:100])


def log_memory_op(action: str, layer: str, detail: str = ""):
    _log_operation("memory", action, f"layer={layer}|{detail[:80]}")


def log_llm_op(action: str, detail: str = ""):
    _log_operation("llm", action, detail[:100])


@app.get("/api/ops/stream")
async def ops_stream():
    async def event_generator():
        last_ping = time.time()
        while True:
            try:
                if time.time() - last_ping >= 15:
                    yield f"data: {json.dumps({'type': 'heartbeat', 'ts': time.time()})}\n\n"
                    last_ping = time.time()
                try:
                    entry = _op_event_queue.get_nowait()
                    yield f"data: {json.dumps({'type': 'op_event', **entry}, ensure_ascii=False)}\n\n"
                except _queue.Empty:
                    await asyncio.sleep(0.3)
                    continue
            except asyncio.CancelledError:
                break

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
            "Access-Control-Allow-Origin": "*",
        },
    )


@app.get("/api/operations/log")
def get_operations_log(limit: int = 50, category: str = None):
    with _operation_log_lock:
        entries = list(_operation_log)
    if category:
        entries = [e for e in entries if e["category"] == category]
    return {"total": len(entries), "entries": entries[-limit:]}


@app.get("/api/operations/summary")
def get_operations_summary():
    with _operation_log_lock:
        entries = list(_operation_log)
    from collections import Counter

    cat_counts = Counter(e["category"] for e in entries)
    action_counts = Counter(e["action"] for e in entries)
    recent = entries[-10:] if entries else []
    colored_counts = {}
    for cat, count in cat_counts.items():
        cfg = OP_CATEGORY_CONFIG.get(cat, {"label": cat.upper(), "color": "#6B7280"})
        colored_counts[cat] = {"count": count, **cfg}
    return {
        "total_operations": len(entries),
        "by_category": dict(colored_counts),
        "by_action": dict(action_counts),
        "recent": recent,
        "category_config": OP_CATEGORY_CONFIG,
        "tvp_declarations": [e for e in entries if e["category"] == "tvp"],
        "mcp_calls": [e for e in entries if e["category"] == "mcp"],
        "memory_ops": [e for e in entries if e["category"] == "memory"],
        "llm_ops": [e for e in entries if e["category"] == "llm"],
    }


@app.get("/api/operations/header")
def get_operations_header():
    with _operation_log_lock:
        recent = list(_operation_log[-8:])
    if not recent:
        return {"header": "", "html": "", "recent_count": 0, "categories": []}
    parts = []
    for e in recent:
        icon = {"tvp": "[TVP]", "mcp": "[MCP]", "memory": "[MEM]", "llm": "[LLM]"}.get(
            e["category"], "[OPS]"
        )
        parts.append(f"{icon}#{e['action']}")
    header_text = " | ".join(parts)
    return {
        "header": header_text,
        "recent_count": len(recent),
        "categories": list(set(e["category"] for e in recent)),
    }


_original_memory_post = None
_original_memory_get = None


@app.on_event("startup")
async def _log_route_patch_status():
    _log_operation(
        "tvp",
        "system→@tianshu",
        "task=route_logging_patch|ctx=all routes have inline _op_log",
    )


@app.get("/api/shutdown")
def trigger_shutdown():
    _perform_graceful_shutdown()
    threading.Timer(2.0, lambda: os._exit(0)).start()
    return {"status": "shutting_down", "message": "天机正在优雅停机..."}


# atexit清理钩子: 确保Python退出前停止所有后台线程


def _atexit_cleanup():
    if not _SHUTDOWN_EVENT.is_set():
        _perform_graceful_shutdown()


_atexit.register(_atexit_cleanup)


if __name__ == "__main__":
    import argparse

    import uvicorn

    parser = argparse.ArgumentParser(description="Tianji Memory Engine Server")
    parser.add_argument("--host", default=os.environ.get("AI_MEMORY_HOST", "0.0.0.0"))
    parser.add_argument(
        "--port", type=int, default=int(os.environ.get("AI_MEMORY_PORT", "8771"))
    )
    args = parser.parse_args()

    host = args.host
    port = args.port

    if sys.platform != "win32":
        signal.signal(signal.SIGTERM, _perform_graceful_shutdown)
        signal.signal(signal.SIGINT, _perform_graceful_shutdown)

    uvicorn.run(
        "server.main:app",
        host=host,
        port=port,
        reload=False,
        log_level="warning",
        access_log=False,
    )
