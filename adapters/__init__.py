# -*- coding: utf-8-sig -*-
"""天机 adapters 包  [v10-ready]

多平台适配器集合。新增统一适配器策略门面 (IAdapterStrategy):
    - LocalAdapterStrategy  (本地进程内适配, strategy_interface.py)
    - RemoteAdapterStrategy (灵境跨平台网关 stub, remote_stub.py)
    - CherryClawAdapter     (CherryClaw 全量记忆接入, cherryclaw_adapter.py)
"""
from .strategy_interface import LocalAdapterStrategy
from .remote_stub import RemoteAdapterStrategy
from .cherryclaw_adapter import CherryClawAdapter, CherryClawMemoryEntry, CherryClawMemoryStats

__all__ = [
    "LocalAdapterStrategy",
    "RemoteAdapterStrategy",
    "CherryClawAdapter",
    "CherryClawMemoryEntry",
    "CherryClawMemoryStats",
]
