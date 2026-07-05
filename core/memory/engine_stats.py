# -*- coding: utf-8-sig -*-
"""engine_stats.py — ICMEEngineStatsMixin (SSS-PhaseB)

从 engine.py 拆分的方法组: stats
"""

import json
import threading
import time
from collections import OrderedDict, defaultdict
from typing import Any
from ..shared.config import DEFAULT_CONFIG, ICMEConfig, TIANJI_V91_PROTOCOL_MODE
from ..shared.learning_bridge import ClosedLoopLearningBridge
from . import (
    ArchiveManager,
    MemoryEntry,
    MemoryIndex,
    MemoryWriter,
    PromotionEngine,
)
try:
    from ..processors.conflict_resolver import (
        ConflictResolver,
        ConflictType,
        ResolutionStrategy,
        ResolutionVerdict,
    )
    from ..processors.consolidation_processor import (
        ConsolidationProcessor,
        OrchestrationStrategy,
    )
    from ..processors.preference_drift_detector import (
        DriftType,
        PreferenceDriftDetector,
    )
    _PROCESSORS_AVAILABLE = True
except ImportError:
    _PROCESSORS_AVAILABLE = False
__all__ = ["ICMEEngine", "MemoryEntry"]



from typing import Optional

class ICMEEngineStatsMixin:
    """stats方法组Mixin"""

    def stats(self) -> dict:
        with self._lock:
            layer_counts = {}
            for name, layer_data in self._layers.items():
                layer_counts[name] = len(layer_data)
            total_calls = self._stats["total_recall_calls"]
            hit_rate = (
                round(self._stats["total_recall_hits"] / max(total_calls, 1) * 100, 1)
                if total_calls > 0
                else 0.0
            )
            avg_latency_ms = (
                round(self._stats["total_recall_latency_ms"] / max(total_calls, 1), 1)
                if total_calls > 0
                else 0.0
            )
            result = {
                "total_entries": self._stats["total_entries"],
                "total_accesses": self._stats["total_accesses"],
                "uptime_seconds": round(time.time() - self._stats["start_time"], 1),
                "layers": layer_counts,
                "archive_entries": len(self._archive),
                "consolidations": self._stats["total_consolidations"],
                "archivals": self._stats["total_archivals"],
                "rejected": self._stats["total_rejected"],
                "downgraded": self._stats["total_downgraded"],
                "hit_rate": hit_rate,
                "avg_recall_latency_ms": avg_latency_ms,
                "conflicts": self._stats["total_conflicts"],
                "consolidations_triggered": self._stats[
                    "total_consolidations_triggered"
                ],
                "hard_cap_enforcements": self._stats["total_hard_cap_enforcements"],
                "consolidation_events_logged": len(self._consolidation_event_log),
                "data_path": str(self._data_path),
            }

            # [STO-PHASE-3] 注入存储健康评分
            try:
                from .storage_health import StorageHealthMonitor
                if not hasattr(self, '_health_monitor'):
                    self._health_monitor = StorageHealthMonitor(
                        sqlite_store=getattr(self, '_store', None),
                        data_path=self._data_path,
                    )
                health_stats = self._health_monitor.get_health_stats()
                result.update(health_stats)
            except Exception:
                result.setdefault("health_score", -1)  # 不可用时标记为-1

            return result

    def verify_consistency(self) -> dict:
        errors = []
        warnings = []
        with self._lock:
            for layer_name, layer_data in self._layers.items():
                computed_size = sum(e.size_bytes for e in layer_data.values())
                tracked_size = self._layer_sizes.get(layer_name, 0)
                if abs(computed_size - tracked_size) > 1024:
                    errors.append(
                        f"{layer_name}: computed={computed_size} tracked={tracked_size} diff={abs(computed_size - tracked_size)}"
                    )
                actual_count = len(layer_data)
                tracked_count = self._accumulated_entries.get(layer_name, 0)
            total_from_layers = sum(len(v) for v in self._layers.values())
            total_tracked = self._stats["total_entries"]
            if total_from_layers != total_tracked:
                errors.append(
                    f"total_entries mismatch: layers={total_from_layers} stats={total_tracked}"
                )
            for layer_name in self._layers:
                should, reason = self._should_consolidate(layer_name)
                can, wait_reason = self._can_consolidate_now(layer_name)
                if should and not can:
                    warnings.append(
                        f"{layer_name}: needs_consolidation but blocked ({wait_reason})"
                    )
                if should:
                    warnings.append(f"{layer_name}: consolidation_needed ({reason})")
            tag_index_size = sum(len(v) for v in self._tag_index.values())
            if tag_index_size < total_from_layers:
                warnings.append(
                    f"tag_index may be incomplete: {tag_index_size} < {total_from_layers}"
                )
        return {
            "consistent": len(errors) == 0,
            "errors": errors,
            "warnings": warnings,
            "checked_at": time.time(),
        }

    def get_consolidation_event_log(self, limit: int = 50) -> list[dict]:
        with self._lock:
            return self._consolidation_event_log[-limit:]

    def replay_memory(
        self, memory_id: str, up_to_timestamp: float | None = None
    ) -> dict | None:
        if self._store:
            try:
                return self._store.replay_events(memory_id, up_to_timestamp)
            except Exception:
                pass
        return None

    def _start_consolidation_daemon(self):
        import logging as _logging
        import threading as _th

        _logger = _logging.getLogger(__name__)
        self._consolidation_running = True
        interval = getattr(self.config, "consolidation_interval_minutes", 5) * 60

        def _daemon_loop():
            while self._consolidation_running:
                try:
                    time.sleep(interval)
                    if not self._consolidation_running:
                        break
                    for layer_name in ["sensory", "working", "short_term", "episodic", "semantic"]:
                        try:
                            self._auto_consolidate(layer_name)
                        except Exception as e:
                            _logger.warning(
                                f"Consolidation daemon error for {layer_name}: {e}"
                            )
                except Exception as e:
                    _logger.error(f"Consolidation daemon loop error: {e}")
                    time.sleep(10)

        _t = _th.Thread(
            target=_daemon_loop, name="ICME-Consolidation-Daemon", daemon=True
        )
        _t.start()
        _logger.info(f"Consolidation daemon started (interval={interval}s)")

    def build_export_data(self) -> dict:
        with self._lock:
            layers_data = {}
            for name, layer_data in self._layers.items():
                layers_data[name] = [e.to_dict() for e in layer_data.values()]
            return {
                "stats": self.stats(),
                "layers": layers_data,
                "archive_count": len(self._archive),
                "exported_at": time.time(),
                "version": "5.0.0-accumulation",
            }
