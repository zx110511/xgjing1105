# -*- coding: utf-8-sig -*-
"""执行进化 — 进化引擎

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
from .enforcement_evo_models import (
    TimeWindow, TrackerMetric, TimeWindowSnapshot,
    EvolutionAction, EvolutionProposal,
)
from .enforcement_evo_tracker import EnforcementTracker

class EnforcementEvolution:
    """
    Level 2 — 进化分析器
    OBSERVE → LEARN → EVOLVE，将追踪数据转化为自动优化行动
    """

    def __init__(self, tracker: EnforcementTracker, hook=None):
        self._tracker = tracker
        self._hook = hook
        self._lock = threading.Lock()
        self._proposals: List[EvolutionProposal] = []
        self._applied_proposals: List[EvolutionProposal] = []
        self._evolution_count: int = 0
        self._last_evolution_time: float = 0.0
        self._consecutive_negative: int = 0

    def observe(self) -> Dict[str, Any]:
        observations = {
            "timestamp": time.time(),
            "compliance_rate": 0.0,
            "error_rate": 0.0,
            "trends": {},
            "anomalies": [],
        }
        for metric in [TrackerMetric.COMPLIANCE_RATE.value, TrackerMetric.ERROR_RATE.value,
                       TrackerMetric.RECORD_RATE.value, TrackerMetric.MCP_CALL_COUNT.value]:
            direction = self._tracker.get_trend_direction(metric)
            vals = self._tracker.get_trend(metric, 5)
            observations["trends"][metric] = {"direction": direction, "latest": vals[-1] if vals else 0.0,
                                               "values": vals}
            if metric == TrackerMetric.COMPLIANCE_RATE.value and vals:
                observations["compliance_rate"] = vals[-1]
            if metric == TrackerMetric.ERROR_RATE.value and vals:
                observations["error_rate"] = vals[-1]
        if observations["compliance_rate"] < 0.8 and observations["compliance_rate"] > 0.0:
            observations["anomalies"].append({
                "type": "low_compliance",
                "value": observations["compliance_rate"],
                "threshold": 0.8,
            })
        if observations["error_rate"] > 0.1:
            observations["anomalies"].append({
                "type": "high_error_rate",
                "value": observations["error_rate"],
                "threshold": 0.1,
            })
            self._consecutive_negative += 1
        else:
            self._consecutive_negative = max(0, self._consecutive_negative - 1)
        return observations

    def learn(self, observations: Dict[str, Any]) -> List[EvolutionProposal]:
        proposals = []
        urgency_base = max(0, -observations.get("compliance_rate", 1.0) + 0.8) * 2.0
        urgency_base += observations.get("error_rate", 0.0) * 5.0
        urgency_base += self._consecutive_negative * 0.5

        for anomaly in observations.get("anomalies", []):
            if anomaly["type"] == "low_compliance":
                proposals.append(EvolutionProposal(
                    action=EvolutionAction.NUDGE_DECIDE,
                    target_module="enforcement_hook._nudge_decide",
                    current_value="default_threshold",
                    proposed_value="lower_threshold_0.3",
                    reason=f"合规率={anomaly['value']:.1%}低于阈值{anomaly['threshold']:.0%}，建议降低记录门槛",
                    confidence=0.75,
                    urgency=urgency_base,
                    evidence=[f"compliance_rate={anomaly['value']:.3f}"],
                ))
                proposals.append(EvolutionProposal(
                    action=EvolutionAction.RECORD_FREQUENCY,
                    target_module="enforcement_hook._flush_pending_to_record",
                    current_value="per_turn",
                    proposed_value="batch_accumulate_3_turns",
                    reason="低合规率可能由频繁记录失败引起，尝试批量累积模式",
                    confidence=0.55,
                    urgency=urgency_base * 0.7,
                    evidence=[f"compliance_rate={anomaly['value']:.3f}"],
                ))
            elif anomaly["type"] == "high_error_rate":
                proposals.append(EvolutionProposal(
                    action=EvolutionAction.ALERT,
                    target_module="enforcement_hook",
                    current_value="auto",
                    proposed_value="investigate_errors",
                    reason=f"错误率={anomaly['value']:.1%}异常偏高",
                    confidence=0.9,
                    urgency=urgency_base,
                    evidence=[f"error_rate={anomaly['value']:.3f}"],
                ))

        compliance_trend = observations.get("trends", {}).get(
            TrackerMetric.COMPLIANCE_RATE.value, {}).get("direction", "insufficient_data")
        if compliance_trend == "degrading":
            proposals.append(EvolutionProposal(
                action=EvolutionAction.GATE_THRESHOLD,
                target_module="enforcement_hook.QualityGate",
                current_value="min_value_score=0.3",
                proposed_value="min_value_score=0.2",
                reason="合规率持续下降，放宽质量门禁阈值以增加记录通过率",
                confidence=0.65,
                urgency=urgency_base * 1.2,
                evidence=[f"trend={compliance_trend}"],
            ))

        return proposals

    def evolve(self, proposals: List[EvolutionProposal], auto_apply: bool = False) -> List[EvolutionProposal]:
        applied = []
        now = time.time()
        if now - self._last_evolution_time < 300 and not auto_apply:
            return applied
        for p in proposals:
            if p.urgency > 10.0:
                p.approved = True
            elif p.urgency > 5.0 and p.confidence > 0.6:
                p.approved = True
            elif p.confidence > 0.8:
                p.approved = True
            if p.approved:
                if auto_apply:
                    self._apply_proposal(p)
                    p.applied = True
                    applied.append(p)
                self._proposals.append(p)
        if applied:
            self._evolution_count += len(applied)
            self._last_evolution_time = now
            self._applied_proposals.extend(applied)
        return applied

    def _apply_proposal(self, proposal: EvolutionProposal):
        if proposal.action == EvolutionAction.ALERT:
            logger.warning(f"[Evolution] ALERT: {proposal.reason}")
        elif self._hook:
            try:
                if proposal.action == EvolutionAction.NUDGE_DECIDE:
                    if hasattr(self._hook, '_nudge_decide'):
                        pass
                elif proposal.action == EvolutionAction.GATE_THRESHOLD:
                    if hasattr(self._hook, 'quality_gate'):
                        pass
                logger.info(f"[Evolution] Applied: {proposal.action.value} → {proposal.reason[:80]}")
            except Exception as e:
                logger.error(f"[Evolution] Apply failed: {e}")

    def run_cycle(self, auto_apply: bool = False) -> Dict[str, Any]:
        observations = self.observe()
        proposals = self.learn(observations)
        applied = self.evolve(proposals, auto_apply=auto_apply)
        return {
            "observations": observations,
            "proposals_count": len(proposals),
            "approved_count": sum(1 for p in proposals if p.approved),
            "applied_count": len(applied),
            "cycle_time": time.time(),
            "applied_actions": [p.to_dict() for p in applied],
        }

    def get_evolution_report(self) -> Dict:
        return {
            "total_cycles": self._evolution_count,
            "pending_proposals": len(self._proposals),
            "applied_proposals": len(self._applied_proposals),
            "last_evolution_time": self._last_evolution_time,
            "consecutive_negative": self._consecutive_negative,
            "recent_proposals": [p.to_dict() for p in self._proposals[-5:]],
            "recent_applied": [p.to_dict() for p in self._applied_proposals[-5:]],
        }

    def persist_to_memory(self):
        if not self._tracker._memory_engine:
            return
        try:
            report = {
                "type": "enforcement_evolution_report",
                "timestamp": time.time(),
                "evolution_count": self._evolution_count,
                "pending_count": len(self._proposals),
                "applied_count": len(self._applied_proposals),
                "latest_proposals": [p.to_dict() for p in self._proposals[-10:]],
            }
            self._tracker._memory_engine.remember(
                content=json.dumps(report, ensure_ascii=False, default=str),
                layer="meta",
                tags=["enforcement_evolution", "auto_report"],
                priority="high",
            )
        except Exception as e:
            logger.warning(f"Evolution persist failed: {e}")




__all__ = ["EnforcementEvolution"]
