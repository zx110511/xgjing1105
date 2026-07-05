"""Microsoft Agent Task Span — 从enforcement_hook.py提取"""
from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

class MsAgentTaskSpanKind(str, Enum):
    TASK_START = "ms.agent.task.start"
    TASK_COMPLETE = "ms.agent.task.complete"
    TASK_FAIL = "ms.agent.task.fail"
    TOOL_CALL = "ms.agent.tool.call"
    TASK_INPUT = "ms.agent.task.input"
    TASK_OUTPUT = "ms.agent.task.output"
    LLM_REQUEST = "ms.agent.llm.request"
    AGENT_INTERACTION = "ms.agent.interaction"


@dataclass
class MsAgentTaskSpan:
    span_id: str
    trace_id: str
    task_id: str = ""
    parent_span_id: str = ""
    kind: MsAgentTaskSpanKind = MsAgentTaskSpanKind.TASK_START
    agent_name: str = "tianshu"
    agent_version: str = "v8.2.0"
    start_time: float = field(default_factory=time.time)
    end_time: float = 0.0
    task_type: str = ""
    task_priority: str = "medium"
    task_status: str = "running"
    task_input: str = ""
    task_output: str = ""
    tool_name: str = ""
    tool_call_params: str = ""
    tool_call_result: str = ""
    tool_duration_ms: float = 0.0
    llm_model: str = ""
    llm_request_text: str = ""
    llm_response_text: str = ""
    llm_token_count: int = 0
    source_agent: str = ""
    target_agent: str = ""
    interaction_type: str = ""
    error_message: str = ""
    status_code: str = "UNSET"
    attributes: Dict = field(default_factory=dict)
    events: List[Dict] = field(default_factory=list)

    def set_task_input(self, input_text: str):
        self.task_input = input_text[:2000]
        self.kind = MsAgentTaskSpanKind.TASK_INPUT

    def set_task_output(self, output_text: str):
        self.task_output = output_text[:2000]
        self.kind = MsAgentTaskSpanKind.TASK_OUTPUT
        self.task_status = "completed"

    def set_tool_call(self, tool_name: str, params: str = "", result: str = ""):
        self.tool_name = tool_name
        self.tool_call_params = params[:500]
        self.tool_call_result = result[:500]
        self.kind = MsAgentTaskSpanKind.TOOL_CALL

    def set_llm_request(self, model: str, request: str, response: str = "",
                        token_count: int = 0):
        self.llm_model = model
        self.llm_request_text = request[:2000]
        self.llm_response_text = response[:2000]
        self.llm_token_count = token_count
        self.kind = MsAgentTaskSpanKind.LLM_REQUEST

    def set_agent_interaction(self, source: str, target: str, interaction: str):
        self.source_agent = source
        self.target_agent = target
        self.interaction_type = interaction
        self.kind = MsAgentTaskSpanKind.AGENT_INTERACTION

    def finish(self, status: str = "completed", error: str = ""):
        self.end_time = time.time()
        self.task_status = status
        self.error_message = error[:500]
        self.status_code = "OK" if status == "completed" else "ERROR"

    def to_dict(self) -> dict:
        d = {
            "span_id": self.span_id,
            "trace_id": self.trace_id,
            "task_id": self.task_id,
            "parent_span_id": self.parent_span_id,
            "kind": self.kind.value,
            "agent": {"name": self.agent_name, "version": self.agent_version},
            "start_time": self.start_time,
            "end_time": self.end_time,
            "task": {
                "type": self.task_type,
                "priority": self.task_priority,
                "status": self.task_status,
                "input": self.task_input[:500],
                "output": self.task_output[:500],
            },
            "status": {"code": self.status_code, "message": self.error_message},
            "attributes": dict(self.attributes),
        }
        if self.tool_name:
            d["tool"] = {
                "name": self.tool_name,
                "params": self.tool_call_params[:300],
                "result": self.tool_call_result[:300],
                "duration_ms": self.tool_duration_ms,
            }
        if self.llm_model:
            d["llm"] = {
                "model": self.llm_model,
                "request": self.llm_request_text[:300],
                "response": self.llm_response_text[:300],
                "token_count": self.llm_token_count,
            }
        if self.source_agent:
            d["interaction"] = {
                "source": self.source_agent,
                "target": self.target_agent,
                "type": self.interaction_type,
            }
        if self.events:
            d["events"] = self.events
        return d

    @property
    def duration_ms(self) -> float:
        return ((self.end_time or time.time()) - self.start_time) * 1000


class MsAgentTaskSpanManager:
    def __init__(self):
        self._active_spans: Dict[str, MsAgentTaskSpan] = {}
        self._span_history: List[MsAgentTaskSpan] = []
        self._max_history = 500
        self._lock = threading.Lock() if hasattr(threading, 'Lock') else None

    def start_task(self, task_id: str, task_type: str, agent_name: str = "tianshu",
                   priority: str = "medium") -> MsAgentTaskSpan:
        import uuid
        span = MsAgentTaskSpan(
            span_id=uuid.uuid4().hex[:16],
            trace_id=uuid.uuid4().hex[:32],
            task_id=task_id,
            kind=MsAgentTaskSpanKind.TASK_START,
            agent_name=agent_name,
            task_type=task_type,
            task_priority=priority,
        )
        if self._lock:
            with self._lock:
                self._active_spans[task_id] = span
        else:
            self._active_spans[task_id] = span
        return span

    def record_tool_call(self, task_id: str, tool_name: str,
                         params: Dict = None, result: str = "") -> Optional[MsAgentTaskSpan]:
        span = self._get_or_create(task_id, MsAgentTaskSpanKind.TOOL_CALL)
        if span:
            span.set_tool_call(tool_name, json.dumps(params or {}), result)
            span.tool_duration_ms = (time.time() - span.start_time) * 1000
        return span

    def record_llm_request(self, task_id: str, model: str, request: str,
                           response: str = "", tokens: int = 0) -> Optional[MsAgentTaskSpan]:
        span = self._get_or_create(task_id, MsAgentTaskSpanKind.LLM_REQUEST)
        if span:
            span.set_llm_request(model, request, response, tokens)
        return span

    def record_agent_interaction(self, task_id: str, source: str,
                                 target: str, interaction: str) -> Optional[MsAgentTaskSpan]:
        span = self._get_or_create(task_id, MsAgentTaskSpanKind.AGENT_INTERACTION)
        if span:
            span.set_agent_interaction(source, target, interaction)
        return span

    def finish_task(self, task_id: str, status: str = "completed",
                    output: str = "", error: str = "") -> Optional[MsAgentTaskSpan]:
        span = self._active_spans.pop(task_id, None)
        if span:
            span.finish(status, error)
            if output:
                span.set_task_output(output)
            self._add_to_history(span)
        return span

    def _get_or_create(self, task_id: str, kind: MsAgentTaskSpanKind) -> Optional[MsAgentTaskSpan]:
        if task_id in self._active_spans:
            return self._active_spans[task_id]
        import uuid
        span = MsAgentTaskSpan(
            span_id=uuid.uuid4().hex[:16],
            trace_id=uuid.uuid4().hex[:32],
            task_id=task_id, kind=kind,
        )
        if self._lock:
            with self._lock:
                self._active_spans[task_id] = span
        else:
            self._active_spans[task_id] = span
        return span

    def _add_to_history(self, span: MsAgentTaskSpan):
        if self._lock:
            with self._lock:
                self._span_history.append(span)
                if len(self._span_history) > self._max_history:
                    self._span_history = self._span_history[-self._max_history:]
        else:
            self._span_history.append(span)
            if len(self._span_history) > self._max_history:
                self._span_history = self._span_history[-self._max_history:]

    def get_task_span(self, task_id: str) -> Optional[MsAgentTaskSpan]:
        return self._active_spans.get(task_id)

    def get_history(self, limit: int = 50) -> List[Dict]:
        spans = self._span_history[-limit:]
        return [s.to_dict() for s in spans]

    def get_stats(self) -> Dict:
        total = len(self._span_history)
        completed = sum(1 for s in self._span_history if s.task_status == "completed")
        failed = sum(1 for s in self._span_history if s.task_status == "failed")
        return {
            "total_tasks": total,
            "active_tasks": len(self._active_spans),
            "completed": completed,
            "failed": failed,
            "success_rate": completed / max(total, 1),
        }

