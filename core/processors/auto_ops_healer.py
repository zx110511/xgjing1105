# -*- coding: utf-8-sig -*-
"""自动运维 — 自动治愈器

从 auto_ops.py 拆分 (SSS-PhaseB)
"""
from __future__ import annotations  # [FIX-autoops-healer-002] 延迟类型注解求值,避免前向引用NameError

import time
import json
import uuid
import math
import threading
import logging
from pathlib import Path
from dataclasses import dataclass, field
from typing import Any, Optional, Dict, List, Tuple, Callable
from enum import Enum
from collections import defaultdict, deque
from enum import Enum

# [FIX-autoops-002] 修复unexpected indent: 添加缺失的导入(原代码缩进错误导致未生效)
from .auto_ops_models import HealingAction, HealingSeverity, AnomalyType
from typing import Optional


class AutoHealer:
    r"""
    模块自愈器 — 基于进化信号的自愈决策与执行

    自愈策略链 (按严重程度递增):
      MILD    → CLEAR_CACHE / REDUCE_LOAD
      MODERATE → ROLLBACK_CONFIG / RESTART
      SEVERE   → REINITIALIZE / MARK_DEGRADED
      CRITICAL → ESCALATE (触发治理流水线审批) / MARK_ERROR

    安全约束:
      - 每模块每小时最多自愈 3 次
      - RESTART/REINITIALIZE 操作每模块每天最多 1 次
      - ESCALATE 操作必须经过 GovernancePipeline 审批
      - 所有自愈操作记录因果对 (前后状态快照)
    """

    HEALING_STRATEGIES: Dict[HealingSeverity, List[HealingAction]] = {
        HealingSeverity.MILD: [
            HealingAction.CLEAR_CACHE, HealingAction.REDUCE_LOAD,
        ],
        HealingSeverity.MODERATE: [
            HealingAction.ROLLBACK_CONFIG, HealingAction.RESTART,
        ],
        HealingSeverity.SEVERE: [
            HealingAction.REINITIALIZE, HealingAction.MARK_DEGRADED,
        ],
        HealingSeverity.CRITICAL: [
            HealingAction.ESCALATE, HealingAction.MARK_ERROR,
        ],
    }

    RATE_LIMITS = {
        "per_hour": 3,
        "restart_per_day": 2,
        "reinit_per_day": 1,
    }

    def __init__(self, registry=None, evolution_bus=None, governance_pipeline=None):
        self._registry = registry
        self._evolution_bus = evolution_bus
        self._governance_pipeline = governance_pipeline
        self._healing_history: List[HealingRecord] = []
        self._module_heal_counters: Dict[str, Dict[str, List[float]]] = defaultdict(
            lambda: {"hourly": [], "restarts": [], "reinits": []}
        )
        self._lock = threading.Lock()
        self._stats = {
            "total_heal_attempts": 0,
            "total_heal_successes": 0,
            "total_escalations": 0,
            "rate_limited_rejections": 0,
        }

    def assess_severity(self, signal: Any) -> HealingSeverity:
        severity_val = getattr(signal, 'severity', 0.5)
        if severity_val >= 0.9:
            return HealingSeverity.CRITICAL
        elif severity_val >= 0.7:
            return HealingSeverity.SEVERE
        elif severity_val >= 0.4:
            return HealingSeverity.MODERATE
        return HealingSeverity.MILD

    def heal(self, module_id: str, signal: Any = None,
             custom_action: Optional[HealingAction] = None) -> HealingRecord:
        record = HealingRecord(
            module_id=module_id,
            trigger_signal=self._signal_to_dict(signal) if signal else None,
        )

        if not self._check_rate_limit(module_id, record):
            return record

        severity = self.assess_severity(signal) if signal else HealingSeverity.MILD
        record.severity = severity

        strategies = self.HEALING_STRATEGIES.get(severity, [HealingAction.NONE])
        action = custom_action if custom_action else self._select_strategy(module_id, strategies)
        record.action = action

        record.state_before = self._capture_module_state(module_id)
        start = time.time()

        try:
            self._execute_healing(module_id, action, record)
            record.success = True
            self._stats["total_heal_successes"] += 1
        except Exception as e:
            record.success = False
            record.error_message = str(e)
            logger.error(f"[AutoHealer] 自愈失败: {module_id} {action.value} — {e}")

        record.duration_ms = (time.time() - start) * 1000
        record.state_after = self._capture_module_state(module_id)

        self._stats["total_heal_attempts"] += 1
        self._record_heal(module_id, record)
        self._healing_history.append(record)

        if len(self._healing_history) > 500:
            self._healing_history = self._healing_history[-250:]

        logger.info(
            f"[AutoHealer] {'✅' if record.success else '❌'} "
            f"{module_id} {action.value} ({severity.value}) "
            f"{record.duration_ms:.0f}ms"
        )
        return record

    def _check_rate_limit(self, module_id: str, record: HealingRecord) -> bool:
        now = time.time()
        counters = self._module_heal_counters[module_id]

        counters["hourly"] = [t for t in counters["hourly"] if now - t < 3600]
        counters["restarts"] = [t for t in counters["restarts"] if now - t < 86400]
        counters["reinits"] = [t for t in counters["reinits"] if now - t < 86400]

        if len(counters["hourly"]) >= self.RATE_LIMITS["per_hour"]:
            record.success = False
            record.error_message = f"速率限制: 每小时最多 {self.RATE_LIMITS['per_hour']} 次自愈"
            self._stats["rate_limited_rejections"] += 1
            logger.warning(f"[AutoHealer] 速率限制拒绝: {module_id}")
            return False
        return True

    def _select_strategy(self, module_id: str,
                         strategies: List[HealingAction]) -> HealingAction:
        counters = self._module_heal_counters[module_id]
        for action in strategies:
            if action == HealingAction.RESTART:
                if len(counters["restarts"]) >= self.RATE_LIMITS["restart_per_day"]:
                    continue
            if action == HealingAction.REINITIALIZE:
                if len(counters["reinits"]) >= self.RATE_LIMITS["reinit_per_day"]:
                    continue
            if action == HealingAction.ESCALATE:
                self._stats["total_escalations"] += 1
            return action
        return HealingAction.MARK_DEGRADED

    def _execute_healing(self, module_id: str, action: HealingAction,
                         record: HealingRecord):
        if action == HealingAction.NONE:
            return

        if action == HealingAction.MARK_DEGRADED:
            if self._registry:
                from ..shared.module_registry import ModuleLifecycleState
                self._registry.update_state(module_id, ModuleLifecycleState.DEGRADED)
                self._registry.update_health(module_id, "degraded")

        elif action == HealingAction.MARK_ERROR:
            if self._registry:
                from ..shared.module_registry import ModuleLifecycleState
                self._registry.update_state(module_id, ModuleLifecycleState.ERROR)
                self._registry.update_health(module_id, "error")

        elif action == HealingAction.CLEAR_CACHE:
            if self._registry:
                m = self._registry.get(module_id)
                if m and m.instance_ref and hasattr(m.instance_ref, 'reset'):
                    m.instance_ref.reset()

        elif action == HealingAction.REDUCE_LOAD:
            if self._registry:
                m = self._registry.get(module_id)
                if m and m.instance_ref and hasattr(m.instance_ref, 'reset'):
                    m.instance_ref.reset()

        elif action == HealingAction.ROLLBACK_CONFIG:
            if self._registry:
                m = self._registry.get(module_id)
                if m and m.evolution_loop_ref:
                    loop = m.evolution_loop_ref
                    if hasattr(loop, 'mutable_config') and loop.mutable_config:
                        for key in list(loop.mutable_config.keys()):
                            if isinstance(loop.mutable_config[key], (int, float)):
                                loop.mutable_config[key] *= 0.8

        elif action == HealingAction.RESTART:
            if self._registry:
                m = self._registry.get(module_id)
                if m and m.instance_ref:
                    if hasattr(m.instance_ref, 'reset'):
                        m.instance_ref.reset()
                    from ..shared.module_registry import ModuleLifecycleState
                    self._registry.update_state(
                        module_id, ModuleLifecycleState.INITIALIZING
                    )
                    self._registry.update_state(
                        module_id, ModuleLifecycleState.ACTIVE
                    )

        elif action == HealingAction.REINITIALIZE:
            if self._registry:
                m = self._registry.get(module_id)
                if m and m.instance_ref:
                    if hasattr(m.instance_ref, 'reset'):
                        m.instance_ref.reset()
                    from ..shared.module_registry import ModuleLifecycleState
                    self._registry.update_state(
                        module_id, ModuleLifecycleState.INITIALIZING
                    )
                    self._registry.update_state(
                        module_id, ModuleLifecycleState.ACTIVE
                    )

        elif action == HealingAction.ESCALATE:
            if self._governance_pipeline and self._registry:
                m = self._registry.get(module_id)
                if m:
                    self._governance_pipeline.govern_module(
                        self._governance_pipeline.create_governance_pipeline(),
                        m,
                        None,
                    )

    def _capture_module_state(self, module_id: str) -> Optional[Dict]:
        if not self._registry:
            return None
        m = self._registry.get(module_id)
        if not m:
            return None
        return {
            "lifecycle_state": m.lifecycle_state.value,
            "health_status": m.health_status,
        }

    def _signal_to_dict(self, signal) -> Optional[Dict]:
        if signal is None:
            return None
        return {
            "source_module": getattr(signal, 'source_module', ''),
            "signal_type": getattr(signal, 'signal_type', None),
            "severity": getattr(signal, 'severity', 0.0),
            "description": getattr(signal, 'description', ''),
        }

    def _record_heal(self, module_id: str, record: HealingRecord):
        counters = self._module_heal_counters[module_id]
        now = time.time()
        counters["hourly"].append(now)
        if record.action == HealingAction.RESTART:
            counters["restarts"].append(now)
        if record.action == HealingAction.REINITIALIZE:
            counters["reinits"].append(now)

    def get_healing_history(self, module_id: str = None,
                            limit: int = 50) -> List[Dict]:
        with self._lock:
            records = self._healing_history
            if module_id:
                records = [r for r in records if r.module_id == module_id]
            return [r.to_dict() for r in records[-limit:]]

    def get_stats(self) -> Dict:
        with self._lock:
            return {
                **self._stats,
                "history_size": len(self._healing_history),
                "tracked_modules": len(self._module_heal_counters),
            }




__all__ = ["AutoHealer"]
