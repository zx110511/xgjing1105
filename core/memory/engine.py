# -*- coding: utf-8-sig -*-
"""engine.py — 主类组合层 (SSS-PhaseB拆分后)

ICMEEngine通过多继承Mixin组合各方法组。
"""

from .engine_init import ICMEEngineInitMixin
from .engine_evo import ICMEEngineEvoMixin
from .engine_event import ICMEEngineEventMixin
from .engine_remember import ICMEEngineRememberMixin
from .engine_recall import ICMEEngineRecallMixin
from .engine_consolidate import ICMEEngineConsolidateMixin
from .engine_forget import ICMEEngineForgetMixin
from .engine_capacity import ICMEEngineCapacityMixin
from .engine_stats import ICMEEngineStatsMixin
from . import MemoryEntry


class ICMEEngine(ICMEEngineInitMixin, ICMEEngineEvoMixin, ICMEEngineEventMixin, ICMEEngineRememberMixin, ICMEEngineRecallMixin, ICMEEngineConsolidateMixin, ICMEEngineForgetMixin, ICMEEngineCapacityMixin, ICMEEngineStatsMixin):
    """ICMEEngine — 组合各方法组Mixin"""
    pass


__all__ = ["ICMEEngine", "MemoryEntry"]
