# -*- coding: utf-8-sig -*-
"""MCP调用拦截钩子 — P2高级, PRE+POST阶段

版本: 1.0.0
"""

from __future__ import annotations

import sys
import logging
import time
from pathlib import Path
from typing import Dict, Any

_GLOBAL_HOOKS_ROOT = str(Path(__file__).resolve().parent.parent.parent.parent.parent)
if _GLOBAL_HOOKS_ROOT not in sys.path:
    sys.path.insert(0, _GLOBAL_HOOKS_ROOT)

from hooks.base import SyncHook, HookPhase, HookPriority, HookResult, HookContext, HookVerdict

logger = logging.getLogger("tianji.hooks.mcp_intercept")

MCP_PRIORITY = {
    "tianji_health": 0, "memory_recall": 1, "memory_remember": 1,
    "memory_stats": 2, "memory_capacity": 2, "agent_dispatch": 3,
    "agent_status": 4, "agent_list": 4,
}


class MCPInterceptHook(SyncHook):
    """MCP调用拦截钩子"""

    SLOW_CALL_THRESHOLD_MS = 1500.0
    VERY_SLOW_CALL_THRESHOLD_MS = 5000.0

    def __init__(self):
        super().__init__(name="mcp_intercept", phase=HookPhase.PRE, priority=HookPriority.P2_HIGH, enabled=True, fail_safe=True, tags=["mcp", "intercept", "P2"])
        self._pending_calls: Dict[str, Dict] = {}
        self._call_stats: Dict[str, Dict] = {}

    def execute(self, context: HookContext) -> HookResult:
        if context.operation != "mcp_call":
            return HookResult(hook_id=self._hook_id, hook_name=self.name, verdict=HookVerdict.PASS, message="not_mcp_call")
        if context.phase == HookPhase.PRE:
            return self._handle_pre(context)
        elif context.phase == HookPhase.POST:
            return self._handle_post(context)
        return HookResult(hook_id=self._hook_id, hook_name=self.name, verdict=HookVerdict.PASS)

    def _handle_pre(self, context: HookContext) -> HookResult:
        payload = context.payload
        tool_name = payload.get("tool_name", "")
        server_name = payload.get("server_name", "")
        self._pending_calls[context.trace_id] = {"tool_name": tool_name, "server_name": server_name, "start_time": time.monotonic(), "session_id": context.session_id, "agent_id": context.agent_id}
        return HookResult(hook_id=self._hook_id, hook_name=self.name, verdict=HookVerdict.MODIFY, message="mcp_call_tracked", modified_context={"payload": {**payload, "_mcp_trace_id": context.trace_id, "_mcp_priority": MCP_PRIORITY.get(tool_name, 99)}}, metadata={"tool_name": tool_name, "server_name": server_name})

    def _handle_post(self, context: HookContext) -> HookResult:
        pending = self._pending_calls.pop(context.trace_id, None)
        payload = context.payload
        tool_name = payload.get("tool_name", "")
        status = payload.get("status", "unknown")
        duration_ms = (time.monotonic() - pending["start_time"]) * 1000 if pending else 0.0
        self._update_tool_stats(tool_name, duration_ms, status == "success")
        metadata: Dict[str, Any] = {"tool_name": tool_name, "duration_ms": round(duration_ms, 2), "status": status}
        if duration_ms > self.VERY_SLOW_CALL_THRESHOLD_MS:
            logger.warning(f"[MCP-VERY-SLOW] {tool_name} 耗时 {duration_ms:.0f}ms | trace={context.trace_id}")
            metadata["performance_alert"] = "very_slow"
        elif duration_ms > self.SLOW_CALL_THRESHOLD_MS:
            logger.info(f"[MCP-SLOW] {tool_name} 耗时 {duration_ms:.0f}ms | trace={context.trace_id}")
            metadata["performance_alert"] = "slow"
        return HookResult(hook_id=self._hook_id, hook_name=self.name, verdict=HookVerdict.PASS, message="mcp_call_completed", metadata=metadata)

    def _update_tool_stats(self, tool_name: str, duration_ms: float, success: bool) -> None:
        if tool_name not in self._call_stats:
            self._call_stats[tool_name] = {"total_calls": 0, "success_count": 0, "error_count": 0, "total_duration_ms": 0.0, "max_duration_ms": 0.0}
        stats = self._call_stats[tool_name]
        stats["total_calls"] += 1
        stats["total_duration_ms"] += duration_ms
        if success:
            stats["success_count"] += 1
        else:
            stats["error_count"] += 1
        stats["max_duration_ms"] = max(stats["max_duration_ms"], duration_ms)

    def get_stats(self) -> Dict[str, Any]:
        base_stats = super().get_stats()
        tool_summary = {}
        for name, stats in self._call_stats.items():
            avg = stats["total_duration_ms"] / stats["total_calls"] if stats["total_calls"] > 0 else 0
            tool_summary[name] = {**stats, "avg_duration_ms": round(avg, 2)}
        base_stats["tool_stats"] = tool_summary
        return base_stats
