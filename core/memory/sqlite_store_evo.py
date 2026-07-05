# -*- coding: utf-8-sig -*-
"""sqlite_store_evo.py — SQLiteMemoryStoreEvoMixin (SSS-PhaseB)

从 sqlite_store.py 拆分的方法组: evo
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

class SQLiteMemoryStoreEvoMixin:
    """evo方法组Mixin"""

    def _calc_store_effectiveness(
        self, action: str, state_before: dict[str, Any], state_after: dict[str, Any]
    ) -> float:
        if action == "insert":
            layer = state_after.get("layer", "")
            return 0.4 if layer else 0.2
        elif action == "insert_batch":
            count = state_after.get("batch_count", 0)
            return min(0.7, 0.2 + count * 0.02) if count > 0 else 0.0
        elif action == "search":
            results = state_after.get("results_count", 0)
            return min(0.6, 0.1 + results * 0.05) if results > 0 else 0.0
        elif action == "vacuum":
            return 0.3
        return 0.0

    def _learn_from_store(
        self, causal_pairs: list[Any], effectiveness_summary: dict[str, Any]
    ) -> dict[str, Any]:
        return {
            "patterns_found": len(causal_pairs),
            "avg_effectiveness": effectiveness_summary.get("avg_effectiveness", 0.0),
            "total_writes": self._stats["total_writes"],
            "total_reads": self._stats["total_reads"],
            "cache_hit_rate": (
                self._stats["cache_hits"]
                / max(self._stats["cache_hits"] + self._stats["cache_misses"], 1)
            ),
        }

    def _evolve_store_config(
        self, learn_result: dict[str, Any], mutable_config: dict[str, Any]
    ) -> dict[str, Any]:
        changes = {}
        cache_hit_rate = learn_result.get("cache_hit_rate", 0.5)
        if cache_hit_rate < 0.3:
            changes["cache_size"] = min(
                2000, mutable_config.get("cache_size", 500) + 100
            )
        if cache_hit_rate > 0.8 and mutable_config.get("cache_size", 500) > 200:
            changes["cache_size"] = max(200, mutable_config.get("cache_size", 500) - 50)
        return {"rules_modified": changes, "skills_created": []}
