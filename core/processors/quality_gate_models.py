# -*- coding: utf-8-sig -*-
"""质量门禁 — 数据模型

从 quality_gate.py 拆分 (SSS-PhaseB)
"""

import threading
import time
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple
from ..shared.config import DEFAULT_CONFIG, QualityGateConfig
from .gate import (
    PLUGIN_INFO,
    LocalGateStrategy,
    NoiseFilter,
    PolicyEngine,
    RemoteGateStrategy,
)
from .gate.noise_filter import (
    char_ngrams,
    has_semantic_overlap,
    longest_common_substring,
)
from ..shared.protocols import (
    GateResult as ProtocolGateResult,
)
from ..shared.protocols import (
    GateVerdict as ProtocolGateVerdict,
)
from ..shared.protocols import (
    IGatePolicy,
    IGateStrategy,
)
try:
    from .processors.conflict_resolver import (
        ConflictResolver,
        ResolutionVerdict,
    )
    from .processors.preference_drift_detector import PreferenceDriftDetector
except ImportError:
    ConflictResolver = None
    ResolutionVerdict = None
    PreferenceDriftDetector = None
try:
    from .evolution_loop import EvolutionLoop
except ImportError:
    EvolutionLoop = None


from typing import Dict

class GateVerdict(str, Enum):
    """门禁判决 (v9.1 兼容枚举, 小写值)  [v10-ready]

    保留小写值以兼容现有调用方 (engine/writer 以 ``== "reject"`` 比较)。
    v10 标准枚举见 core.shared.protocols.GateVerdict (大写值)。
    """

    PASS = "pass"
    DOWNGRADE = "downgrade"
    REJECT = "reject"
    CONFLICT = "conflict"
    PENDING_UPSTREAM = "pending_upstream"


@dataclass
class GateResult:
    """门禁判决富结果 (v9.1 兼容载体)  [v10-ready]

    保留 target_layer/conflicts_with/quality_dimensions 等字段，
    供 engine/writer 等既有调用方直接消费，不破坏 v9.1 行为。
    """

    verdict: GateVerdict
    target_layer: str
    reason: str
    adjustments: Dict[str, Any] = field(default_factory=dict)
    conflicts_with: List[str] = field(default_factory=list)
    suggested_upstream: Optional[str] = None
    quality_dimensions: Dict[str, float] = field(default_factory=dict)




__all__ = ["GateVerdict", "GateResult"]
