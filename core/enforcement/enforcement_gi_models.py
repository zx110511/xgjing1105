# -*- coding: utf-8-sig -*-
"""enforcement_gi_models.py — 全局影响分析数据模型 (SSS-PhaseE合并精简)

合并PhaseB过度拆分的小文件，消除over-engineering:
- ImpactTier (18行) ← enforcement_gi_impacttier.py
- ImpactDimension (21行) ← enforcement_gi_impactdimension.py
- ModuleImpact (45行) ← enforcement_gi_moduleimpact.py
- SubWeightDetail (28行) ← enforcement_gi_subweightdetail.py
- WeightBreakdown (79行) ← enforcement_gi_weightbreakdown.py
- StandardGap (117行) ← enforcement_gi_standardgap.py
- ConsumerDemand (98行) ← enforcement_gi_consumerdemand.py
- ModuleEvolutionSpec (699行) ← enforcement_gi_moduleevolutionspec.py (保留独立文件，太大)

源文件行数: 1026 → 合并后: ~450行 (56%瘦身)
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List


# ============================================================================
# 枚举定义
# ============================================================================

class ImpactTier(str, Enum):
    """影响等级"""
    S = "S"  # 核心基础设施
    A = "A"  # 关键链路
    B = "B"  # 重要依存
    C = "C"  # 弱关联
    D = "D"  # 几乎无关


class ImpactDimension(str, Enum):
    """影响维度"""
    DIRECT = "直接影响"
    MEMORY_STORE = "记忆存储链"
    LEARNING = "学习进化链"
    KNOWLEDGE = "知识抽取链"
    AGENT_SCHEDULE = "智能调度链"
    GOVERNANCE = "治理审计链"
    API_EXPOSE = "API暴露链"
    INFRASTRUCTURE = "基础设施链"


# ============================================================================
# 数据类定义
# ============================================================================

@dataclass
class ModuleImpact:
    """模块影响评估"""
    module_name: str
    file_path: str
    tier: ImpactTier
    diw: float
    dfw: float
    eu: float
    sc: float
    composite: float = 0.0
    dimensions: List[str] = field(default_factory=list)
    evolution_targets: List[str] = field(default_factory=list)
    impact_description: str = ""

    def __post_init__(self):
        self.composite = round(
            self.diw * 0.40 + self.dfw * 0.30 + self.eu * 0.20 + self.sc * 0.10, 4
        )

    def to_dict(self) -> dict:
        return {
            "module": self.module_name,
            "tier": self.tier.value,
            "diw": self.diw,
            "dfw": self.dfw,
            "eu": self.eu,
            "sc": self.sc,
            "composite": self.composite,
            "dimensions": self.dimensions,
            "evolution_targets": self.evolution_targets,
        }


@dataclass
class SubWeightDetail:
    """四维权重的子维度分解，用于精确校准"""
    name: str
    value: float
    description: str = ""
    calibration_source: str = ""

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "value": self.value,
            "description": self.description,
            "calibration_source": self.calibration_source,
        }


@dataclass
class WeightBreakdown:
    """四维权重的完整分解"""
    diw_value: float
    diw_subs: List[SubWeightDetail] = field(default_factory=list)
    dfw_value: float = 0.0
    dfw_subs: List[SubWeightDetail] = field(default_factory=list)
    eu_value: float = 0.0
    eu_subs: List[SubWeightDetail] = field(default_factory=list)
    sc_value: float = 0.0
    sc_subs: List[SubWeightDetail] = field(default_factory=list)
    composite: float = 0.0

    def __post_init__(self):
        self.composite = round(
            self.diw_value * 0.40
            + self.dfw_value * 0.30
            + self.eu_value * 0.20
            + self.sc_value * 0.10,
            4,
        )

    def to_calibration_report(self) -> dict:
        return {
            "composite": self.composite,
            "diw": {"total": self.diw_value, "subs": [s.to_dict() for s in self.diw_subs]},
            "dfw": {"total": self.dfw_value, "subs": [s.to_dict() for s in self.dfw_subs]},
            "eu": {"total": self.eu_value, "subs": [s.to_dict() for s in self.eu_subs]},
            "sc": {"total": self.sc_value, "subs": [s.to_dict() for s in self.sc_subs]},
        }


# 子权重常量
DIW_SUB_WEIGHTS = {
    "field_dependency": 0.35,
    "api_dependency": 0.25,
    "behavior_dependency": 0.25,
    "lifecycle_dependency": 0.15,
}

DFW_SUB_WEIGHTS = {
    "data_through_rate": 0.40,
    "data_quality_impact": 0.30,
    "data_path_criticality": 0.30,
}

EU_SUB_WEIGHTS = {
    "gap_severity": 0.35,
    "alignment_urgency": 0.30,
    "consumer_demand_pressure": 0.20,
    "standard_gap": 0.15,
}

SC_SUB_WEIGHTS = {
    "availability_requirement": 0.35,
    "security_impact": 0.25,
    "recoverability_impact": 0.25,
    "dependency_count": 0.15,
}


@dataclass
class StandardGap:
    """国际标准对标差距"""
    standard_name: str
    standard_version: str
    current_support: float
    gap_description: str
    required_fields: List[str] = field(default_factory=list)
    priority: str = "P2"

    def to_dict(self) -> dict:
        return {
            "standard": f"{self.standard_name} {self.standard_version}",
            "current_support": self.current_support,
            "gap": self.gap_description,
            "required_fields": self.required_fields,
            "priority": self.priority,
        }


STANDARD_GAPS: Dict[str, StandardGap] = {
    "otel_genai_agent": StandardGap(
        "OpenTelemetry GenAI Agent Spans", "v1.41.0", 0.35,
        "天机MCP拦截器未按OTel标准生成create_agent/invoke_agent/execute_tool span，"
        "缺少gen_ai.agent.name、gen_ai.conversation.id等标准属性",
        ["gen_ai.agent.name", "gen_ai.agent.id", "gen_ai.agent.version",
         "gen_ai.conversation.id", "gen_ai.operation.name", "gen_ai.provider.name"], "P1"),
    "otel_genai_tool": StandardGap(
        "OpenTelemetry GenAI Tool Execution", "v1.41.0", 0.30,
        "天机MCP工具调用未记录execute_tool span标准属性",
        ["tool.name", "tool.parameters", "tool.result.status", "tool.call.duration_ms"], "P1"),
    "otel_evaluation": StandardGap(
        "OpenTelemetry GenAI Evaluation", "v1.41.0", 0.15,
        "天机未实现gen_ai.evaluation标准评估属性",
        ["gen_ai.evaluation.name", "gen_ai.evaluation.score.value",
         "gen_ai.evaluation.score.label", "gen_ai.evaluation.explanation"], "P2"),
    "vcon_container": StandardGap(
        "IETF vCon", "draft-ietf-vcon-vcon-core-01", 0.40,
        "天机ConversationRecord未对齐vCon JSON容器格式",
        ["vcon_uuid", "parties[]", "dialog[]", "analysis[]", "attachments[]"], "P1"),
    "aos_instrument": StandardGap(
        "OWASP Agent Observability Standard", "Working Draft 2026", 0.10,
        "天机缺少OWASP AOS定义的Instrument/Trace/Inspect三柱架构",
        ["instrument_hooks", "trace_events", "AgBOM_component_list"], "P2"),
    "iso_daml": StandardGap(
        "ISO 24617-2 DiAML", "2020", 0.55,
        "天机ISO标注仅覆盖10维中的5维，缺少ContactMgmt/PartnerMgmt/TimeMgmt/OwnCommMgmt维度",
        ["contact_management_dim", "partner_management_dim",
         "time_management_dim", "own_communication_management_dim"], "P1"),
    "ms_agent_task": StandardGap(
        "Microsoft Agent Framework execute_task span", "2025.10", 0.20,
        "天机Agent调度未记录execute_task/agent_to_agent_interaction span",
        ["execute_task span", "agent_to_agent_interaction span",
         "agent.state.management span", "agent_planning span"], "P2"),
}


@dataclass
class ConsumerDemand:
    """下游消费模块需求"""
    consumer_name: str
    demand_score: float
    required_fields: List[str]
    max_tolerable_latency_ms: float = 5000.0
    description: str = ""

    def to_dict(self) -> dict:
        return {
            "consumer": self.consumer_name,
            "demand": self.demand_score,
            "required_fields": self.required_fields,
            "max_latency_ms": self.max_tolerable_latency_ms,
            "description": self.description,
        }


CONSUMER_DEMANDS: Dict[str, ConsumerDemand] = {
    "memory_engine": ConsumerDemand("memory_engine", 0.95,
        ["session_id", "user_input", "ai_response", "timestamp", "content_hash"],
        5000.0, "记忆引擎需要完整对话内容+哈希去重"),
    "quality_gate": ConsumerDemand("quality_gate", 0.85,
        ["content_hash", "conversation_class", "iso_annotation", "prov_trace"],
        3000.0, "质量门禁需要分类+标注信息以执行三问推演判决"),
    "learning": ConsumerDemand("learning", 0.80,
        ["user_input", "ai_response", "agent_id", "conversation_class", "tags"],
        10000.0, "学习闭环需要用户意图+AI响应+分类标签以提炼Skill"),
    "knowledge": ConsumerDemand("knowledge", 0.75,
        ["user_input", "ai_response", "tags", "iso_annotation", "prov_trace"],
        8000.0, "知识抽取器需要语义标注+溯源信息以构建知识图谱"),
    "agent_schedule": ConsumerDemand("agent_schedule", 0.70,
        ["agent_id", "agent_switches", "mcp_call_details", "dispatch_count"],
        3000.0, "智能调度需要Agent切换记录+MCP调用细节以优化调度策略"),
    "governance": ConsumerDemand("governance", 0.65,
        ["prov_trace", "fair_metadata", "content_hash", "token_economy"],
        15000.0, "治理审计需要PROV溯源+FAIR元数据+Token经济以合规审计"),
    "api": ConsumerDemand("api", 0.55,
        ["session_id", "timestamp", "agent_id", "conversation_class"],
        2000.0, "API路由层需要基本标识信息以提供查询服务"),
    "security": ConsumerDemand("security", 0.60,
        ["content_hash", "prov_trace", "file_operations"],
        10000.0, "安全审计需要文件操作记录+溯源链以检测异常行为"),
    "performance": ConsumerDemand("performance", 0.45,
        ["token_economy", "mcp_call_details", "dispatch_count"],
        5000.0, "性能分析需要Token消耗+MCP调用时长以诊断瓶颈"),
}


__all__ = [
    "ImpactTier", "ImpactDimension", "ModuleImpact", "SubWeightDetail",
    "WeightBreakdown", "StandardGap", "ConsumerDemand",
    "DIW_SUB_WEIGHTS", "DFW_SUB_WEIGHTS", "EU_SUB_WEIGHTS", "SC_SUB_WEIGHTS",
    "STANDARD_GAPS", "CONSUMER_DEMANDS",
]
