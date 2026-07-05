# -*- coding: utf-8-sig -*-
"""sqlite_store_cache.py — SQLiteMemoryStoreCacheMixin (SSS-PhaseB)

从 sqlite_store.py 拆分的方法组: cache
源文件: sqlite_store.py
"""

import json
import logging
import shutil
import sqlite3
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any



from typing import Dict

class SQLiteMemoryStoreCacheMixin:
    """cache方法组Mixin"""

    def _cache_get(self, key: str) -> dict | None:
        with self._cache_lock:
            if key in self._cache:
                self._stats["cache_hits"] += 1
                return self._cache[key].copy()
            self._stats["cache_misses"] += 1
            return None

    def _cache_set(self, key: str, value: dict):
        with self._cache_lock:
            if len(self._cache) >= self._cache_max:
                for _ in range(self._cache_max // 4):
                    self._cache.pop(next(iter(self._cache)), None)
            self._cache[key] = value.copy()

    def _cache_pop(self, key: str):
        with self._cache_lock:
            self._cache.pop(key, None)

    def _update_tag_index(self, conn, memory_id: str, tags: list[str]):
        conn.execute("DELETE FROM tag_index WHERE memory_id = ?", (memory_id,))
        for tag in tags:
            conn.execute(
                "INSERT OR IGNORE INTO tag_index(tag, memory_id) VALUES (?, ?)",
                (tag, memory_id),
            )

    def _row_to_dict(row) -> dict:
        d = dict(row)
        for field in ["tags", "metadata", "related_ids", "changelog"]:
            if d.get(field) and isinstance(d[field], str):
                try:
                    d[field] = json.loads(d[field])
                except (json.JSONDecodeError, TypeError):
                    d[field] = [] if field != "metadata" else {}
        # FTS5 rank映射为score: rank为负数(越小越相关), 转为0-1正分数
        fts_rank = d.pop("fts_rank", None)
        if fts_rank is not None and "score" not in d:
            d["score"] = round(1.0 / (1.0 + abs(fts_rank)), 4) if fts_rank < 0 else 0.0
        d.pop("archived", None)
        d.pop("content_segmented", None)
        return d

    def close(self):
        if hasattr(self._local, "conn") and self._local.conn is not None:
            try:
                self._local.conn.close()
            except Exception:
                pass
            self._local.conn = None

