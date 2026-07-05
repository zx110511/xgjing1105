# -*- coding: utf-8-sig -*-
"""经验自动沉淀 - 复用器（主动推荐）

智能检索和推荐相关经验，与记忆系统和调度系统集成。

架构位置: D4悟道域 - 进化处理器
版本: v1.0.0 (Phase 3)

核心功能:
  1. 经验检索 - 语义+关键词混合检索
  2. 上下文适配 - 智能过滤和排序
  3. 与memory_recall集成 - 检索记忆时自动关联经验
  4. 与agent_dispatch集成 - 调度时参考历史成功经验
  5. 推荐结果格式化
"""

from __future__ import annotations

import time
import logging
import threading
from typing import Any, Dict, List, Optional, Tuple

from .experience_models import (
    ExperienceEntry,
    ExperienceDomain,
    PatternType,
    ExperienceGrade,
)
from .experience_store import ExperienceStore, get_experience_store

logger = logging.getLogger(__name__)


class ExperienceRetriever:
    """经验复用器 - 主动推荐系统

    Phase 3 核心功能:
    - 混合检索（关键词+领域+等级）
    - 上下文智能适配
    - 质量排序（S>A>B>C>D）
    - 与记忆检索联动
    - 与Agent调度联动
    """

    VERSION = "1.0.0"

    def __init__(
        self,
        store: Optional[ExperienceStore] = None,
        max_results: int = 5,
        min_confidence: float = 0.3,
    ) -> None:
        self._store = store or get_experience_store()
        self._max_results = max_results
        self._min_confidence = min_confidence
        self._lock = threading.Lock()
        self._stats = {
            "queries": 0,
            "results_returned": 0,
            "cache_hits": 0,
        }

        logger.info(
            "ExperienceRetriever 初始化完成 (max_results=%d, min_confidence=%.2f)",
            max_results, min_confidence,
        )

    # ── 核心检索 ──

    def search_experiences(
        self,
        query: str,
        domain: Optional[str] = None,
        pattern_type: Optional[str] = None,
        min_grade: Optional[str] = None,
        limit: Optional[int] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """搜索经验

        Args:
            query: 搜索关键词
            domain: 领域过滤
            pattern_type: 模式类型过滤
            min_grade: 最低等级 (S/A/B/C/D)
            limit: 返回数量限制
            context: 上下文信息，用于适配排序

        Returns:
            经验列表，按相关度和质量排序
        """
        self._stats["queries"] += 1
        actual_limit = limit or self._max_results

        try:
            # Step 1: 候选集获取
            candidates = self._get_candidates(query, domain, pattern_type, min_grade)

            if not candidates:
                return []

            # Step 2: 评分与排序
            scored = []
            for exp in candidates:
                relevance = self._calc_relevance(exp, query, context)
                quality = self._calc_quality_score(exp)
                final_score = relevance * 0.6 + quality * 0.4

                if final_score > 0:
                    scored.append((exp, final_score, relevance, quality))

            # Step 3: 排序和截断
            scored.sort(key=lambda x: x[1], reverse=True)
            top = scored[:actual_limit]

            self._stats["results_returned"] += len(top)

            # Step 4: 格式化输出
            return [
                self._format_result(exp, score, relevance, quality)
                for exp, score, relevance, quality in top
            ]

        except Exception as e:
            logger.warning("搜索经验失败: %s", e)
            return []

    def _get_candidates(
        self,
        query: str,
        domain: Optional[str],
        pattern_type: Optional[str],
        min_grade: Optional[str],
    ) -> List[ExperienceEntry]:
        """获取候选经验集"""
        candidates = []
        seen_ids = set()

        # 方式1: 通过traces全文搜索找到相关trace，再找关联经验
        try:
            traces = self._store.search_traces(query, limit=20)
            for trace in traces:
                exps = self._store.list_experiences(limit=50)
                for exp in exps:
                    if trace.trace_id in exp.source_trace_ids and exp.experience_id not in seen_ids:
                        candidates.append(exp)
                        seen_ids.add(exp.experience_id)
        except Exception as e:
            logger.debug("全文搜索候选失败: %s", e)

        # 方式2: 通过领域+模式直接获取
        try:
            filtered = self._store.list_experiences(
                domain=domain,
                pattern_type=pattern_type,
                limit=50,
            )
            for exp in filtered:
                if exp.experience_id not in seen_ids:
                    candidates.append(exp)
                    seen_ids.add(exp.experience_id)
        except Exception as e:
            logger.debug("按条件获取候选失败: %s", e)

        # 方式3: 如果查询关键词在经验内容中匹配
        if query:
            query_lower = query.lower()
            all_exps = self._store.list_experiences(limit=100)
            for exp in all_exps:
                if exp.experience_id in seen_ids:
                    continue
                exp_text = " ".join([
                    exp.trigger_context.get("task_type", ""),
                    exp.trigger_context.get("tool", ""),
                    str(exp.metadata.get("tags", [])),
                ]).lower()
                if query_lower in exp_text:
                    candidates.append(exp)
                    seen_ids.add(exp.experience_id)

        # 统一过滤: 领域
        if domain:
            candidates = [
                c for c in candidates
                if c.domain.value == domain
            ]

        # 统一过滤: 模式类型
        if pattern_type:
            candidates = [
                c for c in candidates
                if c.pattern_type.value == pattern_type
            ]

        # 统一过滤: 等级
        if min_grade:
            grade_order = {"S": 5, "A": 4, "B": 3, "C": 2, "D": 1}
            min_level = grade_order.get(min_grade, 0)
            candidates = [
                c for c in candidates
                if grade_order.get(c.grade.value, 0) >= min_level
            ]

        return candidates

    def _calc_relevance(
        self,
        exp: ExperienceEntry,
        query: str,
        context: Optional[Dict[str, Any]],
    ) -> float:
        """计算相关度评分 (0-1)"""
        if not query:
            return 0.5  # 无查询，中等相关

        score = 0.0
        query_lower = query.lower()

        # 工具名匹配
        tool = exp.trigger_context.get("tool", "").lower()
        if tool and query_lower in tool:
            score += 0.4

        # 任务类型匹配
        task_type = exp.trigger_context.get("task_type", "").lower()
        if task_type and query_lower in task_type:
            score += 0.3

        # 标签匹配
        tags = exp.metadata.get("tags", [])
        matching_tags = [t for t in tags if query_lower in str(t).lower()]
        if matching_tags:
            score += min(0.2, len(matching_tags) * 0.05)

        # 上下文适配
        if context:
            ctx_agent = context.get("agent_id", "").lower()
            exp_agent = exp.trigger_context.get("agent", "").lower()
            if ctx_agent and exp_agent and ctx_agent == exp_agent:
                score += 0.1

            ctx_domain = context.get("domain", "")
            if ctx_domain and exp.domain.value == ctx_domain:
                score += 0.1

        return min(1.0, max(0.0, score))

    def _calc_quality_score(self, exp: ExperienceEntry) -> float:
        """计算质量评分 (0-1)"""
        score = 0.0

        # 等级权重
        grade_weights = {"S": 1.0, "A": 0.85, "B": 0.7, "C": 0.5, "D": 0.3}
        score += grade_weights.get(exp.grade.value, 0.3) * 0.5

        # 置信度
        confidence = exp.metadata.get("confidence", 0.3)
        score += confidence * 0.2

        # 复用次数
        reuse_count = exp.metadata.get("reuse_count", 0)
        if reuse_count > 0:
            score += min(0.15, reuse_count * 0.02)

        # 成功率
        success_rate = exp.metadata.get("success_rate", 0.5)
        score += success_rate * 0.15

        return min(1.0, max(0.0, score))

    def _format_result(
        self,
        exp: ExperienceEntry,
        final_score: float,
        relevance: float,
        quality: float,
    ) -> Dict[str, Any]:
        """格式化推荐结果"""
        return {
            "experience_id": exp.experience_id,
            "domain": exp.domain.value,
            "pattern_type": exp.pattern_type.value,
            "grade": exp.grade.value,
            "title": self._generate_title(exp),
            "summary": self._generate_summary(exp),
            "tool_chain": exp.solution.get("tool_chain", []),
            "key_params": exp.solution.get("parameters", {}),
            "success_rate": exp.metadata.get("success_rate", 0.0),
            "reuse_count": exp.metadata.get("reuse_count", 0),
            "confidence": exp.metadata.get("confidence", 0.0),
            "relevance_score": round(relevance, 3),
            "quality_score": round(quality, 3),
            "final_score": round(final_score, 3),
            "tags": exp.metadata.get("tags", []),
            "created_at": exp.created_at,
        }

    def _generate_title(self, exp: ExperienceEntry) -> str:
        """生成经验标题"""
        tool = exp.trigger_context.get("tool", "未知工具")
        pattern = exp.pattern_type.value

        if pattern == "success_pattern":
            return f"{tool} 成功模式"
        elif pattern == "failure_lesson":
            return f"{tool} 失败教训"
        elif pattern == "best_practice":
            return f"{tool} 最佳实践"
        elif pattern == "optimization":
            return f"{tool} 优化方案"
        else:
            return f"{tool} 经验"

    def _generate_summary(self, exp: ExperienceEntry) -> str:
        """生成经验摘要"""
        outcome = exp.outcome
        quality = outcome.get("quality_score", 0)
        duration = outcome.get("duration_ms", 0)

        parts = []

        if exp.pattern_type == PatternType.FAILURE_LESSON:
            error_type = outcome.get("error_type", "未知错误")
            parts.append(f"错误类型: {error_type}")
            parts.append(f"质量评分: {quality:.2f}")
        else:
            parts.append(f"质量评分: {quality:.2f}")
            if duration > 0:
                parts.append(f"平均耗时: {duration:.0f}ms")

        reuse = exp.metadata.get("reuse_count", 0)
        if reuse > 0:
            parts.append(f"已复用 {reuse} 次")

        success_rate = exp.metadata.get("success_rate", 0)
        if success_rate > 0:
            parts.append(f"成功率: {success_rate:.0%}")

        return " | ".join(parts)

    # ── 与memory_recall集成 ──

    def augment_memory_recall(
        self,
        query: str,
        memory_results: List[Dict[str, Any]],
        layer: Optional[str] = None,
    ) -> Dict[str, Any]:
        """增强记忆检索结果 - 自动关联相关经验

        Args:
            query: 原始查询
            memory_results: 记忆检索结果
            layer: 记忆层级

        Returns:
            {
                "memories": [...],  # 原始记忆结果
                "related_experiences": [...],  # 相关经验
                "experience_summary": "...",  # 经验摘要
            }
        """
        # 从记忆结果中提取领域信息
        domain = None
        if layer and "semantic" in layer:
            domain = ExperienceDomain.MEMORY.value

        # 搜索相关经验
        experiences = self.search_experiences(
            query=query,
            domain=domain,
            limit=3,
        )

        # 生成经验摘要
        summary = self._generate_experience_summary(experiences)

        return {
            "memories": memory_results,
            "related_experiences": experiences,
            "experience_summary": summary,
            "experience_count": len(experiences),
        }

    def _generate_experience_summary(self, experiences: List[Dict[str, Any]]) -> str:
        """生成经验集合的摘要"""
        if not experiences:
            return "暂无相关经验"

        parts = [f"找到 {len(experiences)} 条相关经验:"]
        for i, exp in enumerate(experiences[:3], 1):
            grade = exp.get("grade", "?")
            title = exp.get("title", "")
            score = exp.get("final_score", 0)
            parts.append(f"{i}. [{grade}] {title} (匹配度 {score:.0%})")

        return "\n".join(parts)

    # ── 与agent_dispatch集成 ──

    def recommend_for_dispatch(
        self,
        task_type: str,
        available_agents: List[str],
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """为Agent调度提供经验推荐

        Args:
            task_type: 任务类型
            available_agents: 可用Agent列表
            context: 上下文信息

        Returns:
            {
                "recommended_agent": "...",
                "confidence": 0.0-1.0,
                "supporting_experiences": [...],
                "reasoning": "...",
                "alternatives": [...],
            }
        """
        # 搜索相关调度经验
        experiences = self.search_experiences(
            query=task_type,
            domain=ExperienceDomain.AGENT_DISPATCH.value,
            pattern_type=PatternType.SUCCESS_PATTERN.value,
            limit=10,
            context=context or {},
        )

        if not experiences:
            return {
                "recommended_agent": None,
                "confidence": 0.0,
                "supporting_experiences": [],
                "reasoning": "暂无历史调度经验，使用默认调度策略",
                "alternatives": available_agents[:3],
            }

        # 统计各Agent的成功经验数
        agent_scores: Dict[str, float] = {}
        agent_experiences: Dict[str, List[Dict]] = {}

        for exp in experiences:
            agent = exp.get("key_params", {}).get("agent", "")
            if not agent or agent not in available_agents:
                # 尝试从trigger_context中获取
                agent = ""

            # 从经验中提取执行过的Agent
            # Phase 3 MVP: 简化处理，直接根据经验整体评分
            score = exp.get("final_score", 0)
            for agent_id in available_agents:
                if agent_id not in agent_scores:
                    agent_scores[agent_id] = 0.0
                    agent_experiences[agent_id] = []
                agent_scores[agent_id] += score * 0.1  # 每条经验贡献一点
                agent_experiences[agent_id].append(exp)

        # 如果没有明确的Agent关联，使用整体经验
        if not any(v > 0 for v in agent_scores.values()):
            top_exp = experiences[0]
            return {
                "recommended_agent": available_agents[0] if available_agents else None,
                "confidence": top_exp.get("final_score", 0.5) * 0.5,
                "supporting_experiences": experiences[:3],
                "reasoning": f"基于 {len(experiences)} 条历史经验推荐，参考成功模式",
                "alternatives": available_agents[1:4],
            }

        # 选择得分最高的Agent
        sorted_agents = sorted(agent_scores.items(), key=lambda x: x[1], reverse=True)
        top_agent, top_score = sorted_agents[0]

        total_score = sum(agent_scores.values())
        confidence = top_score / total_score if total_score > 0 else 0.0

        return {
            "recommended_agent": top_agent,
            "confidence": round(confidence, 3),
            "supporting_experiences": agent_experiences.get(top_agent, [])[:3],
            "reasoning": f"基于 {len(experiences)} 条历史经验，{top_agent} 成功率最高",
            "alternatives": [a for a, _ in sorted_agents[1:4]],
        }

    # ── 统计信息 ──

    def get_stats(self) -> Dict[str, Any]:
        """获取复用器统计信息"""
        store_stats = self._store.get_stats()
        return {
            "retriever_version": self.VERSION,
            "session_stats": self._stats.copy(),
            "store_stats": store_stats.to_dict(),
            "config": {
                "max_results": self._max_results,
                "min_confidence": self._min_confidence,
            },
        }


# 模块级默认实例
_default_retriever: Optional[ExperienceRetriever] = None
_retriever_lock = threading.Lock()


def get_experience_retriever(
    store: Optional[ExperienceStore] = None,
) -> ExperienceRetriever:
    """获取默认经验复用器实例（单例）"""
    global _default_retriever
    if _default_retriever is None:
        with _retriever_lock:
            if _default_retriever is None:
                _default_retriever = ExperienceRetriever(store=store)
    return _default_retriever


__all__ = [
    "ExperienceRetriever",
    "get_experience_retriever",
]
