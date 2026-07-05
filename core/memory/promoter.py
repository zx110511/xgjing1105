r"""
天机记忆系统 (TIANJI) - 层级晋升组件 PromotionEngine  [v10-ready]
================================================================
负责记忆层级晋升全链路：固结触发判定 → promotion_score 多维评分 →
单条/批量固结 → 自动固结 / 硬上限强制晋升 / 渐进式编排 / L0 TTL。

[v10-ready] 组件通过构造函数接收 engine 宿主，所有共享状态与跨组件协作
（如归档 forget、容量 margin 计算等）均经由宿主访问，组件之间不互相 import。
"""

import time

from . import MemoryEntry


class PromotionEngine:
    """晋升引擎 — consolidate / promotion_score / 自动固结编排。"""

    def __init__(self, engine):
        self._engine = engine

    # ---------------------------------------------------------------- 触发判定
    def _check_orchestration_trigger(self, layer_name: str) -> tuple[bool, str]:
        layer_config = self._engine.config.get_layer(layer_name)
        if not layer_config:
            return False, "no_config"

        accumulated_bytes = self._engine._accumulated_bytes.get(layer_name, 0)
        accumulated_entries = self._engine._accumulated_entries.get(layer_name, 0)
        threshold_bytes = getattr(layer_config, "accumulation_threshold_bytes", 0)
        threshold_entries = getattr(layer_config, "accumulation_threshold_entries", 0)

        if threshold_bytes > 0 and accumulated_bytes >= threshold_bytes:
            return True, f"delta_bytes_trigger({accumulated_bytes}/{threshold_bytes})"

        if threshold_entries > 0 and accumulated_entries >= threshold_entries:
            return (
                True,
                f"delta_entries_trigger({accumulated_entries}/{threshold_entries})",
            )

        current_rate = self._engine._calc_current_rate(layer_name)
        rate_threshold = getattr(layer_config, "rate_threshold_bytes_per_sec", 0)
        if rate_threshold > 0 and current_rate >= rate_threshold:
            return (
                True,
                f"burst_rate_trigger({current_rate:.0f}/{rate_threshold:.0f} B/s)",
            )

        margin_ratio = self._engine._get_margin_ratio(layer_name)
        safety = getattr(layer_config, "margin_management", None)
        if safety is not None and margin_ratio < safety.safety_floor:
            return (
                True,
                f"safety_floor_breach(margin={margin_ratio:.2f}<{safety.safety_floor})",
            )
        if safety is not None and margin_ratio < safety.target_margin:
            return (
                True,
                f"below_target_margin(margin={margin_ratio:.2f}<{safety.target_margin})",
            )

        if margin_ratio < 0.05:
            return True, f"safety_floor_breach(margin={margin_ratio:.2f})"
        if margin_ratio < 0.15:
            return True, f"below_target_margin(margin={margin_ratio:.2f})"

        return (
            False,
            f"below_threshold(bytes={accumulated_bytes}/{threshold_bytes}, entries={accumulated_entries}/{threshold_entries}, margin={margin_ratio:.2f})",
        )

    def _should_consolidate(self, layer_name: str) -> tuple[bool, str]:
        return self._engine._check_orchestration_trigger(layer_name)

    def _can_consolidate_now(self, layer_name: str) -> tuple[bool, str]:
        layer_config = self._engine.config.get_layer(layer_name)
        if not layer_config:
            return False, "no_config"
        elapsed = time.time() - self._engine._last_consolidation_time.get(
            layer_name, 0.0
        )
        if elapsed < layer_config.min_consolidation_interval_seconds:
            return (
                False,
                f"anti_thrash(wait {layer_config.min_consolidation_interval_seconds - elapsed:.1f}s)",
            )
        return True, "ready"

    def _reset_accumulation(self, layer_name: str):
        if layer_name in self._engine._accumulated_bytes:
            self._engine._accumulated_bytes[layer_name] = 0
        if layer_name in self._engine._accumulated_entries:
            self._engine._accumulated_entries[layer_name] = 0
        if layer_name in self._engine._last_consolidation_time:
            self._engine._last_consolidation_time[layer_name] = time.time()

    def _log_consolidation_event(self, event: dict):
        event["timestamp"] = time.time()
        self._engine._consolidation_event_log.append(event)
        if (
            len(self._engine._consolidation_event_log)
            > self._engine._consolidation_event_log_max
        ):
            self._engine._consolidation_event_log = (
                self._engine._consolidation_event_log[
                    -self._engine._consolidation_event_log_max :
                ]
            )

    # ----------------------------------------------------------- 单条/批量固结
    def _validate_consolidation_params(
        self, from_layer: str, to_layer: str, entry_id: str
    ) -> MemoryEntry | None:
        """验证巩固参数并返回条目"""
        if (
            from_layer not in self._engine._layers
            or to_layer not in self._engine._layers
        ):
            return None
        if entry_id not in self._engine._layers[from_layer]:
            return None
        return self._engine._layers[from_layer].pop(entry_id)

    def _create_consolidated_entry(
        self, entry: MemoryEntry, from_layer: str, to_layer: str
    ) -> MemoryEntry:
        """创建巩固后的新条目"""
        return MemoryEntry(
            id=entry.id,
            content=f"[{from_layer}->{to_layer}] {entry.content}",
            layer=to_layer,
            tags=entry.tags + [f"from-{from_layer}"],
            priority=entry.priority,
            effectiveness_score=entry.effectiveness_score,
            related_ids=entry.related_ids,
            metadata={
                **entry.metadata,
                "consolidated_at": time.time(),
                "source_layer": from_layer,
            },
        )

    def consolidate(self, from_layer: str, to_layer: str, entry_id: str) -> str | None:
        """巩固条目到更高层"""
        with self._engine._lock:
            entry = self._engine._validate_consolidation_params(
                from_layer, to_layer, entry_id
            )
            if entry is None:
                return None

            self._engine._update_layer_size(from_layer, -entry.size_bytes)
            self._engine._unindex_tags(entry_id, entry.tags)

            new_entry = self._engine._create_consolidated_entry(
                entry, from_layer, to_layer
            )

            self._engine._layers[to_layer][entry.id] = new_entry
            self._engine._update_layer_size(to_layer, new_entry.size_bytes)
            self._engine._index_tags(entry.id, new_entry.tags)
            self._engine._stats["total_consolidations"] += 1

            return entry.id

    def consolidate_batch(
        self,
        from_layer: str,
        to_layer: str | None = None,
        threshold: float = 0.6,
        max_entries: int = 50,
        use_quality_promotion: bool = True,
    ) -> dict:
        with self._engine._lock:
            if from_layer not in self._engine._layers:
                return {
                    "status": "error",
                    "error": f"layer {from_layer} not found",
                    "consolidated": 0,
                }
            target_layer = to_layer
            if not target_layer:
                layer_order = [
                    "sensory",
                    "working",
                    "short_term",
                    "episodic",
                    "semantic",
                    "meta",
                ]
                try:
                    idx = layer_order.index(from_layer)
                    if idx < len(layer_order) - 1:
                        target_layer = layer_order[idx + 1]
                except ValueError:
                    return {
                        "status": "error",
                        "error": f"invalid layer: {from_layer}",
                        "consolidated": 0,
                    }
            if target_layer not in self._engine._layers:
                self._engine._layers[target_layer] = {}
            candidates = []
            for entry_id, entry in list(self._engine._layers[from_layer].items()):
                if use_quality_promotion:
                    score = self._engine.promotion_score(entry)
                    if score >= threshold:
                        candidates.append((score, entry_id, entry))
                else:
                    candidates.append((0.5, entry_id, entry))
            candidates.sort(key=lambda x: x[0], reverse=True)
            candidates = candidates[:max_entries]
            results = []
            for score, entry_id, entry in candidates:
                self._engine._layers[from_layer].pop(entry_id)
                self._engine._update_layer_size(from_layer, -entry.size_bytes)
                self._engine._unindex_tags(entry_id, entry.tags)
                new_entry = MemoryEntry(
                    id=entry.id,
                    content=f"[{from_layer}->{target_layer}] {entry.content[:1000]}",
                    layer=target_layer,
                    tags=entry.tags + [f"from-{from_layer}", "batch-consolidated"],
                    priority=entry.priority,
                    effectiveness_score=entry.effectiveness_score,
                    related_ids=entry.related_ids,
                    metadata={
                        **entry.metadata,
                        "consolidated_at": time.time(),
                        "source_layer": from_layer,
                        "promotion_score": round(score, 4),
                    },
                )
                self._engine._layers[target_layer][entry.id] = new_entry
                self._engine._update_layer_size(target_layer, new_entry.size_bytes)
                self._engine._index_tags(entry.id, new_entry.tags)
                self._engine._stats["total_consolidations"] += 1
                results.append(
                    {
                        "id": entry.id,
                        "promotion_score": round(score, 4),
                        "from": from_layer,
                        "to": target_layer,
                        "size_bytes": new_entry.size_bytes,
                    }
                )
            if from_layer in self._engine._layers:
                self._engine._auto_consolidate(from_layer)
            # [v10-ready] 晋升后触发图谱同步（天罡-17）
            try:
                if results and target_layer in ("episodic", "semantic"):
                    from core.memory.graph_store import TianjiGraphStore as KnowledgeGraphStore

                    _promoted = []
                    for _r in results:
                        _e = self._engine._layers.get(target_layer, {}).get(_r["id"])
                        if _e is not None:
                            _promoted.append(
                                {
                                    "content": getattr(_e, "content", ""),
                                    "tags": getattr(_e, "tags", []),
                                    "metadata": getattr(_e, "metadata", {}),
                                }
                            )
                    if _promoted:
                        _graph = KnowledgeGraphStore()
                        if hasattr(_graph, "sync_from_memories"):
                            _graph.sync_from_memories(_promoted)
            except Exception:
                pass  # 图谱同步失败不影响晋升主流程
            return {
                "status": "completed",
                "from_layer": from_layer,
                "to_layer": target_layer,
                "consolidated": len(results),
                "threshold": threshold,
                "candidates_available": len(self._engine._layers.get(from_layer, {})),
                "results": results,
            }

    def smart_promote(
        self, layer: str, threshold: float = 0.6, limit: int = 10
    ) -> list[dict]:
        return self._engine.consolidate_batch(
            from_layer=layer,
            to_layer=None,
            threshold=threshold,
            max_entries=limit,
            use_quality_promotion=True,
        )["results"]

    def consolidate_all_layers(
        self, threshold: float = 0.6, max_per_layer: int = 30
    ) -> dict:
        results = {}
        total = 0
        layers_to_scan = ["sensory", "working", "short_term", "episodic", "semantic"]
        for layer in layers_to_scan:
            if layer in self._engine._layers and len(self._engine._layers[layer]) > 0:
                r = self._engine.consolidate_batch(
                    from_layer=layer,
                    threshold=threshold,
                    max_entries=max_per_layer,
                    use_quality_promotion=True,
                )
                results[layer] = r
                total += r["consolidated"]
        return {
            "status": "completed",
            "total_consolidated": total,
            "layer_results": results,
        }

    def check_l0_ttl(
        self, ttl_days: int = 7, archive_days: int = 30, max_l0_size_mb: float = 10.0
    ) -> dict:
        result = {
            "scanned": 0,
            "consolidated_to_l1": 0,
            "archived": 0,
            "force_consolidated": 0,
            "errors": [],
        }

        now = time.time()
        ttl_seconds = ttl_days * 86400
        archive_seconds = archive_days * 86400

        with self._engine._lock:
            if "sensory" not in self._engine._layers:
                return result

            l0_entries = list(self._engine._layers["sensory"].items())
            result["scanned"] = len(l0_entries)

            total_size = sum(e.size_bytes for _, e in l0_entries)
            if total_size > max_l0_size_mb * 1024 * 1024:
                sorted_entries = sorted(l0_entries, key=lambda x: x[1].created_at or 0)
                force_count = 0
                for entry_id, entry in sorted_entries:
                    if total_size <= max_l0_size_mb * 1024 * 1024 * 0.8:
                        break
                    try:
                        cid = self._engine.consolidate("sensory", "working", entry_id)
                        if cid:
                            force_count += 1
                            total_size -= entry.size_bytes
                    except Exception as e:
                        result["errors"].append(str(e))
                result["force_consolidated"] = force_count

            l0_entries = list(self._engine._layers["sensory"].items())

            for entry_id, entry in l0_entries:
                age = now - (entry.created_at or now)

                if age > archive_seconds:
                    try:
                        if entry_id in self._engine._layers.get("sensory", {}):
                            self._engine._layers["sensory"].pop(entry_id, None)
                            self._engine._update_layer_size(
                                "sensory", -entry.size_bytes
                            )
                            self._engine._unindex_tags(entry_id, entry.tags)
                            self._engine._archive[entry.id] = MemoryEntry(
                                id=entry.id,
                                content=entry.content[:500],
                                layer="archive",
                                tags=entry.tags + ["ttl-archived"],
                                priority="low",
                                created_at=entry.created_at,
                                last_accessed=time.time(),
                                access_count=entry.access_count,
                                effectiveness_score=entry.effectiveness_score,
                                related_ids=entry.related_ids,
                                metadata={
                                    **entry.metadata,
                                    "archived_at": now,
                                    "reason": "l0_ttl_expired",
                                },
                            )
                            result["archived"] += 1
                    except Exception as e:
                        result["errors"].append(str(e))

                elif age > ttl_seconds:
                    try:
                        cid = self._engine.consolidate("sensory", "working", entry_id)
                        if cid:
                            result["consolidated_to_l1"] += 1
                    except Exception as e:
                        result["errors"].append(str(e))

        return result

    def get_consolidation_candidates(
        self, layer: str = "", threshold: float = 0.5
    ) -> list[dict]:
        layers = (
            [layer]
            if layer
            else [name for name in self._engine._layers if name not in ("meta",)]
        )
        candidates = []
        for layer_name in layers:
            if layer_name not in self._engine._layers:
                continue
            for entry_id, entry in self._engine._layers[layer_name].items():
                score = self._engine.promotion_score(entry)
                if score >= threshold:
                    candidates.append(
                        {
                            "entry_id": entry_id,
                            "layer": layer_name,
                            "score": round(score, 4),
                            "tags": entry.tags[:5],
                            "size_bytes": entry.size_bytes,
                        }
                    )
        candidates.sort(key=lambda x: x["score"], reverse=True)
        return candidates

    # --------------------------------------------------------- promotion_score
    def _calculate_recency_factor(self, entry: MemoryEntry) -> float:
        """计算新近度因子"""
        time_diff = time.time() - entry.last_accessed
        return max(0.1, 1.0 - time_diff / (30 * 24 * 3600))

    def _calculate_weighted_promotion_sum(
        self,
        entry: MemoryEntry,
        recency_factor: float,
        upstream_depth: float,
        connectedness: float,
        quality_score: float,
        delta_frequency: float,
        consolidation_benefit: float,
        margin_pressure: float,
    ) -> float:
        """计算加权晋升分数"""
        w = self._engine.config.promotion_weights

        return (
            entry.priority_weight() * w.priority_weight
            + entry.effectiveness_score * w.effectiveness
            + recency_factor * w.recency
            + min(1.0, entry.access_count / 20) * w.access_count
            + upstream_depth * w.upstream_depth
            + connectedness * w.connectedness
            + quality_score * getattr(w, "quality_score", 0.10)
            + delta_frequency * getattr(w, "delta_frequency", 0.05)
            + consolidation_benefit * getattr(w, "consolidation_benefit", 0.05)
            + margin_pressure * getattr(w, "margin_pressure", 0.05)
        )

    def promotion_score(self, entry: MemoryEntry, engine=None) -> float:
        """计算条目晋升分数"""
        recency_factor = self._engine._calculate_recency_factor(entry)
        upstream_depth = self._engine._calc_upstream_depth(entry)
        connectedness = self._engine._calc_connectedness(entry)
        quality_score = self._engine._calc_quality_score(entry)
        delta_frequency = self._engine._calc_delta_frequency(entry)
        consolidation_benefit = self._engine._calc_consolidation_benefit(entry)
        margin_pressure = self._engine._calc_margin_pressure(entry.layer)

        return self._engine._calculate_weighted_promotion_sum(
            entry,
            recency_factor,
            upstream_depth,
            connectedness,
            quality_score,
            delta_frequency,
            consolidation_benefit,
            margin_pressure,
        )

    def _calc_upstream_depth(self, entry: MemoryEntry) -> float:
        if not entry.related_ids:
            return 0.3
        total_depth = 0
        count = 0
        for rid in entry.related_ids[:10]:
            for layer_name, layer_data in self._engine._layers.items():
                if rid in layer_data:
                    ref = layer_data[rid]
                    layer_idx = self._engine.config.get_layer_index(ref.layer)
                    total_depth += (layer_idx + 1) / 6.0
                    count += 1
                    break
        if count == 0:
            return 0.3
        return min(1.0, total_depth / count)

    def _calc_connectedness(self, entry: MemoryEntry) -> float:
        if not entry.related_ids:
            return 0.2
        related_count = len(entry.related_ids)
        score = min(1.0, related_count / 10.0)
        total_links = 0
        for rid in entry.related_ids[:5]:
            for layer_name, layer_data in self._engine._layers.items():
                if rid in layer_data:
                    ref = layer_data[rid]
                    total_links += len(ref.related_ids)
                    break
        avg_links = total_links / max(1, min(5, len(entry.related_ids)))
        score = (score + min(1.0, avg_links / 20.0)) / 2.0
        return max(0.2, score)

    def _calc_quality_score(self, entry: MemoryEntry) -> float:
        dims = []
        if entry.metadata.get("conflict_resolution") in ("confirm", "merged"):
            dims.append(0.8)
        elif entry.metadata.get("conflict_resolution") == "denied":
            dims.append(0.2)
        else:
            dims.append(0.5)
        if entry.tags and len(entry.tags) >= 2:
            dims.append(min(1.0, len(entry.tags) / 5.0))
        else:
            dims.append(0.3)
        if entry.metadata.get("upstream_id") or entry.related_ids:
            dims.append(0.7)
        else:
            dims.append(0.3)
        return sum(dims) / len(dims) if dims else 0.5

    def _calc_delta_frequency(self, entry: MemoryEntry) -> float:
        accumulated = self._engine._accumulated_entries.get(entry.layer, 0)
        layer_config = self._engine.config.get_layer(entry.layer)
        if not layer_config or layer_config.accumulation_threshold_entries <= 0:
            return 0.5
        ratio = accumulated / layer_config.accumulation_threshold_entries
        return min(1.0, ratio)

    def _calc_consolidation_benefit(self, entry: MemoryEntry) -> float:
        margin_ratio = self._engine._get_margin_ratio(entry.layer)
        if margin_ratio < 0.15:
            return 0.9
        elif margin_ratio < 0.30:
            return 0.7
        elif margin_ratio < 0.50:
            return 0.4
        return 0.1

    def _calc_margin_pressure(self, layer_name: str) -> float:
        margin_ratio = self._engine._get_margin_ratio(layer_name)
        layer_config = self._engine.config.get_layer(layer_name)
        if not layer_config:
            return 0.5
        safety = getattr(layer_config, "margin_management", None)
        if safety is None:
            return 0.5
        safety_floor = getattr(safety, "safety_floor", 0.05)
        target_margin = getattr(safety, "target_margin", 0.15)
        if margin_ratio < safety_floor:
            return 1.0
        if margin_ratio < target_margin:
            return 0.5 + 0.5 * (target_margin - margin_ratio) / max(
                target_margin - safety_floor, 0.01
            )
        return max(0.0, 0.5 * (1.0 - margin_ratio))

    # ---------------------------------------------------- 自动固结 / 硬上限编排
    def _auto_consolidate(self, from_layer: str):
        self._engine._sync_evo_config()
        layer_config = self._engine.config.get_layer(from_layer)
        if not layer_config:
            return
        next_layer = self._engine.config.get_next_layer(from_layer)

        should, reason = self._engine._should_consolidate(from_layer)
        margin_ratio = self._engine._get_margin_ratio(from_layer)

        # MarginManagement: 余量驱动的自动固结触发
        mm = getattr(layer_config, 'margin_management', None)
        if mm and mm.should_auto_consolidate(margin_ratio) and not should:
            should = True
            reason = "margin_management_triggered"

        if not should:
            return

        margin_level = self._engine._get_margin_level(from_layer)
        if margin_level == "green":
            ratio = getattr(layer_config, "consolidation_ratio", 0.15)
        elif margin_level == "yellow" or margin_level == "orange":
            ratio = getattr(layer_config, "deep_consolidation_ratio", 0.25)
        else:
            ratio = getattr(layer_config, "emergency_consolidation_ratio", 0.50)

        # MarginManagement: 驱逐低价值条目
        if mm:
            evict_cfg = mm.get_evict_config(margin_ratio)
            if evict_cfg:
                evict_result = self._engine.force_evict_overcapacity(
                    from_layer,
                    target_ratio=evict_cfg["target_ratio"],
                    max_evict=200,
                )
                self._engine._log_consolidation_event({
                    "event": "margin_eviction",
                    "from_layer": from_layer,
                    "margin_level": margin_level,
                    "evict_config": evict_cfg,
                    "evict_result": evict_result,
                })

        if not next_layer:
            if margin_level == "red":
                entries = sorted(
                    self._engine._layers[from_layer].values(),
                    key=lambda e: self._engine.promotion_score(e),
                    reverse=True,
                )
                archive_count = max(3, int(len(entries) * ratio))
                for entry in entries[:archive_count]:
                    self._engine.forget(entry.id)
                self._engine._log_consolidation_event(
                    {
                        "event": "archive_no_next_layer",
                        "from_layer": from_layer,
                        "trigger_reason": reason,
                        "margin_level": margin_level,
                        "archived_count": archive_count,
                    }
                )
            else:
                self._engine._log_consolidation_event(
                    {
                        "event": "consolidation_skipped_no_next",
                        "from_layer": from_layer,
                        "trigger_reason": reason,
                        "margin_level": margin_level,
                    }
                )
            self._engine._reset_accumulation(from_layer)
            return

        entries = sorted(
            self._engine._layers[from_layer].values(),
            key=lambda e: self._engine.promotion_score(e),
            reverse=True,
        )
        consolidate_count = max(3, int(len(entries) * ratio))
        promoted = 0
        for entry in entries[:consolidate_count]:
            if self._engine.consolidate(from_layer, next_layer.name, entry.id):
                promoted += 1

        self._engine._stats["total_consolidations_triggered"] += 1
        self._engine._log_consolidation_event(
            {
                "event": "consolidation_executed",
                "from_layer": from_layer,
                "to_layer": next_layer.name,
                "trigger_reason": reason,
                "margin_level": margin_level,
                "consolidation_ratio": ratio,
                "promoted_count": promoted,
                "total_in_layer": len(entries),
                "accumulated_bytes_before": self._engine._accumulated_bytes.get(
                    from_layer, 0
                ),
                "accumulated_entries_before": self._engine._accumulated_entries.get(
                    from_layer, 0
                ),
            }
        )
        if self._engine._learning_bridge:
            try:
                self._engine._learning_bridge.on_consolidation(
                    {
                        "event": "consolidation_executed",
                        "from_layer": from_layer,
                        "to_layer": next_layer.name,
                        "trigger_reason": reason,
                        "promoted_count": promoted,
                    }
                )
            except Exception:
                pass
        self._engine._reset_accumulation(from_layer)

        self._engine._trigger_evolution_cycle(from_layer)
        new_margin = self._engine._get_margin_ratio(from_layer)
        safety = getattr(layer_config, "margin_management", None)
        target = safety.target_margin if safety else 0.15
        if new_margin < target:
            self._engine._progressive_orchestration(from_layer, depth=1)

    def _check_hard_cap(self, layer_name: str):
        layer_config = self._engine.config.get_layer(layer_name)
        if not layer_config:
            return
        size = self._engine._get_layer_size(layer_name)
        if size < layer_config.hard_cap_bytes:
            return
        next_layer = self._engine.config.get_next_layer(layer_name)
        if not next_layer:
            remaining = size - layer_config.max_size_bytes
            if remaining > 0:
                self._engine._log_consolidation_event(
                    {
                        "event": "hard_cap_no_next_layer",
                        "layer": layer_name,
                        "overflow_bytes": remaining,
                        "total_size": size,
                        "hard_cap": layer_config.hard_cap_bytes,
                    }
                )
            return

        entries = sorted(
            self._engine._layers[layer_name].values(),
            key=lambda e: self._engine.promotion_score(e),
            reverse=True,
        )
        overflow = max(0, size - layer_config.max_size_bytes)
        freed = 0
        promoted = 0
        for entry in entries:
            if freed >= overflow and size - freed <= layer_config.max_size_bytes * 0.9:
                break
            entry_size = entry.size_bytes
            if self._engine.consolidate(layer_name, next_layer.name, entry.id):
                freed += entry_size
                promoted += 1

        self._engine._stats["total_hard_cap_enforcements"] += 1
        self._engine._log_consolidation_event(
            {
                "event": "hard_cap_enforced",
                "layer": layer_name,
                "to_layer": next_layer.name,
                "overflow_bytes": overflow,
                "freed_bytes": freed,
                "promoted_count": promoted,
                "remaining_size": self._engine._get_layer_size(layer_name),
            }
        )
        self._engine._reset_accumulation(layer_name)

        if self._engine._evo_loop:
            self._engine._evo_loop.record_action(
                action="capacity_enforcement",
                state_before={"layer": layer_name, "overflow_bytes": overflow},
                state_after={"promoted": promoted, "freed_bytes": freed},
            )

    def force_consolidate_layer(self, layer_name: str) -> int:
        with self._engine._lock:
            layer_config = self._engine.config.get_layer(layer_name)
            if not layer_config:
                return 0
            next_layer = self._engine.config.get_next_layer(layer_name)
            if not next_layer:
                return 0
            entries = sorted(
                self._engine._layers[layer_name].values(),
                key=lambda e: self._engine.promotion_score(e),
                reverse=True,
            )
            count = max(5, int(len(entries) * 0.2))
            promoted = 0
            for entry in entries[:count]:
                if self._engine.consolidate(layer_name, next_layer.name, entry.id):
                    promoted += 1
            self._engine._log_consolidation_event(
                {
                    "event": "force_consolidation",
                    "from_layer": layer_name,
                    "to_layer": next_layer.name,
                    "promoted_count": promoted,
                    "total_in_layer": len(entries),
                }
            )
            self._engine._reset_accumulation(layer_name)
            return promoted

    def _progressive_orchestration(self, layer_name: str, depth: int = 1):
        if depth > 3:
            return
        layer_config = self._engine.config.get_layer(layer_name)
        if not layer_config:
            return
        next_layer = self._engine.config.get_next_layer(layer_name)
        if not next_layer:
            return
        margin_after = self._engine._get_margin_ratio(layer_name)
        safety = getattr(layer_config, "margin_management", None)
        target = safety.target_margin if safety else 0.15
        if margin_after >= target:
            return
        if depth == 1:
            ratio = getattr(layer_config, "deep_consolidation_ratio", 0.25)
        elif depth == 2:
            ratio = getattr(layer_config, "emergency_consolidation_ratio", 0.50)
        else:
            ratio = 0.80
        entries = sorted(
            self._engine._layers[layer_name].values(),
            key=lambda e: self._engine.promotion_score(e),
            reverse=True,
        )
        extra_count = max(3, int(len(entries) * ratio))
        extra_promoted = 0
        for entry in entries[:extra_count]:
            if self._engine.consolidate(layer_name, next_layer.name, entry.id):
                extra_promoted += 1
        self._engine._log_consolidation_event(
            {
                "event": "progressive_orchestration",
                "from_layer": layer_name,
                "to_layer": next_layer.name,
                "depth": depth,
                "ratio": ratio,
                "extra_promoted": extra_promoted,
                "margin_before": margin_after,
            }
        )
        new_margin = self._engine._get_margin_ratio(layer_name)
        if new_margin < target:
            self._engine._progressive_orchestration(layer_name, depth=depth + 1)
