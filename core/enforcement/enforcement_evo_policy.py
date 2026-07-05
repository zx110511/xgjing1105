# -*- coding: utf-8-sig -*-
"""执行进化 — 自适应记录策略

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
from .enforcement_evo_alignment import ConsumerProfile, ADAPTIVE_FIELD_WEIGHTS

class AdaptiveRecordingPolicy:
    """
    适应性录入策略 — 基于下游消费模块需求动态调整录入行为

    核心原则: 录入行为不是固定的，而是根据"谁在消费这些数据"自适应调整。
    每个消费模块有独立的 required_fields + nice_to_have + preferred_layer + batch_size。

    三阶自适应:
      1. Consumer-Aware: 根据活跃消费者决定录入哪些字段(required vs nice_to_have)
      2. Load-Aware: 根据系统负载决定batch_size(低负载逐条/高负载批量)
      3. Feedback-Aware: 根据消费模块反馈调整字段权重(冷字段降权/热字段升权)
    """

    def __init__(self):
        self._active_consumers: List[ConsumerProfile] = list(ConsumerProfile)
        self._consumer_health: Dict[ConsumerProfile, float] = {c: 1.0 for c in ConsumerProfile}
        self._field_demand: Dict[str, float] = {}
        self._recompute_field_demand()

    def set_active_consumers(self, consumers: List[ConsumerProfile]):
        self._active_consumers = consumers
        self._recompute_field_demand()

    def update_consumer_health(self, profile: ConsumerProfile, health: float):
        self._consumer_health[profile] = max(0.0, min(1.0, health))
        self._recompute_field_demand()

    def _recompute_field_demand(self):
        self._field_demand = {}
        for field, weights in ADAPTIVE_FIELD_WEIGHTS.items():
            total = 0.0
            count = 0
            for profile in self._active_consumers:
                w = weights.get(profile, 0.1)
                h = self._consumer_health.get(profile, 1.0)
                total += w * h
                count += 1
            self._field_demand[field] = total / max(count, 1) if count > 0 else 0.0

    def get_required_fields(self) -> List[str]:
        return [f for f, d in self._field_demand.items() if d >= 0.5]

    def get_nice_to_have_fields(self) -> List[str]:
        return [f for f, d in self._field_demand.items() if 0.2 <= d < 0.5]

    def get_skip_fields(self) -> List[str]:
        return [f for f, d in self._field_demand.items() if d < 0.2]

    def get_preferred_layer(self) -> str:
        layer_votes = {}
        for profile in self._active_consumers:
            req = CONSUMER_REQUIREMENTS.get(profile, {})
            layer = req.get("preferred_layer", "episodic")
            layer_votes[layer] = layer_votes.get(layer, 0) + self._consumer_health.get(profile, 1.0)
        if not layer_votes:
            return "episodic"
        return max(layer_votes, key=layer_votes.get)

    def get_adaptive_batch_size(self) -> int:
        sizes = []
        for profile in self._active_consumers:
            req = CONSUMER_REQUIREMENTS.get(profile, {})
            sizes.append(req.get("batch_size", 1))
        if not sizes:
            return 1
        return max(1, int(sum(sizes) / len(sizes)))

    def get_min_content_length(self) -> int:
        lengths = []
        for profile in self._active_consumers:
            req = CONSUMER_REQUIREMENTS.get(profile, {})
            lengths.append(req.get("min_content_length", 30))
        if not lengths:
            return 30
        return max(lengths)

    def should_record_field(self, field_name: str) -> bool:
        return self._field_demand.get(field_name, 0.0) >= 0.2

    def get_policy_summary(self) -> Dict:
        return {
            "active_consumers": [c.value for c in self._active_consumers],
            "consumer_health": {k.value: v for k, v in self._consumer_health.items()},
            "field_demand": {k: round(v, 3) for k, v in self._field_demand.items()},
            "required_fields": self.get_required_fields(),
            "nice_to_have_fields": self.get_nice_to_have_fields(),
            "skip_fields": self.get_skip_fields(),
            "preferred_layer": self.get_preferred_layer(),
            "batch_size": self.get_adaptive_batch_size(),
            "min_content_length": self.get_min_content_length(),
        }

__all__ = ["AdaptiveRecordingPolicy"]
