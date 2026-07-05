# -*- coding: utf-8-sig -*-
"""经验自动沉淀 - 评估器

自动评估操作轨迹的质量，识别成功模式与失败教训，
生成可复用的经验条目。

架构位置: D4悟道域 - 进化处理器
版本: v1.0.0 (Phase 2)

评估维度:
  1. 任务完成度 (40%) - 是否达成目标
  2. 效率 (20%) - 工具调用次数/耗时
  3. 创新性 (15%) - 是否有新方法/新思路
  4. 可复用性 (15%) - 是否通用可迁移
  5. 稳定性 (10%) - 是否可重复成功
"""

from __future__ import annotations

import time
import logging
import hashlib
import threading
from typing import Any, Dict, List, Optional, Tuple

from .experience_models import (
    OperationTrace,
    ExperienceEntry,
    ExperienceDomain,
    PatternType,
    ExperienceGrade,
)
from .experience_store import ExperienceStore, get_experience_store

logger = logging.getLogger(__name__)


class ExperienceEvaluator:
    """经验评估器

    Phase 2 核心功能:
    - 五维质量评分
    - 成功模式/失败教训自动识别
    - 经验去重与聚类
    - 经验等级自动计算
    - 批量评估处理
    """

    VERSION = "1.0.0"

    # 五维权重
    WEIGHTS = {
        "completeness": 0.40,  # 任务完成度
        "efficiency": 0.20,     # 效率
        "innovation": 0.15,     # 创新性
        "reusability": 0.15,    # 可复用性
        "stability": 0.10,      # 稳定性
    }

    def __init__(
        self,
        store: Optional[ExperienceStore] = None,
        auto_evaluate: bool = True,
        batch_size: int = 50,
    ) -> None:
        self._store = store or get_experience_store()
        self._auto_evaluate = auto_evaluate
        self._batch_size = batch_size
        self._lock = threading.Lock()
        self._stats = {
            "evaluated": 0,
            "promoted": 0,
            "demoted": 0,
            "skipped": 0,
            "errors": 0,
        }

        logger.info(
            "ExperienceEvaluator 初始化完成 (auto_evaluate=%s, batch_size=%d)",
            auto_evaluate,
            batch_size,
        )

    # ── 单条轨迹评估 ──

    def evaluate_trace(self, trace: OperationTrace) -> Dict[str, Any]:
        """评估单条操作轨迹的质量

        Args:
            trace: 操作轨迹

        Returns:
            评估结果字典:
                - overall_score: 综合评分 (0-1)
                - dimensions: 各维度评分
                - pattern_type: 模式类型
                - grade: 经验等级
                - should_promote: 是否值得沉淀为经验
        """
        dimensions = self._score_dimensions(trace)
        overall = self._calculate_overall(dimensions)
        pattern_type = self._classify_pattern(trace, overall)
        grade = self._calculate_grade(overall, 1)
        should_promote = self._should_promote(trace, overall, pattern_type)

        return {
            "overall_score": overall,
            "dimensions": dimensions,
            "pattern_type": pattern_type,
            "grade": grade,
            "should_promote": should_promote,
        }

    def _score_dimensions(self, trace: OperationTrace) -> Dict[str, float]:
        """五维评分

        Returns:
            {completeness, efficiency, innovation, reusability, stability}
        """
        return {
            "completeness": self._score_completeness(trace),
            "efficiency": self._score_efficiency(trace),
            "innovation": self._score_innovation(trace),
            "reusability": self._score_reusability(trace),
            "stability": self._score_stability(trace),
        }

    def _score_completeness(self, trace: OperationTrace) -> float:
        """任务完成度评分 (0-1)

        Phase 2 MVP: 基于success标记 + 结果摘要长度
        """
        if not trace.success:
            return 0.0

        score = 0.7  # 基础分：成功了

        # 结果摘要越丰富，完成度可能越高
        if trace.result_summary:
            summary_len = len(trace.result_summary)
            if summary_len > 500:
                score += 0.15
            elif summary_len > 100:
                score += 0.10
            elif summary_len > 20:
                score += 0.05

        # 有标签说明上下文丰富
        if trace.context_tags:
            score += min(0.15, len(trace.context_tags) * 0.03)

        return min(1.0, max(0.0, score))

    def _score_efficiency(self, trace: OperationTrace) -> float:
        """效率评分 (0-1)

        基于耗时：越快效率越高
        """
        if trace.duration_ms <= 0:
            return 0.5  # 未知耗时，给中等分

        # 基准：100ms为满分，10s为0分
        duration = trace.duration_ms
        if duration <= 100:
            return 1.0
        elif duration >= 10000:
            return 0.1
        else:
            # 对数衰减
            import math
            ratio = math.log10(duration / 100) / math.log10(10000 / 100)
            return max(0.1, 1.0 - ratio * 0.9)

    def _score_innovation(self, trace: OperationTrace) -> float:
        """创新性评分 (0-1)

        Phase 2 MVP: 基于工具组合和参数的独特性
        """
        score = 0.3  # 基础分

        # 参数数量多可能意味着更复杂的用法
        param_count = len(trace.tool_params) if trace.tool_params else 0
        if param_count >= 5:
            score += 0.2
        elif param_count >= 3:
            score += 0.15
        elif param_count >= 1:
            score += 0.1

        # 有上下文标签可能说明应用场景特殊
        if trace.context_tags and len(trace.context_tags) >= 3:
            score += 0.1

        # 有父轨迹说明是组合操作的一部分
        if trace.parent_trace_id:
            score += 0.1

        return min(1.0, max(0.0, score))

    def _score_reusability(self, trace: OperationTrace) -> float:
        """可复用性评分 (0-1)

        评估这个经验是否容易被复用
        """
        score = 0.4  # 基础分

        # 通用工具复用性高
        generic_tools = {
            "memory_recall", "memory_remember", "agent_dispatch",
            "search_memories", "tianji_semantic_search",
        }
        if trace.tool_name in generic_tools:
            score += 0.3

        # 有明确的领域分类
        domain = ExperienceEntry._infer_domain(trace.tool_name)
        if domain != ExperienceDomain.OTHER:
            score += 0.1

        # 有上下文标签
        if trace.context_tags and len(trace.context_tags) >= 2:
            score += 0.1

        # 成功的经验更容易复用
        if trace.success:
            score += 0.1

        return min(1.0, max(0.0, score))

    def _score_stability(self, trace: OperationTrace) -> float:
        """稳定性评分 (0-1)

        Phase 2 MVP: 基于错误类型和历史成功率
        """
        if trace.success:
            # 成功的操作，基础分高
            score = 0.8
            # 有明确结果摘要更稳定
            if trace.result_summary and len(trace.result_summary) > 10:
                score += 0.1
        else:
            # 失败的操作，看错误类型
            score = 0.3
            transient_errors = {"TimeoutError", "ConnectionError", "RateLimitError"}
            if trace.error_type in transient_errors:
                score += 0.2  # 临时错误，不代表不稳定

        return min(1.0, max(0.0, score))

    def _calculate_overall(self, dimensions: Dict[str, float]) -> float:
        """计算综合评分"""
        total = 0.0
        for dim, weight in self.WEIGHTS.items():
            total += dimensions.get(dim, 0.0) * weight
        return round(total, 4)

    def _classify_pattern(self, trace: OperationTrace, overall_score: float) -> PatternType:
        """分类模式类型"""
        if trace.success:
            if overall_score >= 0.8:
                return PatternType.BEST_PRACTICE
            elif overall_score >= 0.6:
                return PatternType.SUCCESS_PATTERN
            else:
                return PatternType.SUCCESS_PATTERN
        else:
            return PatternType.FAILURE_LESSON

    def _calculate_grade(self, overall_score: float, sample_count: int) -> ExperienceGrade:
        """计算经验等级

        Args:
            overall_score: 综合评分
            sample_count: 验证样本数

        Returns:
            经验等级 (S/A/B/C/D)
        """
        if sample_count >= 100 and overall_score >= 0.9:
            return ExperienceGrade.S
        elif sample_count >= 10 and overall_score >= 0.8:
            return ExperienceGrade.A
        elif sample_count >= 3 and overall_score >= 0.6:
            return ExperienceGrade.B
        elif sample_count >= 1 and overall_score >= 0.4:
            return ExperienceGrade.C
        else:
            return ExperienceGrade.D

    def _should_promote(self, trace: OperationTrace, overall_score: float, pattern_type: PatternType) -> bool:
        """判断是否值得沉淀为经验"""
        # 失败教训也值得沉淀（避免重复踩坑）
        if not trace.success and trace.error_message:
            return True

        # 成功的经验，质量达到一定阈值
        if trace.success and overall_score >= 0.5:
            return True

        # 有特殊标签的也沉淀
        if trace.context_tags and any(
            tag in trace.context_tags for tag in ["important", "critical", "lesson"]
        ):
            return True

        return False

    # ── 经验生成与升级 ──

    def promote_trace(self, trace: OperationTrace) -> Optional[str]:
        """将操作轨迹升级为经验条目

        Args:
            trace: 操作轨迹

        Returns:
            经验ID（如果成功升级）
        """
        evaluation = self.evaluate_trace(trace)

        if not evaluation["should_promote"]:
            self._stats["skipped"] += 1
            return None

        try:
            # 检查是否已有相似经验
            similar = self._find_similar_experience(trace)
            if similar:
                # 合并到已有经验
                self._merge_into_experience(similar, trace, evaluation)
                self._stats["promoted"] += 1
                return similar.experience_id

            # 创建新经验
            experience = ExperienceEntry.from_trace(trace)
            experience.grade = evaluation["grade"]
            experience.pattern_type = evaluation["pattern_type"]

            # 更新质量评分
            if "outcome" in experience.__dict__ or True:
                experience.outcome["quality_score"] = evaluation["overall_score"]
                experience.outcome["dimensions"] = evaluation["dimensions"]

            # 更新元数据
            experience.metadata["confidence"] = evaluation["overall_score"]
            experience.metadata["evaluation_version"] = self.VERSION

            eid = self._store.add_experience(experience)
            self._stats["evaluated"] += 1
            self._stats["promoted"] += 1

            logger.debug(
                "轨迹升级为经验: %s → %s (score=%.3f, grade=%s)",
                trace.trace_id, eid, evaluation["overall_score"], evaluation["grade"].value,
            )
            return eid

        except Exception as e:
            self._stats["errors"] += 1
            logger.warning("升级轨迹失败: %s", e)
            return None

    def _find_similar_experience(self, trace: OperationTrace) -> Optional[ExperienceEntry]:
        """查找相似经验（用于去重和合并）

        Phase 2 MVP: 基于工具名+内容哈希的简单匹配
        """
        trace_hash = trace.content_hash()
        domain = ExperienceEntry._infer_domain(trace.tool_name)

        experiences = self._store.list_experiences(
            domain=domain.value,
            limit=20,
        )

        for exp in experiences:
            # 检查是否同源工具
            exp_tool = exp.trigger_context.get("tool", "")
            if exp_tool == trace.tool_name:
                # 检查参数相似度
                exp_params = exp.trigger_context.get("tool_params", {})
                if exp_params and trace.tool_params:
                    # 简单的键集相似度
                    exp_keys = set(exp_params.keys())
                    trace_keys = set(trace.tool_params.keys())
                    if exp_keys and trace_keys:
                        similarity = len(exp_keys & trace_keys) / len(exp_keys | trace_keys)
                        if similarity >= 0.7:
                            return exp
                elif not exp_params and not trace.tool_params:
                    return exp

        return None

    def _merge_into_experience(
        self,
        experience: ExperienceEntry,
        trace: OperationTrace,
        evaluation: Dict[str, Any],
    ) -> None:
        """将新轨迹合并到已有经验中"""
        # 添加源轨迹ID
        if trace.trace_id not in experience.source_trace_ids:
            experience.source_trace_ids.append(trace.trace_id)

        # 更新统计
        sample_count = len(experience.source_trace_ids)
        old_success_rate = experience.metadata.get("success_rate", 0.5)
        new_success = 1.0 if trace.success else 0.0
        experience.metadata["success_rate"] = (
            old_success_rate * (sample_count - 1) + new_success
        ) / sample_count

        experience.metadata["reuse_count"] = experience.metadata.get("reuse_count", 0) + 1
        experience.metadata["last_used"] = trace.timestamp

        # 更新质量评分（加权平均）
        old_score = experience.outcome.get("quality_score", 0.5)
        new_score = evaluation["overall_score"]
        experience.outcome["quality_score"] = (
            old_score * 0.7 + new_score * 0.3
        )

        # 重新计算等级
        experience.grade = self._calculate_grade(
            experience.outcome["quality_score"],
            sample_count,
        )

        experience.updated_at = time.time()

        self._store.add_experience(experience)
        logger.debug("合并到经验: %s (样本数=%d)", experience.experience_id, sample_count)

    # ── 批量评估 ──

    def evaluate_pending(self, limit: int = 100) -> Dict[str, int]:
        """批量评估待处理的轨迹

        Args:
            limit: 最多评估多少条

        Returns:
            统计结果 {evaluated, promoted, skipped, errors}
        """
        traces = self._store.list_traces(limit=limit)
        promoted = 0
        skipped = 0
        errors = 0

        for trace in traces:
            try:
                # 检查是否已经升级过
                existing = self._find_similar_experience(trace)
                if existing and trace.trace_id in existing.source_trace_ids:
                    skipped += 1
                    continue

                result = self.promote_trace(trace)
                if result:
                    promoted += 1
                else:
                    skipped += 1
            except Exception as e:
                errors += 1
                logger.warning("批量评估失败: %s", e)

        return {
            "total": len(traces),
            "promoted": promoted,
            "skipped": skipped,
            "errors": errors,
        }

    # ── 统计信息 ──

    def get_stats(self) -> Dict[str, Any]:
        """获取评估器统计信息"""
        return {
            "evaluator_version": self.VERSION,
            "session_stats": self._stats.copy(),
            "weights": self.WEIGHTS.copy(),
        }


# 模块级默认实例
_default_evaluator: Optional[ExperienceEvaluator] = None
_evaluator_lock = threading.Lock()


def get_experience_evaluator(
    store: Optional[ExperienceStore] = None,
) -> ExperienceEvaluator:
    """获取默认经验评估器实例（单例）"""
    global _default_evaluator
    if _default_evaluator is None:
        with _evaluator_lock:
            if _default_evaluator is None:
                _default_evaluator = ExperienceEvaluator(store=store)
    return _default_evaluator


__all__ = [
    "ExperienceEvaluator",
    "get_experience_evaluator",
]
