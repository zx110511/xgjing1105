# -*- coding: utf-8 -*-
"""
学习闭环桥接器 + 进化闭环桥接器
[SSS-PhaseB] 从engine.py拆分

LearningBridge: 五阶段完全对接ClosedLoopLearningEngine
EvolutionBridge: 连接evolution_engine与LawDomain
"""

import logging
import time
from datetime import datetime
from typing import Any

logger = logging.getLogger("tianji.law_domain")

from .core import EmpiricalLaw, LawDomain, LawPriority


class LearningBridge:
    """
    学习闭环桥接器 v2.0 — 深度集成ClosedLoopLearningEngine

    E4增强: 五阶段完全对接
    ┌─────────────┐    ┌──────────────┐    ┌────────────────┐
    │  EXECUTE     │───→│  EVALUATE    │───→│   EXTRACT      │
    │  (任务执行)   │    │  (复杂度评估) │    │ ↓ 法则挖掘触发  │
    └─────────────┘    └──────────────┘    └────────────────┘
                                                   ↓
    ┌─────────────┐    ┌──────────────┐    ┌────────────────┐
    │  (循环继续)  │←──│   REFLECT    │←──│ CONSOLIDATE    │
    │             │    │  (反思优化)   │    │ ↓ 法则生成+激活 │
    └─────────────┘    └──────────────┘    └────────────────┘
    """

    def __init__(self, law_domain):
        self._domain = law_domain
        self._pending_extractions: list[dict] = []
        self._consolidation_batch: list = []
        self._stats = {
            "tasks_bridged": 0,
            "laws_triggered": 0,
            "reflect_cycles": 0,
            "extract_phase_calls": 0,
            "consolidate_phase_calls": 0,
            "laws_auto_activated": 0,
            "experience_pool_size": 0,
        }

    def on_execute_phase(
        self, task_id: str, agent_id: str, task_description: str
    ) -> str:
        """E4: EXECUTE阶段 — 任务开始时注册监控"""
        task_key = f"{task_id}:{agent_id}:{int(time.time())}"
        logger.debug(f"[学习桥接-EXECUTE] 注册任务: {task_key}")
        return task_key

    def on_evaluate_phase(
        self,
        task_key: str,
        complexity_str: str,
        success: bool,
        error_info: str,
        duration_ms: float,
    ) -> list[EmpiricalLaw] | None:
        """
        E4: EVALUATE阶段 — 复杂度评估后决定是否触发法则挖掘

        触发条件(满足任一即触发):
        1. complexity = critical (无论成功失败)
        2. complexity = complex 且 任务失败
        3. 包含错误信息(error_info非空)
        """
        self._stats["tasks_bridged"] += 1

        should_trigger = (
            complexity_str in ("critical",)
            or (complexity_str in ("complex",) and not success)
            or (bool(error_info.strip()) if error_info else False)
        )

        if not should_trigger:
            logger.debug(
                f"[学习桥接-EVALUATE] {task_key}: 不触发 (complexity={complexity_str}, success={success})"
            )
            return None

        logger.info(
            f"[学习桥接-EVALUATE] {task_key}: 触发法则挖掘 (complexity={complexity_str}, success={success})"
        )

        combined_input = f"任务: {task_key}\n复杂度: {complexity_str}\n成功: {success}"
        if error_info:
            combined_input += f"\n错误信息: {error_info}"
        if duration_ms > 0:
            combined_input += f"\n耗时: {duration_ms}ms"

        laws = self._domain.quick_mine(combined_input)
        self._stats["laws_triggered"] += len(laws)

        # 存入待提取队列
        self._pending_extractions.append({
            "task_key": task_key,
            "complexity": complexity_str,
            "success": success,
            "error": error_info,
            "laws_generated": len(laws),
            "timestamp": time.time(),
        })
        self._stats["extract_phase_calls"] += 1

        return laws

    def on_consolidate_phase(self) -> list[EmpiricalLaw]:
        """E4: CONSOLIDATE阶段 — 批量处理经验并生成法则"""
        self._stats["consolidate_phase_calls"] += 1

        if not self._pending_extractions:
            return []

        # 收集所有待处理的错误信息
        all_inputs = []
        for ext in self._pending_extractions[-20:]:  # 最近20条
            if ext.get("error"):
                all_inputs.append(ext["error"])

        if not all_inputs:
            return []

        combined = "\n---\n".join(all_inputs)
        laws = self._domain.quick_mine(combined)

        # 自动激活高价值法则(评分>=8)
        auto_activated = 0
        for law in laws:
            if law.value_score and law.value_score >= 8:
                self._domain.lifecycle_manager.validate_law(law.law_id)
                self._domain.lifecycle_manager.activate_law(law.law_id)
                auto_activated += 1

        self._stats["laws_auto_activated"] += auto_activated
        logger.info(f"[学习桥接-CONSOLIDATE] 生成{len(laws)}条法则，自动激活{auto_activated}条")

        return laws

    def on_reflect_phase(self, cycle_id: str = "") -> dict:
        """E4: REFLECT阶段 — 反思周期优化"""
        self._stats["reflect_cycles"] += 1

        # 清理过期待提取记录(超过1小时)
        cutoff = time.time() - 3600
        before = len(self._pending_extractions)
        self._pending_extractions = [
            e for e in self._pending_extractions if e.get("timestamp", 0) > cutoff
        ]
        cleaned = before - len(self._pending_extractions)

        report = {
            "cycle_id": cycle_id or f"reflect-{int(time.time())}",
            "reflected_at": datetime.now().isoformat(),
            "pending_cleaned": cleaned,
            "remaining_pending": len(self._pending_extractions),
            "reflect_count": self._stats["reflect_cycles"],
            "pending_extractions_cleaned": cleaned,
            "total_auto_activated": self._stats["laws_auto_activated"],
            "bridge_stats": dict(self._stats),
        }

        logger.info(f"[学习桥接-REFLECT] {cycle_id}: 完成 - {report}")
        return report

    def get_integration_status(self) -> dict:
        """获取学习闭环集成状态概览"""
        return {
            "learning_bridge_version": "2.0",
            "supported_phases": ["EXECUTE", "EVALUATE", "EXTRACT", "CONSOLIDATE", "REFLECT"],
            "stats": dict(self._stats),
            "pool_status": {
                "pending_extractions": len(self._pending_extractions),
                "consolidation_batch_size": len(self._consolidation_batch),
                "last_activity": self._pending_extractions[-1]["timestamp"]
                if self._pending_extractions else None,
            },
            "config": {
                "auto_activate_threshold": 8.0,
                "consolidate_batch_size": 10,
                "max_pool_size": 100,
            },
        }

    def get_stats(self) -> dict:
        return dict(self._stats)


class EvolutionBridge:
    """
    进化闭环桥接器 — 将evolution_engine与LawDomain连接

    连接点:
    - evolution_engine Level-2 RULE_ADDITION → LawDomain.validate+activate
    - evolution_engine Level-1 PARAMETER_TUNING → LawDomain.optimize active laws
    - 定期进化审查 → 废弃过时法则 + 升级活跃法则
    """

    def __init__(self, law_domain):
        self._domain = law_domain
        self._stats = {
            "evolution_cycles": 0,
            "laws_optimized": 0,
            "laws_deprecated": 0,
            "new_rules_added": 0,
        }

    def on_evolution_cycle(self, evolution_data: dict = None) -> dict:
        """执行一轮进化审查"""
        self._stats["evolution_cycles"] += 1
        results = {"optimized": 0, "deprecated": 0, "activated": 0}

        active_laws = self._domain.lifecycle_manager.get_active_laws()

        # 升级高频使用的法则
        for law in active_laws:
            if law.activation_count and law.activation_count > 100:
                if self._should_upgrade(law):
                    law.version += 1
                    law.last_optimized_at = datetime.now().isoformat()
                    results["optimized"] += 1

        # 废弃过时法则(90天未优化且低频)
        deprecated_candidates = [
            l
            for l in active_laws
            if l.meta.get("created_at", "")
            and self._days_since(l.meta["created_at"]) > 90
        ]
        for law in deprecated_candidates:
            self._domain.lifecycle_manager.deactivate_law(
                law.law_id, reason="90天未优化且低频使用"
            )
            results["deprecated"] += 1

        self._stats["laws_optimized"] += results["optimized"]
        self._stats["laws_deprecated"] += results["deprecated"]
        return results

    def _should_upgrade(self, law: EmpiricalLaw) -> bool:
        return law.activation_count % 50 == 0 if law.activation_count else False

    def _days_since(self, iso_date: str) -> int:
        try:
            dt = datetime.fromisoformat(iso_date)
            return (datetime.now() - dt).days
        except (ValueError, TypeError):
            return 999

    def get_stats(self) -> dict:
        return dict(self._stats)
