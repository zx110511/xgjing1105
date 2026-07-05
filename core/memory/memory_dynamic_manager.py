r"""
六层记忆动态更新统筹管理体系 v1.0
====================================
以各层记忆存储的累计变化量为唯一数据统筹管理标准，
实现经验内容动态更新、统筹管理的完整闭环体系。

核心机制:
1. 累计变化量追踪器 (AccumulationTracker) - 实时追踪六层记忆的写入/删除/晋升变化量
2. 动态阈值管理器 (DynamicThresholdManager) - 根据变化量趋势动态调整各层阈值
3. 统筹调度器 (OrchestrationScheduler) - 基于变化量统筹调度晋升/归档/清理
4. 容量预警系统 (CapacityAlertSystem) - 多级预警+自动响应
5. 反馈优化引擎 (FeedbackOptimizer) - 从操作反馈持续优化管理策略
6. 记忆录入协调器 (MemoryImportCoordinator) - 协调批量记忆录入过程
"""

import time
import json
import uuid
import hashlib
import threading
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, field
from typing import Any, Optional, List, Dict, Tuple
from collections import OrderedDict, defaultdict


@dataclass
class AccumulationSnapshot:
    layer: str
    timestamp: float
    total_entries: int
    total_bytes: int
    delta_entries: int
    delta_bytes: int
    write_rate_entries_per_min: float
    write_rate_bytes_per_min: float
    promotion_in_count: int
    promotion_out_count: int
    archive_count: int
    reject_count: int


@dataclass
class DynamicThreshold:
    layer: str
    base_threshold_bytes: int
    base_threshold_entries: int
    current_threshold_bytes: int
    current_threshold_entries: int
    adjustment_factor: float
    last_adjusted: float
    adjustment_history: list = field(default_factory=list)


@dataclass
class CapacityAlert:
    id: str
    layer: str
    level: str
    message: str
    timestamp: float
    metric_value: float
    threshold_value: float
    auto_action_taken: str
    resolved: bool = False


class AccumulationTracker:
    def __init__(self):
        self._snapshots: Dict[str, List[AccumulationSnapshot]] = defaultdict(list)
        self._max_snapshots_per_layer = 1000
        self._current_deltas: Dict[str, Dict] = {}
        self._lock = threading.RLock()
        self._layers_config = {
            "sensory": {"max_bytes": 10 * 1024 * 1024, "max_entries": 5000},
            "working": {"max_bytes": 50 * 1024 * 1024, "max_entries": 10000},
            "short_term": {"max_bytes": 100 * 1024 * 1024, "max_entries": 20000},
            "episodic": {"max_bytes": 500 * 1024 * 1024, "max_entries": 100000},
            "semantic": {"max_bytes": 2 * 1024 * 1024 * 1024, "max_entries": 500000},
            "meta": {"max_bytes": 100 * 1024 * 1024, "max_entries": 50000},
        }
        for layer_name in self._layers_config:
            self._current_deltas[layer_name] = {
                "delta_entries": 0,
                "delta_bytes": 0,
                "promotion_in": 0,
                "promotion_out": 0,
                "archive_count": 0,
                "reject_count": 0,
                "last_snapshot_time": time.time(),
                "write_timestamps": [],
            }

    def record_write(self, layer: str, size_bytes: int):
        with self._lock:
            if layer in self._current_deltas:
                self._current_deltas[layer]["delta_entries"] += 1
                self._current_deltas[layer]["delta_bytes"] += size_bytes
                self._current_deltas[layer]["write_timestamps"].append(time.time())
                self._current_deltas[layer]["write_timestamps"] = [
                    t for t in self._current_deltas[layer]["write_timestamps"]
                    if time.time() - t <= 300
                ]

    def record_delete(self, layer: str, size_bytes: int):
        with self._lock:
            if layer in self._current_deltas:
                self._current_deltas[layer]["delta_entries"] -= 1
                self._current_deltas[layer]["delta_bytes"] -= size_bytes

    def record_promotion(self, from_layer: str, to_layer: str, size_bytes: int):
        with self._lock:
            if from_layer in self._current_deltas:
                self._current_deltas[from_layer]["promotion_out"] += 1
            if to_layer in self._current_deltas:
                self._current_deltas[to_layer]["promotion_in"] += 1

    def record_archive(self, layer: str):
        with self._lock:
            if layer in self._current_deltas:
                self._current_deltas[layer]["archive_count"] += 1

    def record_reject(self, layer: str):
        with self._lock:
            if layer in self._current_deltas:
                self._current_deltas[layer]["reject_count"] += 1

    def take_snapshot(self, layer: str, total_entries: int, total_bytes: int) -> AccumulationSnapshot:
        with self._lock:
            delta = self._current_deltas.get(layer, {})
            now = time.time()
            elapsed = now - delta.get("last_snapshot_time", now)
            elapsed_min = max(elapsed / 60.0, 0.001)

            write_ts = delta.get("write_timestamps", [])
            recent_writes = len([t for t in write_ts if now - t <= 60])
            write_rate_entries = recent_writes

            write_bytes_in_window = 0
            if len(write_ts) >= 2:
                write_rate_bytes = delta.get("delta_bytes", 0) / elapsed_min
            else:
                write_rate_bytes = 0

            snap = AccumulationSnapshot(
                layer=layer,
                timestamp=now,
                total_entries=total_entries,
                total_bytes=total_bytes,
                delta_entries=delta.get("delta_entries", 0),
                delta_bytes=delta.get("delta_bytes", 0),
                write_rate_entries_per_min=write_rate_entries,
                write_rate_bytes_per_min=write_rate_bytes,
                promotion_in_count=delta.get("promotion_in", 0),
                promotion_out_count=delta.get("promotion_out", 0),
                archive_count=delta.get("archive_count", 0),
                reject_count=delta.get("reject_count", 0),
            )

            self._snapshots[layer].append(snap)
            if len(self._snapshots[layer]) > self._max_snapshots_per_layer:
                self._snapshots[layer] = self._snapshots[layer][-self._max_snapshots_per_layer:]

            self._current_deltas[layer] = {
                "delta_entries": 0,
                "delta_bytes": 0,
                "promotion_in": 0,
                "promotion_out": 0,
                "archive_count": 0,
                "reject_count": 0,
                "last_snapshot_time": now,
                "write_timestamps": [],
            }
            return snap

    def take_all_snapshots(self, layer_stats: Dict[str, Dict]) -> List[AccumulationSnapshot]:
        results = []
        for layer_name, stats in layer_stats.items():
            snap = self.take_snapshot(
                layer=layer_name,
                total_entries=stats.get("entry_count", 0),
                total_bytes=stats.get("size_bytes", 0),
            )
            results.append(snap)
        return results

    def get_trend(self, layer: str, window_seconds: int = 3600) -> Dict:
        with self._lock:
            snaps = self._snapshots.get(layer, [])
            now = time.time()
            recent = [s for s in snaps if now - s.timestamp <= window_seconds]
            if not recent:
                return {"trend": "no_data", "growth_rate": 0.0, "avg_write_rate": 0.0}
            total_delta = sum(s.delta_entries for s in recent)
            total_bytes_delta = sum(s.delta_bytes for s in recent)
            time_span = recent[-1].timestamp - recent[0].timestamp if len(recent) > 1 else 1
            growth_rate = total_delta / max(time_span / 60.0, 0.001)
            avg_write_rate = total_bytes_delta / max(time_span, 0.001)
            if growth_rate > 5:
                trend = "rapid_growth"
            elif growth_rate > 1:
                trend = "growth"
            elif growth_rate > -1:
                trend = "stable"
            else:
                trend = "declining"
            return {
                "trend": trend,
                "growth_rate_entries_per_min": round(growth_rate, 2),
                "avg_write_rate_bytes_per_sec": round(avg_write_rate, 2),
                "total_delta_entries": total_delta,
                "total_delta_bytes": total_bytes_delta,
                "sample_count": len(recent),
                "time_span_seconds": round(time_span, 1),
            }

    def get_all_trends(self) -> Dict[str, Dict]:
        result = {}
        for layer_name in self._layers_config:
            result[layer_name] = self.get_trend(layer_name)
        return result

    def get_summary(self) -> Dict:
        with self._lock:
            summary = {}
            for layer_name, snaps in self._snapshots.items():
                if not snaps:
                    summary[layer_name] = {"snapshot_count": 0}
                    continue
                latest = snaps[-1]
                summary[layer_name] = {
                    "snapshot_count": len(snaps),
                    "latest_total_entries": latest.total_entries,
                    "latest_total_bytes": latest.total_bytes,
                    "latest_delta_entries": latest.delta_entries,
                    "latest_delta_bytes": latest.delta_bytes,
                    "latest_write_rate": latest.write_rate_entries_per_min,
                    "latest_promotion_in": latest.promotion_in_count,
                    "latest_promotion_out": latest.promotion_out_count,
                }
            return summary


class DynamicThresholdManager:
    def __init__(self, accumulation_tracker: AccumulationTracker):
        self._tracker = accumulation_tracker
        self._thresholds: Dict[str, DynamicThreshold] = {}
        self._lock = threading.RLock()
        self._adjustment_interval = 300
        self._last_adjustment = 0.0
        self._base_thresholds = {
            "sensory": {"bytes": 1 * 1024 * 1024, "entries": 100},
            "working": {"bytes": 5 * 1024 * 1024, "entries": 200},
            "short_term": {"bytes": 10 * 1024 * 1024, "entries": 500},
            "episodic": {"bytes": 50 * 1024 * 1024, "entries": 1000},
            "semantic": {"bytes": 200 * 1024 * 1024, "entries": 5000},
            "meta": {"bytes": 10 * 1024 * 1024, "entries": 500},
        }
        for layer_name, bt in self._base_thresholds.items():
            self._thresholds[layer_name] = DynamicThreshold(
                layer=layer_name,
                base_threshold_bytes=bt["bytes"],
                base_threshold_entries=bt["entries"],
                current_threshold_bytes=bt["bytes"],
                current_threshold_entries=bt["entries"],
                adjustment_factor=1.0,
                last_adjusted=time.time(),
            )

    def get_threshold(self, layer: str) -> DynamicThreshold:
        return self._thresholds.get(layer)

    def adjust_thresholds(self):
        with self._lock:
            now = time.time()
            if now - self._last_adjustment < self._adjustment_interval:
                return
            self._last_adjustment = now

            for layer_name, threshold in self._thresholds.items():
                trend = self._tracker.get_trend(layer_name)
                trend_type = trend.get("trend", "stable")
                growth_rate = trend.get("growth_rate_entries_per_min", 0.0)

                if trend_type == "rapid_growth":
                    factor = max(0.3, 1.0 - growth_rate * 0.05)
                elif trend_type == "growth":
                    factor = max(0.5, 1.0 - growth_rate * 0.02)
                elif trend_type == "declining":
                    factor = min(2.0, 1.0 + 0.1)
                else:
                    factor = 1.0

                threshold.adjustment_factor = round(factor, 3)
                threshold.current_threshold_bytes = int(threshold.base_threshold_bytes * factor)
                threshold.current_threshold_entries = int(threshold.base_threshold_entries * factor)
                threshold.last_adjusted = now
                threshold.adjustment_history.append({
                    "timestamp": now,
                    "factor": factor,
                    "trend": trend_type,
                    "growth_rate": growth_rate,
                })
                if len(threshold.adjustment_history) > 100:
                    threshold.adjustment_history = threshold.adjustment_history[-100:]

    def get_all_thresholds(self) -> Dict[str, Dict]:
        result = {}
        for layer_name, t in self._thresholds.items():
            result[layer_name] = {
                "base_bytes": t.base_threshold_bytes,
                "current_bytes": t.current_threshold_bytes,
                "base_entries": t.base_threshold_entries,
                "current_entries": t.current_threshold_entries,
                "adjustment_factor": t.adjustment_factor,
                "last_adjusted": t.last_adjusted,
            }
        return result


class CapacityAlertSystem:
    def __init__(self):
        self._alerts: List[CapacityAlert] = []
        self._max_alerts = 500
        self._lock = threading.RLock()
        self._alert_levels = {
            "green": 0.50,
            "yellow": 0.70,
            "orange": 0.85,
            "red": 0.95,
        }

    def check_capacity(self, layer: str, usage_ratio: float) -> Optional[CapacityAlert]:
        level = "green"
        for lvl, threshold in sorted(self._alert_levels.items(), key=lambda x: x[1]):
            if usage_ratio >= threshold:
                level = lvl

        if level == "green":
            return None

        messages = {
            "yellow": f"层{layer}使用率达{usage_ratio:.1%}，建议关注",
            "orange": f"层{layer}使用率达{usage_ratio:.1%}，需要清理或晋升",
            "red": f"层{layer}使用率达{usage_ratio:.1%}，紧急处理！",
        }

        auto_actions = {
            "yellow": "monitoring",
            "orange": "auto_consolidate",
            "red": "emergency_promote",
        }

        alert = CapacityAlert(
            id=hashlib.sha256(f"{layer}{time.time()}{uuid.uuid4()}".encode()).hexdigest()[:12],
            layer=layer,
            level=level,
            message=messages.get(level, ""),
            timestamp=time.time(),
            metric_value=usage_ratio,
            threshold_value=self._alert_levels.get(level, 0.5),
            auto_action_taken=auto_actions.get(level, "none"),
        )

        with self._lock:
            self._alerts.append(alert)
            if len(self._alerts) > self._max_alerts:
                self._alerts = self._alerts[-self._max_alerts:]

        return alert

    def get_active_alerts(self, level: Optional[str] = None) -> List[CapacityAlert]:
        with self._lock:
            alerts = [a for a in self._alerts if not a.resolved]
            if level:
                alerts = [a for a in alerts if a.level == level]
            return alerts

    def resolve_alert(self, alert_id: str):
        with self._lock:
            for a in self._alerts:
                if a.id == alert_id:
                    a.resolved = True
                    break

    def get_alert_summary(self) -> Dict:
        with self._lock:
            active = [a for a in self._alerts if not a.resolved]
            by_level = defaultdict(int)
            for a in active:
                by_level[a.level] += 1
            return {
                "total_alerts": len(self._alerts),
                "active_alerts": len(active),
                "by_level": dict(by_level),
                "latest_alert": active[-1].message if active else None,
            }


class FeedbackOptimizer:
    def __init__(self):
        self._feedback_log: List[Dict] = []
        self._max_log = 500
        self._optimization_rules: Dict[str, Dict] = {}
        self._lock = threading.RLock()
        self._initialize_default_rules()

    def _initialize_default_rules(self):
        self._optimization_rules = {
            "consolidation_efficiency": {
                "metric": "promoted_ratio",
                "target": 0.7,
                "action_if_below": "reduce_threshold",
                "action_if_above": "increase_threshold",
            },
            "rejection_rate": {
                "metric": "reject_ratio",
                "target": 0.05,
                "action_if_below": "maintain",
                "action_if_above": "relax_quality_gate",
            },
            "capacity_balance": {
                "metric": "max_layer_usage_ratio",
                "target": 0.8,
                "action_if_below": "maintain",
                "action_if_above": "aggressive_consolidate",
            },
        }

    def record_feedback(self, operation: str, layer: str, result: Dict):
        with self._lock:
            entry = {
                "timestamp": time.time(),
                "operation": operation,
                "layer": layer,
                "result": result,
            }
            self._feedback_log.append(entry)
            if len(self._feedback_log) > self._max_log:
                self._feedback_log = self._feedback_log[-self._max_log:]

    def analyze_and_optimize(self, layer_stats: Dict, threshold_manager: DynamicThresholdManager) -> List[Dict]:
        recommendations = []
        with self._lock:
            for layer_name, stats in layer_stats.items():
                usage = stats.get("usage_ratio", 0.0)
                if usage > 0.9:
                    recommendations.append({
                        "layer": layer_name,
                        "action": "emergency_consolidate",
                        "reason": f"usage={usage:.1%} > 90%",
                        "priority": "critical",
                    })
                elif usage > 0.7:
                    recommendations.append({
                        "layer": layer_name,
                        "action": "proactive_consolidate",
                        "reason": f"usage={usage:.1%} > 70%",
                        "priority": "high",
                    })

                recent_ops = [f for f in self._feedback_log
                              if f["layer"] == layer_name
                              and time.time() - f["timestamp"] <= 3600]
                if recent_ops:
                    rejects = sum(1 for f in recent_ops if f.get("result", {}).get("status") == "rejected")
                    reject_rate = rejects / len(recent_ops)
                    if reject_rate > 0.1:
                        recommendations.append({
                            "layer": layer_name,
                            "action": "relax_quality_gate",
                            "reason": f"reject_rate={reject_rate:.1%} > 10%",
                            "priority": "medium",
                        })

        return recommendations

    def get_feedback_summary(self) -> Dict:
        with self._lock:
            if not self._feedback_log:
                return {"total_operations": 0}
            by_op = defaultdict(int)
            by_layer = defaultdict(int)
            for f in self._feedback_log:
                by_op[f["operation"]] += 1
                by_layer[f["layer"]] += 1
            return {
                "total_operations": len(self._feedback_log),
                "by_operation": dict(by_op),
                "by_layer": dict(by_layer),
            }


class MemoryImportCoordinator:
    def __init__(self, data_path: Path):
        self._data_path = data_path
        self._import_log: List[Dict] = []
        self._max_log = 1000
        self._lock = threading.RLock()
        self._batch_size = 20
        self._import_stats = {
            "total_imported": 0,
            "total_skipped": 0,
            "total_errors": 0,
            "batches_completed": 0,
        }

    def prepare_batch(self, conversations: List[Dict], batch_index: int) -> Dict:
        batch_id = hashlib.sha256(f"batch_{batch_index}_{time.time()}".encode()).hexdigest()[:12]
        batch = {
            "batch_id": batch_id,
            "batch_index": batch_index,
            "size": len(conversations),
            "conversations": conversations,
            "status": "prepared",
            "created_at": time.time(),
        }
        return batch

    def format_memory_entry(self, conv: Dict) -> Dict:
        content_parts = []
        content_parts.append(f"[Trae对话] {conv.get('time', 'unknown')}")
        content_parts.append(f"资源: {conv.get('resource', 'unknown')}")
        content_parts.append(f"会话ID: {conv.get('id', 'unknown')}")

        if conv.get("content_text"):
            content_parts.append(f"内容摘要: {conv['content_text'][:500]}")
        elif conv.get("content_samples"):
            for sample in conv["content_samples"][:2]:
                content_parts.append(f"文件[{sample.get('file', '?')}]: {sample.get('preview', '')[:200]}")

        content = "\n".join(content_parts)

        tags = ["trae", "conversation", f"date:{conv.get('time', '')[:10]}"]
        if conv.get("resource"):
            res = conv.get("resource", "")
            if "天机" in res or "tianji" in res.lower():
                tags.append("tianji")
            if "元初" in res:
                tags.append("yuanchu")

        layer = self._determine_layer(conv)

        return {
            "content": content,
            "layer": layer,
            "tags": tags,
            "priority": "medium",
            "metadata": {
                "source": "trae_history",
                "session_id": conv.get("id", ""),
                "timestamp": conv.get("timestamp", 0),
                "resource": conv.get("resource", ""),
                "file_count": conv.get("file_count", 0),
                "total_file_size": conv.get("total_file_size", 0),
            },
        }

    def _determine_layer(self, conv: Dict) -> str:
        file_count = conv.get("file_count", 0)
        total_size = conv.get("total_file_size", 0)
        has_code = any(
            f.get("suffix", "") in (".py", ".ts", ".tsx", ".js", ".bat", ".ps1")
            for f in conv.get("files", [])
        )

        if file_count > 10 or total_size > 100000:
            return "episodic"
        elif file_count > 3 or has_code:
            return "short_term"
        else:
            return "working"

    def record_import(self, batch_id: str, results: List[Dict]):
        with self._lock:
            imported = sum(1 for r in results if r.get("status") == "stored")
            skipped = sum(1 for r in results if r.get("status") == "skipped")
            errors = sum(1 for r in results if r.get("status") == "error")

            self._import_stats["total_imported"] += imported
            self._import_stats["total_skipped"] += skipped
            self._import_stats["total_errors"] += errors
            self._import_stats["batches_completed"] += 1

            self._import_log.append({
                "batch_id": batch_id,
                "timestamp": time.time(),
                "imported": imported,
                "skipped": skipped,
                "errors": errors,
            })
            if len(self._import_log) > self._max_log:
                self._import_log = self._import_log[-self._max_log:]

    def get_import_stats(self) -> Dict:
        with self._lock:
            return {
                **self._import_stats,
                "recent_batches": self._import_log[-10:],
            }


class MemoryDynamicManager:
    def __init__(self, data_path: str):
        self._data_path = Path(data_path)
        self._tracker = AccumulationTracker()
        self._threshold_mgr = DynamicThresholdManager(self._tracker)
        self._alert_sys = CapacityAlertSystem()
        self._optimizer = FeedbackOptimizer()
        self._import_coord = MemoryImportCoordinator(self._data_path)
        self._lock = threading.RLock()
        self._running = False
        self._monitor_thread = None
        self._snapshot_interval = 60
        self._adjustment_interval = 300
        self._last_snapshot_time = 0
        self._last_adjustment_time = 0
        self._state_file = self._data_path / "dynamic_manager_state.json"

    @property
    def tracker(self) -> AccumulationTracker:
        return self._tracker

    @property
    def threshold_manager(self) -> DynamicThresholdManager:
        return self._threshold_mgr

    @property
    def alert_system(self) -> CapacityAlertSystem:
        return self._alert_sys

    @property
    def optimizer(self) -> FeedbackOptimizer:
        return self._optimizer

    @property
    def import_coordinator(self) -> MemoryImportCoordinator:
        return self._import_coord

    def on_memory_write(self, layer: str, size_bytes: int, entry_id: str = ""):
        self._tracker.record_write(layer, size_bytes)
        self._optimizer.record_feedback("write", layer, {
            "entry_id": entry_id,
            "size_bytes": size_bytes,
            "status": "stored",
        })

    def on_memory_delete(self, layer: str, size_bytes: int):
        self._tracker.record_delete(layer, size_bytes)

    def on_memory_promotion(self, from_layer: str, to_layer: str, size_bytes: int):
        self._tracker.record_promotion(from_layer, to_layer, size_bytes)
        self._optimizer.record_feedback("promotion", from_layer, {
            "to_layer": to_layer,
            "size_bytes": size_bytes,
            "status": "promoted",
        })

    def on_memory_reject(self, layer: str, reason: str):
        self._tracker.record_reject(layer)
        self._optimizer.record_feedback("reject", layer, {
            "reason": reason,
            "status": "rejected",
        })

    def run_monitoring_cycle(self, layer_stats: Dict[str, Dict]) -> Dict:
        results = {
            "timestamp": time.time(),
            "snapshots": [],
            "alerts": [],
            "threshold_adjustments": {},
            "optimization_recommendations": [],
        }

        snapshots = self._tracker.take_all_snapshots(layer_stats)
        results["snapshots"] = [
            {
                "layer": s.layer,
                "total_entries": s.total_entries,
                "total_bytes": s.total_bytes,
                "delta_entries": s.delta_entries,
                "delta_bytes": s.delta_bytes,
                "write_rate": s.write_rate_entries_per_min,
            }
            for s in snapshots
        ]

        for layer_name, stats in layer_stats.items():
            usage = stats.get("usage_ratio", 0.0)
            alert = self._alert_sys.check_capacity(layer_name, usage)
            if alert:
                results["alerts"].append({
                    "layer": alert.layer,
                    "level": alert.level,
                    "message": alert.message,
                    "auto_action": alert.auto_action_taken,
                })

        self._threshold_mgr.adjust_thresholds()
        results["threshold_adjustments"] = self._threshold_mgr.get_all_thresholds()

        recommendations = self._optimizer.analyze_and_optimize(
            layer_stats, self._threshold_mgr
        )
        results["optimization_recommendations"] = recommendations

        return results

    def get_full_dashboard(self) -> Dict:
        return {
            "accumulation_summary": self._tracker.get_summary(),
            "trends": self._tracker.get_all_trends(),
            "thresholds": self._threshold_mgr.get_all_thresholds(),
            "alerts": self._alert_sys.get_alert_summary(),
            "feedback": self._optimizer.get_feedback_summary(),
            "import_stats": self._import_coord.get_import_stats(),
            "timestamp": time.time(),
        }

    def save_state(self):
        state = {
            "import_stats": self._import_coord.get_import_stats(),
            "thresholds": self._threshold_mgr.get_all_thresholds(),
            "alert_summary": self._alert_sys.get_alert_summary(),
            "timestamp": time.time(),
        }
        self._data_path.mkdir(parents=True, exist_ok=True)
        with open(str(self._state_file), 'w', encoding='utf-8') as f:
            json.dump(state, f, indent=2, ensure_ascii=False, default=str)

    def load_state(self):
        if self._state_file.exists():
            try:
                with open(str(self._state_file), 'r', encoding='utf-8-sig') as f:
                    state = json.load(f)
                return state
            except Exception:
                return {}
        return {}
