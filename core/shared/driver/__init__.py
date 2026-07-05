# -*- coding: utf-8-sig -*-
r"""
core.driver — DeepSeek驾驶者子包  [v10-ready]
=============================================
由 core/deepseek_driver.py (1891+行) 按职责拆分而来 (P1-02)。

子模块:
  - decision.py     : 决策引擎 (EventType/TianjiEvent/DriverDecision/EvolutionSignal/DecisionEngine)
  - causal.py       : 因果记录 (CausalPair/CausalPairRecorder/OfflineCatchup)
  - urgency.py      : 紧迫度累积 (UrgencyAccumulator/EffectWatchdog)
  - orchestrator.py : 三循环编排 (TriggerFrequencyTracker/DriverOrchestrator)

兼容性: core/deepseek_driver.py 仍作为路由层对外暴露 DeepSeekDriver 等符号，
        `from core.shared.deepseek_driver import DeepSeekDriver` 继续可用。
"""
from __future__ import annotations

from .decision import (
    DEFAULT_MUTABLE_RULES,
    DRIVER_SYSTEM_PROMPT,
    EVOLUTION_EVAL_PROMPT,
    DecisionEngine,
    DriverDecision,
    EventType,
    EvolutionSignal,
    TianjiEvent,
)
from .causal import CausalPair, CausalPairRecorder, CausalRecorder, OfflineCatchup
from .urgency import EffectWatchdog, UrgencyAccumulator
from .orchestrator import DriverOrchestrator, TriggerFrequencyTracker

__all__ = [
    # decision
    "EventType",
    "TianjiEvent",
    "DriverDecision",
    "EvolutionSignal",
    "DecisionEngine",
    "DRIVER_SYSTEM_PROMPT",
    "EVOLUTION_EVAL_PROMPT",
    "DEFAULT_MUTABLE_RULES",
    # causal
    "CausalPair",
    "CausalPairRecorder",
    "CausalRecorder",
    "OfflineCatchup",
    # urgency
    "UrgencyAccumulator",
    "EffectWatchdog",
    # orchestrator
    "DriverOrchestrator",
    "TriggerFrequencyTracker",
]
