"""OTel GenAI 属性定义 — 从enforcement_hook.py提取"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

class OtelGenAISpanKind(str, Enum):
    CREATE_AGENT = "create_agent"
    INVOKE_AGENT_CLIENT = "invoke_agent_client"
    INVOKE_AGENT_INTERNAL = "invoke_agent_internal"
    INVOKE_WORKFLOW = "invoke_workflow"
    EXECUTE_TOOL = "execute_tool"


@dataclass
class GenAIAgentAttributes:
    name: str = ""
    agent_id: str = ""
    version: str = "v8.2.0"
    provider_name: str = "memory-engine-global"
    conversation_id: str = ""
    operation_name: str = ""
    model_name: str = "deepseek-chat"

    def to_otel_dict(self) -> dict:
        return {
            "gen_ai.agent.name": self.name,
            "gen_ai.agent.id": self.agent_id,
            "gen_ai.agent.version": self.version,
            "gen_ai.provider.name": self.provider_name,
            "gen_ai.conversation.id": self.conversation_id,
            "gen_ai.operation.name": self.operation_name,
            "gen_ai.model.name": self.model_name,
        }


@dataclass
class OtelGenAISpan:
    span_id: str
    trace_id: str
    parent_span_id: str = ""
    span_kind: OtelGenAISpanKind = OtelGenAISpanKind.EXECUTE_TOOL
    start_time: float = field(default_factory=time.time)
    end_time: float = 0.0
    agent_attrs: GenAIAgentAttributes = field(default_factory=GenAIAgentAttributes)
    tool_name: str = ""
    tool_parameters: str = ""
    tool_result_status: str = ""
    tool_duration_ms: float = 0.0
    workflow_name: str = ""
    workflow_phase: str = ""
    source_agent: str = ""
    target_agent: str = ""
    status_code: str = "UNSET"
    status_message: str = ""
    events: List[Dict] = field(default_factory=list)
    links: List[Dict] = field(default_factory=list)

    def to_otel_dict(self) -> dict:
        d = {
            "span_id": self.span_id,
            "trace_id": self.trace_id,
            "parent_span_id": self.parent_span_id,
            "span_kind": self.span_kind.value,
            "start_time_unix_nano": int(self.start_time * 1e9),
            "end_time_unix_nano": int(self.end_time * 1e9) if self.end_time else 0,
            "status": {"code": self.status_code, "message": self.status_message},
            "attributes": self.agent_attrs.to_otel_dict(),
        }
        if self.span_kind == OtelGenAISpanKind.EXECUTE_TOOL:
            d["attributes"].update({
                "tool.name": self.tool_name,
                "tool.parameters": self.tool_parameters,
                "tool.result.status": self.tool_result_status,
                "tool.call.duration_ms": self.tool_duration_ms,
            })
        if self.span_kind == OtelGenAISpanKind.INVOKE_AGENT_INTERNAL:
            d["attributes"].update({
                "gen_ai.agent.source": self.source_agent,
                "gen_ai.agent.target": self.target_agent,
            })
        if self.span_kind == OtelGenAISpanKind.INVOKE_WORKFLOW:
            d["attributes"].update({
                "gen_ai.agent.workflow.name": self.workflow_name,
                "gen_ai.agent.workflow.phase": self.workflow_phase,
            })
        if self.events:
            d["events"] = self.events
        if self.links:
            d["links"] = self.links
        return d

    def finish(self):
        if not self.end_time:
            self.end_time = time.time()
        if self.tool_duration_ms == 0.0:
            self.tool_duration_ms = (self.end_time - self.start_time) * 1000

    @property
    def duration_ms(self) -> float:
        return ((self.end_time or time.time()) - self.start_time) * 1000


