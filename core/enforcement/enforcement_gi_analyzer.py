# -*- coding: utf-8-sig -*-
"""执行进化 — 全局影响分析器 (GlobalImpactAnalyzer)

从 enforcement_global_impact.py 拆分 (SSS-PhaseB)
"""

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Set, Tuple
from .enforcement_gi_models import (
    ImpactTier, ModuleImpact, ConsumerDemand, CONSUMER_DEMANDS,
    StandardGap, STANDARD_GAPS,
)
from .enforcement_gi_moduleevolutionspec import ModuleEvolutionSpec, GLOBAL_IMPACT_MATRIX

class GlobalImpactAnalyzer:
    """全局辐射影响分析器 v2.0 — 增强版"""

    def get_by_tier(self, tier: ImpactTier) -> List[ModuleImpact]:
        return [m for m in GLOBAL_IMPACT_MATRIX if m.tier == tier]

    def get_top_n(self, n: int = 10) -> List[ModuleImpact]:
        return sorted(GLOBAL_IMPACT_MATRIX, key=lambda m: m.composite, reverse=True)[:n]

    def get_evolution_candidates(
        self, min_composite: float = 0.4
    ) -> List[ModuleImpact]:
        return [
            m
            for m in GLOBAL_IMPACT_MATRIX
            if m.composite >= min_composite and len(m.evolution_targets) > 0
        ]

    def get_tier_summary(self) -> Dict:
        summary = {}
        for tier in ImpactTier:
            modules = self.get_by_tier(tier)
            if modules:
                summary[tier.value] = {
                    "count": len(modules),
                    "avg_composite": round(
                        sum(m.composite for m in modules) / len(modules), 4
                    ),
                    "modules": [m.module_name for m in modules],
                    "total_evolution_targets": sum(
                        len(m.evolution_targets) for m in modules
                    ),
                }
        return summary

    def get_dimension_coverage(self) -> Dict[str, List[str]]:
        coverage = {}
        for dim in ImpactDimension:
            modules = [
                m.module_name for m in GLOBAL_IMPACT_MATRIX if dim.value in m.dimensions
            ]
            if modules:
                coverage[dim.value] = modules
        return coverage

    def get_priority_evolution_order(self) -> List[Dict]:
        candidates = self.get_evolution_candidates(min_composite=0.3)
        return [
            {
                "rank": i + 1,
                "module": m.module_name,
                "tier": m.tier.value,
                "composite": m.composite,
                "evolution_targets": m.evolution_targets,
                "impact_description": m.impact_description,
            }
            for i, m in enumerate(candidates)
        ]

    def generate_report(self) -> Dict:
        return {
            "title": "天机v9.1 对话录入基础设施 全局辐射影响报告",
            "generated_at": time.time(),
            "total_modules_analyzed": len(GLOBAL_IMPACT_MATRIX),
            "tier_summary": self.get_tier_summary(),
            "dimension_coverage": self.get_dimension_coverage(),
            "top_10_by_impact": [m.to_dict() for m in self.get_top_n(10)],
            "evolution_candidates": len(self.get_evolution_candidates()),
            "priority_order": self.get_priority_evolution_order()[:15],
            "weight_formula": "CompositeScore = DIW*0.40 + DFW*0.30 + EU*0.20 + SC*0.10",
        }

    def get_full_evolution_specs(self) -> List[ModuleEvolutionSpec]:
        """从GLOBAL_IMPACT_MATRIX导出完整的进化规格表，含工时估算和风险等级"""
        specs = []
        for m in GLOBAL_IMPACT_MATRIX:
            effort, risk = _estimate_effort_and_risk(m)
            standards, consumers = _map_standards_and_consumers(m)
            specs.append(
                ModuleEvolutionSpec(
                    module_name=m.module_name,
                    tier=m.tier,
                    composite=m.composite,
                    evolution_targets=m.evolution_targets,
                    estimated_effort_hours=effort,
                    risk_level=risk,
                    standard_alignment=standards,
                    consumer_impacts=consumers,
                )
            )
        return sorted(specs, key=lambda s: s.composite, reverse=True)

    def get_standard_gap_report(self) -> Dict:
        """生成国际标准对标差距报告"""
        total_gap_score = sum(g.current_support for g in STANDARD_GAPS.values())
        return {
            "total_standards": len(STANDARD_GAPS),
            "avg_support": round(total_gap_score / len(STANDARD_GAPS), 2),
            "p1_gaps": [
                g.to_dict() for g in STANDARD_GAPS.values() if g.priority == "P1"
            ],
            "p2_gaps": [
                g.to_dict() for g in STANDARD_GAPS.values() if g.priority == "P2"
            ],
            "top_gap": max(
                STANDARD_GAPS.values(), key=lambda g: 1.0 - g.current_support
            ).to_dict(),
        }

    def get_consumer_demand_report(self) -> Dict:
        """生成下游消费者需求汇总报告"""
        demands = list(CONSUMER_DEMANDS.values())
        return {
            "total_consumers": len(demands),
            "avg_demand": round(sum(d.demand_score for d in demands) / len(demands), 2),
            "high_demand": [d.to_dict() for d in demands if d.demand_score >= 0.8],
            "field_demand_count": _aggregate_field_demand(demands),
            "field_priority_order": _compute_field_priority(demands),
        }

    def get_tier_evolution_schedule(self, turn_count: int = 0) -> Dict:
        """基于对话轮数的动态进化评估调度"""

        def should_evaluate(tier: ImpactTier, turns: int) -> bool:
            intervals = {
                ImpactTier.S: 10,
                ImpactTier.A: 50,
                ImpactTier.B: 200,
                ImpactTier.C: 1000,
                ImpactTier.D: -1,
            }
            interval = intervals.get(tier, 1000)
            return interval > 0 and turns % interval == 0

        return {
            "current_turn": turn_count,
            "next_evaluations": {
                tier.value: {
                    "interval": {"S": 10, "A": 50, "B": 200, "C": 1000, "D": -1}[
                        tier.value
                    ],
                    "turns_until_next": _turns_until_next(tier, turn_count),
                    "modules_count": len(self.get_by_tier(tier)),
                    "should_evaluate_now": should_evaluate(tier, turn_count),
                }
                for tier in ImpactTier
            },
        }

    def generate_adaptive_strategy(
        self, active_consumers: List[str] = None, system_load: float = 0.5
    ) -> Dict:
        """生成适应性录入策略建议"""
        if active_consumers is None:
            active_consumers = list(CONSUMER_DEMANDS.keys())

        required_fields: Set[str] = set()
        preferred_layer_votes: Dict[str, float] = {}
        max_latency_ms = float("inf")

        for consumer_name in active_consumers:
            demand = CONSUMER_DEMANDS.get(consumer_name)
            if not demand:
                continue
            for f in demand.required_fields:
                required_fields.add(f)
            layer = "episodic"
            preferred_layer_votes[layer] = (
                preferred_layer_votes.get(layer, 0.0) + demand.demand_score
            )
            max_latency_ms = min(max_latency_ms, demand.max_tolerable_latency_ms)

        preferred_layer = (
            max(preferred_layer_votes, key=preferred_layer_votes.get)
            if preferred_layer_votes
            else "episodic"
        )

        if system_load > 0.8:
            required_fields = {
                f
                for f in required_fields
                if f
                in {
                    "session_id",
                    "timestamp",
                    "user_input",
                    "ai_response",
                    "content_hash",
                }
            }
        elif system_load > 0.5:
            required_fields = {
                f for f in required_fields if f not in {"prov_trace", "fair_metadata"}
            }

        return {
            "active_consumers": active_consumers,
            "system_load": system_load,
            "required_fields": sorted(required_fields),
            "preferred_layer": preferred_layer,
            "max_tolerable_latency_ms": max_latency_ms,
            "strategy": "degraded_core_only"
            if system_load > 0.8
            else "balanced_essential"
            if system_load > 0.5
            else "full_fidelity",
        }

    def generate_comprehensive_report(self) -> Dict:
        """生成综合分析报告"""
        report = self.generate_report()
        report.update(
            {
                "version": "2.0.0",
                "standard_gap_analysis": self.get_standard_gap_report(),
                "consumer_demand_analysis": self.get_consumer_demand_report(),
                "evolution_schedule": self.get_tier_evolution_schedule(),
                "full_evolution_specs": [
                    s.to_dict() for s in self.get_full_evolution_specs()
                ],
                "adaptive_strategy_default": self.generate_adaptive_strategy(),
                "weight_sub_dimensions": {
                    "diw": DIW_SUB_WEIGHTS,
                    "dfw": DFW_SUB_WEIGHTS,
                    "eu": EU_SUB_WEIGHTS,
                    "sc": SC_SUB_WEIGHTS,
                },
                "sub_weight_calibration": _generate_calibration_examples(),
            }
        )
        return report


def _estimate_effort_and_risk(m: ModuleImpact) -> Tuple[float, str]:
    """根据module影响评估估算工时和风险等级"""
    target_count = len(m.evolution_targets)
    if m.tier == ImpactTier.S:
        effort = target_count * 3.0
        risk = "high"
    elif m.tier == ImpactTier.A:
        effort = target_count * 1.5
        risk = "medium"
    elif m.tier == ImpactTier.B:
        effort = target_count * 0.8
        risk = "low"
    else:
        effort = target_count * 0.3
        risk = "low"
    return round(effort, 1), risk


def _map_standards_and_consumers(m: ModuleImpact) -> Tuple[List[str], List[str]]:
    """将模块映射到相关标准和消费者"""
    standards = []
    consumers = []
    name_lower = m.module_name.lower()
    target_text = " ".join(m.evolution_targets).lower()

    if "otel_genai" in name_lower or "mcp" in name_lower or "agent" in name_lower:
        standards.append("otel_genai_agent")
    if "mcp" in name_lower or "tool" in target_text:
        standards.append("otel_genai_tool")
    if "vcon" in target_text or "record" in name_lower:
        standards.append("vcon_container")
    if "iso" in target_text or "dialogue" in target_text:
        standards.append("iso_daml")
    if "agent" in name_lower or "tvp" in name_lower:
        standards.append("aos_instrument")

    if "engine" in name_lower or "store" in name_lower:
        consumers.append("memory_engine")
    if "quality" in name_lower or "gate" in name_lower:
        consumers.append("quality_gate")
    if "learn" in name_lower or "evol" in name_lower:
        consumers.append("learning")
    if "knowledge" in name_lower or "kg_" in name_lower:
        consumers.append("knowledge")
    if "agent" in name_lower or "schedule" in name_lower:
        consumers.append("agent_schedule")
    if "governance" in name_lower or "audit" in name_lower:
        consumers.append("governance")

    return standards, consumers


def _aggregate_field_demand(demands: List[ConsumerDemand]) -> Dict[str, float]:
    """聚合所有消费者对每个字段的需求分数"""
    field_scores: Dict[str, float] = {}
    for d in demands:
        for f in d.required_fields:
            field_scores[f] = field_scores.get(f, 0.0) + d.demand_score
    return {
        f: round(s, 2)
        for f, s in sorted(field_scores.items(), key=lambda x: x[1], reverse=True)
    }


def _compute_field_priority(demands: List[ConsumerDemand]) -> List[Dict]:
    """计算字段优先级排序（下游需求驱动）"""
    aggregated = _aggregate_field_demand(demands)
    max_score = max(aggregated.values()) if aggregated else 1.0
    return [
        {"field": f, "aggregate_demand": s, "priority_score": round(s / max_score, 2)}
        for f, s in sorted(aggregated.items(), key=lambda x: x[1], reverse=True)
    ]


def _turns_until_next(tier: ImpactTier, current_turns: int) -> int:
    intervals = {
        ImpactTier.S: 10,
        ImpactTier.A: 50,
        ImpactTier.B: 200,
        ImpactTier.C: 1000,
        ImpactTier.D: -1,
    }
    interval = intervals.get(tier, 1000)
    if interval < 0:
        return -1
    remainder = current_turns % interval
    return interval - remainder if remainder > 0 else 0


def _generate_calibration_examples() -> List[Dict]:
    """生成四维权重校准示例"""
    examples = []
    modules = sorted(GLOBAL_IMPACT_MATRIX, key=lambda m: m.composite, reverse=True)

    for m in modules[:5]:
        diw_subs = [
            SubWeightDetail(
                "field_dependency",
                round(m.diw * 0.35, 3),
                f"{m.module_name}对ConversationRecord字段的直接依赖",
            ),
            SubWeightDetail(
                "api_dependency",
                round(m.diw * 0.25, 3),
                f"{m.module_name}通过API消费录入数据",
            ),
            SubWeightDetail(
                "behavior_dependency",
                round(m.diw * 0.25, 3),
                f"录入行为变化直接影响{m.module_name}逻辑",
            ),
            SubWeightDetail(
                "lifecycle_dependency",
                round(m.diw * 0.15, 3),
                f"{m.module_name}生命周期与录入耦合",
            ),
        ]
        dfw_subs = [
            SubWeightDetail(
                "data_through_rate",
                round(m.dfw * 0.40, 3),
                f"录入数据流经{m.module_name}的比例",
            ),
            SubWeightDetail(
                "data_quality_impact",
                round(m.dfw * 0.30, 3),
                f"录入质量对{m.module_name}产出的影响",
            ),
            SubWeightDetail(
                "data_path_criticality",
                round(m.dfw * 0.30, 3),
                f"数据路径上{m.module_name}的关键度",
            ),
        ]
        eu_subs = [
            SubWeightDetail(
                "gap_severity",
                round(m.eu * 0.35, 3),
                f"{m.module_name}当前与理想状态的差距",
            ),
            SubWeightDetail(
                "alignment_urgency",
                round(m.eu * 0.30, 3),
                f"思考对齐对{m.module_name}的紧迫性",
            ),
            SubWeightDetail(
                "consumer_demand_pressure",
                round(m.eu * 0.20, 3),
                f"下游消费者对{m.module_name}的需求压力",
            ),
            SubWeightDetail(
                "standard_gap",
                round(m.eu * 0.15, 3),
                f"国际标准对{m.module_name}的对标差距",
            ),
        ]
        sc_subs = [
            SubWeightDetail(
                "availability_requirement",
                round(m.sc * 0.35, 3),
                f"{m.module_name}的可用性要求",
            ),
            SubWeightDetail(
                "security_impact", round(m.sc * 0.25, 3), f"{m.module_name}的安全影响面"
            ),
            SubWeightDetail(
                "recoverability_impact",
                round(m.sc * 0.25, 3),
                f"{m.module_name}故障恢复难度",
            ),
            SubWeightDetail(
                "dependency_count",
                round(m.sc * 0.15, 3),
                f"依赖{m.module_name}的下游模块数",
            ),
        ]
        wb = WeightBreakdown(
            diw_value=m.diw,
            diw_subs=diw_subs,
            dfw_value=m.dfw,
            dfw_subs=dfw_subs,
            eu_value=m.eu,
            eu_subs=eu_subs,
            sc_value=m.sc,
            sc_subs=sc_subs,
        )
        examples.append(
            {
                "module": m.module_name,
                "tier": m.tier.value,
                "breakdown": wb.to_calibration_report(),
            }
        )
    return examples


def get_global_impact_matrix() -> List[ModuleImpact]:
    return GLOBAL_IMPACT_MATRIX


def get_top_impact_modules(n: int = 5) -> List[ModuleImpact]:
    return sorted(GLOBAL_IMPACT_MATRIX, key=lambda m: m.composite, reverse=True)[:n]


def get_standard_gaps() -> Dict[str, StandardGap]:
    return STANDARD_GAPS


def get_consumer_demands() -> Dict[str, ConsumerDemand]:
    return CONSUMER_DEMANDS


def get_analyzer() -> GlobalImpactAnalyzer:
    return GlobalImpactAnalyzer()


__all__ = ["GlobalImpactAnalyzer"]
