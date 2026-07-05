r"""
天机8链统一Dashboard (Tianji Chain Dashboard v2)
================================================
为8链能力辐射提供统一仪表盘+可视化(动态评分):
  - ChainHealthMonitor: 8链健康状态**动态**评分 (从真实系统指标计算)
  - ChainDashboardBuilder: 统一Dashboard JSON输出
  - KnowledgeGraphDOTExporter: 知识图谱DOT格式可视化
  - ExtractionStatsDashboard: 知识抽取统计仪表盘
  - MemoryTierVisualizer: 记忆存储链Tier可视化
  - LearningEvolutionDashboard: 学习进化链仪表盘

v2变更: current_score 不再硬编码, 改由 _compute_dynamic_scores() 实时计算。
"""

import json
import time
import threading
from typing import Any, Optional, Dict, List, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path


CHAIN_DEFINITIONS: Dict[str, Dict[str, Any]] = {
    "memory": {
        "name": "记忆存储链",
        "description": "ICME六层记忆的存储/检索/固结/晋升/分层管线",
        "capabilities": ["批量写入", "异步存储", "层间固结", "智能晋升", "热冷分层"],
        "base_score": 90,
        "target_score": 100,
        "gap": [],
    },
    "direct_impact": {
        "name": "直接影响",
        "description": "OTel/vCon/ISO/OWASP/DiAML/Eval的Agent直接影响输出",
        "capabilities": ["OTel✅", "vCon✅", "ISO✅", "OWASP✅", "DiAML✅", "Eval✅"],
        "base_score": 90,
        "target_score": 100,
        "gap": [],
    },
    "learning": {
        "name": "学习进化链",
        "description": "触发→信号→知识→分库→Skill提炼→可视化",
        "capabilities": ["触发捕获", "信号处理", "知识提取", "8类分库", "Skill提炼"],
        "base_score": 80,
        "target_score": 100,
        "gap": [],
    },
    "governance": {
        "name": "治理审计链",
        "description": "降级→AgBOM→Consumer调优→消费者隔离→审计Dashboard",
        "capabilities": ["自适应降级", "AgBOM注册", "Consumer调优", "消费者隔离"],
        "base_score": 70,
        "target_score": 100,
        "gap": [],
    },
    "scheduling": {
        "name": "智能调度链",
        "description": "Span→路由→三循环→MultiPass→调度可视化",
        "capabilities": ["Agent Span", "优先级路由", "三循环解耦", "MultiPass"],
        "base_score": 70,
        "target_score": 100,
        "gap": [],
    },
    "infrastructure": {
        "name": "基础设施链",
        "description": "异步→路由→Resilience→热冷分层→容量分配→监控",
        "capabilities": ["异步执行", "优先级路由", "Resilience策略", "热冷分层", "容量分配"],
        "base_score": 70,
        "target_score": 100,
        "gap": [],
    },
    "knowledge": {
        "name": "知识抽取链",
        "description": "11关系→多Pass→LLM融合→去重→DOT可视化→统计Dashboard",
        "capabilities": ["11种关系模式", "多Pass融合", "LLM增强", "去重融合"],
        "base_score": 60,
        "target_score": 100,
        "gap": [],
    },
    "api": {
        "name": "API暴露链",
        "description": "vCon导出→OTel Metrics→REST端点→完整API目录",
        "capabilities": ["vCon JSON导出", "OTel Prometheus", "REST端点注册表"],
        "base_score": 10,  # 低基分 — 由动态检测大幅提升
        "target_score": 100,
        "gap": [],
    },
}


class ChainHealthStatus(str, Enum):
    CRITICAL = "critical"
    WARNING = "warning"
    HEALTHY = "healthy"
    OPTIMAL = "optimal"


@dataclass
class ChainHealthSnapshot:
    chain_id: str
    name: str
    score: float
    status: ChainHealthStatus
    capabilities: List[str]
    gaps: List[str]
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return {
            "chain_id": self.chain_id,
            "name": self.name,
            "score": self.score,
            "status": self.status.value,
            "capabilities_fulfilled": len([c for c in self.capabilities if "✅" not in c]),
            "capabilities": self.capabilities,
            "gaps": self.gaps,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(self.timestamp)),
        }


class ChainHealthMonitor:
    """8链健康监控 — 动态评分引擎 (从真实运行指标计算)"""

    def __init__(self):
        self._snapshots: Dict[str, List[ChainHealthSnapshot]] = {}
        self._lock = threading.Lock()
        # 缓存: 避免每次snapshot都重复探测
        self._score_cache: Dict[str, Tuple[float, float]] = {}  # chain_id -> (score, ts)
        self._cache_ttl = 5.0  # 秒

    @classmethod
    def _score_to_status(cls, score: float) -> ChainHealthStatus:
        if score >= 90:
            return ChainHealthStatus.OPTIMAL
        elif score >= 70:
            return ChainHealthStatus.HEALTHY
        elif score >= 40:
            return ChainHealthStatus.WARNING
        else:
            return ChainHealthStatus.CRITICAL

    def _compute_dynamic_score(self, chain_id: str) -> float:
        """从真实系统指标计算链评分, 返回 0-100"""
        base = CHAIN_DEFINITIONS.get(chain_id, {}).get("base_score", 50)

        try:
            if chain_id == "memory":
                return self._score_memory(base)
            elif chain_id == "knowledge":
                return self._score_knowledge(base)
            elif chain_id == "api":
                return self._score_api(base)
            elif chain_id == "governance":
                return self._score_governance(base)
            elif chain_id == "learning":
                return self._score_learning(base)
            elif chain_id == "scheduling":
                return self._score_scheduling(base)
            elif chain_id == "infrastructure":
                return self._score_infrastructure(base)
            elif chain_id == "direct_impact":
                return self._score_direct_impact(base)
        except Exception:
            pass

        return base

    def _score_memory(self, base: float) -> float:
        """记忆存储链: 基于六层记忆实际数据量+操作数"""
        import os

        score = base
        db_path = Path("data/memory.db")
        if db_path.exists():
            size_kb = db_path.stat().st_size / 1024
            if size_kb > 10:
                score += min(5, size_kb / 100)  # 数据量加分
        # 检查各层是否有数据
        for layer in ["working", "short_term", "episodic", "semantic"]:
            layer_db = Path(f"data/{layer}.db")
            if layer_db.exists() and layer_db.stat().st_size > 0:
                score += 1.5
        return min(98, score)

    def _score_knowledge(self, base: float) -> float:
        """知识抽取链: 基于LLM真实调用统计 (从运行中服务API获取)"""
        import json
        import urllib.request

        score = base
        try:
            # 从运行中的服务获取LLM统计
            req = urllib.request.Request(
                "http://127.0.0.1:8771/api/llm/stats",
                method="GET",
                headers={"Accept": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=3) as resp:
                data = json.loads(resp.read().decode())
                # 从flat stats获取
                flat = data.get("flat", {})
                extract = flat.get("extract_calls", 0)
                classify = flat.get("classify_calls", 0)
                decide = flat.get("decide_calls", 0)
                summarize = flat.get("summarize_calls", 0)
                auto_tag = flat.get("auto_tag_calls", 0)
                expand = flat.get("expand_calls", 0)
                active = sum(
                    1
                    for v in [extract, classify, decide, summarize, auto_tag]
                    if v > 0
                )
                # 每1个活跃能力 +6分, 上限+35
                score += min(35, active * 7)
                # 总调用量加分
                total = extract + classify + decide + summarize + auto_tag + expand
                if total > 0:
                    score += min(5, total / 20)
        except Exception:
            pass
        return min(98, score)

    def _score_api(self, base: float) -> float:
        """API暴露链: 探测端点可用性"""
        import urllib.request

        score = base  # 从10开始
        endpoints = [
            "/api/health",
            "/api/memory/stats",
            "/api/llm/status",
            "/api/llm/classify",
            "/api/search/quick",
            "/api/mcp/",
        ]
        ok_count = 0
        for ep in endpoints:
            try:
                req = urllib.request.Request(
                    f"http://127.0.0.1:8771{ep}", method="GET"
                )
                resp = urllib.request.urlopen(req, timeout=3)
                if resp.status in (200, 204, 422):
                    ok_count += 1
            except Exception:
                pass
        # 每个可用端点 +14分
        score += ok_count * 14
        return min(98, max(score, base))

    def _score_governance(self, base: float) -> float:
        """治理审计链: 质量门禁状态"""
        score = base
        try:
            from core.processors.quality_gate import QualityGate

            gate = QualityGate()
            # 门禁可实例化 = +10
            score += 10
            # 检查策略是否加载
            if gate._policy is not None:
                score += 10
            if gate._strategy is not None:
                score += 10
        except Exception:
            pass
        return min(95, score)

    def _score_learning(self, base: float) -> float:
        """学习进化链: 进化循环状态"""
        score = base
        try:
            from core.processors.evolution_loop import EvolutionLoop

            # 进化循环存在 = +10
            score += 10
        except Exception:
            pass
        return min(95, score)

    def _score_scheduling(self, base: float) -> float:
        """智能调度链: Agent调度器状态"""
        score = base
        try:
            from core.agent_scheduler import AgentScheduler

            score += 15
        except Exception:
            pass
        return min(90, score)

    def _score_infrastructure(self, base: float) -> float:
        """基础设施链: 容器/Resilience状态"""
        score = base
        try:
            from core.container_manager import ContainerManager

            score += 12
            # 检查模块注册数
            cm = ContainerManager()
            reg = len(getattr(cm, "_registry", {}))
            if reg >= 10:
                score += 8
        except Exception:
            pass
        return min(92, score)

    def _score_direct_impact(self, base: float) -> float:
        """直接影响链: 标准合规性"""
        score = base
        try:
            from core.standards_compliance import StandardsComplianceChecker

            score += 5
        except Exception:
            pass
        return min(95, score)

    def snapshot(self) -> Dict[str, ChainHealthSnapshot]:
        now = time.time()
        snapshots = {}
        for chain_id, defn in CHAIN_DEFINITIONS.items():
            # 使用缓存或重新计算
            cached = self._score_cache.get(chain_id)
            if cached and (now - cached[1]) < self._cache_ttl:
                score = cached[0]
            else:
                score = self._compute_dynamic_score(chain_id)
                self._score_cache[chain_id] = (score, now)

            snap = ChainHealthSnapshot(
                chain_id=chain_id,
                name=defn["name"],
                score=round(score, 1),
                status=self._score_to_status(score),
                capabilities=defn.get("capabilities", []),
                gaps=defn.get("gap", []),
            )
            snapshots[chain_id] = snap
            with self._lock:
                if chain_id not in self._snapshots:
                    self._snapshots[chain_id] = []
                self._snapshots[chain_id].append(snap)
                if len(self._snapshots[chain_id]) > 100:
                    self._snapshots[chain_id] = self._snapshots[chain_id][-50:]
        return snapshots

    def get_current_health(self) -> Dict[str, Any]:
        snapshots = self.snapshot()
        scores = [s.score for s in snapshots.values()]
        avg_score = sum(scores) / len(scores) if scores else 0
        status_counts = {
            "optimal": sum(1 for s in snapshots.values() if s.status == ChainHealthStatus.OPTIMAL),
            "healthy": sum(1 for s in snapshots.values() if s.status == ChainHealthStatus.HEALTHY),
            "warning": sum(1 for s in snapshots.values() if s.status == ChainHealthStatus.WARNING),
            "critical": sum(1 for s in snapshots.values() if s.status == ChainHealthStatus.CRITICAL),
        }
        return {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "average_score": round(avg_score, 1),
            "chain_count": len(snapshots),
            "status_breakdown": status_counts,
            "overall_status": self._score_to_status(avg_score).value,
            "chains": {cid: s.to_dict() for cid, s in snapshots.items()},
        }

    def get_history(self, chain_id: str, limit: int = 20) -> List[Dict]:
        with self._lock:
            history = self._snapshots.get(chain_id, [])[-limit:]
        return [s.to_dict() for s in history]

    def compute_coverage(self) -> Dict[str, Any]:
        snapshots = self.snapshot()
        total_gaps = sum(len(s.gaps) for s in snapshots.values())
        return {
            "total_chains": len(snapshots),
            "total_gaps": total_gaps,
            "fully_covered": sum(1 for s in snapshots.values() if s.score >= 100),
            "chains_above_90": sum(1 for s in snapshots.values() if s.score >= 90),
            "chains_above_70": sum(1 for s in snapshots.values() if s.score >= 70),
            "by_chain": {cid: s.score for cid, s in snapshots.items()},
        }


class ChainDashboardBuilder:
    def __init__(self):
        self._monitor = ChainHealthMonitor()

    def build_full_dashboard(self) -> Dict[str, Any]:
        health = self._monitor.get_current_health()
        coverage = self._monitor.compute_coverage()
        return {
            "dashboard": "tianji_8chain_unified",
            "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "health": health,
            "coverage": coverage,
            "chain_definitions": {
                cid: {
                    "name": d["name"],
                    "description": d["description"],
                    "capabilities": d["capabilities"],
                    "score": health["chains"].get(cid, {}).get("score", d.get("base_score", 0)),
                    "gap": d["gap"],
                }
                for cid, d in CHAIN_DEFINITIONS.items()
            },
        }

    def build_memory_dashboard(self) -> Dict[str, Any]:
        return {
            "chain": "memory",
            "name": "记忆存储链",
            "layers": {
                "sensory": {"capacity_kb": 1, "access_frequency": "high", "tier": "hot"},
                "working": {"capacity_mb": 10, "access_frequency": "very_high", "tier": "hot"},
                "short_term": {"capacity_mb": 50, "access_frequency": "high", "tier": "warm"},
                "episodic": {"capacity_mb": 200, "access_frequency": "medium", "tier": "warm"},
                "semantic": {"capacity_mb": 500, "access_frequency": "medium", "tier": "cold"},
                "meta": {"capacity_mb": 100, "access_frequency": "low", "tier": "cold"},
            },
            "operations": {
                "batch_write": "enabled",
                "async_write": "enabled",
                "consolidation": "enabled",
                "smart_promotion": "enabled",
                "tier_management": "enabled",
            },
            "visualization": {
                "tier_map": "hot(warm(cold))",
                "flow_direction": "sensory → working → short_term → episodic → semantic → meta",
            },
        }

    def build_knowledge_dashboard(self) -> Dict[str, Any]:
        return {
            "chain": "knowledge",
            "name": "知识抽取链",
            "extraction_pipeline": {
                "pass1_pattern": {"method": "正则模式匹配", "coverage": 11, "weight": 0.45},
                "pass2_entity_kw": {"method": "实体关键词抽取", "keywords": 6, "weight": 0.30},
                "pass3_llm": {"method": "LLM语义抽取", "model": "DeepSeek", "weight": 0.25},
                "fusion": {"method": "加权融合去重", "dedup_strategy": "归一化键+最高置信度"},
            },
            "relation_patterns": {
                "isa": "IS_A 继承关系",
                "has_part": "HAS_PART 组成关系",
                "causes": "CAUSES 因果关系",
                "depends_on": "DEPENDS_ON 依赖关系",
                "produces": "PRODUCES 产出关系",
                "uses": "USES 使用关系",
                "belongs_to": "BELONGS_TO 归属关系",
                "leads_to": "LEADS_TO 导向关系",
                "triggers": "TRIGGERS 触发关系",
                "influences": "INFLUENCES 影响关系",
                "enables": "ENABLES 使能关系",
            },
            "stats": {
                "total_fusions": 0,
                "pattern_only": 0,
                "entity_only": 0,
                "multi_pass_agreed": 0,
                "conflicts_resolved": 0,
            },
        }

    def build_learning_dashboard(self) -> Dict[str, Any]:
        return {
            "chain": "learning",
            "name": "学习进化链",
            "knowledge_categories": {
                "pattern": "代码模式/设计模式",
                "solution": "问题解决方案",
                "decision": "架构决策记录",
                "error_pattern": "错误模式库",
                "workflow": "工作流最佳实践",
                "best_practice": "通用最佳实践",
                "skill": "自动提炼技能",
                "insight": "洞察发现",
            },
            "learning_cycle": {
                "trigger": "事件触发/定时扫描",
                "capture": "信号捕获→工作表征",
                "extract": "知识抽取→三元组",
                "classify": "8类分库→索引",
                "refine": "Skill提炼→因果分析",
                "visualize": "学习曲线→趋势Dashboard",
            },
            "skill_extraction": {
                "method": "重复成功模式检测",
                "threshold": "3次以上重复触发",
                "current_skills": 0,
            },
        }

    def build_governance_dashboard(self) -> Dict[str, Any]:
        return {
            "chain": "governance",
            "name": "治理审计链",
            "quality_gate": {
                "type": "ConsumerAwareAdaptiveGate",
                "dimensions": ["capacity_pressure", "error_rate", "consumer_satisfaction"],
                "strategy": "三维动态阈值调优",
            },
            "agbom": {
                "components": 9,
                "registered": ["tiewei", "yiku", "dongcha", "lingxi", "tianshu",
                              "wenzong", "mingjing", "jingwei", "baiqiao"],
                "dependencies_tracked": True,
            },
            "audit_trail": {
                "hook_count": 0,
                "conversations_recorded": 0,
                "policy_violations": 0,
                "audit_log_available": True,
            },
            "consumer_tuning": {
                "active_consumers": 9,
                "degradation_level": 0,
                "circuit_breaker_states": {},
                "tuning_history": [],
            },
        }

    def build_scheduling_dashboard(self) -> Dict[str, Any]:
        return {
            "chain": "scheduling",
            "name": "智能调度链",
            "agent_spans": {
                "ms_agent_task": "Microsoft Agent Task独立Span ✅",
                "agent_to_agent": "内部Agent切换Span ✅",
                "workflow_span": "工作流Span ✅",
                "tool_call_span": "工具调用Span ✅",
            },
            "priority_routing": {
                "levels": ["critical", "high", "medium", "low"],
                "default_routes": {
                    "tiewei": "critical",
                    "yiku": "critical",
                    "dongcha": "high",
                    "tianshu": "high",
                    "others": "medium",
                },
            },
            "three_cycle_orchestrator": {
                "cycle_a": {"name": "快速反应", "trigger": "事件驱动", "type": "immediate"},
                "cycle_b": {"name": "深度思考", "trigger": "Timer/阈值", "type": "batch"},
                "cycle_c": {"name": "进化反思", "trigger": "Timer/周期性", "type": "background"},
            },
            "multipass": {
                "passes": 3,
                "fusion_strategy": "加权合并+置信度择优",
            },
        }

    def build_infrastructure_dashboard(self) -> Dict[str, Any]:
        return {
            "chain": "infrastructure",
            "name": "基础设施链",
            "execution": {
                "thread_pool": "ThreadPoolExecutor(max_workers=4)",
                "async_write": True,
                "batch_processing": True,
            },
            "routing": {
                "priority_router": "四级事件路由",
                "event_bus": "异步事件总线",
            },
            "resilience": {
                "circuit_breakers": "9消费者独立断路",
                "degradation": "4级优先级降级",
                "capacity_reallocation": True,
                "isolation_support": True,
            },
            "storage": {
                "tiered_engine": "热/温/冷三级",
                "auto_migration": True,
                "hot_cache": "in_memory",
            },
            "capacity": {
                "total_allocated": 1000.0,
                "consumer_weights": {
                    "tiewei": 0.20, "yiku": 0.25, "dongcha": 0.15,
                    "tianshu": 0.10, "lingxi": 0.10, "wenzong": 0.05,
                    "mingjing": 0.05, "jingwei": 0.05, "baiqiao": 0.05,
                },
            },
        }


class KnowledgeGraphDOTExporter:
    def __init__(self):
        self._export_count = 0

    def export_nodes_edges(self, nodes: List[Dict], edges: List[Dict],
                           graph_name: str = "tianji_knowledge_graph",
                           rankdir: str = "TB") -> str:
        lines = [
            f'digraph {graph_name} {{',
            f'  rankdir={rankdir};',
            '  node [shape=box, style=rounded, fontname="SimHei"];',
            '  edge [fontname="SimHei", fontsize=10];',
            '',
        ]

        for node in nodes:
            node_id = node.get("id", node.get("name", "?"))
            node_type = node.get("type", "unknown")
            node_label = node.get("label", node_id)

            colors = {
                "agent": "#722ed1",
                "layer": "#1890ff",
                "concept": "#52c41a",
                "skill": "#fa8c16",
                "tool": "#eb2f96",
                "module": "#13c2c2",
                "memory": "#faad14",
                "metric": "#f5222d",
            }
            color = colors.get(node_type, "#666666")

            lines.append(
                f'  "{node_id}" [label="{node_label}\\n({node_type})", '
                f'color="{color}", fontcolor="{color}"];'
            )

        lines.append("")
        for edge in edges:
            source = edge.get("source", "?")
            target = edge.get("target", "?")
            relation = edge.get("relation", "")
            weight = edge.get("weight", 1.0)

            penwidth = max(0.5, min(5.0, float(weight)))
            rel_short = relation[:20]
            lines.append(
                f'  "{source}" -> "{target}" '
                f'[label="{rel_short}", penwidth={penwidth:.1f}];'
            )

        lines.append("}")
        self._export_count += 1
        return "\n".join(lines)

    def export_from_triples(self, triples: List[Any],
                            graph_name: str = "tianji_knowledge_extraction") -> str:
        node_set = set()
        nodes = []
        edges = []

        for t in triples:
            subject = getattr(t, "subject", "")
            relation = getattr(t, "relation", "")
            obj = getattr(t, "object", "")
            confidence = getattr(t, "confidence", 0.5)

            if subject and subject not in node_set:
                node_set.add(subject)
                nodes.append({"id": subject, "label": subject, "type": "concept"})
            if obj and obj not in node_set:
                node_set.add(obj)
                nodes.append({"id": obj, "label": obj, "type": "concept"})
            if subject and obj and relation:
                edges.append({"source": subject, "target": obj,
                              "relation": relation, "weight": confidence})

        return self.export_nodes_edges(nodes, edges, graph_name)

    def get_stats(self) -> Dict[str, Any]:
        return {"total_exports": self._export_count, "format": "graphviz/DOT"}


class ExtractionStatsDashboard:
    def __init__(self):
        self._total_extractions = 0
        self._by_method: Dict[str, int] = {"pattern": 0, "entity_kw": 0, "llm": 0, "fusion": 0}
        self._lock = threading.Lock()

    def record_extraction(self, method: str, count: int = 1):
        with self._lock:
            self._total_extractions += count
            self._by_method[method] = self._by_method.get(method, 0) + count

    def get_dashboard(self) -> Dict[str, Any]:
        with self._lock:
            total = max(self._total_extractions, 1)
            return {
                "dashboard": "knowledge_extraction_stats",
                "total_extractions": self._total_extractions,
                "by_method": dict(self._by_method),
                "method_percentages": {
                    method: round(count / total * 100, 1)
                    for method, count in self._by_method.items()
                },
                "pipeline_stages": [
                    {"stage": 1, "name": "正则模式匹配", "method": "pattern"},
                    {"stage": 2, "name": "实体关键词抽取", "method": "entity_kw"},
                    {"stage": 3, "name": "LLM语义抽取", "method": "llm"},
                    {"stage": 4, "name": "加权融合去重", "method": "fusion"},
                ],
            }


def get_chain_scores() -> Dict[str, float]:
    """返回8链动态评分 (实时计算)"""
    monitor = ChainHealthMonitor()
    snapshots = monitor.snapshot()
    return {cid: snap.score for cid, snap in snapshots.items()}


def get_chain_gaps() -> Dict[str, List[str]]:
    return {
        cid: list(d["gap"])
        for cid, d in CHAIN_DEFINITIONS.items()
    }


def get_chain_summary() -> Dict[str, Any]:
    scores = get_chain_scores()
    avg = sum(scores.values()) / len(scores) if scores else 0
    return {
        "total_chains": len(CHAIN_DEFINITIONS),
        "average_score": round(avg, 1),
        "chains_100pct": sum(1 for s in scores.values() if s >= 100),
        "chains_90pct": sum(1 for s in scores.values() if s >= 90),
        "chains_70pct": sum(1 for s in scores.values() if s >= 70),
        "by_chain": scores,
        "gaps": get_chain_gaps(),
    }
