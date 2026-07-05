# -*- coding: utf-8-sig -*-
"""EnforcementHook数据模型层 — 从hook_core.py拆分 [SSS-PhaseB]

包含24个纯数据模型类:
  - vCon系列: vConConsentStatus/vConLifecycleState/vConParty/vConConsent/vConLifecycle
  - 操作记录: FileOperation/MCPCallDetail/ErrorLog
  - 分类枚举: ConversationClass
  - Token经济: TokenEconomy
  - 七维日志: SevenDimensionalLogModel/ReasoningLog/StateLog/DecisionLog/ActionLog/ObservationLog/ReflectionLog
  - LoongSuite合规: LoongSuiteAgentCategory/LoongSuiteMetadata/LoongSuiteAlignment
  - 反馈循环: FeedbackRecord/FeedbackAwareLoop
  - FAIR元数据: FAIRMetadata
  - 核心记录: ConversationRecord/EnforcementDecision
"""

from __future__ import annotations

import hashlib
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from .otel_attributes import OtelGenAISpan


# ═══ vCon (虚拟对话) 数据模型 ═══

class vConConsentStatus(str, Enum):
    GRANTED = "granted"
    DENIED = "denied"
    PENDING = "pending"
    REVOKED = "revoked"
    EXPIRED = "expired"


class vConLifecycleState(str, Enum):
    INITIATED = "initiated"
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    ARCHIVED = "archived"
    DELETED = "deleted"


@dataclass
class vConParty:
    party_id: str = ""
    name: str = ""
    role: str = "unknown"
    provider: str = "memory-engine-global"
    meta: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {"party_id": self.party_id, "name": self.name, "role": self.role,
                "provider": self.provider, "meta": self.meta}


@dataclass
class vConConsent:
    party_id: str = ""
    consent_type: str = "explicit"
    granted: bool = True
    consent_timestamp: float = field(default_factory=time.time)
    scope: str = "conversation_recording"
    purpose: str = "memory_enhancement"
    retention_days: int = 365
    revocable: bool = True

    def to_dict(self) -> dict:
        return {"party_id": self.party_id, "consent_type": self.consent_type,
                "granted": self.granted, "consent_timestamp": self.consent_timestamp,
                "scope": self.scope, "purpose": self.purpose,
                "retention_days": self.retention_days, "revocable": self.revocable}


@dataclass
class vConLifecycle:
    state: vConLifecycleState = vConLifecycleState.ACTIVE
    transitions: list[dict] = field(default_factory=list)
    scitt_receipt: str = ""
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    archived_at: float | None = None
    deleted_at: float | None = None

    def to_dict(self) -> dict:
        return {"state": self.state.value, "transitions": self.transitions,
                "scitt_receipt": self.scitt_receipt, "created_at": self.created_at,
                "updated_at": self.updated_at, "archived_at": self.archived_at,
                "deleted_at": self.deleted_at}

    def transition(self, new_state: vConLifecycleState, reason: str = "") -> None:
        self.transitions.append({"from": self.state.value, "to": new_state.value,
                                  "reason": reason, "timestamp": time.time()})
        self.state = new_state
        self.updated_at = time.time()
        if new_state == vConLifecycleState.ARCHIVED:
            self.archived_at = time.time()
        elif new_state == vConLifecycleState.DELETED:
            self.deleted_at = time.time()


# ═══ 操作记录 ═══

@dataclass
class FileOperation:
    operation: str
    path: str
    lines_changed: dict[str, int] = field(default_factory=dict)
    reason: str = ""
    content_before: str = ""
    content_after: str = ""
    file_size: int = 0
    content_hash: str = ""
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return {k: v for k, v in self.__dict__.items()}


@dataclass
class MCPCallDetail:
    tool_name: str
    params_summary: str = ""
    result_summary: str = ""
    duration_ms: float = 0.0
    status: str = "unknown"

    def to_dict(self) -> dict:
        return {k: v for k, v in self.__dict__.items()}


@dataclass
class ErrorLog:
    error_type: str
    message: str
    context: str = ""
    resolved: bool = False
    resolution: str = ""
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return {k: v for k, v in self.__dict__.items()}


# ═══ 分类与Token经济 ═══

class ConversationClass(str, Enum):
    TASK = "task"
    QUESTION = "question"
    INSTRUCTION = "instruction"
    FEEDBACK = "feedback"
    COMMITMENT = "commitment"
    SOCIAL = "social"
    REASONING = "reasoning"
    ERROR = "error"
    UNKNOWN = "unknown"


class TokenEconomy:
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    model: str = "deepseek-chat"
    estimated_cost_usd: float = 0.0

    def to_dict(self) -> dict:
        return {"prompt_tokens": self.prompt_tokens, "completion_tokens": self.completion_tokens,
                "total_tokens": self.total_tokens, "model": self.model,
                "estimated_cost_usd": round(self.estimated_cost_usd, 6)}

    def estimate(self) -> None:
        self.total_tokens = self.prompt_tokens + self.completion_tokens
        self.estimated_cost_usd = (self.prompt_tokens * 0.27 + self.completion_tokens * 1.10) / 1_000_000


# ═══ 七维日志模型 ═══

class SevenDimensionalLogModel:
    ACTION = "action"
    OBSERVATION = "observation"
    REASONING = "reasoning"
    STATE = "state"
    REFLECTION = "reflection"
    DECISION = "decision"
    TOKEN_ECONOMY = "token_economy"
    DIMENSIONS = [ACTION, OBSERVATION, REASONING, STATE, REFLECTION, DECISION, TOKEN_ECONOMY]


@dataclass
class ReasoningLog:
    chain_id: str = ""
    steps: list[dict] = field(default_factory=list)
    conclusion: str = ""
    confidence: float = 0.0
    duration_ms: float = 0.0
    model_used: str = "deepseek-chat"
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return {k: v for k, v in self.__dict__.items()}

    def add_step(self, thought: str, evidence: str = "", confidence: float = 0.0) -> None:
        self.steps.append({"thought": thought, "evidence": evidence,
                           "confidence": confidence, "timestamp": time.time()})


@dataclass
class StateLog:
    entity_id: str = ""
    state_type: str = ""
    old_state: str = ""
    new_state: str = ""
    trigger: str = ""
    duration_in_state_ms: float = 0.0
    metadata: dict = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return {k: v for k, v in self.__dict__.items()}


@dataclass
class DecisionLog:
    decision_id: str = ""
    options: list[str] = field(default_factory=list)
    chosen: str = ""
    rationale: str = ""
    alternatives: list[str] = field(default_factory=list)
    risk_assessment: str = ""
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return {k: v for k, v in self.__dict__.items()}


@dataclass
class ActionLog:
    action_id: str = ""
    action_type: str = ""
    target: str = ""
    parameters: dict = field(default_factory=dict)
    result: str = ""
    duration_ms: float = 0.0
    status: str = "unknown"
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return {k: v for k, v in self.__dict__.items()}


@dataclass
class ObservationLog:
    observation_id: str = ""
    source: str = ""
    content: str = ""
    relevance_score: float = 0.0
    triggered_by: str = ""
    context_window_id: str = ""
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return {k: v for k, v in self.__dict__.items()}


@dataclass
class ReflectionLog:
    reflection_id: str = ""
    trigger_event: str = ""
    self_assessment: str = ""
    lessons_learned: list[str] = field(default_factory=list)
    improvement_actions: list[str] = field(default_factory=list)
    effectiveness_before: float = 0.0
    effectiveness_after: float = 0.0
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return {k: v for k, v in self.__dict__.items()}


# ═══ LoongSuite 合规体系 ═══

class LoongSuiteAgentCategory(str, Enum):
    ASSISTANT = "assistant"
    PLANNER = "planner"
    EXECUTOR = "executor"
    EVALUATOR = "evaluator"
    ORCHESTRATOR = "orchestrator"
    CODER = "coder"
    REVIEWER = "reviewer"
    ANALYZER = "analyzer"
    RETRIEVER = "retriever"
    GUARDIAN = "guardian"


@dataclass
class LoongSuiteMetadata:
    agent_category: LoongSuiteAgentCategory = LoongSuiteAgentCategory.ASSISTANT
    provider_vendor: str = "memory-engine-global"
    provider_region: str = "cn"
    compliance_level: str = "internal"
    data_classification: str = "conversation_log"
    retention_policy: str = "P365D"
    audit_ready: bool = True
    ai_governance_tag: str = ""
    model_family: str = "deepseek"
    model_version: str = "v3"
    deployment_mode: str = "on_premise"
    risk_tier: str = "low"

    def to_dict(self) -> dict:
        return self.to_loongsuite_dict()

    def to_loongsuite_dict(self) -> dict:
        prefix = "loongsuite."
        return {
            f"{prefix}agent.category": self.agent_category.value,
            f"{prefix}provider.vendor": self.provider_vendor,
            f"{prefix}provider.region": self.provider_region,
            f"{prefix}compliance.level": self.compliance_level,
            f"{prefix}data.classification": self.data_classification,
            f"{prefix}retention.policy": self.retention_policy,
            f"{prefix}audit.ready": self.audit_ready,
            f"{prefix}ai_governance.tag": self.ai_governance_tag,
            f"{prefix}model.family": self.model_family,
            f"{prefix}model.version": self.model_version,
            f"{prefix}deployment.mode": self.deployment_mode,
            f"{prefix}risk.tier": self.risk_tier,
        }


class LoongSuiteAlignment:
    AGENT_CATEGORY_MAP = {
        "tianshu": LoongSuiteAgentCategory.ORCHESTRATOR,
        "tiewei": LoongSuiteAgentCategory.GUARDIAN,
        "yiku": LoongSuiteAgentCategory.RETRIEVER,
        "dongcha": LoongSuiteAgentCategory.ANALYZER,
        "luling": LoongSuiteAgentCategory.GUARDIAN,
        "lingxi": LoongSuiteAgentCategory.ASSISTANT,
        "wenzong": LoongSuiteAgentCategory.PLANNER,
        "miaobi": LoongSuiteAgentCategory.CODER,
        "mingjing": LoongSuiteAgentCategory.REVIEWER,
        "tiansuan": LoongSuiteAgentCategory.ANALYZER,
        "jingwei": LoongSuiteAgentCategory.PLANNER,
        "kuangshi": LoongSuiteAgentCategory.RETRIEVER,
        "baiqiao": LoongSuiteAgentCategory.ORCHESTRATOR,
        "shiguan": LoongSuiteAgentCategory.EVALUATOR,
        "jinshu": LoongSuiteAgentCategory.EXECUTOR,
        "qianli": LoongSuiteAgentCategory.GUARDIAN,
        "gongzao": LoongSuiteAgentCategory.EXECUTOR,
        "zhenshan": LoongSuiteAgentCategory.GUARDIAN,
        "zhuiguang": LoongSuiteAgentCategory.ANALYZER,
        "lianli": LoongSuiteAgentCategory.ANALYZER,
        "huasheng": LoongSuiteAgentCategory.EVALUATOR,
        "wanxiang": LoongSuiteAgentCategory.ANALYZER,
    }

    @classmethod
    def classify_agent(cls, agent_id: str) -> LoongSuiteAgentCategory:
        return cls.AGENT_CATEGORY_MAP.get(agent_id, LoongSuiteAgentCategory.ASSISTANT)

    @classmethod
    def generate_metadata(cls, agent_id: str) -> LoongSuiteMetadata:
        cat = cls.classify_agent(agent_id)
        return LoongSuiteMetadata(agent_category=cat, ai_governance_tag=f"tianji-{cat.value}-{agent_id}")

    @classmethod
    def compliance_check(cls, record) -> dict:
        issues = []
        if not getattr(record, 'vcon_uuid', None): issues.append("missing vcon_uuid")
        if not getattr(record, 'agent_id', None): issues.append("missing agent_id")
        if not getattr(record, 'content_hash', None): issues.append("missing content_hash")
        if not getattr(record, 'timestamp', None): issues.append("missing timestamp")
        if not getattr(record, 'fair_metadata', None): issues.append("missing fair_metadata")
        return {
            "compliant": len(issues) == 0, "issues": issues,
            "standard": "LoongSuite GenAI v2026.05",
            "alignment_score": max(0.0, 1.0 - len(issues) * 0.2),
        }


# ═══ 反馈循环 ═══

@dataclass
class FeedbackRecord:
    feedback_id: str = ""
    source_module: str = ""
    feedback_type: str = ""
    content: str = ""
    severity: str = "info"
    acknowledged: bool = False
    action_taken: str = ""
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return {k: v for k, v in self.__dict__.items()}


class FeedbackAwareLoop:
    MAX_QUEUE = 200

    def __init__(self):
        self._feedback_queue: list[FeedbackRecord] = []
        self._lock = threading.Lock()
        self._consumer_satisfaction: dict[str, float] = {}
        self._loop_iterations: int = 0
        self._adjustments_made: int = 0

    def receive_feedback(self, source_module: str, feedback_type: str,
                         content: str, severity: str = "info") -> FeedbackRecord:
        record = FeedbackRecord(
            feedback_id=f"fb-{int(time.time() * 1000)}-{len(self._feedback_queue)}",
            source_module=source_module, feedback_type=feedback_type,
            content=content, severity=severity,
        )
        with self._lock:
            self._feedback_queue.append(record)
            if len(self._feedback_queue) > self.MAX_QUEUE:
                self._feedback_queue = self._feedback_queue[-self.MAX_QUEUE:]
        return record

    def process_feedback(self, callback=None) -> dict:
        with self._lock:
            unacknowledged = [f for f in self._feedback_queue if not f.acknowledged]
            results = []
            for fb in unacknowledged[:10]:
                if callback:
                    action = callback(fb)
                    fb.action_taken = str(action) if action else "no_action"
                fb.acknowledged = True
                results.append({"feedback_id": fb.feedback_id, "source": fb.source_module, "action": fb.action_taken})
            return {"processed": len(results), "results": results}

    def get_satisfaction(self, module: str) -> float:
        return self._consumer_satisfaction.get(module, 0.5)

    def update_satisfaction(self, module: str, score: float) -> None:
        self._consumer_satisfaction[module] = max(0.0, min(1.0, score))

    def get_stats(self) -> dict:
        with self._lock:
            return {
                "total_feedback": len(self._feedback_queue),
                "unacknowledged": sum(1 for f in self._feedback_queue if not f.acknowledged),
                "consumer_satisfaction": dict(self._consumer_satisfaction),
                "loop_iterations": self._loop_iterations,
                "adjustments_made": self._adjustments_made,
            }

    def run_loop_iteration(self, adjust_fn=None) -> dict:
        self._loop_iterations += 1
        stats = self.get_stats()
        if adjust_fn:
            changes = adjust_fn(stats)
            if changes:
                self._adjustments_made += 1
                return {"iteration": self._loop_iterations, "changes": changes}
        return {"iteration": self._loop_iterations, "changes": None}


# ═══ FAIR 元数据 ═══

@dataclass
class FAIRMetadata:
    findable_id: str = ""
    accessible_uri: str = ""
    interoperable_schema: str = "ISO 24617-2:2020 / W3C PROV-DM / Tianji v9.1 Schema"
    reusable_license: str = "TIANJI-INTERNAL-1.0"
    keywords: list[str] = field(default_factory=list)
    created_date: str = ""
    modified_date: str = ""

    def to_dict(self) -> dict:
        return {k: v for k, v in self.__dict__.items()}


# ═══ ISO/PROV 前向引用 (避免循环导入) ═══

class ISOAnnotation:
    def __init__(self):
        self.dialogue_acts: list[dict] = []
        self.communicative_function: str = ""
        self.confidence: float = 0.0

    def to_dict(self) -> dict:
        return {"dialogue_acts": self.dialogue_acts,
                "communicative_function": self.communicative_function,
                "confidence": self.confidence}


class PROVTrace:
    def __init__(self):
        self.activities: list[dict] = []
        self.entities: list[dict] = []
        self.derivations: list[dict] = []

    def to_dict(self) -> dict:
        return {"activities": self.activities, "entities": self.entities,
                "derivations": self.derivations}


# ═══ 核心对话记录 ═══

@dataclass
class ConversationRecord:
    session_id: str
    user_input: str
    ai_response: str
    agent_id: str
    timestamp: float
    turn_number: int = 1
    mcp_calls_made: list[str] = field(default_factory=list)
    mcp_call_details: list[MCPCallDetail] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    file_operations: list[FileOperation] = field(default_factory=list)
    error_log: list[ErrorLog] = field(default_factory=list)
    agent_switches: list[dict] = field(default_factory=list)
    recorded: bool = False
    memory_id: str = ""
    content_hash: str = ""
    conversation_class: str = "unknown"
    iso_annotation: ISOAnnotation | None = None
    prov_trace: PROVTrace | None = None
    token_economy: TokenEconomy | None = None
    fair_metadata: FAIRMetadata | None = None
    vcon_uuid: str = ""
    vcon_parties: list[vConParty] = field(default_factory=list)
    vcon_consents: list[vConConsent] = field(default_factory=list)
    vcon_lifecycle: vConLifecycle | None = None
    otel_spans: list[OtelGenAISpan] = field(default_factory=list)
    otel_trace_id: str = ""
    reasoning_logs: list[ReasoningLog] = field(default_factory=list)
    state_logs: list[StateLog] = field(default_factory=list)
    feedback_records: list[FeedbackRecord] = field(default_factory=list)
    token_economy_logs: list[TokenEconomy] = field(default_factory=list)
    loongsuite_metadata: LoongSuiteMetadata | None = None
    file_snap: dict[str, Any] = field(default_factory=dict)
    trigger_frequency: int = 0
    standards_check: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if not self.content_hash and (self.user_input or self.ai_response):
            raw = f"{self.session_id}|{self.turn_number}|{self.user_input}|{self.ai_response}"
            self.content_hash = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:20]

    def to_dict(self) -> dict:
        d = {k: v for k, v in self.__dict__.items() if not k.startswith("_")}
        for key in ["vcon_lifecycle", "token_economy", "fair_metadata",
                     "loongsuite_metadata", "iso_annotation", "prov_trace"]:
            val = getattr(d.get(key), 'to_dict', lambda: None)()
            if val is not None:
                d[key] = val
        if isinstance(d.get("vcon_lifecycle"), vConLifecycle):
            d["vcon_lifecycle"] = d["vcon_lifecycle"].to_dict()
        if isinstance(d.get("token_economy"), TokenEconomy):
            d["token_economy"] = d["token_economy"].to_dict()
        return d


@dataclass
class EnforcementDecision:
    level: str = "observe"
    rule_id: str = ""
    reason: str = ""
    auto_applied: bool = False
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return {k: v for k, v in self.__dict__.items()}
