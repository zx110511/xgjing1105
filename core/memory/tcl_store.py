# -*- coding: utf-8-sig -*-
"""TCL规范化 — 术语存储

从 tcl_normalizer.py 拆分 (SSS-PhaseB)
"""
from __future__ import annotations  # [FIX-tcl-store-001] 延迟类型注解求值

import hashlib
import json
import logging
import re
import sqlite3
import threading
import time

logger = logging.getLogger("tianji.tcl_store")  # [FIX-tcl-store-003] 补充缺失的logger定义
from dataclasses import asdict, dataclass, field


from typing import Dict
from .tcl_models import TermEntry  # [FIX-tcl-001] 补充缺失的TermEntry导入

# [FIX-tcl-store-002] 补充缺失的DDL常量定义(TerminologyStore._init_tables引用)
TERMINOLOGY_DDL = """
CREATE TABLE IF NOT EXISTS tianji_terminology (
    canonical_id TEXT PRIMARY KEY,
    canonical_term TEXT NOT NULL UNIQUE,
    aliases TEXT NOT NULL DEFAULT '[]',
    definition TEXT NOT NULL DEFAULT '',
    domain TEXT NOT NULL DEFAULT 'tianji_core',
    layer TEXT NOT NULL DEFAULT 'semantic',
    frequency INTEGER NOT NULL DEFAULT 0,
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_term_domain ON tianji_terminology(domain);
CREATE INDEX IF NOT EXISTS idx_term_layer ON tianji_terminology(layer);
"""

ALIAS_INDEX_DDL = """
CREATE INDEX IF NOT EXISTS idx_term_alias_lookup ON tianji_terminology(canonical_term);
"""

class TerminologyStore:
    """术语表存储层"""

    def __init__(self, db_path: str):
        self._db_path = db_path
        self._lock = threading.RLock()
        self._alias_cache: dict[str, str] = {}
        self._term_cache: dict[str, TermEntry] = {}
        self._cache_loaded = False
        self._init_tables()

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path, timeout=10)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=5000")
        conn.row_factory = sqlite3.Row
        return conn

    def _init_tables(self):
        conn = self._get_conn()
        try:
            conn.executescript(TERMINOLOGY_DDL)
            conn.executescript(ALIAS_INDEX_DDL)
            conn.commit()
        finally:
            conn.close()

    def _load_cache(self):
        """加载别名缓存到内存(加速Level 2查询)"""
        if self._cache_loaded:
            return
        conn = self._get_conn()
        try:
            rows = conn.execute("SELECT * FROM tianji_terminology").fetchall()
            for row in rows:
                entry = TermEntry.from_dict(dict(row))
                self._term_cache[entry.canonical_id] = entry
                self._alias_cache[entry.canonical_term.lower()] = entry.canonical_id
                for alias in entry.aliases:
                    self._alias_cache[alias.lower()] = entry.canonical_id
            self._cache_loaded = True
            logger.info(
                f"[TCL] Loaded {len(self._term_cache)} terms, "
                f"{len(self._alias_cache)} alias entries into cache"
            )
        finally:
            conn.close()

    def add_term(self, entry: TermEntry) -> str:
        """添加术语条目"""
        with self._lock:
            if not entry.canonical_id:
                hash_prefix = hashlib.sha256(
                    entry.canonical_term.encode("utf-8")
                ).hexdigest()[:8]
                entry.canonical_id = f"tcl:{entry.domain}:{hash_prefix}"

            entry.updated_at = time.time()
            if not entry.created_at:
                entry.created_at = time.time()

            conn = self._get_conn()
            try:
                conn.execute(
                    """INSERT OR REPLACE INTO tianji_terminology
                       (canonical_id, canonical_term, aliases, definition,
                        domain, layer, frequency, created_at, updated_at)
                       VALUES (?,?,?,?,?,?,?,?,?)""",
                    (
                        entry.canonical_id,
                        entry.canonical_term,
                        json.dumps(entry.aliases, ensure_ascii=False),
                        entry.definition,
                        entry.domain,
                        entry.layer,
                        entry.frequency,
                        entry.created_at,
                        entry.updated_at,
                    ),
                )
                # 更新别名倒排索引
                conn.execute(
                    "DELETE FROM tianji_alias_index WHERE canonical_id = ?",
                    (entry.canonical_id,),
                )
                for alias in entry.aliases:
                    conn.execute(
                        "INSERT OR IGNORE INTO tianji_alias_index (alias_text, canonical_id) VALUES (?,?)",
                        (alias.lower(), entry.canonical_id),
                    )
                conn.execute(
                    "INSERT OR IGNORE INTO tianji_alias_index (alias_text, canonical_id) VALUES (?,?)",
                    (entry.canonical_term.lower(), entry.canonical_id),
                )
                conn.commit()
            finally:
                conn.close()

            # 更新内存缓存
            self._term_cache[entry.canonical_id] = entry
            self._alias_cache[entry.canonical_term.lower()] = entry.canonical_id
            for alias in entry.aliases:
                self._alias_cache[alias.lower()] = entry.canonical_id

            return entry.canonical_id

    def lookup_by_term(self, term: str) -> TermEntry | None:
        """通过规范术语名查找"""
        self._load_cache()
        canonical_id = self._alias_cache.get(term.lower())
        if canonical_id:
            return self._term_cache.get(canonical_id)
        return None

    def lookup_by_alias(self, alias: str) -> TermEntry | None:
        """通过别名查找(含规范术语名)"""
        self._load_cache()
        canonical_id = self._alias_cache.get(alias.lower())
        if canonical_id:
            return self._term_cache.get(canonical_id)
        return None

    def get_all_terms(self, domain: str = "") -> list[TermEntry]:
        """获取全部术语"""
        self._load_cache()
        entries = list(self._term_cache.values())
        if domain:
            entries = [e for e in entries if e.domain == domain]
        return entries

    def increment_frequency(self, canonical_id: str) -> None:
        """增加术语使用频率"""
        with self._lock:
            entry = self._term_cache.get(canonical_id)
            if entry:
                entry.frequency += 1
                entry.updated_at = time.time()
                conn = self._get_conn()
                try:
                    conn.execute(
                        "UPDATE tianji_terminology SET frequency=?, updated_at=? WHERE canonical_id=?",
                        (entry.frequency, entry.updated_at, canonical_id),
                    )
                    conn.commit()
                finally:
                    conn.close()

    def get_stats(self) -> dict:
        """获取术语表统计"""
        self._load_cache()
        total = len(self._term_cache)
        by_domain: dict[str, int] = {}
        total_aliases = 0
        for entry in self._term_cache.values():
            by_domain[entry.domain] = by_domain.get(entry.domain, 0) + 1
            total_aliases += len(entry.aliases)
        return {
            "total_terms": total,
            "total_aliases": total_aliases,
            "avg_aliases_per_term": round(total_aliases / max(total, 1), 1),
            "by_domain": by_domain,
            "cache_entries": len(self._alias_cache),
        }


# ---------------------------------------------------------------------------
# 归一化引擎
# ---------------------------------------------------------------------------




__all__ = ["TerminologyStore"]
