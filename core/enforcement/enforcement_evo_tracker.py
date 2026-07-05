# -*- coding: utf-8-sig -*-
"""执行进化 — 追踪器

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

class EnforcementTracker:
    """
    Level 1 — 长久追踪引擎
    从ConversationRegistry采集指标 → 多时间窗口聚合 → 持久化到天机L5
    """

    def __init__(self, registry=None, memory_engine=None):
        self._registry = registry
        self._memory_engine = memory_engine
        self._lock = threading.Lock()
        self._snapshots: Dict[TimeWindow, List[TimeWindowSnapshot]] = {
            w: [] for w in TimeWindow
        }
        self._trends: Dict[str, List[float]] = defaultdict(list)
        self._last_snapshot_time: Dict[TimeWindow, float] = {
            w: 0.0 for w in TimeWindow
        }
        self._total_turns_since_last: int = 0
        self._running = True

    def set_registry(self, registry):
        self._registry = registry

    def set_memory_engine(self, engine):
        self._memory_engine = engine

    def collect_metrics(self, registry_stats: dict) -> Dict[str, float]:
        metrics = {}
        metrics[TrackerMetric.COMPLIANCE_RATE.value] = registry_stats.get("compliance_rate", 0.0)
        metrics[TrackerMetric.ERROR_RATE.value] = registry_stats.get("error_rate", 0.0)
        metrics[TrackerMetric.RECORD_RATE.value] = registry_stats.get("record_rate", 0.0)
        metrics[TrackerMetric.MCP_CALL_COUNT.value] = registry_stats.get("mcp_calls_total", 0.0)
        metrics[TrackerMetric.DISPATCH_COUNT.value] = registry_stats.get("total_dispatches", 0.0)
        return metrics

    def snapshot(self, window: TimeWindow) -> Optional[TimeWindowSnapshot]:
        now = time.time()
        with self._lock:
            interval = self._window_seconds(window)
            if now - self._last_snapshot_time.get(window, 0.0) < interval * 0.8:
                return None
            reg_stats = {}
            if self._registry:
                try:
                    reg_stats = self._registry.get_stats()
                except Exception:
                    pass
            metrics = self.collect_metrics(reg_stats)
            snap = TimeWindowSnapshot(
                window_type=window,
                window_start=now - interval,
                window_end=now,
                metrics=metrics,
                turn_count=self._get_turn_count(),
                session_count=reg_stats.get("active_sessions", 0),
            )
            self._snapshots[window].append(snap)
            if len(self._snapshots[window]) > 100:
                self._snapshots[window] = self._snapshots[window][-100:]
            self._last_snapshot_time[window] = now
            self._update_trends(metrics)
            return snap

    def _window_seconds(self, window: TimeWindow) -> float:
        return {
            TimeWindow.MINUTE: 60,
            TimeWindow.HOURLY: 3600,
            TimeWindow.DAILY: 86400,
            TimeWindow.WEEKLY: 604800,
        }.get(window, 3600)

    def _get_turn_count(self) -> int:
        if self._registry:
            try:
                return self._registry._total_turns
            except Exception:
                pass
        return 0

    def _update_trends(self, metrics: Dict[str, float]):
        for key, val in metrics.items():
            self._trends[key].append(val)
            if len(self._trends[key]) > 500:
                self._trends[key] = self._trends[key][-500:]

    def get_trend(self, metric: str, window_size: int = 10) -> List[float]:
        return self._trends.get(metric, [])[-window_size:]

    def get_trend_direction(self, metric: str, window_size: int = 5) -> str:
        vals = self.get_trend(metric, window_size)
        if len(vals) < 3:
            return "insufficient_data"
        first_half = sum(vals[:len(vals)//2]) / max(len(vals)//2, 1)
        second_half = sum(vals[len(vals)//2:]) / max(len(vals) - len(vals)//2, 1)
        diff = second_half - first_half
        if abs(diff) < 0.01:
            return "stable"
        return "improving" if diff > 0 else "degrading"

    def get_snapshot_report(self, window: TimeWindow, limit: int = 10) -> List[dict]:
        snaps = self._snapshots.get(window, [])[-limit:]
        return [s.to_dict() for s in snaps]

    def persist_to_memory(self):
        if not self._memory_engine:
            return
        try:
            report = {
                "type": "enforcement_tracker_snapshot",
                "timestamp": time.time(),
                "trends": {k: v[-50:] for k, v in self._trends.items()},
                "latest_hourly": self._snapshots.get(TimeWindow.HOURLY, [])[-1:],
                "latest_daily": self._snapshots.get(TimeWindow.DAILY, [])[-1:],
            }
            self._memory_engine.remember(
                content=json.dumps(report, ensure_ascii=False, default=str),
                layer="meta",
                tags=["enforcement_tracker", "auto_snapshot"],
                priority="medium",
            )
        except Exception as e:
            logger.warning(f"Tracker persist failed: {e}")

    def get_status_summary(self) -> Dict:
        return {
            "snapshot_counts": {w.value: len(v) for w, v in self._snapshots.items()},
            "trended_metrics": len(self._trends),
            "compliance_trend": self.get_trend_direction(TrackerMetric.COMPLIANCE_RATE.value),
            "error_trend": self.get_trend_direction(TrackerMetric.ERROR_RATE.value),
        }




__all__ = ["EnforcementTracker"]
