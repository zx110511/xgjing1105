# -*- coding: utf-8-sig -*-
"""TianjiEnforcementHook 核心 — SSS-PhaseB 瘦身后 (3033→~200行导入层)

原始3033行已拆分为:
  - hook_otel.py      → OTel追踪 (OtelMCPInterceptor等)
  - hook_models.py    → 24个数据模型类
  - hook_registry.py  → 对话注册表
  - hook_core.py      → 本文件: 核心Hook类(保留，待PhaseE进一步拆分)

注意: TianjiEnforcementHook仍约2000行，标记为PhaseE候选(over-engineered评估)
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from core.shared.platform_detector import get_platform
from core.event_wiring.turn_logger import TurnLogger

# 从子模块导入所有数据模型
from .hook_models import (
    ConversationRecord,
    EnforcementDecision,
    FAIRMetadata,
    FeedbackAwareLoop,
    FileOperation,
    LoongSuiteAlignment,
    MCPCallDetail,
    TokenEconomy,
)
from .hook_otel import EnforcementLevel, OtelMCPInterceptor
from .hook_registry import ConversationRegistry
from .enforcement_evolution import AdaptiveRecordingPolicy
from .otel_attributes import GenAIAgentAttributes, OtelGenAISpan, OtelGenAISpanKind
from .standards.iso_diaml import ISO_COMMUNICATION_FUNCTIONS, DiAMLSerializer
from .standards.ms_agent_span import MsAgentTaskSpanManager
from .standards.otel_eval import OTelEvaluationBridge
from .standards.owasp_inspect import OWASPAosBridge, OWASPInspectEngine


class ConsumerProfile:
    def __init__(self, agent_id: str = "", session_id: str = ""):
        self.agent_id = agent_id
        self.session_id = session_id


class TianjiEnforcementHook:
    """
    天机强制执行钩子 — 核心类 [SSS-PhaseB: 已瘦身，数据模型全部外置]

    借鉴Hermes Agent的闭环学习架构.
    """

    VERSION = "2.0.0"

    def __init__(
        self,
        registry: ConversationRegistry | None = None,
        memory_api_url: str = "http://127.0.0.1:8771",
        event_bus=None,
        local_cache_dir: Path | None = None,
    ):
        self.registry = registry or ConversationRegistry()
        self.memory_api_url = memory_api_url
        self.event_bus = event_bus
        self.local_cache_dir = local_cache_dir
        self._enabled = True
        self._enforcement_level = EnforcementLevel.MANDATORY
        self._stats = {
            "hooks_triggered": 0, "records_enforced": 0,
            "records_skipped": 0, "nudges_sent": 0,
            "skills_extracted": 0, "errors": 0,
        }
        self._pending_cache: list[ConversationRecord] = []
        self._current_session_id: str | None = None
        self._session_agent_id: dict[str, str] = {}
        self._pending_file_ops: dict[str, list[FileOperation]] = {}
        self._pending_errors: dict[str, list[ErrorLog]] = {}
        self._pending_mcp_calls: dict[str, list[MCPCallDetail]] = {}
        self._pending_switches: dict[str, list[dict]] = {}
        self._dispatch_history: list[dict] = []
        self._dispatch_stats: dict = {"total_dispatches": 0, "by_task_type": {}, "by_priority": {}}
        self._trigger_counts: dict[str, int] = {}

        # 子系统实例
        self._otel_interceptor = OtelMCPInterceptor()
        self._turn_logger = TurnLogger()
        self._feedback_loop = FeedbackAwareLoop()
        self._aos_bridge = OWASPAosBridge()
        self._eval_bridge = OTelEvaluationBridge()
        self._inspect_engine = OWASPInspectEngine()
        self._diaml_serializer = DiAMLSerializer()
        self._ms_span_manager = MsAgentTaskSpanManager()
        self._adaptive_policy = AdaptiveRecordingPolicy()

        # 进化循环 (可选依赖)
        self._evo_loop = None
        try:
            from ..processors.evolution_loop import EvolutionLoop
            self._evo_loop = EvolutionLoop(
                module_name="enforcement_hook",
                effectiveness_fn=self._calc_hook_effectiveness,
                learn_fn=self._learn_from_enforcement,
                evolve_fn=self._evolve_hook_config,
                mutable_config={"enforcement_level": "mandatory", "skip_threshold": 0.1},
                health_metrics_fn=self._get_hook_health,
            )
        except ImportError:
            pass

    @property
    def enabled(self) -> bool:
        return self._enabled

    def _resolve_agent_id(self, session_id: str, provided_agent_id: str) -> str:
        if provided_agent_id:
            self._session_agent_id[session_id] = provided_agent_id
            return provided_agent_id
        return self._session_agent_id.get(session_id, "unknown")

    def set_session_agent(self, session_id: str, agent_id: str) -> None:
        self._session_agent_id[session_id] = agent_id

    # ── 注册API ──

    def register_file_operation(self, session_id: str, op: FileOperation) -> None:
        self._pending_file_ops.setdefault(session_id, []).append(op)

    def register_error(self, session_id: str, error: ErrorLog) -> None:
        self._pending_errors.setdefault(session_id, []).append(error)

    def register_mcp_call(self, session_id: str, call: MCPCallDetail) -> None:
        self._pending_mcp_calls.setdefault(session_id, []).append(call)

    def register_agent_switch(self, session_id: str, switch: dict) -> None:
        self._pending_switches.setdefault(session_id, []).append(switch)

    # ── 对话完成 ──

    def conversation_complete(
        self, session_id: str, user_input: str, ai_response: str,
        agent_id: str = "", turn_number: int = 1,
    ) -> ConversationRecord:
        resolved_agent = self._resolve_agent_id(session_id, agent_id)
        record = ConversationRecord(
            session_id=session_id, user_input=user_input,
            ai_response=ai_response, agent_id=resolved_agent,
            timestamp=time.time(), turn_number=turn_number,
        )
        self._flush_pending_to_record(record, session_id)
        self.registry.register(record)
        self._stats["hooks_triggered"] += 1
        self._track_token_economy(record)
        self._populate_vcon(record)
        self._generate_fair_metadata(record)
        self._classify_conversation(record)
        self._stats["records_enforced"] += 1
        return record

    def _flush_pending_to_record(self, record: ConversationRecord, session_id: str) -> None:
        if session_id in self._pending_file_ops:
            record.file_operations = self._pending_file_ops.pop(session_id, [])
        if session_id in self._pending_errors:
            record.error_log = self._pending_errors.pop(session_id, [])
        if session_id in self._pending_mcp_calls:
            mcp_list = self._pending_mcp_calls.pop(session_id, [])
            record.mcp_call_details = mcp_list
            record.mcp_calls_made = [c.tool_name for c in mcp_list]
        if session_id in self._pending_switches:
            record.agent_switches = self._pending_switches.pop(session_id, [])

    # ── 记录填充 (精简版) ──

    def _track_token_economy(self, record: ConversationRecord) -> None:
        te = TokenEconomy()
        te.prompt_tokens = len(record.user_input) // 3
        te.completion_tokens = len(record.ai_response) // 2
        te.estimate()
        record.token_economy = te

    def _populate_vcon(self, record: ConversationRecord) -> None:
        from .hook_models import vConLifecycle, vConParty, vConLifecycleState
        record.vcon_lifecycle = vConLifecycle(state=vConLifecycleState.ACTIVE)
        record.vcon_parties.append(vConParty(party_id=record.agent_id, name=record.agent_id, role="agent"))

    def _generate_fair_metadata(self, record: ConversationRecord) -> None:
        record.fair_metadata = FAIRMetadata(
            findable_id=record.content_hash,
            created_date=time.strftime("%Y-%m-%d", time.localtime(record.timestamp)),
        )

    def _classify_conversation(self, record: ConversationRecord) -> None:
        text = (record.user_input + record.ai_response).lower()
        if any(kw in text for kw in ("如何", "怎么", "为什么", "?")):
            record.conversation_class = "question"
        elif any(kw in text for kw in ("请", "执行", "创建", "修改")):
            record.conversation_class = "task"
        else:
            record.conversation_class = "unknown"

    # ── 统计/健康 ──

    def get_otel_stats(self) -> dict:
        return self._otel_interceptor.get_otel_stats()

    def get_dispatch_stats(self) -> dict:
        return dict(self._dispatch_stats)

    def track_dispatch(self, task_type: str, priority: str = "medium") -> None:
        entry = {"task_type": task_type, "priority": priority, "timestamp": time.time()}
        self._dispatch_history.append(entry)
        self._dispatch_stats["total_dispatches"] += 1
        self._dispatch_stats["by_task_type"][task_type] = \
            self._dispatch_stats["by_task_type"].get(task_type, 0) + 1

    def _get_hook_health(self) -> dict[str, float]:
        total = max(self._stats["hooks_triggered"], 1)
        return {
            "effectiveness": self._stats["records_enforced"] / total,
            "error_rate": self._stats["errors"] / total,
            "coverage": len(self._session_agent_id) / max(total * 0.1, 1),
        }

    def _calc_hook_effectiveness(self) -> float:
        h = self._get_hook_health()
        return (h["effectiveness"] * 0.5 + (1 - h["error_rate"]) * 0.3 + h["coverage"] * 0.2)

    def _learn_from_enforcement(self, causal_pairs, summary) -> dict:
        return {"learned": True, "causal_pairs": len(causal_pairs), "summary": summary}

    def _evolve_hook_config(self, learn_result, config) -> dict:
        return {"config": config, "evolved": True}


class SkillExtractionPipeline:
    """技能提取管线 — 从对话中提取可复用模式"""

    def __init__(self, hook: TianjiEnforcementHook | None = None,
                 memory_api_url: str = "http://127.0.0.1:8771"):
        self.hook = hook
        self.memory_api_url = memory_api_url

    def extract_from_conversation(
        self, user_input: str, ai_response: str, session_id: str
    ) -> str | None:
        conv_text = f"{user_input}\n\n{ai_response}"
        if len(conv_text) < 500:
            return None
        prompt = f"""从以下对话中提取可复用的流程/模式/经验:

{conv_text[:3000]}

返回JSON: {{"skill_title": "标题", "skill_body": "描述(3-5句话)", "tags": ["标签"], "confidence": 0.8}}"""
        try:
            import urllib.request
            data = json.dumps({"content": prompt, "layer": "semantic",
                               "tags": ["skill_extraction"]}, ensure_ascii=False).encode("utf-8")
            req = urllib.request.Request(f"{self.memory_api_url}/api/memory/store",
                                         data=data, headers={"Content-Type": "application/json; charset=utf-8"},
                                         method="POST")
            resp = urllib.request.urlopen(req, timeout=5)
            result = json.loads(resp.read().decode("utf-8"))
            return result.get("memory_id")
        except Exception:
            return None
