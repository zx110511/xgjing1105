# -*- coding: utf-8-sig -*-
"""经验自动沉淀 - 采集器

无侵入式采集工具调用轨迹，作为经验自动沉淀的基础。

架构位置: D4悟道域 - 进化处理器
版本: v1.0.0 (Phase 1 MVP)

采集方式:
  1. 直接API调用 (collect_trace)
  2. 事件总线订阅 (experience.collect)
  3. 钩子系统集成 (register_mcp_call)
"""

from __future__ import annotations

import time
import logging
import threading
from typing import Any, Dict, List, Optional

from .experience_models import (
    OperationTrace,
    ExperienceEntry,
    CollectionStats,
    ExperienceDomain,
    PatternType,
)
from .experience_store import ExperienceStore, get_experience_store

logger = logging.getLogger(__name__)


class ExperienceCollector:
    """经验采集器

    Phase 1 MVP:
    - 采集MCP工具调用轨迹
    - 自动标记成功/失败
    - 异步写入存储（不影响主流程）
    - 事件总线集成
    """

    VERSION = "1.0.0"

    def __init__(
        self,
        store: Optional[ExperienceStore] = None,
        event_bus: Any = None,
        async_enabled: bool = True,
        flush_interval: float = 1.0,
    ) -> None:
        self._store = store or get_experience_store()
        self._event_bus = event_bus
        self._async_enabled = async_enabled
        self._flush_interval = flush_interval
        self._enabled = True
        self._lock = threading.Lock()
        self._pending_traces: List[OperationTrace] = []
        self._flush_thread: Optional[threading.Thread] = None
        self._flush_event = threading.Event()
        self._stats = {
            "collected": 0,
            "success": 0,
            "failure": 0,
            "errors": 0,
            "skipped": 0,
        }

        if self._event_bus:
            self._subscribe_events()

        if self._async_enabled:
            self._start_flush_thread()

        logger.info(
            "ExperienceCollector 初始化完成 (async=%s, event_bus=%s)",
            async_enabled,
            event_bus is not None,
        )

    def _start_flush_thread(self) -> None:
        """启动后台刷盘线程"""
        self._flush_thread = threading.Thread(
            target=self._flush_loop, daemon=True, name="exp-collector-flush"
        )
        self._flush_thread.start()

    def _flush_loop(self) -> None:
        """后台刷盘循环"""
        while self._enabled:
            self._flush_event.wait(timeout=self._flush_interval)
            self._flush_event.clear()
            if self._pending_traces:
                self._flush_pending()

    @property
    def enabled(self) -> bool:
        return self._enabled

    @enabled.setter
    def enabled(self, value: bool) -> None:
        self._enabled = value
        logger.info("ExperienceCollector %s", "启用" if value else "停用")

    def _subscribe_events(self) -> None:
        """订阅事件总线的采集事件"""
        try:
            self._event_bus.subscribe("experience.collect", self._on_collect_event)
            self._event_bus.subscribe("mcp.tool_called", self._on_mcp_tool_event)
            self._event_bus.subscribe("agent.dispatched", self._on_agent_event)
            self._event_bus.subscribe("memory.stored", self._on_memory_event)
            logger.debug("事件总线订阅完成")
        except Exception as e:
            logger.warning("事件总线订阅失败: %s", e)

    def _on_collect_event(self, event: Any) -> None:
        """处理经验采集事件"""
        try:
            payload = getattr(event, "payload", {})
            if isinstance(payload, dict):
                trace_data = payload.get("trace") or payload
                self.collect_trace(**trace_data)
        except Exception as e:
            logger.warning("处理采集事件失败: %s", e)

    def _on_mcp_tool_event(self, event: Any) -> None:
        """处理MCP工具调用事件"""
        try:
            payload = getattr(event, "payload", {})
            if isinstance(payload, dict):
                self.collect_trace(
                    tool_name=payload.get("tool_name", ""),
                    tool_params=payload.get("params", {}),
                    result_summary=payload.get("result_summary", ""),
                    success=payload.get("success", False),
                    duration_ms=payload.get("duration_ms", 0.0),
                    error_type=payload.get("error_type", ""),
                    error_message=payload.get("error_message", ""),
                    agent_id=payload.get("agent_id", ""),
                    session_id=payload.get("session_id", ""),
                    context_tags=["mcp_tool"],
                )
        except Exception as e:
            logger.debug("处理MCP工具事件失败: %s", e)

    def _on_agent_event(self, event: Any) -> None:
        """处理Agent调度事件"""
        try:
            payload = getattr(event, "payload", {})
            if isinstance(payload, dict):
                self.collect_trace(
                    tool_name="agent_dispatch",
                    tool_params={"task_type": payload.get("task_type", "")},
                    result_summary=f"调度到 {payload.get('agent_id', 'unknown')}",
                    success=True,
                    duration_ms=0.0,
                    agent_id=payload.get("agent_id", ""),
                    session_id=payload.get("session_id", ""),
                    context_tags=["agent_dispatch"],
                    task_type=payload.get("task_type", ""),
                )
        except Exception as e:
            logger.debug("处理Agent事件失败: %s", e)

    def _on_memory_event(self, event: Any) -> None:
        """处理记忆写入事件"""
        try:
            payload = getattr(event, "payload", {})
            if isinstance(payload, dict):
                self.collect_trace(
                    tool_name="memory_remember",
                    tool_params={"layer": payload.get("layer", "")},
                    result_summary=f"写入 {payload.get('layer', 'unknown')} 层",
                    success=True,
                    duration_ms=0.0,
                    session_id=payload.get("session_id", ""),
                    context_tags=["memory", payload.get("layer", "")],
                )
        except Exception as e:
            logger.debug("处理记忆事件失败: %s", e)

    # ── 核心采集API ──

    def collect_trace(
        self,
        tool_name: str,
        tool_params: Optional[Dict[str, Any]] = None,
        result_summary: str = "",
        success: bool = False,
        duration_ms: float = 0.0,
        error_type: str = "",
        error_message: str = "",
        agent_id: str = "",
        session_id: str = "",
        task_type: str = "",
        context_tags: Optional[List[str]] = None,
        parent_trace_id: str = "",
    ) -> str:
        """采集一条操作轨迹

        Args:
            tool_name: 工具名称
            tool_params: 工具参数
            result_summary: 结果摘要
            success: 是否成功
            duration_ms: 耗时(毫秒)
            error_type: 错误类型
            error_message: 错误信息
            agent_id: 执行Agent
            session_id: 会话ID
            task_type: 任务类型
            context_tags: 上下文标签
            parent_trace_id: 父轨迹ID

        Returns:
            trace_id: 轨迹ID
        """
        if not self._enabled:
            return ""

        try:
            trace = OperationTrace(
                session_id=session_id,
                agent_id=agent_id,
                task_type=task_type,
                tool_name=tool_name,
                tool_params=tool_params or {},
                result_summary=result_summary,
                success=success,
                duration_ms=duration_ms,
                error_type=error_type,
                error_message=error_message,
                context_tags=context_tags or [],
                parent_trace_id=parent_trace_id,
            )

            if self._async_enabled:
                with self._lock:
                    self._pending_traces.append(trace)
                self._stats["collected"] += 1
                if success:
                    self._stats["success"] += 1
                else:
                    self._stats["failure"] += 1
                self._flush_async()
            else:
                self._store.add_trace(trace)
                self._stats["collected"] += 1
                if success:
                    self._stats["success"] += 1
                else:
                    self._stats["failure"] += 1

            return trace.trace_id

        except Exception as e:
            self._stats["errors"] += 1
            logger.warning("采集轨迹失败: %s", e)
            return ""

    def collect_mcp_call(
        self,
        tool_name: str,
        params: Dict[str, Any],
        result: Any,
        success: bool,
        duration_ms: float,
        agent_id: str = "",
        session_id: str = "",
        error: Optional[Exception] = None,
    ) -> str:
        """采集MCP工具调用（便捷方法）

        Args:
            tool_name: 工具名
            params: 输入参数
            result: 返回结果
            success: 是否成功
            duration_ms: 耗时
            agent_id: Agent ID
            session_id: 会话ID
            error: 异常对象

        Returns:
            trace_id
        """
        result_summary = ""
        error_type = ""
        error_message = ""

        if success:
            if isinstance(result, str):
                result_summary = result[:200]
            elif isinstance(result, dict):
                result_summary = str(result.get("status", result.get("message", "success")))[:200]
            else:
                result_summary = str(result)[:200]
        else:
            if error:
                error_type = type(error).__name__
                error_message = str(error)[:500]
            elif isinstance(result, str):
                error_message = result[:500]

        return self.collect_trace(
            tool_name=tool_name,
            tool_params=self._sanitize_params(params),
            result_summary=result_summary,
            success=success,
            duration_ms=duration_ms,
            error_type=error_type,
            error_message=error_message,
            agent_id=agent_id,
            session_id=session_id,
            context_tags=["mcp", tool_name],
        )

    def _sanitize_params(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """参数脱敏 - 移除敏感信息"""
        if not params:
            return {}

        sensitive_keys = {
            "password", "token", "api_key", "secret", "authorization",
            "key", "credential", "auth",
        }

        sanitized = {}
        for k, v in params.items():
            if any(s in k.lower() for s in sensitive_keys):
                sanitized[k] = "***REDACTED***"
            elif isinstance(v, (dict, list)):
                sanitized[k] = str(v)[:200]
            else:
                sanitized[k] = str(v)[:200] if v is not None else None

        return sanitized

    # ── 异步刷盘 ──

    def _flush_async(self) -> None:
        """通知刷盘线程处理"""
        if self._async_enabled and self._flush_event:
            self._flush_event.set()

    def _flush_pending(self) -> int:
        """将待处理轨迹写入存储

        Returns:
            实际写入的轨迹数量
        """
        with self._lock:
            if not self._pending_traces:
                return 0
            pending = list(self._pending_traces)
            self._pending_traces.clear()

        count = 0
        for trace in pending:
            try:
                self._store.add_trace(trace)
                count += 1
            except Exception as e:
                logger.warning("写入轨迹失败: %s", e)
                self._stats["errors"] += 1

        return count

    def flush(self) -> int:
        """强制刷盘所有待处理轨迹

        Returns:
            刷盘的轨迹数量
        """
        return self._flush_pending()

    # ── 经验生成 (Phase 1 基础版) ──

    def generate_experience_from_trace(self, trace_id: str) -> Optional[str]:
        """从操作轨迹生成经验条目（Phase 1 MVP基础版）

        Phase 2将实现更复杂的评估和聚类。
        """
        trace = self._store.get_trace(trace_id)
        if not trace:
            return None

        try:
            experience = ExperienceEntry.from_trace(trace)
            return self._store.add_experience(experience)
        except Exception as e:
            logger.warning("生成经验失败: %s", e)
            return None

    # ── 查询与统计 ──

    def get_stats(self) -> Dict[str, Any]:
        """获取采集器统计信息"""
        store_stats = self._store.get_stats()
        return {
            "collector_version": self.VERSION,
            "enabled": self._enabled,
            "async_enabled": self._async_enabled,
            "session_stats": self._stats.copy(),
            "store_stats": store_stats.to_dict(),
        }

    def get_recent_traces(self, limit: int = 20, tool_name: Optional[str] = None) -> List[Dict[str, Any]]:
        """获取最近的操作轨迹"""
        traces = self._store.list_traces(limit=limit, tool_name=tool_name)
        return [t.to_dict() for t in traces]

    def search_traces(self, keyword: str, limit: int = 20) -> List[Dict[str, Any]]:
        """搜索操作轨迹"""
        traces = self._store.search_traces(keyword, limit=limit)
        return [t.to_dict() for t in traces]


# 模块级默认实例
_default_collector: Optional[ExperienceCollector] = None
_collector_lock = threading.Lock()


def get_experience_collector(
    store: Optional[ExperienceStore] = None,
    event_bus: Any = None,
) -> ExperienceCollector:
    """获取默认经验采集器实例（单例）"""
    global _default_collector
    if _default_collector is None:
        with _collector_lock:
            if _default_collector is None:
                _default_collector = ExperienceCollector(
                    store=store,
                    event_bus=event_bus,
                )
    return _default_collector


__all__ = [
    "ExperienceCollector",
    "get_experience_collector",
]
