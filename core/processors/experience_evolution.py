# -*- coding: utf-8-sig -*-
"""经验自动沉淀 - 进化引擎（自进化闭环）

经验生命周期管理: 自动升级 / 自动降级 / 自动淘汰 / 反馈循环。

架构位置: D4悟道域 - 进化处理器
版本: v1.0.0 (Phase 4)

核心功能:
  1. 经验升级 - 高复用+高成功率 → 等级晋升 (D→C→B→A→S)
  2. 经验降级 - 长期未用或成功率下降 → 等级降低
  3. 经验淘汰 - 过期/质量过低/重复冗余 → 归档删除
  4. 反馈循环 - 使用结果回写 → 更新经验置信度和复用计数
  5. 进化调度 - 定期巡检 + 事件触发
"""

from __future__ import annotations

import time
import logging
import threading
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from .experience_models import (
    ExperienceEntry,
    ExperienceDomain,
    PatternType,
    ExperienceGrade,
)
from .experience_store import ExperienceStore, get_experience_store

logger = logging.getLogger(__name__)


@dataclass
class EvolutionResult:
    """进化执行结果"""
    upgraded: List[str] = field(default_factory=list)
    downgraded: List[str] = field(default_factory=list)
    archived: List[str] = field(default_factory=list)
    merged: List[str] = field(default_factory=list)
    total_checked: int = 0
    duration_ms: float = 0.0

    def summary(self) -> str:
        return (
            f"检查 {self.total_checked} 条, "
            f"升级 {len(self.upgraded)}, "
            f"降级 {len(self.downgraded)}, "
            f"淘汰 {len(self.archived)}, "
            f"合并 {len(self.merged)}"
        )


class ExperienceEvolutionEngine:
    """经验进化引擎 - 自进化闭环

    Phase 4 核心功能:
    - 基于数据的自动等级调整
    - 生命周期管理（创建→成长→成熟→衰退→淘汰）
    - 反馈闭环（使用结果→质量重评→等级调整）
    - 定期巡检与事件触发双模式
    """

    VERSION = "1.0.0"

    GRADE_ORDER = ["D", "C", "B", "A", "S"]

    def __init__(
        self,
        store: Optional[ExperienceStore] = None,
        upgrade_reuse_threshold: int = 5,
        upgrade_success_rate: float = 0.8,
        downgrade_unused_days: int = 30,
        downgrade_success_rate: float = 0.4,
        archive_max_age_days: int = 180,
        archive_min_grade: str = "D",
    ) -> None:
        self._store = store or get_experience_store()
        self._upgrade_reuse_threshold = upgrade_reuse_threshold
        self._upgrade_success_rate = upgrade_success_rate
        self._downgrade_unused_days = downgrade_unused_days
        self._downgrade_success_rate = downgrade_success_rate
        self._archive_max_age_days = archive_max_age_days
        self._archive_min_grade = ExperienceGrade(archive_min_grade)
        self._lock = threading.Lock()
        self._stats = {
            "evolution_cycles": 0,
            "total_upgraded": 0,
            "total_downgraded": 0,
            "total_archived": 0,
            "total_merged": 0,
            "last_run_time": 0.0,
        }

        logger.info(
            "ExperienceEvolutionEngine 初始化完成 "
            "(升级阈值: 复用>=%d次 & 成功率>=%.0f%%, "
            "降级阈值: 未用>=%d天 或 成功率<%.0f%%, "
            "淘汰阈值: 超过%d天且等级<=%s)",
            upgrade_reuse_threshold, upgrade_success_rate * 100,
            downgrade_unused_days, downgrade_success_rate * 100,
            archive_max_age_days, archive_min_grade,
        )

    # ── 核心进化循环 ──

    def run_evolution_cycle(self) -> EvolutionResult:
        """执行一次完整的进化循环

        流程:
        1. 扫描所有经验条目
        2. 检查升级条件 → 升级符合条件的
        3. 检查降级条件 → 降级符合条件的
        4. 检查淘汰条件 → 淘汰符合条件的
        5. 检查重复合并 → 合并相似经验
        """
        start = time.time()
        result = EvolutionResult()

        with self._lock:
            try:
                all_exps = self._store.list_experiences(limit=10000)
                result.total_checked = len(all_exps)

                for exp in all_exps:
                    action = self._check_evolution_action(exp)
                    if action == "upgrade":
                        self._do_upgrade(exp)
                        result.upgraded.append(exp.experience_id)
                    elif action == "downgrade":
                        self._do_downgrade(exp)
                        result.downgraded.append(exp.experience_id)
                    elif action == "archive":
                        self._do_archive(exp)
                        result.archived.append(exp.experience_id)

                merged = self._merge_duplicates(all_exps)
                result.merged.extend(merged)

                self._stats["evolution_cycles"] += 1
                self._stats["total_upgraded"] += len(result.upgraded)
                self._stats["total_downgraded"] += len(result.downgraded)
                self._stats["total_archived"] += len(result.archived)
                self._stats["total_merged"] += len(result.merged)
                self._stats["last_run_time"] = time.time()

            except Exception as e:
                logger.error("进化循环执行失败: %s", e)

        result.duration_ms = (time.time() - start) * 1000
        logger.info("进化循环完成: %s (耗时 %.0fms)", result.summary(), result.duration_ms)
        return result

    def _check_evolution_action(self, exp: ExperienceEntry) -> Optional[str]:
        """判断经验应执行的进化动作

        Returns:
            "upgrade" | "downgrade" | "archive" | None
        """
        now = time.time()
        age_days = (now - exp.created_at) / 86400 if exp.created_at > 0 else 0
        last_used = exp.metadata.get("last_used_at", exp.created_at)
        unused_days = (now - last_used) / 86400 if last_used > 0 else age_days

        reuse_count = exp.metadata.get("reuse_count", 0)
        success_rate = exp.metadata.get("success_rate", 0.5)
        confidence = exp.metadata.get("confidence", 0.5)
        quality_score = exp.outcome.get("quality_score", 0.5)

        if self._should_archive(exp, age_days, unused_days, quality_score, confidence):
            return "archive"

        if self._should_upgrade(exp, reuse_count, success_rate, quality_score):
            return "upgrade"

        if self._should_downgrade(exp, unused_days, success_rate, quality_score):
            return "downgrade"

        return None

    def _should_upgrade(
        self,
        exp: ExperienceEntry,
        reuse_count: int,
        success_rate: float,
        quality_score: float,
    ) -> bool:
        """判断是否应该升级"""
        if exp.grade == ExperienceGrade.S:
            return False

        conditions = 0
        total_conditions = 3

        if reuse_count >= self._upgrade_reuse_threshold:
            conditions += 1

        if success_rate >= self._upgrade_success_rate:
            conditions += 1

        if quality_score >= 0.8:
            conditions += 1

        return conditions >= 2 and reuse_count >= 3

    def _should_downgrade(
        self,
        exp: ExperienceEntry,
        unused_days: float,
        success_rate: float,
        quality_score: float,
    ) -> bool:
        """判断是否应该降级"""
        if exp.grade == ExperienceGrade.D:
            return False

        if unused_days >= self._downgrade_unused_days:
            return True

        if success_rate < self._downgrade_success_rate and success_rate > 0:
            return True

        if quality_score < 0.3:
            return True

        return False

    def _should_archive(
        self,
        exp: ExperienceEntry,
        age_days: float,
        unused_days: float,
        quality_score: float,
        confidence: float,
    ) -> bool:
        """判断是否应该淘汰归档"""
        grade_idx = self.GRADE_ORDER.index(exp.grade.value)
        min_grade_idx = self.GRADE_ORDER.index(self._archive_min_grade.value)

        if grade_idx > min_grade_idx:
            return False

        if age_days >= self._archive_max_age_days and unused_days >= self._archive_max_age_days * 0.8:
            return True

        if quality_score < 0.15 and confidence < 0.2:
            return True

        if exp.pattern_type == PatternType.FAILURE_LESSON and quality_score < 0.2:
            if age_days > 90:
                return True

        return False

    # ── 升级 / 降级 / 淘汰 ──

    def _do_upgrade(self, exp: ExperienceEntry) -> None:
        """执行经验升级"""
        idx = self.GRADE_ORDER.index(exp.grade.value)
        if idx >= len(self.GRADE_ORDER) - 1:
            return

        new_grade = ExperienceGrade(self.GRADE_ORDER[idx + 1])
        old_grade = exp.grade
        exp.grade = new_grade
        exp.metadata["upgrade_count"] = exp.metadata.get("upgrade_count", 0) + 1
        exp.metadata["last_upgraded_at"] = time.time()
        exp.updated_at = time.time()

        self._store.add_experience(exp)
        logger.info("经验升级: %s [%s → %s]", exp.experience_id, old_grade.value, new_grade.value)

    def _do_downgrade(self, exp: ExperienceEntry) -> None:
        """执行经验降级"""
        idx = self.GRADE_ORDER.index(exp.grade.value)
        if idx <= 0:
            return

        new_grade = ExperienceGrade(self.GRADE_ORDER[idx - 1])
        old_grade = exp.grade
        exp.grade = new_grade
        exp.metadata["downgrade_count"] = exp.metadata.get("downgrade_count", 0) + 1
        exp.metadata["last_downgraded_at"] = time.time()
        exp.updated_at = time.time()

        self._store.add_experience(exp)
        logger.info("经验降级: %s [%s → %s]", exp.experience_id, old_grade.value, new_grade.value)

    def _do_archive(self, exp: ExperienceEntry) -> None:
        """执行经验淘汰归档

        软删除: 标记为archived，而非物理删除
        """
        exp.metadata["archived"] = True
        exp.metadata["archived_at"] = time.time()
        exp.metadata["archive_reason"] = "evolution_cleanup"
        exp.grade = ExperienceGrade.D
        exp.updated_at = time.time()

        self._store.add_experience(exp)
        logger.info("经验淘汰归档: %s", exp.experience_id)

    # ── 重复合并 ──

    def _merge_duplicates(self, exps: List[ExperienceEntry]) -> List[str]:
        """合并高度相似的重复经验

        策略: 同一领域+同一工具+同一模式类型 → 合并为一条，保留质量高的
        """
        merged_ids: List[str] = []

        groups: Dict[str, List[ExperienceEntry]] = {}
        for exp in exps:
            if exp.metadata.get("archived", False):
                continue
            key = f"{exp.domain.value}|{exp.trigger_context.get('tool', '')}|{exp.pattern_type.value}"
            groups.setdefault(key, []).append(exp)

        for key, group in groups.items():
            if len(group) < 2:
                continue

            group.sort(
                key=lambda e: (
                    self.GRADE_ORDER.index(e.grade.value),
                    e.outcome.get("quality_score", 0),
                    e.metadata.get("reuse_count", 0),
                ),
                reverse=True,
            )

            primary = group[0]
            for dup in group[1:]:
                self._merge_into_primary(primary, dup)
                merged_ids.append(dup.experience_id)
                dup.metadata["archived"] = True
                dup.metadata["archive_reason"] = "merged_into_" + primary.experience_id
                dup.updated_at = time.time()
                self._store.add_experience(dup)

            self._store.add_experience(primary)

        return merged_ids

    def _merge_into_primary(self, primary: ExperienceEntry, dup: ExperienceEntry) -> None:
        """将重复经验合并入主经验"""
        for trace_id in dup.source_trace_ids:
            if trace_id not in primary.source_trace_ids:
                primary.source_trace_ids.append(trace_id)

        primary.metadata["reuse_count"] = (
            primary.metadata.get("reuse_count", 0) + dup.metadata.get("reuse_count", 0)
        )

        dup_succ = dup.metadata.get("success_count", 0)
        dup_total = dup.metadata.get("total_uses", 0)
        prim_succ = primary.metadata.get("success_count", 0)
        prim_total = primary.metadata.get("total_uses", 0)

        total_succ = dup_succ + prim_succ
        total_uses = dup_total + prim_total
        if total_uses > 0:
            primary.metadata["success_rate"] = total_succ / total_uses

        primary.metadata["success_count"] = total_succ
        primary.metadata["total_uses"] = total_uses

        for tag in dup.metadata.get("tags", []):
            if tag not in primary.metadata.get("tags", []):
                primary.metadata.setdefault("tags", []).append(tag)

        primary.metadata["merge_count"] = primary.metadata.get("merge_count", 0) + 1
        primary.updated_at = time.time()

    # ── 反馈循环 ──

    def record_usage_feedback(
        self,
        experience_id: str,
        success: bool,
        duration_ms: float = 0.0,
        feedback_note: str = "",
    ) -> bool:
        """记录经验使用反馈 → 更新质量指标 → 触发生命周期调整

        这是自进化闭环的核心入口：
        每次经验被使用后，调用此方法回写结果，
        引擎自动计算新的成功率、置信度，并判断是否需要等级调整。
        """
        with self._lock:
            exp = self._store.get_experience(experience_id)
            if not exp:
                logger.warning("反馈的经验不存在: %s", experience_id)
                return False

            metadata = exp.metadata
            metadata["reuse_count"] = metadata.get("reuse_count", 0) + 1
            metadata["last_used_at"] = time.time()

            total_uses = metadata.get("total_uses", 0) + 1
            success_count = metadata.get("success_count", 0) + (1 if success else 0)
            metadata["total_uses"] = total_uses
            metadata["success_count"] = success_count
            metadata["success_rate"] = success_count / total_uses if total_uses > 0 else 0.5

            old_conf = metadata.get("confidence", 0.5)
            alpha = 0.1
            new_conf = old_conf * (1 - alpha) + (1.0 if success else 0.0) * alpha
            metadata["confidence"] = max(0.05, min(0.99, new_conf))

            if feedback_note:
                notes = metadata.get("feedback_notes", [])
                notes.append({"time": time.time(), "success": success, "note": feedback_note})
                if len(notes) > 50:
                    notes = notes[-50:]
                metadata["feedback_notes"] = notes

            outcome = exp.outcome
            old_dur = outcome.get("duration_ms", 0)
            old_count = outcome.get("sample_count", 1)
            if duration_ms > 0 and old_dur > 0:
                outcome["duration_ms"] = (old_dur * old_count + duration_ms) / (old_count + 1)
                outcome["sample_count"] = old_count + 1
            elif duration_ms > 0:
                outcome["duration_ms"] = duration_ms
                outcome["sample_count"] = 1

            exp.updated_at = time.time()
            self._store.add_experience(exp)

            action = self._check_evolution_action(exp)
            if action == "upgrade":
                self._do_upgrade(exp)
            elif action == "downgrade":
                self._do_downgrade(exp)

            logger.info(
                "经验反馈记录: %s (成功=%s, 新成功率=%.0f%%, 新置信度=%.2f)",
                experience_id, success,
                metadata["success_rate"] * 100, metadata["confidence"],
            )
            return True

    # ── 主动进化操作 ──

    def promote_experience(self, experience_id: str) -> bool:
        """手动升级经验（管理员/高级用户使用）"""
        with self._lock:
            exp = self._store.get_experience(experience_id)
            if not exp:
                return False
            self._do_upgrade(exp)
            return True

    def demote_experience(self, experience_id: str) -> bool:
        """手动降级经验"""
        with self._lock:
            exp = self._store.get_experience(experience_id)
            if not exp:
                return False
            self._do_downgrade(exp)
            return True

    def archive_experience(self, experience_id: str, reason: str = "manual") -> bool:
        """手动归档经验"""
        with self._lock:
            exp = self._store.get_experience(experience_id)
            if not exp:
                return False
            self._do_archive(exp)
            exp.metadata["archive_reason"] = reason
            self._store.add_experience(exp)
            return True

    # ── 统计信息 ──

    def get_stats(self) -> Dict[str, Any]:
        """获取进化引擎统计信息"""
        store_stats = self._store.get_stats()
        return {
            "evolution_version": self.VERSION,
            "engine_stats": self._stats.copy(),
            "store_stats": store_stats.to_dict(),
            "config": {
                "upgrade_reuse_threshold": self._upgrade_reuse_threshold,
                "upgrade_success_rate": self._upgrade_success_rate,
                "downgrade_unused_days": self._downgrade_unused_days,
                "downgrade_success_rate": self._downgrade_success_rate,
                "archive_max_age_days": self._archive_max_age_days,
                "archive_min_grade": self._archive_min_grade.value,
            },
        }

    def get_lifecycle_distribution(self) -> Dict[str, int]:
        """获取各等级经验分布"""
        distribution: Dict[str, int] = {g: 0 for g in self.GRADE_ORDER}
        distribution["archived"] = 0

        exps = self._store.list_experiences(limit=10000)
        for exp in exps:
            if exp.metadata.get("archived", False):
                distribution["archived"] += 1
            else:
                distribution[exp.grade.value] += 1

        return distribution


_default_engine: Optional[ExperienceEvolutionEngine] = None
_engine_lock = threading.Lock()


def get_evolution_engine(
    store: Optional[ExperienceStore] = None,
) -> ExperienceEvolutionEngine:
    """获取默认进化引擎实例（单例）"""
    global _default_engine
    if _default_engine is None:
        with _engine_lock:
            if _default_engine is None:
                _default_engine = ExperienceEvolutionEngine(store=store)
    return _default_engine


__all__ = [
    "ExperienceEvolutionEngine",
    "EvolutionResult",
    "get_evolution_engine",
]
