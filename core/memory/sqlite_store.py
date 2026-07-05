# -*- coding: utf-8-sig -*-
"""sqlite_store.py — 主类组合层 (SSS-PhaseB拆分后)

SQLiteMemoryStore通过多继承Mixin组合各方法组。
"""

from .sqlite_store_init import SQLiteMemoryStoreInitMixin
from .sqlite_store_crud import SQLiteMemoryStoreCrudMixin
from .sqlite_store_search import SQLiteMemoryStoreSearchMixin
from .sqlite_store_stats import SQLiteMemoryStoreStatsMixin
from .sqlite_store_cache import SQLiteMemoryStoreCacheMixin
from .sqlite_store_evo import SQLiteMemoryStoreEvoMixin
from dataclasses import dataclass


@dataclass
class StorageStats:
    file_path: str
    file_size_mb: float
    total_entries: int
    wal_size_kb: float
    last_vacuum: float
    cache_hits: int
    cache_misses: int


from typing import Dict

class SQLiteMemoryStore(SQLiteMemoryStoreInitMixin, SQLiteMemoryStoreCrudMixin, SQLiteMemoryStoreSearchMixin, SQLiteMemoryStoreStatsMixin, SQLiteMemoryStoreCacheMixin, SQLiteMemoryStoreEvoMixin):
    """SQLiteMemoryStore — 组合各方法组Mixin"""
    SCHEMA_VERSION = 4


__all__ = ["SQLiteMemoryStore", "StorageStats"]
