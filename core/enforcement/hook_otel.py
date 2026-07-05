# -*- coding: utf-8-sig -*-
"""OTel追踪子系统 — 从hook_core.py拆分 [SSS-PhaseB]

包含: EnforcementLevel / OtelSpanContext / OtelMCPInterceptor
"""

from __future__ import annotations

import threading
import time
from enum import Enum
from typing import Any

from .otel_attributes import GenAIAgentAttributes, OtelGenAISpan, OtelGenAISpanKind


class EnforcementLevel(str, Enum):
    MANDATORY = "mandatory"
    NUDGE = "nudge"
    OBSERVE = "observe"


class OtelSpanContext:
    trace_id: str
    span_id: str
    trace_flags: int = 1

    def to_dict(self) -> dict:
        return {
            "trace_id": self.trace_id,
            "span_id": self.span_id,
            "trace_flags": self.trace_flags,
        }


class OtelMCPInterceptor:
    """OTel MCP调用拦截器 — 管理Span生命周期"""

    MAX_HISTORY = 1000

    def __init__(self, service_name: str = "tianji-enforcement-hook"):
        self._active_spans: dict[str, OtelGenAISpan] = {}
        self._span_history: list[OtelGenAISpan] = []
        self._trace_counter: int = 0
        self._span_counter: int = 0
        self._lock = threading.Lock()
        self._service_name = service_name

    def start_span(
        self,
        span_kind: OtelGenAISpanKind,
        tool_name: str = "",
        agent_name: str = "",
        conversation_id: str = "",
        parent_span: OtelGenAISpan | None = None,
    ) -> OtelGenAISpan:
        with self._lock:
            self._trace_counter += 1
            self._span_counter += 1
            trace_id = f"{int(time.time() * 1000):x}-{self._trace_counter:06x}"
            span_id = f"{self._span_counter:016x}"

            span = OtelGenAISpan(
                span_id=span_id,
                trace_id=trace_id,
                parent_span_id=parent_span.span_id if parent_span else "",
                span_kind=span_kind,
                start_time=time.time(),
                tool_name=tool_name,
                agent_attrs=GenAIAgentAttributes(
                    name=agent_name,
                    agent_id=agent_id,
                    conversation_id=conversation_id,
                    operation_name=tool_name or span_kind.value,
                ),
            )
            self._active_spans[span_id] = span
            return span

    def end_span(self, span: OtelGenAISpan, status_code: str = "OK", status_message: str = "") -> None:
        with self._lock:
            span.status_code = status_code
            span.status_message = status_message
            span.finish()
            if span.span_id in self._active_spans:
                del self._active_spans[span.span_id]
            self._span_history.append(span)
            if len(self._span_history) > self.MAX_HISTORY:
                self._span_history = self._span_history[-self.MAX_HISTORY:]

    def intercept_mcp_call(
        self,
        tool_name: str,
        params_summary: str = "",
        result_summary: str = "",
        duration_ms: float = 0.0,
        status: str = "success",
        session_id: str = "",
        agent_id: str = "",
    ) -> OtelGenAISpan:
        span = self.start_span(
            span_kind=OtelGenAISpanKind.EXECUTE_TOOL,
            tool_name=tool_name,
            agent_name=agent_id,
            conversation_id=session_id,
        )
        span.tool_parameters = params_summary
        span.tool_result_status = status
        span.tool_duration_ms = duration_ms
        self.end_span(span, "OK" if status == "success" else "ERROR", result_summary[:500] if result_summary else "")
        return span

    def intercept_agent_switch(
        self, source_agent: str, target_agent: str,
        task_type: str, session_id: str = "", priority: str = "medium",
    ) -> OtelGenAISpan:
        span = self.start_span(
            span_kind=OtelGenAISpanKind.INVOKE_AGENT_INTERNAL,
            tool_name=task_type, agent_name=source_agent, conversation_id=session_id,
        )
        span.source_agent = source_agent
        span.target_agent = target_agent
        span.tool_name = task_type
        span.links.append({"linked_span_id": "", "attributes": {"gen_ai.agent.dispatch.priority": priority}})
        self.end_span(span, "OK")
        return span

    def intercept_workflow(
        self, workflow_name: str, phase: str, session_id: str = "", agent_id: str = ""
    ) -> OtelGenAISpan:
        span = self.start_span(
            span_kind=OtelGenAISpanKind.INVOKE_WORKFLOW,
            tool_name=workflow_name, agent_name=agent_id, conversation_id=session_id,
        )
        span.workflow_name = workflow_name
        span.workflow_phase = phase
        self.end_span(span, "OK")
        return span

    def get_active_spans(self) -> list[dict]:
        return [s.to_dict() for s in list(self._active_spans.values())]

    def get_recent_spans(self, limit: int = 20) -> list[dict]:
        recent = self._span_history[-limit:]
        return [s.to_dict() for s in reversed(recent)]

    def get_otel_stats(self) -> dict:
        return {
            "service": self._service_name,
            "active_spans": len(self._active_spans),
            "total_spans_recorded": len(self._span_history),
            "trace_count": self._trace_counter,
            "history_size": len(self._span_history),
        }
