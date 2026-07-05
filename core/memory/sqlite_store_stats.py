# -*- coding: utf-8-sig -*-
"""sqlite_store_stats.py — SQLiteMemoryStoreStatsMixin (SSS-PhaseB)

从 sqlite_store.py 拆分的方法组: stats
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

class SQLiteMemoryStoreStatsMixin:
    """stats方法组Mixin"""

    def get_layer_stats(self) -> dict[str, dict]:
        conn = self._get_conn()
        rows = conn.execute("""
            SELECT
                layer,
                COUNT(*) as entry_count,
                SUM(size_bytes) as total_bytes,
                AVG(value_score) as avg_score,
                MAX(created_at) as latest_entry
            FROM memories WHERE archived = 0
            GROUP BY layer
        """).fetchall()
        return {
            row["layer"]: {
                "entry_count": row["entry_count"],
                "total_bytes": row["total_bytes"] or 0,
                "avg_score": round(row["avg_score"] or 0.0, 4),
                "latest_entry": row["latest_entry"] or 0.0,
            }
            for row in rows
        }

    def get_total_stats(self) -> dict:
        conn = self._get_conn()
        total = conn.execute(
            "SELECT COUNT(*) as cnt FROM memories WHERE archived = 0"
        ).fetchone()["cnt"]
        archived = conn.execute(
            "SELECT COUNT(*) as cnt FROM memories WHERE archived = 1"
        ).fetchone()["cnt"]
        total_size = conn.execute(
            "SELECT COALESCE(SUM(size_bytes), 0) as total FROM memories"
        ).fetchone()["total"]
        return {
            "total_entries": total,
            "archived_entries": archived,
            "total_size_bytes": total_size,
            "total_size_mb": round(total_size / (1024 * 1024), 2),
            "total_writes": self._stats["total_writes"],
            "total_reads": self._stats["total_reads"],
            "db_file_size_mb": round(self.db_path.stat().st_size / (1024 * 1024), 2)
            if self.db_path.exists()
            else 0,
        }

    def vacuum(self):
        self._stats["vacuum_ops"] += 1
        conn = self._get_conn()
        conn.execute("PRAGMA optimize")
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        self._stats["last_vacuum"] = time.time()

        if self._evo_loop is not None:
            try:
                self._evo_loop.record_action(
                    action="vacuum",
                    state_before={"last_vacuum": self._stats["last_vacuum"] - 0.001},
                    state_after={"last_vacuum": self._stats["last_vacuum"]},
                )
            except Exception as e:
                logger.debug(f"[SQLiteStore] evo_loop.record_action(vacuum) 忽略: {e}")

    def get_storage_stats(self) -> StorageStats:
        file_size = self.db_path.stat().st_size if self.db_path.exists() else 0
        wal_size = (
            (self.db_path.parent / f"{self.db_path.name}-wal").stat().st_size
            if (self.db_path.parent / f"{self.db_path.name}-wal").exists()
            else 0
        )
        return StorageStats(
            file_path=str(self.db_path),
            file_size_mb=round(file_size / (1024 * 1024), 2),
            total_entries=self.get_total_stats()["total_entries"],
            wal_size_kb=round(wal_size / 1024, 2),
            last_vacuum=self._stats["last_vacuum"],
            cache_hits=self._stats["cache_hits"],
            cache_misses=self._stats["cache_misses"],
        )

    def health(self) -> dict[str, Any]:
        return {
            "status": "ready",
            "version": "1.1",
            "db_path": str(self.db_path),
            "total_writes": self._stats["total_writes"],
            "total_reads": self._stats["total_reads"],
            "cache_hits": self._stats["cache_hits"],
            "cache_misses": self._stats["cache_misses"],
            "insert_ops": self._stats["insert_ops"],
            "batch_ops": self._stats["batch_ops"],
            "search_ops": self._stats["search_ops"],
            "errors": self._stats["errors"],
            "evo_loop_active": self._evo_loop is not None,
            "recorder_attached": self._recorder is not None,
            "db_size_mb": round(self.db_path.stat().st_size / (1024 * 1024), 2)
            if self.db_path.exists()
            else 0,
        }

    def get_stats(self) -> dict[str, Any]:
        return {
            "version": "1.1",
            **self._stats,
            "health": self.health(),
            "evo_loop": self._evo_loop.get_stats() if self._evo_loop else {},
        }

    def tick(self):
        if self._evo_loop is not None:
            try:
                self._evo_loop.tick()
            except Exception:
                pass

