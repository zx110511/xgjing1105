# -*- coding: utf-8-sig -*-
"""进化引擎 — 数据模型

从 evolution_engine.py 拆分 (SSS-PhaseB)
"""

import copy
import hashlib
import json
import logging
import sqlite3
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any
try:
    from ..shared.config import MEMORY_DATA_PATH
except ImportError:
    from core.shared.config import MEMORY_DATA_PATH


from typing import Optional

class EvolutionLevel(str, Enum):
    PARAMETER_TUNING = "level_1_parameter_tuning"
    RULE_ADDITION = "level_2_rule_addition"
    ARCHITECTURE_EVOLUTION = "level_3_architecture_evolution"


class EvolutionStatus(str, Enum):
    PROPOSED = "proposed"
    VALIDATED = "validated"
    APPLIED = "applied"
    ROLLED_BACK = "rolled_back"
    REJECTED = "rejected"


@dataclass
class RuleChange:
    rule_name: str
    old_value: Any
    new_value: Any
    level: EvolutionLevel
    reason: str
    confidence: float
    deepseek_validated: bool = False
    deepseek_assessment: str = ""
    change_id: str = ""
    timestamp: float = field(default_factory=time.time)
    status: EvolutionStatus = EvolutionStatus.PROPOSED
    rollback_snapshot: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if not self.change_id:
            raw = f"{self.rule_name}:{self.new_value}:{self.timestamp}"
            self.change_id = hashlib.md5(raw.encode()).hexdigest()[:12]

    def to_dict(self) -> dict:
        return {
            "change_id": self.change_id,
            "rule_name": self.rule_name,
            "old_value": str(self.old_value)[:200],
            "new_value": str(self.new_value)[:200],
            "level": self.level.value,
            "reason": self.reason[:500],
            "confidence": self.confidence,
            "deepseek_validated": self.deepseek_validated,
            "status": self.status.value,
            "timestamp": self.timestamp,
        }


@dataclass
class ArchitectureProposal:
    proposal_id: str
    title: str
    description: str
    current_architecture: str
    proposed_change: str
    expected_benefit: str
    risk_assessment: str
    deepseek_analysis: str
    confidence: float
    requires_human_approval: bool = True
    status: EvolutionStatus = EvolutionStatus.PROPOSED
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return {
            "proposal_id": self.proposal_id,
            "title": self.title,
            "description": self.description[:500],
            "proposed_change": self.proposed_change[:500],
            "expected_benefit": self.expected_benefit[:300],
            "risk_assessment": self.risk_assessment[:300],
            "confidence": self.confidence,
            "requires_human_approval": self.requires_human_approval,
            "status": self.status.value,
        }




__all__ = ["EvolutionLevel", "EvolutionStatus", "RuleChange", "ArchitectureProposal"]
