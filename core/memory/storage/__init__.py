"""
[v10-ready] core.storage — 存储子包 (P1-03)

由 core/hybrid_engine.py 拆分而来, 按职责划分为三个独立模块:
  - backend.py    : StorageBackend 抽象后端契约
  - migration.py  : MigrationManager (JSON → SQLite 迁移/增量同步)
  - tiered.py     : TieredStorageEngine + MemoryTier + TierConfig (热冷分层)

兼容性: 原 core.hybrid_engine 中的公开类名 (TieredStorageEngine / MemoryTier
        / TierConfig / TIER_DEFAULTS / ICMEStorageEngine) 继续可用。
"""

from .backend import StorageBackend
from .migration import MigrationManager
from .tiered import (
    TIER_DEFAULTS,
    MemoryTier,
    TierConfig,
    TieredStorageEngine,
)

__all__ = [
    "StorageBackend",
    "MigrationManager",
    "TieredStorageEngine",
    "MemoryTier",
    "TierConfig",
    "TIER_DEFAULTS",
]
