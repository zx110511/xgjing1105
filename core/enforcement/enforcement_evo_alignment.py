# -*- coding: utf-8-sig -*-
"""执行进化 — 对齐+消费者画像

从 enforcement_evolution.py 拆分 (SSS-PhaseB)
"""

import time
import json
import threading
import logging
from pathlib import Path
from typing import Any, Optional, Dict, List, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from collections import defaultdict
try:
    from collections import Counter
except ImportError:
    Counter = None
from .enforcement_evo_tracker import EnforcementTracker
from .enforcement_evo_engine import EnforcementEvolution

class EvolutionTarget(Enum):
    """需要进化的10大对象清单"""
    CONVERSATION_RECORD = "conversation_record_fields"
    CLASSIFIER = "_classify_conversation_weights"
    ISO_ANNOTATOR = "_annotate_iso_dialogue_acts_rules"
    NUDGE_DECIDE = "_nudge_decide_thresholds"
    TOKEN_ESTIMATOR = "_track_token_economy_formula"
    FAIR_TEMPLATE = "fair_metadata_template"
    QUALITY_GATE = "quality_gate_thresholds"
    MCP_INTERCEPT = "mcp_intercept_policy"
    TVP_DETECTOR = "_detect_agent_switches_patterns"
    REGISTRY_CACHE = "conversation_registry_cache"


EVOLUTION_TARGETS = {
    EvolutionTarget.CONVERSATION_RECORD: {"priority": "P0", "frequency": "per_sprint",
                                           "parent": "ConversationRecord",
                                           "描述": "对话记录字段随需求动态扩展", "file": "core/enforcement_hook.py"},
    EvolutionTarget.CLASSIFIER: {"priority": "P1", "frequency": "per_100_turns",
                                  "parent": "_classify_conversation",
                                  "描述": "关键词权重随对话模式分布自适应", "file": "core/enforcement_hook.py"},
    EvolutionTarget.ISO_ANNOTATOR: {"priority": "P1", "frequency": "per_200_turns",
                                     "parent": "_annotate_iso_dialogue_acts",
                                     "描述": "ISO 24617-2标注规则按实际对话行为分布校准", "file": "core/enforcement_hook.py"},
    EvolutionTarget.NUDGE_DECIDE: {"priority": "P0", "frequency": "per_50_turns",
                                    "parent": "_nudge_decide",
                                    "描述": "记录决策阈值自适应（layer/priority判断）", "file": "core/enforcement_hook.py"},
    EvolutionTarget.TOKEN_ESTIMATOR: {"priority": "P2", "frequency": "per_month",
                                       "parent": "_track_token_economy",
                                       "描述": "Token价格公式按DeepSeek官方定价更新", "file": "core/enforcement_hook.py"},
    EvolutionTarget.FAIR_TEMPLATE: {"priority": "P2", "frequency": "per_release",
                                     "parent": "_generate_fair_metadata",
                                     "描述": "FAIR元数据模板按项目标准演变", "file": "core/enforcement_hook.py"},
    EvolutionTarget.QUALITY_GATE: {"priority": "P1", "frequency": "per_100_turns",
                                    "parent": "QualityGate",
                                    "描述": "质量门禁阈值（min_value_score/max_similarity）自动校准",
                                    "file": "core/quality_gate.py"},
    EvolutionTarget.MCP_INTERCEPT: {"priority": "P1", "frequency": "per_200_turns",
                                     "parent": "handle_tools_call",
                                     "描述": "MCP拦截策略按工具使用热度调整记录粒度",
                                     "file": "mcp/tianji_mcp_server.py"},
    EvolutionTarget.TVP_DETECTOR: {"priority": "P1", "frequency": "per_150_turns",
                                    "parent": "_detect_agent_switches_from_mcp",
                                    "描述": "TVP切换检测模式匹配规则按实际调度频率调优",
                                    "file": "core/enforcement_hook.py"},
    EvolutionTarget.REGISTRY_CACHE: {"priority": "P2", "frequency": "per_1000_turns",
                                      "parent": "ConversationRegistry",
                                      "描述": "缓存淘汰策略根据内存压力自适应调整", "file": "core/enforcement_hook.py"},
}


@dataclass
class UserIntent:
    goals: List[str] = field(default_factory=list)
    constraints: List[str] = field(default_factory=list)
    completion_target: float = 1.0
    required_tools: List[str] = field(default_factory=list)
    priority_hints: List[str] = field(default_factory=list)
    raw_input: str = ""

    def to_dict(self) -> dict:
        return {
            "goals": self.goals,
            "constraints": self.constraints,
            "completion_target": self.completion_target,
            "required_tools": self.required_tools,
            "priority_hints": self.priority_hints,
            "raw_input_summary": self.raw_input[:100],
        }


@dataclass
class AIExecution:
    mcp_calls: List[str] = field(default_factory=list)
    file_operations: int = 0
    errors_encountered: int = 0
    agent_switches: int = 0
    tokens_used: int = 0
    tools_matched: int = 0
    tools_missed: int = 0
    raw_response: str = ""

    def to_dict(self) -> dict:
        return {
            "mcp_calls": self.mcp_calls,
            "file_operations": self.file_operations,
            "errors_encountered": self.errors_encountered,
            "agent_switches": self.agent_switches,
            "tokens_used": self.tokens_used,
            "tools_matched": self.tools_matched,
            "tools_missed": self.tools_missed,
        }


@dataclass
class AlignmentReport:
    session_id: str
    turn_number: int
    intent: UserIntent
    execution: AIExecution
    alignment_score: float = 0.0
    gaps: List[str] = field(default_factory=list)
    suggestions: List[str] = field(default_factory=list)
    evolution_targets_triggered: List[EvolutionTarget] = field(default_factory=list)
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return {
            "session_id": self.session_id,
            "turn_number": self.turn_number,
            "intent": self.intent.to_dict(),
            "execution": self.execution.to_dict(),
            "alignment_score": self.alignment_score,
            "gaps": self.gaps,
            "suggestions": self.suggestions,
            "evolution_targets_triggered": [t.value for t in self.evolution_targets_triggered],
            "timestamp": self.timestamp,
        }


class EnforcementAlignment:
    """
    思考对齐引擎 — 追踪"用户意图 vs AI执行"差异，实现双向对齐

    工作原理:
      每轮对话后自动提取用户意图 → 追踪AI实际执行 → 计算对齐分 → 发现差距 →
      触发对应进化目标 → 反馈到EnforcementEvolution
    """

    GOAL_PATTERNS = {
        "完成": ["完成", "达成", "实现", "做到"],
        "审计": ["审计", "验证", "检查", "测试", "review"],
        "修复": ["修复", "fix", "解决", "处理", "修正"],
        "入库": ["录入", "存储", "记录", "写入", "保存"],
        "分析": ["分析", "评估", "测量", "诊断"],
        "创建": ["创建", "新建", "生成", "构建", "建立"],
        "优化": ["优化", "提升", "改进", "增强"],
    }

    CONSTRAINT_PATTERNS = {
        "100%": ["100%", "全部", "完整", "全量", "所有"],
        "真实": ["真实", "不幻想", "实际", "确实", "准确"],
        "立即": ["立即", "马上", "现在", "紧急"],
        "科学": ["科学", "标准", "规范", "合规"],
    }

    def __init__(self, tracker: EnforcementTracker = None, evolution: EnforcementEvolution = None):
        self._tracker = tracker
        self._evolution = evolution
        self._reports: List[AlignmentReport] = []
        self._lock = threading.Lock()

    def extract_intent(self, user_input: str) -> UserIntent:
        goals = []
        for goal_name, keywords in self.GOAL_PATTERNS.items():
            for kw in keywords:
                if kw in user_input:
                    goals.append(goal_name)
                    break
        constraints = []
        for c_name, keywords in self.CONSTRAINT_PATTERNS.items():
            for kw in keywords:
                if kw in user_input:
                    constraints.append(c_name)
                    break
        tools_needed = []
        tool_hints = [("memory", ["记忆", "天机", "memory", "recall", "remember"]),
                      ("agent", ["调度", "agent", "dispatch", "编排"]),
                      ("code", ["代码", "文件", "code", "write", "文件操作"]),
                      ("search", ["搜索", "检索", "查询", "search"]),
                      ("test", ["测试", "验证", "审计", "test"])]
        for tool, hints in tool_hints:
            for h in hints:
                if h in user_input.lower():
                    tools_needed.append(tool)
                    break
        completion = 1.0
        if "100%" in user_input:
            completion = 1.0
        elif any(kw in user_input for kw in ["全量", "全部"]):
            completion = 0.95
        priority_hints = []
        if any(kw in user_input for kw in ["必须", "立即", "紧急"]):
            priority_hints.append("P0")
        elif any(kw in user_input for kw in ["重要", "尽快"]):
            priority_hints.append("P1")
        return UserIntent(
            goals=goals,
            constraints=constraints,
            completion_target=completion,
            required_tools=tools_needed,
            priority_hints=priority_hints,
            raw_input=user_input,
        )

    def trace_execution(self, record) -> AIExecution:
        tools_used = list(record.mcp_calls_made or [])
        if record.mcp_call_details:
            tools_used.extend([d.tool_name for d in record.mcp_call_details])
        file_ops = len(record.file_operations or [])
        errors = len(record.error_log or [])
        switches = len(record.agent_switches or [])
        tokens = (record.token_economy.total_tokens if record.token_economy else 0)
        return AIExecution(
            mcp_calls=list(set(tools_used)),
            file_operations=file_ops,
            errors_encountered=errors,
            agent_switches=switches,
            tokens_used=tokens,
            raw_response=str(record.ai_response or "")[:200],
        )

    def calculate_alignment(self, intent: UserIntent, execution: AIExecution) -> Tuple[float, List[str], List[str]]:
        gaps = []
        suggestions = []
        score = 1.0

        if intent.required_tools:
            used_tool_set = set(execution.mcp_calls)
            needed_tools_lower = set(t.lower() for t in intent.required_tools)
            execution.tools_matched = 0
            for t in used_tool_set:
                for n in needed_tools_lower:
                    if n in t.lower():
                        execution.tools_matched += 1
                        needed_tools_lower.discard(n)
                        break
            execution.tools_missed = len(needed_tools_lower)
            if execution.tools_missed > 0:
                score -= 0.2 * execution.tools_missed
                gaps.append(f"工具缺失: 需要但未调用 {list(needed_tools_lower)}")
                suggestions.append("扩充必要工具调用链，或降低延迟加载门槛")

        if intent.constraints:
            if "100%" in intent.constraints and execution.errors_encountered > 0:
                score -= 0.15 * execution.errors_encountered
                gaps.append(f"错误存在: {execution.errors_encountered}个错误，违反100%完成度约束")
                suggestions.append("触发错误自动修复流程")
            if "真实" in intent.constraints and execution.mcp_calls and len(execution.mcp_calls) < 3:
                score -= 0.1
                gaps.append("证据稀疏: MCP调用数不足，可能存在幻觉风险")
                suggestions.append("增加验证性MCP调用（如memory_recall验证写入）")
            if "科学" in intent.constraints and execution.file_operations == 0:
                score -= 0.05
                gaps.append("缺乏物证: 无文件操作，口头承诺不可验证")
                suggestions.append("增加至少一次文件写入或测试运行以物化结果")

        if intent.goals:
            goal_hit = 0
            for goal in intent.goals:
                for call in execution.mcp_calls:
                    if goal in call or (goal == "审计" and "audit" in call.lower()):
                        goal_hit += 1
                        break
            goal_rate = goal_hit / len(intent.goals) if intent.goals else 1.0
            if goal_rate < 0.5:
                score -= 0.3
                gaps.append(f"目标缺失: {len(intent.goals)-goal_hit}/{len(intent.goals)}个目标无对应MCP操作")
                suggestions.append("逐目标匹配执行计划，未覆盖目标自动补充操作")

        score = max(0.0, min(1.0, score))
        return score, gaps, suggestions

    def align(self, record, user_input: str = None) -> AlignmentReport:
        ui = user_input or record.user_input
        intent = self.extract_intent(ui)
        execution = self.trace_execution(record)
        score, gaps, suggestions = self.calculate_alignment(intent, execution)

        evo_targets = []
        if score < 0.5:
            evo_targets.append(EvolutionTarget.NUDGE_DECIDE)
        if execution.tools_missed > 0:
            evo_targets.append(EvolutionTarget.MCP_INTERCEPT)
        if execution.errors_encountered > 0:
            evo_targets.append(EvolutionTarget.QUALITY_GATE)
        if len(intent.goals) > 3:
            evo_targets.append(EvolutionTarget.CONVERSATION_RECORD)

        report = AlignmentReport(
            session_id=record.session_id,
            turn_number=record.turn_number,
            intent=intent,
            execution=execution,
            alignment_score=score,
            gaps=gaps,
            suggestions=suggestions,
            evolution_targets_triggered=evo_targets,
        )
        with self._lock:
            self._reports.append(report)
            if len(self._reports) > 200:
                self._reports = self._reports[-200:]
        return report

    def get_alignment_trend(self, window: int = 10) -> Dict:
        with self._lock:
            recent = self._reports[-window:]
        if not recent:
            return {"avg_score": 0.0, "count": 0, "trend": "insufficient_data"}
        scores = [r.alignment_score for r in recent]
        avg = sum(scores) / len(scores)
        first = sum(scores[:len(scores)//2]) / max(len(scores)//2, 1)
        second = sum(scores[len(scores)//2:]) / max(len(scores) - len(scores)//2, 1)
        trend = "improving" if second > first else "degrading" if second < first else "stable"
        return {"avg_score": avg, "count": len(scores), "trend": trend,
                "common_gaps": self._top_gaps(recent),
                "common_suggestions": self._top_suggestions(recent)}

    def _top_gaps(self, reports: List[AlignmentReport]) -> List[str]:
        from collections import Counter
        c = Counter()
        for r in reports:
            c.update(r.gaps)
        return [g for g, _ in c.most_common(3)]

    def _top_suggestions(self, reports: List[AlignmentReport]) -> List[str]:
        from collections import Counter
        c = Counter()
        for r in reports:
            c.update(r.suggestions)
        return [s for s, _ in c.most_common(3)]

    def get_latest_report(self) -> Optional[dict]:
        if not self._reports:
            return None
        return self._reports[-1].to_dict()


class ConsumerProfile(Enum):
    """下游消费模块画像 — 定义各模块对录入数据的需求特征"""
    MEMORY_ENGINE = "memory_engine"           # engine/hybrid_engine/sqlite_store
    QUALITY_GATE = "quality_gate"             # quality_gate
    LEARNING = "learning"                     # learning_loop/evolution_loop/evolution_engine
    KNOWLEDGE = "knowledge"                   # knowledge_extractor/llm_kg_enhancer/kg_sync_hook
    PREFERENCE = "preference"                 # preference_learner/skill_learner
    SCHEDULER = "scheduler"                   # agent_orchestrator/intelligent_scheduler/tvp_bridge
    GOVERNANCE = "governance"                 # governance_pipeline/governance_orchestrator
    API = "api"                               # REST API routes
    ACTIVE_MEMORY = "active_memory"           # active_memory/tianji_intercept


CONSUMER_REQUIREMENTS: Dict[ConsumerProfile, Dict] = {
    ConsumerProfile.MEMORY_ENGINE: {
        "required_fields": ["session_id", "user_input", "ai_response", "timestamp", "content_hash"],
        "nice_to_have": ["agent_id", "mcp_call_details", "tags"],
        "min_content_length": 50,
        "preferred_layer": "episodic",
        "batch_size": 1,
        "description": "记忆引擎需要完整内容+哈希去重，偏好逐条写入episodic层",
    },
    ConsumerProfile.QUALITY_GATE: {
        "required_fields": ["user_input", "ai_response", "content_hash", "tags"],
        "nice_to_have": ["conversation_class", "iso_annotation", "token_economy"],
        "min_content_length": 30,
        "preferred_layer": "working",
        "batch_size": 1,
        "description": "质量门禁需要内容+分类标注进行三问推演，偏好working层预检",
    },
    ConsumerProfile.LEARNING: {
        "required_fields": ["session_id", "user_input", "ai_response", "tags", "conversation_class",
                           "mcp_call_details", "agent_switches"],
        "nice_to_have": ["iso_annotation", "error_log", "token_economy"],
        "min_content_length": 80,
        "preferred_layer": "episodic",
        "batch_size": 15,
        "description": "学习引擎需要完整上下文+分类标注进行模式提炼，偏好episodic批量反思",
    },
    ConsumerProfile.KNOWLEDGE: {
        "required_fields": ["user_input", "ai_response", "iso_annotation", "conversation_class"],
        "nice_to_have": ["prov_trace", "tags", "fair_metadata"],
        "min_content_length": 100,
        "preferred_layer": "semantic",
        "batch_size": 5,
        "description": "知识抽取需要ISO标注+PROV溯源构建知识图谱，偏好semantic层",
    },
    ConsumerProfile.PREFERENCE: {
        "required_fields": ["session_id", "user_input", "conversation_class", "tags"],
        "nice_to_have": ["agent_id", "agent_switches", "mcp_call_details"],
        "min_content_length": 30,
        "preferred_layer": "semantic",
        "batch_size": 10,
        "description": "偏好学习需要用户输入+分类标签推断偏好，偏好semantic批量处理",
    },
    ConsumerProfile.SCHEDULER: {
        "required_fields": ["agent_id", "agent_switches", "mcp_call_details"],
        "nice_to_have": ["conversation_class", "token_economy", "prov_trace"],
        "min_content_length": 20,
        "preferred_layer": "short_term",
        "batch_size": 3,
        "description": "调度器需要Agent切换+TVP记录优化调度策略，偏好short_term快速反馈",
    },
    ConsumerProfile.GOVERNANCE: {
        "required_fields": ["session_id", "agent_id", "file_operations", "error_log",
                           "prov_trace", "fair_metadata"],
        "nice_to_have": ["iso_annotation", "conversation_class", "token_economy"],
        "min_content_length": 50,
        "preferred_layer": "meta",
        "batch_size": 1,
        "description": "治理审计需要操作记录+溯源+FAIR合规，偏好meta层归档",
    },
    ConsumerProfile.API: {
        "required_fields": ["session_id", "user_input", "ai_response", "timestamp"],
        "nice_to_have": ["conversation_class", "tags", "token_economy"],
        "min_content_length": 20,
        "preferred_layer": "episodic",
        "batch_size": 1,
        "description": "API层需要基础字段供查询，偏好episodic层",
    },
    ConsumerProfile.ACTIVE_MEMORY: {
        "required_fields": ["session_id", "tags", "conversation_class"],
        "nice_to_have": ["iso_annotation", "agent_switches", "mcp_call_details"],
        "min_content_length": 10,
        "preferred_layer": "working",
        "batch_size": 1,
        "description": "主动记忆需要标签+分类快速匹配历史上下文，偏好working层",
    },
}


ADAPTIVE_FIELD_WEIGHTS: Dict[str, Dict[ConsumerProfile, float]] = {
    "user_input": {ConsumerProfile.MEMORY_ENGINE: 1.0, ConsumerProfile.QUALITY_GATE: 1.0,
                   ConsumerProfile.LEARNING: 1.0, ConsumerProfile.KNOWLEDGE: 0.9,
                   ConsumerProfile.PREFERENCE: 1.0, ConsumerProfile.SCHEDULER: 0.3,
                   ConsumerProfile.GOVERNANCE: 0.5, ConsumerProfile.API: 1.0,
                   ConsumerProfile.ACTIVE_MEMORY: 0.4},
    "ai_response": {ConsumerProfile.MEMORY_ENGINE: 1.0, ConsumerProfile.QUALITY_GATE: 0.8,
                    ConsumerProfile.LEARNING: 0.9, ConsumerProfile.KNOWLEDGE: 0.8,
                    ConsumerProfile.PREFERENCE: 0.3, ConsumerProfile.SCHEDULER: 0.2,
                    ConsumerProfile.GOVERNANCE: 0.6, ConsumerProfile.API: 1.0,
                    ConsumerProfile.ACTIVE_MEMORY: 0.2},
    "mcp_call_details": {ConsumerProfile.MEMORY_ENGINE: 0.7, ConsumerProfile.QUALITY_GATE: 0.5,
                         ConsumerProfile.LEARNING: 0.9, ConsumerProfile.KNOWLEDGE: 0.3,
                         ConsumerProfile.PREFERENCE: 0.5, ConsumerProfile.SCHEDULER: 1.0,
                         ConsumerProfile.GOVERNANCE: 0.7, ConsumerProfile.API: 0.4,
                         ConsumerProfile.ACTIVE_MEMORY: 0.3},
    "agent_switches": {ConsumerProfile.MEMORY_ENGINE: 0.4, ConsumerProfile.QUALITY_GATE: 0.2,
                       ConsumerProfile.LEARNING: 0.8, ConsumerProfile.KNOWLEDGE: 0.3,
                       ConsumerProfile.PREFERENCE: 0.5, ConsumerProfile.SCHEDULER: 1.0,
                       ConsumerProfile.GOVERNANCE: 0.6, ConsumerProfile.API: 0.3,
                       ConsumerProfile.ACTIVE_MEMORY: 0.4},
    "conversation_class": {ConsumerProfile.MEMORY_ENGINE: 0.3, ConsumerProfile.QUALITY_GATE: 0.7,
                           ConsumerProfile.LEARNING: 0.8, ConsumerProfile.KNOWLEDGE: 0.7,
                           ConsumerProfile.PREFERENCE: 0.8, ConsumerProfile.SCHEDULER: 0.5,
                           ConsumerProfile.GOVERNANCE: 0.5, ConsumerProfile.API: 0.4,
                           ConsumerProfile.ACTIVE_MEMORY: 0.7},
    "iso_annotation": {ConsumerProfile.MEMORY_ENGINE: 0.2, ConsumerProfile.QUALITY_GATE: 0.5,
                       ConsumerProfile.LEARNING: 0.7, ConsumerProfile.KNOWLEDGE: 1.0,
                       ConsumerProfile.PREFERENCE: 0.4, ConsumerProfile.SCHEDULER: 0.3,
                       ConsumerProfile.GOVERNANCE: 0.5, ConsumerProfile.API: 0.2,
                       ConsumerProfile.ACTIVE_MEMORY: 0.5},
    "prov_trace": {ConsumerProfile.MEMORY_ENGINE: 0.2, ConsumerProfile.QUALITY_GATE: 0.3,
                   ConsumerProfile.LEARNING: 0.6, ConsumerProfile.KNOWLEDGE: 0.5,
                   ConsumerProfile.PREFERENCE: 0.2, ConsumerProfile.SCHEDULER: 0.5,
                   ConsumerProfile.GOVERNANCE: 0.9, ConsumerProfile.API: 0.2,
                   ConsumerProfile.ACTIVE_MEMORY: 0.2},
    "token_economy": {ConsumerProfile.MEMORY_ENGINE: 0.1, ConsumerProfile.QUALITY_GATE: 0.4,
                      ConsumerProfile.LEARNING: 0.5, ConsumerProfile.KNOWLEDGE: 0.2,
                      ConsumerProfile.PREFERENCE: 0.2, ConsumerProfile.SCHEDULER: 0.6,
                      ConsumerProfile.GOVERNANCE: 0.4, ConsumerProfile.API: 0.3,
                      ConsumerProfile.ACTIVE_MEMORY: 0.1},
    "fair_metadata": {ConsumerProfile.MEMORY_ENGINE: 0.1, ConsumerProfile.QUALITY_GATE: 0.2,
                      ConsumerProfile.LEARNING: 0.3, ConsumerProfile.KNOWLEDGE: 0.5,
                      ConsumerProfile.PREFERENCE: 0.1, ConsumerProfile.SCHEDULER: 0.2,
                      ConsumerProfile.GOVERNANCE: 0.9, ConsumerProfile.API: 0.3,
                      ConsumerProfile.ACTIVE_MEMORY: 0.1},
    "file_operations": {ConsumerProfile.MEMORY_ENGINE: 0.3, ConsumerProfile.QUALITY_GATE: 0.3,
                        ConsumerProfile.LEARNING: 0.5, ConsumerProfile.KNOWLEDGE: 0.2,
                        ConsumerProfile.PREFERENCE: 0.1, ConsumerProfile.SCHEDULER: 0.4,
                        ConsumerProfile.GOVERNANCE: 0.8, ConsumerProfile.API: 0.2,
                        ConsumerProfile.ACTIVE_MEMORY: 0.1},
    "error_log": {ConsumerProfile.MEMORY_ENGINE: 0.2, ConsumerProfile.QUALITY_GATE: 0.5,
                  ConsumerProfile.LEARNING: 0.6, ConsumerProfile.KNOWLEDGE: 0.3,
                  ConsumerProfile.PREFERENCE: 0.1, ConsumerProfile.SCHEDULER: 0.4,
                  ConsumerProfile.GOVERNANCE: 0.7, ConsumerProfile.API: 0.2,
                  ConsumerProfile.ACTIVE_MEMORY: 0.1},
}




__all__ = ["EvolutionTarget", "UserIntent", "AIExecution", "AlignmentReport", "EnforcementAlignment", "ConsumerProfile"]
