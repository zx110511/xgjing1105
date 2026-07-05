r"""
天机进化闭环协议 (Tianji Evolution Loop Protocol) v9.1
========================================================
让天机的每个模块都具备 OBSERVE → LEARN → EVOLVE 闭环能力。

v1.1: 新增 CausalPairRecorder — 独立因果对记录器 (M6模块)
v1.2: M9 进化闭环协议精调 — urgency公式对齐 max(0,-eff)*2.0 + 阈值5.0/10.0 + _consecutive_negative<0
v9.1: M35 EvolutionBus — 进化总线自闭环 + health() + record_action() + 双注入

灵境道谱溯源: D3-4【模式发现煞】· 道三·进化体道 · 四地煞之化之术
  - 跨模块信号路由模式发现+进化信号广播联动+ROUTING_TABLE自适应调节
灵境道谱溯源: D6-3【事件总线煞】· 道六·容器体道 · 四地煞之容之术
  - 模块注册/注销事件总线+signal_history FIFO归档+500条滑动窗口
  - 源文件: core/evolution_loop.py → EvolutionBus

设计哲学:
  不是为每个模块写一套独立的进化逻辑，
  而是定义一套统一的"进化骨架"，每个模块只需实现3个接口:
    1. observe()  — 观测自身运行效果
    2. learn()    — 从观测中提炼知识
    3. evolve()   — 基于知识修改自身行为

  骨架负责:
    - 统一的因果对记录
    - 统一的Urgency累积
    - 统一的EffectWatchdog验证
    - 统一的进化信号广播(模块间联动)

  模块只需负责:
    - 定义"什么算好/坏" (effectiveness_calculator)
    - 定义"怎么学" (learn_logic)
    - 定义"怎么改" (evolve_logic)

Challenger主动寻找问题:
  每个模块的EvolutionLoop内置Challenger子模块，
  定期扫描模块健康指标，主动发现问题而非被动等待异常。

架构位置: 天机/core/evolution_loop.py
依赖: 天机/core/deepseek_driver.py (UrgencyAccumulator, EffectWatchdog, OfflineCatchup)
"""

import hashlib
import json
import logging
import threading
import time
import urllib.request
import urllib.error

# P0-fix: 递归保护 — 防止 _persist_action_to_icme 递归调用自身导致死循环
_persist_thread_local = threading.local()
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)



from typing import Dict

class LoopPhase(str, Enum):
    IDLE = "idle"
    OBSERVING = "observing"
    LEARNING = "learning"
    EVOLVING = "evolving"
    VALIDATING = "validating"
    ROLLED_BACK = "rolled_back"


class EvolutionSignalType(str, Enum):
    CAPACITY_PRESSURE = "capacity_pressure"
    QUALITY_DEGRADATION = "quality_degradation"
    ROUTE_INEFFICIENCY = "route_inefficiency"
    SCHEDULE_SUBOPTIMAL = "schedule_suboptimal"
    SKILL_UNDERUSE = "skill_underuse"
    GATE_MISJUDGMENT = "gate_misjudgment"
    WORKFLOW_BOTTLENECK = "workflow_bottleneck"
    DELEGATION_FAILURE = "delegation_failure"
    ENFORCEMENT_OVERBLOCK = "enforcement_overblock"
    CUSTOM = "custom"


@dataclass
class ModuleCausalPair:
    module_name: str
    action: str
    state_before: Dict[str, Any]
    state_after: Dict[str, Any]
    effectiveness: float
    timestamp: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if self.timestamp == 0.0:
            self.timestamp = time.time()


@dataclass
class EvolutionSignal:
    source_module: str
    signal_type: EvolutionSignalType
    severity: float
    description: str
    data: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = 0.0
    signal_id: str = ""

    def __post_init__(self):
        if self.timestamp == 0.0:
            self.timestamp = time.time()
        if not self.signal_id:
            self.signal_id = hashlib.md5(
                f"{self.source_module}:{self.signal_type}:{self.timestamp}".encode()
            ).hexdigest()[:12]


@dataclass
class EvolutionResult:
    module_name: str
    phase: LoopPhase
    changes_made: List[Dict[str, Any]] = field(default_factory=list)
    rules_modified: List[Dict[str, Any]] = field(default_factory=list)
    rollback_available: bool = False
    effectiveness_delta: float = 0.0
    summary: str = ""


__all__ = [
    "LoopPhase",
    "EvolutionSignalType",
    "ModuleCausalPair",
    "EvolutionSignal",
    "EvolutionResult",
]
