# -*- coding: utf-8-sig -*-
"""TCL规范化 — 数据模型

从 tcl_normalizer.py 拆分 (SSS-PhaseB)
"""
from __future__ import annotations  # [FIX-tcl-models-001] 延迟类型注解求值

import hashlib
import json
import logging
import re
import sqlite3
import threading
import time
from dataclasses import asdict, dataclass, field


from typing import Dict

@dataclass
class TermEntry:
    """术语条目"""

    canonical_id: str = ""
    canonical_term: str = ""
    aliases: list[str] = field(default_factory=list)
    definition: str = ""
    domain: str = "tianji_core"
    layer: str = "semantic"
    frequency: int = 0
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "TermEntry":
        aliases = d.get("aliases", [])
        if isinstance(aliases, str):
            try:
                aliases = json.loads(aliases)
            except json.JSONDecodeError:
                aliases = []
        return cls(
            canonical_id=d.get("canonical_id", ""),
            canonical_term=d.get("canonical_term", ""),
            aliases=aliases,
            definition=d.get("definition", ""),
            domain=d.get("domain", "tianji_core"),
            layer=d.get("layer", "semantic"),
            frequency=d.get("frequency", 0),
            created_at=d.get("created_at", 0.0),
            updated_at=d.get("updated_at", 0.0),
        )


@dataclass
class NormalizeResult:
    """归一化结果"""

    original: str = ""
    canonical_id: str = ""
    canonical_term: str = ""
    confidence: float = 0.0
    method: str = ""  # exact / alias / fuzzy / llm
    latency_ms: float = 0.0


# ---------------------------------------------------------------------------
# 术语表存储
# ---------------------------------------------------------------------------

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

    CREATE INDEX IF NOT EXISTS idx_term_canonical
        ON tianji_terminology(canonical_term);
    CREATE INDEX IF NOT EXISTS idx_term_domain
        ON tianji_terminology(domain);
"""

# 别名倒排索引表(加速别名查找)
ALIAS_INDEX_DDL = """
    CREATE TABLE IF NOT EXISTS tianji_alias_index (
        alias_text TEXT NOT NULL,
        canonical_id TEXT NOT NULL,
        PRIMARY KEY (alias_text, canonical_id)
    );

    CREATE INDEX IF NOT EXISTS idx_alias_text
        ON tianji_alias_index(alias_text);
"""




__all__ = ["TermEntry", "NormalizeResult"]
