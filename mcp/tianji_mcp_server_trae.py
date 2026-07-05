# -*- coding: utf-8-sig -*-
"""tianji_mcp_server_trae.py — TianjiMCPServerTraeMixin (SSS-PhaseB)

从 tianji_mcp_server.py 拆分的方法组: trae
"""

import io
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

# ── 共享常量 (从core导入) ──────────────────────────────
try:
    from tianji_mcp_server_core import (  # type: ignore
        SYSTEM_NAME, TIANJI_API_URL, _encoding_safe_dict, _encoding_safe_text
    )
except ImportError:
    try:
        from .tianji_mcp_server_core import (  # type: ignore
            SYSTEM_NAME, TIANJI_API_URL, _encoding_safe_dict, _encoding_safe_text
        )
    except ImportError:
        SYSTEM_NAME = "天机-忆库"
        TIANJI_API_URL = "http://127.0.0.1:8771"
        def _encoding_safe_text(t, l=""): return str(t)  # noqa: E701
        def _encoding_safe_dict(d, l=""): return d if isinstance(d, dict) else {}  # noqa: E701


# ── [FIX-MCP-Bug1] _get_encoding_stats 本地实现 (避免未定义错误) ──
def _get_encoding_stats() -> dict:
    """获取编码安全性统计数据 (本地降级实现)"""
    import sys
    try:
        return {
            "stdout_encoding": getattr(sys.stdout, "encoding", "unknown") or "unknown",
            "stderr_encoding": getattr(sys.stderr, "encoding", "unknown") or "unknown",
            "default_encoding": sys.getdefaultencoding(),
            "fs_encoding": sys.getfilesystemencoding(),
            "utf8_mode": getattr(sys.flags, "utf8_mode", 0),
        }
    except Exception as e:
        return {"error": str(e)[:100]}


class TianjiMCPServerTraeMixin:
    """trae方法组Mixin"""

    def _handle_trae_stream_capture(self, args: dict) -> dict:
        content = args.get("content", "")
        agent = args.get("agent", "unknown")
        role = args.get("role", "user")
        conversation_id = args.get("conversation_id", "")
        user_input = args.get("user_input", content if role == "user" else "")
        ai_response = args.get("ai_response", content if role == "assistant" else "")
        file_contents = args.get("file_contents")
        mcp_calls = args.get("mcp_calls", [])

        try:
            try:
                from server.deps import get_trae_capture

                trae_capture = get_trae_capture()
                if trae_capture:
                    capture_result = trae_capture.capture_conversation_turn(
                        user_input=user_input,
                        ai_response=ai_response,
                        session_id=conversation_id,
                        agent_id=agent,
                        platform="trae",
                        mcp_calls=mcp_calls,
                        file_contents=file_contents,
                    )
                    return {
                        "status": "captured",
                        "turn_number": capture_result.get("turn_number", 0),
                        "content_hash": capture_result.get("content_hash", ""),
                        "total_bytes": capture_result.get("total_bytes", 0),
                        "l0_memory_id": capture_result.get("l0_memory_id"),
                        "l0_layer": capture_result.get("l0_layer", "sensory"),
                        "routed_layers": capture_result.get("routed_layers", []),
                        "file_summaries": capture_result.get("file_summaries", 0),
                        "dedup_skips": capture_result.get("dedup_skips", 0),
                        "system": SYSTEM_NAME,
                        "version": "v8.7-full-capture",
                    }
            except Exception:
                pass

            remember_result = self._api_post(
                "/api/memory/",
                {
                    "content": content,
                    "layer": "sensory" if role == "user" else "working",
                    "tags": [
                        "trae-stream-v2",
                        f"agent:{agent}",
                        f"role:{role}",
                        "realtime",
                    ],
                    "priority": "low",
                },
            )
            return {
                "status": "captured_fallback",
                "remember_result": "ok"
                if (
                    isinstance(remember_result, dict)
                    and not remember_result.get("error")
                )
                else "failed",
                "system": SYSTEM_NAME,
                "version": "v8.7-fallback",
            }
        except Exception as e:
            fallback = self._api_post(
                "/api/memory/",
                {
                    "content": content[:500],
                    "layer": "sensory",
                    "tags": ["trae-stream-fallback", f"agent:{agent}"],
                    "priority": "low",
                },
            )
            return {
                "status": "fallback_captured",
                "direct_write": "ok"
                if isinstance(fallback, dict) and not fallback.get("error")
                else "failed",
                "error_detail": str(e)[:200],
                "system": SYSTEM_NAME,
            }

    def _handle_trae_stream_snapshot(self, args: dict) -> dict:
        limit = args.get("limit", 20)
        try:
            from core.shared.tianji_container import get_container

            container = get_container()
            if not container:
                # v9.1-fix: MCP进程隔离降级 — 通过REST API获取
                recent = self._api_post(
                    "/api/mcp/tools/list_memories", {"limit": limit, "offset": 0}
                )
                recent_entries = (
                    recent.get("results", []) if isinstance(recent, dict) else []
                )
                return {
                    "status": "degraded_api_fallback",
                    "entries": recent_entries,
                    "total_buffered": len(recent_entries),
                    "degraded_reason": "MCP进程隔离—已通过API降级获取",
                    "system": SYSTEM_NAME,
                    "version": "v9.1-api-fallback",
                }
            # container存在: 直接查询sensory层
            try:
                from server.deps import get_engine

                engine = get_engine()
                if engine:
                    entries = engine.query(layer="sensory", limit=limit)
                    return {
                        "status": "success",
                        "entries": entries if isinstance(entries, list) else [],
                        "total_buffered": len(entries)
                        if isinstance(entries, list)
                        else 0,
                        "system": SYSTEM_NAME,
                    }
            except Exception:
                pass
            return {
                "status": "degraded",
                "entries": [],
                "detail": "engine_not_available",
            }
        except Exception as e:
            return {"status": "error", "entries": [], "error_detail": str(e)[:200]}

    def _handle_trae_monitoring_stats(self, args: dict) -> dict:
        import concurrent.futures as _cf

        results = {}
        with _cf.ThreadPoolExecutor(max_workers=4) as executor:
            mem_future = executor.submit(self._api_get, "/api/memory/stats")
            health_future = executor.submit(self._api_get, "/api/health")
            system_future = executor.submit(self._api_get, "/api/system/stats")
            ops_future = executor.submit(self._api_get, "/api/ops/stats")
            try:
                results["memory"] = mem_future.result(timeout=5) or {}
            except Exception:
                results["memory"] = {}
            try:
                results["health"] = health_future.result(timeout=5) or {}
            except Exception:
                results["health"] = {}
            try:
                results["system"] = system_future.result(timeout=5) or {}
            except Exception:
                results["system"] = {}
            try:
                results["ops"] = ops_future.result(timeout=5) or {}
            except Exception:
                results["ops"] = {}
        encoding_stats = _get_encoding_stats()
        try:
            from core.shared.tianji_container import get_container

            container = get_container()
            if container:
                rt_cache = getattr(container, "_rt_cache", {})
                scheduler_mod = container._modules.get("trae_agent_scheduler")
                results["scheduler"] = (
                    scheduler_mod.instance.get_stats()
                    if scheduler_mod and scheduler_mod.instance
                    else {}
                )
                results["rt_cache_size"] = len(rt_cache)
                results["rt_modules"] = list(rt_cache.keys())
        except Exception:
            pass
        return {
            "status": "success",
            "timestamp": __import__("datetime").datetime.now().isoformat(),
            "data": results,
            "encoding_safety": encoding_stats,
            "system": SYSTEM_NAME,
            "version": "v8.2-unified-monitoring",
        }
