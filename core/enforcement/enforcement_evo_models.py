# -*- coding: utf-8-sig -*-
"""执行进化 — 数据模型

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

class TimeWindow(str, Enum):
    MINUTE = "minute"
    HOURLY = "hourly"
    DAILY = "daily"
    WEEKLY = "weekly"


class TrackerMetric(str, Enum):
    COMPLIANCE_RATE = "compliance_rate"
    ERROR_RATE = "error_rate"
    AVG_TOKENS = "avg_tokens"
    CLASS_DISTRIBUTION = "class_distribution"
    MCP_CALL_COUNT = "mcp_call_count"
    FILE_OP_COUNT = "file_op_count"
    DISPATCH_COUNT = "dispatch_count"
    RECORD_RATE = "record_rate"
    ISO_DIMENSION_USAGE = "iso_dimension_usage"
    FAIR_COMPLETENESS = "fair_completeness"


@dataclass
class TimeWindowSnapshot:
    window_type: TimeWindow
    window_start: float
    window_end: float
    metrics: Dict[str, float] = field(default_factory=dict)
    turn_count: int = 0
    session_count: int = 0
    tags: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "window_type": self.window_type.value,
            "window_start": self.window_start,
            "window_end": self.window_end,
            "metrics": self.metrics,
            "turn_count": self.turn_count,
            "session_count": self.session_count,
            "tags": self.tags,
        }


class EvolutionAction(str, Enum):
    NUDGE_DECIDE = "adjust_nudge_decide"
    CLASSIFIER_WEIGHT = "adjust_classifier_weight"
    BUFFER_SIZE = "adjust_buffer_size"
    RECORD_FREQUENCY = "adjust_record_frequency"
    GATE_THRESHOLD = "adjust_gate_threshold"
    ALERT = "send_alert"


@dataclass
class EvolutionProposal:
    action: EvolutionAction
    target_module: str
    current_value: Any
    proposed_value: Any
    reason: str
    confidence: float = 0.5
    evidence: List[str] = field(default_factory=list)
    urgency: float = 0.0
    approved: bool = False
    applied: bool = False
    effect_measured: Optional[float] = None

    def to_dict(self) -> dict:
        return {
            "action": self.action.value,
            "target_module": self.target_module,
            "current_value": self.current_value,
            "proposed_value": self.proposed_value,
            "reason": self.reason,
            "confidence": self.confidence,
            "evidence": self.evidence,
            "urgency": self.urgency,
            "approved": self.approved,
            "applied": self.applied,
            "effect_measured": self.effect_measured,
        }




__all__ = ["TimeWindow", "TrackerMetric", "TimeWindowSnapshot", "EvolutionAction", "EvolutionProposal"]
