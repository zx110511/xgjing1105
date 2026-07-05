# -*- coding: utf-8-sig -*-
"""hybrid_engine_stats.py — ICMEStorageEngineStatsMixin (SSS-PhaseB)

从 hybrid_engine.py 拆分的方法组: stats
源文件: hybrid_engine.py
"""

import hashlib
import json
import logging
import time
import uuid
from pathlib import Path
from typing import Any
from ..shared.config import ICMEConfig
from .engine import ICMEEngine, MemoryEntry
from .storage.migration import MigrationManager
from .storage.tiered import (  # noqa: F401
    TieredStorageEngine,
)


from typing import Dict

class ICMEStorageEngineStatsMixin:
    """stats方法组Mixin"""

    def health(self) -> dict[str, Any]:
        return {
            "status": "ready",
            "version": "1.1",
            "storage_backend": "sqlite" if self._use_sqlite else "json",
            "total_entries": self._stats["total_entries"],
            "total_accesses": self._stats.get("total_accesses", 0),
            "total_consolidations": self._stats.get("total_consolidations", 0),
            "total_rejected": self._stats.get("total_rejected", 0),
            "conflicts": self._stats.get("total_conflicts", 0),
            "errors": self._errors,
            "evo_loop_active": self._evo_loop is not None,
            "recorder_attached": self._recorder is not None,
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
            except Exception as e:
                logger.debug(f"[HybridEngine] evo_loop.tick() 跳过: {e}")

    def _calc_hybrid_effectiveness(
        self, action: str, state_before: dict[str, Any], state_after: dict[str, Any]
    ) -> float:
        if action == "remember":
            status = state_after.get("status", "error")
            return (
                0.7
                if status in ("stored", "downgrade")
                else (0.3 if status == "conflict" else -0.5)
            )
        elif action == "remember_batch":
            batch_size = state_after.get("batch_size", 0)
            return min(0.9, 0.3 + batch_size * 0.01) if batch_size > 0 else -0.2
        elif action == "recall":
            hits = state_after.get("hits", 0)
            return 0.3 if hits > 0 else 0.0
        elif action == "consolidate":
            return 0.6 if state_after.get("to_layer") else -0.1
        return 0.0

    def _learn_from_hybrid(
        self, causal_pairs: list[Any], effectiveness_summary: dict[str, Any]
    ) -> dict[str, Any]:
        return {
            "patterns_found": len(causal_pairs),
            "avg_effectiveness": effectiveness_summary.get("avg_effectiveness", 0.0),
            "total_entries": self._stats["total_entries"],
            "total_consolidations": self._stats.get("total_consolidations", 0),
            "total_accesses": self._stats.get("total_accesses", 0),
            "storage_backend": "sqlite" if self._use_sqlite else "json",
        }

    def _evolve_hybrid_config(
        self, learn_result: dict[str, Any], mutable_config: dict[str, Any]
    ) -> dict[str, Any]:
        changes = {}
        total_entries = learn_result.get("total_entries", 0)
        if total_entries > 10000:
            changes["batch_size"] = min(500, mutable_config.get("batch_size", 100) * 2)
        elif total_entries < 1000:
            changes["batch_size"] = 100
        consolidations = learn_result.get("total_consolidations", 0)
        if consolidations > 100 and total_entries > 5000:
            changes["use_sqlite"] = True
        return {"rules_modified": changes, "skills_created": []}

    def stats(self) -> dict:
        if self._use_sqlite:
            st = self._store.get_total_stats()
            layer_stats = self._store.get_layer_stats()
            total_calls = self._stats.get("total_recall_calls", 0)
            quality_hits = self._stats.get("total_recall_quality_hits", 0)
            raw_hits = self._stats.get("total_recall_hits", 0)
            # hit_rate: 高质量命中占总调用的比例 (FTS5 rank<0 或 score>0)
            hit_rate = (
                round(quality_hits / max(total_calls, 1) * 100, 1)
                if total_calls > 0
                else 0.0
            )
            # recall_rate: 有结果返回的比例 (传统指标)
            recall_rate = (
                round(raw_hits / max(total_calls, 1) * 100, 1)
                if total_calls > 0
                else 0.0
            )
            avg_latency = (
                round(
                    self._stats.get("total_recall_latency_ms", 0) / max(total_calls, 1),
                    1,
                )
                if total_calls > 0
                else 0.0
            )
            self._persist_stats_counters()
            result = {
                "total_entries": st["total_entries"],
                "total_accesses": self._stats["total_accesses"],
                "uptime_seconds": round(time.time() - self._stats["start_time"], 1),
                "layers": {k: v["entry_count"] for k, v in layer_stats.items()},
                "archive_entries": st["archived_entries"],
                "consolidations": self._stats["total_consolidations"],
                "archivals": self._stats["total_archivals"],
                "rejected": self._stats.get("total_rejected", 0),
                "downgraded": self._stats.get("total_downgraded", 0),
                "hit_rate": hit_rate,
                "recall_rate": recall_rate,
                "quality_hits": quality_hits,
                "avg_recall_latency_ms": avg_latency,
                "conflicts": self._stats.get("total_conflicts", 0),
                "consolidations_triggered": self._stats.get(
                    "total_consolidations_triggered", 0
                ),
                "hard_cap_enforcements": self._stats.get(
                    "total_hard_cap_enforcements", 0
                ),
                "consolidation_events_logged": len(self._consolidation_event_log),
                "data_path": str(self._data_path),
                "storage_backend": "sqlite",
                "db_size_mb": st.get("db_file_size_mb", st.get("total_size_mb", 0.0)),
            }

            # [STO-PHASE-3] 注入存储健康评分
            try:
                from .storage_health import StorageHealthMonitor
                if not hasattr(self, '_health_monitor'):
                    self._health_monitor = StorageHealthMonitor(
                        sqlite_store=self._store,
                        data_path=self._data_path,
                    )
                health_stats = self._health_monitor.get_health_stats()
                result.update(health_stats)
            except Exception:
                result.setdefault("health_score", -1)

            return result
        return super().stats()

    def get_layer_capacity_info(self) -> dict[str, dict]:
        if self._use_sqlite:
            layer_stats = self._store.get_layer_stats()
            info = {}
            for layer in self.config.layers:
                ls = layer_stats.get(
                    layer.name, {"entry_count": 0, "total_bytes": 0, "avg_score": 0.0}
                )
                usage = (
                    ls["total_bytes"] / layer.max_size_bytes
                    if layer.max_size_bytes > 0
                    else 0
                )
                accumulated = self._accumulated_bytes.get(layer.name, 0)
                acc_entries = self._accumulated_entries.get(layer.name, 0)
                acc_ratio = self._get_accumulation_ratio(layer.name)
                entry_ratio = self._get_accumulation_entry_ratio(layer.name)
                last_cons = self._last_consolidation_time.get(layer.name, 0.0)
                info[layer.name] = {
                    "size_bytes": ls["total_bytes"],
                    "max_size_bytes": layer.max_size_bytes,
                    "hard_cap_bytes": layer.hard_cap_bytes,
                    "entry_count": ls["entry_count"],
                    "max_entries": layer.max_entries,
                    "usage_ratio": round(usage, 4),
                    "capacity_threshold": layer.capacity_threshold,
                    "accumulation_threshold_bytes": layer.accumulation_threshold_bytes,
                    "accumulation_threshold_entries": layer.accumulation_threshold_entries,
                    "accumulated_bytes": accumulated,
                    "accumulated_entries": acc_entries,
                    "accumulation_ratio": round(acc_ratio, 4),
                    "accumulation_entry_ratio": round(entry_ratio, 4),
                    "needs_consolidation": acc_ratio >= 1.0
                    or entry_ratio >= 1.0
                    or ls["entry_count"] > layer.max_entries,
                    "at_hard_cap": ls["total_bytes"] >= layer.hard_cap_bytes
                    or (
                        layer.max_entries > 0 and ls["entry_count"] > layer.max_entries
                    ),
                    "seconds_since_last_consolidation": round(
                        time.time() - last_cons, 1
                    ),
                }
            return info
        return super().get_layer_capacity_info()

    def get_all_entries(self, layer: str | None = None, limit: int = 100) -> list:
        if self._use_sqlite:
            layers = [layer] if layer else None
            return self._store.search(layers=layers, limit=limit, min_score=0.0)
        return super().get_all_entries(layer, limit)

    def full_text_search(self, query: str, limit: int = 20) -> list[dict]:
        if self._use_sqlite:
            return self._store.search(query=query, limit=limit, use_fts=True)
        return self.recall(query=query, limit=limit)

    def build_export_data(self) -> dict:
        if self._use_sqlite:
            layers_data = {}
            for layer_cfg in self.config.layers:
                entries = self._store.search(
                    layers=[layer_cfg.name], limit=10000, min_score=0.0
                )
                layers_data[layer_cfg.name] = entries
            return {
                "stats": self.stats(),
                "layers": layers_data,
                "archive_count": self._store.get_total_stats().get(
                    "archived_entries", 0
                ),
                "exported_at": time.time(),
                "version": "5.0.0-accumulation-sqlite",
            }
        return super().build_export_data()

    def vacuum(self):
        if self._use_sqlite:
            self._store.vacuum()
            logger.info("[ICME] 数据库VACUUM完成")

    def get_storage_stats(self):
        if self._use_sqlite:
            return self._store.get_storage_stats()
        return None

    def close(self):
        if self._use_sqlite:
            self._store.close()
