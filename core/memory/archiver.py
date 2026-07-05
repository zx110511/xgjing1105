r"""
天机记忆系统 (TIANJI) - 归档与容量组件 ArchiveManager  [v10-ready]
=================================================================
负责归档管理与容量/余量追踪：forget 软删除归档 → 超容强制驱逐 →
purge 清层 → size tracking（层大小/余量/累积比/速率）。

[v10-ready] 组件通过构造函数接收 engine 宿主，所有共享状态（_layers/
_layer_sizes/_archive/_accumulated_* 等）均经由宿主访问，组件之间不互相 import。
"""

import time

from . import MemoryEntry


class ArchiveManager:
    """归档与容量管理 — forget / 驱逐 / 余量与 size tracking。"""

    def __init__(self, engine):
        self._engine = engine

    # --------------------------------------------------------- size tracking
    def _get_layer_size(self, layer_name: str) -> int:
        return self._engine._layer_sizes.get(layer_name, 0)

    def _update_layer_size(
        self, layer_name: str, delta: int, track_accumulation: bool = True
    ):
        if layer_name in self._engine._layer_sizes:
            self._engine._layer_sizes[layer_name] += delta
        if track_accumulation:
            if layer_name in self._engine._accumulated_bytes:
                self._engine._accumulated_bytes[layer_name] += max(0, delta)
            if layer_name in self._engine._accumulated_entries:
                self._engine._accumulated_entries[layer_name] += 1 if delta > 0 else 0
            if layer_name in self._engine._rate_tracker and delta > 0:
                self._engine._rate_tracker[layer_name].append((time.time(), delta))
                self._engine._rate_tracker[layer_name] = [
                    (ts, sz)
                    for ts, sz in self._engine._rate_tracker[layer_name]
                    if time.time() - ts <= self._engine._rate_window_seconds
                ]

    def _get_layer_usage(self, layer_name: str) -> float:
        layer_config = self._engine.config.get_layer(layer_name)
        if not layer_config:
            return 0.0
        return self._engine._get_layer_size(layer_name) / layer_config.max_size_bytes

    def _get_margin_ratio(self, layer_name: str) -> float:
        layer_config = self._engine.config.get_layer(layer_name)
        if not layer_config or layer_config.max_size_bytes <= 0:
            return 1.0
        used_bytes = self._engine._get_layer_size(layer_name)
        byte_margin = max(0.0, 1.0 - used_bytes / layer_config.max_size_bytes)
        entry_count = len(self._engine._layers.get(layer_name, {}))
        if layer_config.max_entries > 0:
            entry_margin = max(0.0, 1.0 - entry_count / layer_config.max_entries)
        else:
            entry_margin = 1.0
        return min(byte_margin, entry_margin)

    def _get_margin_level(self, layer_name: str) -> str:
        layer_config = self._engine.config.get_layer(layer_name)
        if not layer_config:
            return "red"
        safety = getattr(layer_config, "margin_management", None)
        if safety is not None:
            return safety.get_level(self._engine._get_margin_ratio(layer_name))
        margin = self._engine._get_margin_ratio(layer_name)
        if margin >= 0.50:
            return "green"
        if margin >= 0.25:
            return "yellow"
        if margin >= 0.10:
            return "orange"
        return "red"

    def _calc_current_rate(self, layer_name: str) -> float:
        records = self._engine._rate_tracker.get(layer_name, [])
        if not records:
            return 0.0
        now = time.time()
        window_records = [
            (ts, sz)
            for ts, sz in records
            if now - ts <= self._engine._rate_window_seconds
        ]
        if not window_records:
            return 0.0
        total_bytes = sum(sz for _, sz in window_records)
        time_span = now - window_records[0][0]
        if time_span <= 0:
            return 0.0
        return total_bytes / time_span

    def _get_accumulation_ratio(self, layer_name: str) -> float:
        layer_config = self._engine.config.get_layer(layer_name)
        if not layer_config or layer_config.accumulation_threshold_bytes <= 0:
            return 0.0
        return (
            self._engine._accumulated_bytes.get(layer_name, 0)
            / layer_config.accumulation_threshold_bytes
        )

    def _get_accumulation_entry_ratio(self, layer_name: str) -> float:
        layer_config = self._engine.config.get_layer(layer_name)
        if not layer_config or layer_config.accumulation_threshold_entries <= 0:
            return 0.0
        return (
            self._engine._accumulated_entries.get(layer_name, 0)
            / layer_config.accumulation_threshold_entries
        )

    # ------------------------------------------------------------- 归档/驱逐
    def forget(self, entry_id: str) -> bool:
        with self._engine._lock:
            for layer_name, layer_data in self._engine._layers.items():
                if entry_id in layer_data:
                    entry = layer_data.pop(entry_id)
                    self._engine._update_layer_size(layer_name, -entry.size_bytes)
                    self._engine._unindex_tags(entry_id, entry.tags)
                    self._engine._stats["total_entries"] -= 1
                    self._engine._stats["total_archivals"] += 1
                    # [FIX-DELETE-500] 移除不存在的_delete_entry_file调用，改为软删除标记
                    # self._engine._delete_entry_file(entry_id, layer_name)
                    self._engine._archive[entry.id] = MemoryEntry(
                        id=entry.id,
                        content=entry.content,
                        layer="archive",
                        tags=entry.tags + ["archived"],
                        priority="low",
                        created_at=entry.created_at,
                        last_accessed=time.time(),
                        access_count=entry.access_count,
                        effectiveness_score=entry.effectiveness_score,
                        related_ids=entry.related_ids,
                        metadata={**entry.metadata, "archived_at": time.time()},
                    )
                    return True
            return False

    def force_evict_overcapacity(
        self, layer: str, target_ratio: float = 0.8, max_evict: int = 200
    ) -> dict:
        with self._engine._lock:
            if layer not in self._engine._layers:
                return {
                    "status": "error",
                    "error": f"layer {layer} not found",
                    "evicted": 0,
                }
            entries = list(self._engine._layers[layer].items())
            current_count = len(entries)
            layer_config = self._engine.config.get_layer(layer)
            max_entries = (
                getattr(layer_config, "max_entries", 2000) if layer_config else 2000
            )
            target_count = int(max_entries * target_ratio)

            if current_count <= max_entries:
                return {
                    "status": "ok",
                    "message": f"within capacity ({current_count}/{max_entries})",
                    "evicted": 0,
                }

            evict_count = min(max_evict, current_count - target_count)
            if evict_count <= 0:
                evict_count = min(max_evict, current_count - int(max_entries * 0.7))

            # 按容量权重排序驱逐 — 容量压力驱动，零时间因子
            mm = (
                getattr(layer_config, "margin_management", None)
                if layer_config
                else None
            )
            if mm and hasattr(mm, "compute_memory_strength_with_usage"):
                usage_ratio = current_count / max_entries if max_entries > 0 else 0
                sorted_entries = sorted(
                    entries,
                    key=lambda x: mm.compute_memory_strength_with_usage(
                        x[1], usage_ratio
                    ),
                )
            elif mm and hasattr(mm, "compute_memory_strength"):
                sorted_entries = sorted(
                    entries,
                    key=lambda x: mm.compute_memory_strength(x[1]),
                )
            else:
                sorted_entries = sorted(
                    entries,
                    key=lambda x: (
                        x[1].effectiveness_score or 0,
                        x[1].access_count or 0,
                        x[1].created_at or 0,
                    ),
                )

            evicted = []
            for i in range(min(evict_count, len(sorted_entries))):
                entry_id, entry = sorted_entries[i]
                self._engine._layers[layer].pop(entry_id)
                self._engine._update_layer_size(layer, -entry.size_bytes)
                self._engine._unindex_tags(entry_id, entry.tags)
                self._engine._stats["total_entries"] -= 1
                self._engine._stats["total_archivals"] += 1
                self._engine._archive[entry.id] = MemoryEntry(
                    id=entry.id,
                    content=entry.content[:500],
                    layer="archive",
                    tags=entry.tags + ["force-evicted", f"from-{layer}"],
                    priority="low",
                    created_at=entry.created_at,
                    last_accessed=time.time(),
                    access_count=entry.access_count,
                    effectiveness_score=entry.effectiveness_score,
                    related_ids=entry.related_ids,
                    metadata={
                        **entry.metadata,
                        "evicted_at": time.time(),
                        "reason": "overcapacity",
                    },
                )
                evicted.append(
                    {
                        "id": entry_id,
                        "layer": layer,
                        "effectiveness_score": entry.effectiveness_score,
                        "size_bytes": entry.size_bytes,
                    }
                )

            remaining = len(self._engine._layers.get(layer, {}))
            return {
                "status": "completed",
                "layer": layer,
                "before": current_count,
                "after": remaining,
                "max_entries": max_entries,
                "evicted": len(evicted),
                "target_ratio": target_ratio,
                "reason": "overcapacity_force_evict",
            }

    def purge_layer(self, layer_name: str) -> int:
        """
        清空指定记忆层的所有条目，恢复容量计数器。

        参数:
          layer_name: 要清空的层级名称

        返回: 删除的条目数
        """
        with self._engine._lock:
            count = len(self._engine._layers.get(layer_name, {}))
            if count == 0:
                return 0
            for entry_id in list(self._engine._layers[layer_name].keys()):
                entry = self._engine._layers[layer_name][entry_id]
                for tag in entry.tags:
                    if tag in self._engine._tag_index:
                        self._engine._tag_index[tag].discard(entry_id)
                self._engine._delete_entry_file(entry_id, layer_name)
            self._engine._layers[layer_name] = {}
            self._engine._layer_sizes[layer_name] = 0
            if layer_name in self._engine._accumulated_bytes:
                self._engine._accumulated_bytes[layer_name] = 0
            if layer_name in self._engine._accumulated_entries:
                self._engine._accumulated_entries[layer_name] = 0
            return count

    # --------------------------------------------------------- 容量统计信息
    def get_layer_capacity_info(self) -> dict[str, dict]:
        with self._engine._lock:
            info = {}
            for layer in self._engine.config.layers:
                size = self._engine._get_layer_size(layer.name)
                usage = size / layer.max_size_bytes if layer.max_size_bytes > 0 else 0
                accumulated = self._engine._accumulated_bytes.get(layer.name, 0)
                acc_entries = self._engine._accumulated_entries.get(layer.name, 0)
                acc_ratio = self._engine._get_accumulation_ratio(layer.name)
                entry_ratio = self._engine._get_accumulation_entry_ratio(layer.name)
                last_cons = self._engine._last_consolidation_time.get(layer.name, 0.0)
                info[layer.name] = {
                    "size_bytes": size,
                    "max_size_bytes": layer.max_size_bytes,
                    "hard_cap_bytes": layer.hard_cap_bytes,
                    "entry_count": len(self._engine._layers[layer.name]),
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
                    or len(self._engine._layers[layer.name]) > layer.max_entries,
                    "at_hard_cap": size >= layer.hard_cap_bytes
                    or (
                        layer.max_entries > 0
                        and len(self._engine._layers[layer.name]) > layer.max_entries
                    ),
                    "seconds_since_last_consolidation": round(
                        time.time() - last_cons, 1
                    ),
                }
            return info

    def get_accumulation_stats(self) -> dict[str, dict]:
        with self._engine._lock:
            stats = {}
            for layer in self._engine.config.layers:
                stats[layer.name] = {
                    "accumulated_bytes": self._engine._accumulated_bytes.get(
                        layer.name, 0
                    ),
                    "threshold_bytes": layer.accumulation_threshold_bytes,
                    "ratio": round(self._engine._get_accumulation_ratio(layer.name), 4),
                    "needs_check": self._engine._get_accumulation_ratio(layer.name)
                    >= 1.0,
                }
            return stats
