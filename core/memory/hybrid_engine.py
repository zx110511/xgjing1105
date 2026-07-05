# -*- coding: utf-8-sig -*-
"""hybrid_engine.py — 主类组合层 (SSS-PhaseB拆分后)

ICMEStorageEngine通过多继承Mixin组合各方法组。
"""

from .hybrid_engine_init import ICMEStorageEngineInitMixin
from .hybrid_engine_remember import ICMEStorageEngineRememberMixin
from .hybrid_engine_recall import ICMEStorageEngineRecallMixin
from .hybrid_engine_consolidate import ICMEStorageEngineConsolidateMixin
from .hybrid_engine_stats import ICMEStorageEngineStatsMixin


class ICMEStorageEngine(ICMEStorageEngineInitMixin, ICMEStorageEngineRememberMixin, ICMEStorageEngineRecallMixin, ICMEStorageEngineConsolidateMixin, ICMEStorageEngineStatsMixin):
    """ICMEStorageEngine — 组合各方法组Mixin"""
    pass


__all__ = ["ICMEStorageEngine"]
