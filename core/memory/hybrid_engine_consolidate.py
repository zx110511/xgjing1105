# -*- coding: utf-8-sig -*-
"""hybrid_engine_consolidate.py — ICMEStorageEngineConsolidateMixin (SSS-PhaseB)

从 hybrid_engine.py 拆分的方法组: consolidate
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


# [FIX-MCP-Bug2/3] 添加 logger 实例 (修复 recall→consolidate→logger未定义 导致 /api/search/quick 和 /api/search/semantic 500 错误)
logger = logging.getLogger(__name__)

# P0-MetaFix: Meta层硬上限 — 防止 consolidate_batch 晋升撑爆Meta层
_META_LAYER_HARD_CAP = 80000  # 与 cleanup_meta_layer.py / evolution_loop.py 一致


from typing import Dict

class ICMEStorageEngineConsolidateMixin:
    """consolidate方法组Mixin"""

    def consolidate(self, from_layer: str, to_layer: str, entry_id: str) -> str | None:
        # [FIX-v9.1-mem-leak] 冷却时间保护: 同层巩固最小间隔60s，防止746K次空转
        _CONSOLIDATION_COOLDOWN = 60.0
        last_cons = self._last_consolidation_time.get(from_layer, 0.0) if hasattr(self, '_last_consolidation_time') else 0.0
        if time.time() - last_cons < _CONSOLIDATION_COOLDOWN:
            logger.debug(f"[HybridEngine] consolidate冷却中({time.time()-last_cons:.0f}s<{_CONSOLIDATION_COOLDOWN}s)，跳过")
            return None

        if self._use_sqlite:
            entry = self._store.get(entry_id)
            if not entry or entry.get("layer") != from_layer:
                return None
            self._store.update(
                entry_id,
                {
                    "layer": to_layer,
                    "content": f"[{from_layer}->{to_layer}] {entry.get('content', '')}",
                    "tags": entry.get("tags", []) + [f"from-{from_layer}"],
                },
            )
            self._stats["total_consolidations"] += 1
            self._persist_stats_counters()

            if self._evo_loop is not None:
                try:
                    self._evo_loop.record_action(
                        action="consolidate",
                        state_before={"entry_id": entry_id, "from_layer": from_layer},
                        state_after={
                            "entry_id": entry_id,
                            "to_layer": to_layer,
                            "total_consolidations": self._stats["total_consolidations"],
                        },
                    )
                except Exception as e:
                    logger.debug(
                        f"[HybridEngine] evo_loop.record_action(consolidate) 忽略: {e}"
                    )

            try:
                from ..shared.kg_sync_hook import KGSyncHook

                if not hasattr(self, "_kg_sync"):
                    self._kg_sync = KGSyncHook(
                        str(self._store._db_path)
                        if hasattr(self._store, "_db_path")
                        else "data/.memory/icme.db"
                    )
                self._kg_sync.on_consolidate(from_layer, to_layer, entry_id)
            except Exception as e:
                logger.debug(f"[HybridEngine] KG同步(on_consolidate)跳过: {e}")

            return entry_id
        return super().consolidate(from_layer, to_layer, entry_id)

    def _auto_consolidate(self, from_layer: str):
        """SQLite模式下override: 使用consolidate_batch代替_layers遍历"""
        if not self._use_sqlite:
            return super()._auto_consolidate(from_layer)

        self._sync_evo_config()
        layer_config = self.config.get_layer(from_layer)
        if not layer_config:
            return

        should, reason = self._should_consolidate(from_layer)
        if not should:
            return

        can, wait_reason = self._can_consolidate_now(from_layer)
        if not can:
            return

        margin_level = self._get_margin_level(from_layer)
        if margin_level == "green":
            ratio = getattr(layer_config, "consolidation_ratio", 0.15)
        elif margin_level in ("yellow", "orange"):
            ratio = getattr(layer_config, "deep_consolidation_ratio", 0.25)
        else:
            ratio = getattr(layer_config, "emergency_consolidation_ratio", 0.50)

        next_layer = self.config.get_next_layer(from_layer)

        # 获取SQLite中的条目数
        layer_stats = self._store.get_layer_stats()
        entry_count = layer_stats.get(from_layer, {}).get("entry_count", 0)
        consolidate_count = max(3, int(entry_count * ratio))

        if not next_layer:
            # 无下一层: 红色边距时归档低价值条目
            if margin_level == "red":
                result = self.consolidate_batch(
                    from_layer=from_layer,
                    threshold=0.0,
                    max_entries=consolidate_count,
                    use_quality_promotion=False,
                )
                archived = result.get("consolidated", 0)
                self._log_consolidation_event(
                    {
                        "event": "archive_no_next_layer_sqlite",
                        "from_layer": from_layer,
                        "trigger_reason": reason,
                        "margin_level": margin_level,
                        "archived_count": archived,
                    }
                )
            else:
                self._log_consolidation_event(
                    {
                        "event": "consolidation_skipped_no_next",
                        "from_layer": from_layer,
                        "trigger_reason": reason,
                        "margin_level": margin_level,
                    }
                )
            self._reset_accumulation(from_layer)
            return

        # 有下一层: 使用consolidate_batch进行晋升
        # 动态阈值: 边距越低，阈值越低，确保超容量时能实际巩固
        if margin_level == "red":
            threshold = 0.0
            use_quality = False
        elif margin_level == "orange":
            threshold = 0.1
            use_quality = True
        elif margin_level == "yellow":
            threshold = 0.2
            use_quality = True
        else:
            threshold = 0.3
            use_quality = True

        result = self.consolidate_batch(
            from_layer=from_layer,
            to_layer=next_layer.name,
            threshold=threshold,
            max_entries=consolidate_count,
            use_quality_promotion=use_quality,
        )
        promoted = result.get("consolidated", 0)

        self._stats["total_consolidations_triggered"] += 1
        self._log_consolidation_event(
            {
                "event": "consolidation_executed_sqlite",
                "from_layer": from_layer,
                "to_layer": next_layer.name,
                "trigger_reason": reason,
                "margin_level": margin_level,
                "consolidation_ratio": ratio,
                "promoted_count": promoted,
                "total_in_layer": entry_count,
                "gate_rejected": result.get("gate_rejected", 0),
            }
        )
        self._reset_accumulation(from_layer)

        # P1-MetaFix: 断开正反馈循环 — Meta层超阈值时不触发进化循环
        # 原问题: consolidate → _trigger_evolution_cycle → evo_loop.record_action
        #       → _persist_action_to_icme → 写入episodic → 下次consolidate又晋升到meta
        #       形成自激正反馈，Meta层疯涨
        try:
            meta_stats = self._store.get_layer_stats().get("meta", {})
            meta_count = meta_stats.get("entry_count", 0)
            if meta_count < _META_LAYER_HARD_CAP:
                self._trigger_evolution_cycle(from_layer)
            else:
                logger.info(
                    f"[HybridEngine] Meta层{meta_count}条≥{_META_LAYER_HARD_CAP}，"
                    f"跳过_trigger_evolution_cycle (断开正反馈)"
                )
        except Exception as e:
            logger.debug(f"[HybridEngine] Meta容量检查失败,降级触发evo: {e}")
            self._trigger_evolution_cycle(from_layer)
        new_margin = self._get_margin_ratio(from_layer)
        safety = getattr(layer_config, "margin_management", None)
        target = safety.target_margin if safety else 0.15
        if new_margin < target:
            self._progressive_orchestration(from_layer, depth=1)

    def consolidate_batch(
        self,
        from_layer: str,
        to_layer: str | None = None,
        threshold: float = 0.6,
        max_entries: int = 50,
        use_quality_promotion: bool = True,
    ) -> dict:
        if not self._use_sqlite:
            return super().consolidate_batch(
                from_layer, to_layer, threshold, max_entries, use_quality_promotion
            )

        layer_order = [
            "sensory",
            "working",
            "short_term",
            "episodic",
            "semantic",
            "meta",
        ]
        target_layer = to_layer
        if not target_layer:
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

        if not target_layer:
            return {
                "status": "error",
                "error": f"no target layer for {from_layer}",
                "consolidated": 0,
            }

        # P0-MetaFix: Meta层晋升硬上限保护 — 防止撑爆Meta层 (断开正反馈循环关键节点)
        if target_layer == "meta":
            try:
                meta_stats = self._store.get_layer_stats().get("meta", {})
                meta_count = meta_stats.get("entry_count", 0)
                if meta_count >= _META_LAYER_HARD_CAP:
                    logger.warning(
                        f"[HybridEngine] Meta层已{meta_count}条≥{_META_LAYER_HARD_CAP}，"
                        f"跳过 {from_layer}->meta 晋升 (断开正反馈循环)"
                    )
                    return {
                        "status": "skipped_meta_cap",
                        "from_layer": from_layer,
                        "to_layer": target_layer,
                        "consolidated": 0,
                        "errors": 0,
                        "gate_rejected": 0,
                        "reason": f"meta_layer_cap_reached ({meta_count}/{_META_LAYER_HARD_CAP})",
                    }
            except Exception as e:
                logger.debug(f"[HybridEngine] Meta容量检查跳过: {e}")

        try:
            all_entries = self._store.search(
                layers=[from_layer], limit=max_entries * 3, min_score=0.0, use_fts=False
            )
        except Exception as e:
            return {
                "status": "error",
                "error": f"search failed: {e}",
                "consolidated": 0,
            }

        candidates = []
        for entry in all_entries:
            score = entry.get("value_score", 0.5) or 0.5
            if use_quality_promotion:
                if score >= threshold:
                    candidates.append((score, entry))
            else:
                candidates.append((0.5, entry))

        candidates.sort(key=lambda x: x[0], reverse=True)
        candidates = candidates[:max_entries]

        consolidated = 0
        errors = 0
        gate_rejected = 0
        for score, entry in candidates:
            try:
                if use_quality_promotion and self._quality_gate:
                    try:
                        gate_result = self._quality_gate.check_promotion(
                            entry.get("content", ""),
                            from_layer,
                            target_layer,
                            entry.get("tags", []),
                            entry.get("priority", "medium"),
                            override_threshold=threshold,
                        )
                        if gate_result.verdict.value not in ("pass", "stored"):
                            gate_rejected += 1
                            continue
                    except Exception as e:
                        logger.debug(
                            f"[HybridEngine] consolidate_batch质量门禁跳过: {e}"
                        )
                existing_tags = entry.get("tags") or []
                existing_meta = entry.get("metadata") or {}
                new_tags = list(
                    set(existing_tags + [f"from-{from_layer}", "batch-consolidated"])
                )
                new_meta = {
                    **existing_meta,
                    "consolidated_at": time.time(),
                    "source_layer": from_layer,
                    "promotion_score": round(score, 4),
                }
                self._store.update(
                    entry["id"],
                    {
                        "layer": target_layer,
                        "tags": new_tags,
                        "metadata": new_meta,
                    },
                )
                consolidated += 1
                self._stats["total_consolidations"] += 1
            except Exception as e:
                errors += 1
                logger.warning(f"[HybridEngine] consolidate_batch条目更新失败: {e}")

        # 重置accumulation计数器，避免重复触发巩固
        if consolidated > 0:
            self._reset_accumulation(from_layer)
            self._persist_stats_counters()

        remaining = len(self._store.search(layers=[from_layer], limit=1, min_score=0.0))
        return {
            "status": "completed",
            "from_layer": from_layer,
            "to_layer": target_layer,
            "consolidated": consolidated,
            "errors": errors,
            "gate_rejected": gate_rejected,
            "threshold": threshold,
            "candidates_available": len(candidates),
            "candidates_examined": len(all_entries),
            "remaining_in_source": remaining,
            "results": [
                {"id": c[1]["id"], "promotion_score": round(c[0], 4)}
                for c in candidates[:consolidated]
            ],
        }

    def force_evict_overcapacity(
        self, layer: str, target_ratio: float = 0.8, max_evict: int = 200
    ) -> dict:
        if not self._use_sqlite:
            return super().force_evict_overcapacity(layer, target_ratio, max_evict)

        try:
            layer_stats = self._store.get_layer_stats()
            ls = layer_stats.get(layer, {"entry_count": 0, "total_bytes": 0})
            current_count = ls["entry_count"]

            layer_config = self.config.get_layer(layer)
            max_entries = (
                getattr(layer_config, "max_entries", 2000) if layer_config else 2000
            )

            if current_count <= max_entries:
                return {
                    "status": "ok",
                    "message": f"within capacity ({current_count}/{max_entries})",
                    "evicted": 0,
                }

            target_count = int(max_entries * target_ratio)
            evict_count = min(max_evict, current_count - target_count)
            if evict_count <= 0:
                evict_count = min(max_evict, current_count - int(max_entries * 0.7))

            entries = self._store.search(
                layers=[layer], limit=evict_count + 10, min_score=0.0, use_fts=False
            )

            sorted_entries = sorted(
                entries,
                key=lambda e: (
                    e.get("value_score") or 0,
                    e.get("access_count") or 0,
                    e.get("created_at") or 0,
                ),
            )

            evicted = 0
            for entry in sorted_entries[:evict_count]:
                try:
                    self._store.delete(entry["id"])
                    evicted += 1
                    self._stats["total_entries"] -= 1
                    self._stats["total_archivals"] += 1
                except Exception as e:
                    logger.warning(f"[HybridEngine] evict条目删除失败: {e}")

            new_stats = self._store.get_layer_stats()
            new_ls = new_stats.get(layer, {"entry_count": 0})
            remaining = new_ls["entry_count"]
            if evicted > 0:
                self._persist_stats_counters()

            return {
                "status": "completed",
                "layer": layer,
                "before": current_count,
                "after": remaining,
                "max_entries": max_entries,
                "evicted": evicted,
                "target_ratio": target_ratio,
                "reason": "overcapacity_force_evict",
            }
        except Exception as e:
            return {"status": "error", "error": str(e), "evicted": 0}

    def auto_promote_sweep(self, max_per_layer: int = 50) -> dict:
        layer_order = ["sensory", "working", "short_term", "episodic", "semantic"]
        sweep_results = {}
        total_promoted = 0
        total_gate_rejected = 0
        total_errors = 0

        for i, from_layer in enumerate(layer_order):
            to_layer = layer_order[i + 1] if i + 1 < len(layer_order) else None
            if not to_layer:
                continue
            try:
                result = self.consolidate_batch(
                    from_layer=from_layer,
                    to_layer=to_layer,
                    threshold=0.4 if i < 2 else 0.5,
                    max_entries=max_per_layer,
                    use_quality_promotion=True,
                )
                promoted = result.get("consolidated", 0)
                rejected = result.get("gate_rejected", 0)
                total_promoted += promoted
                total_gate_rejected += rejected
                total_errors += result.get("errors", 0)
                sweep_results[f"{from_layer}->{to_layer}"] = {
                    "promoted": promoted,
                    "gate_rejected": rejected,
                    "errors": result.get("errors", 0),
                    "remaining": result.get("remaining_in_source", 0),
                }
            except Exception as e:
                total_errors += 1
                sweep_results[f"{from_layer}->{to_layer}"] = {"error": str(e)[:200]}

        self._stats["total_promotion_sweeps"] = (
            self._stats.get("total_promotion_sweeps", 0) + 1
        )
        return {
            "status": "completed",
            "total_promoted": total_promoted,
            "total_gate_rejected": total_gate_rejected,
            "total_errors": total_errors,
            "sweep_details": sweep_results,
        }


# ---------------------------------------------------------------------------
# [v10-ready] 分层存储引擎已拆分至 core.storage.tiered (P1-03)。
# MemoryTier / TierConfig / TIER_DEFAULTS / TieredStorageEngine 已在本文件顶部
# 通过 `from .storage.tiered import ...` re-export, 旧导入路径继续可用。
# ---------------------------------------------------------------------------

    def _calc_value_score(priority: str) -> float:
        weights = {"critical": 0.9, "high": 0.7, "medium": 0.5, "low": 0.3}
        return weights.get(priority, 0.5)

    def _get_layer_size(self, layer_name: str) -> int:
        """SQLite模式下override: 从数据库获取层大小"""
        if not self._use_sqlite:
            return super()._get_layer_size(layer_name)
        layer_stats = self._store.get_layer_stats()
        return layer_stats.get(layer_name, {}).get("total_bytes", 0)

    def _get_margin_ratio(self, layer_name: str) -> float:
        """SQLite模式下override: 使用SQLite统计计算边距比例"""
        if not self._use_sqlite:
            return super()._get_margin_ratio(layer_name)

        layer_config = self.config.get_layer(layer_name)
        if not layer_config or layer_config.max_size_bytes <= 0:
            return 1.0

        # 从SQLite获取真实大小和条目数
        layer_stats = self._store.get_layer_stats()
        stats = layer_stats.get(layer_name, {})
        used_bytes = stats.get("total_bytes", 0)
        entry_count = stats.get("entry_count", 0)

        byte_margin = max(0.0, 1.0 - used_bytes / layer_config.max_size_bytes)
        if layer_config.max_entries > 0:
            entry_margin = max(0.0, 1.0 - entry_count / layer_config.max_entries)
        else:
            entry_margin = 1.0
        return min(byte_margin, entry_margin)

    def _check_hard_cap(self, layer_name: str):
        """SQLite模式下override: 使用consolidate_batch处理hard cap"""
        if not self._use_sqlite:
            return super()._check_hard_cap(layer_name)

        layer_config = self.config.get_layer(layer_name)
        if not layer_config:
            return

        # 检查entry_count是否超过max_entries (SQLite模式下更可靠的超容量检测)
        layer_stats = self._store.get_layer_stats()
        entry_count = layer_stats.get(layer_name, {}).get("entry_count", 0)
        size_bytes = layer_stats.get(layer_name, {}).get("total_bytes", 0)

        over_entry_cap = (
            entry_count > layer_config.max_entries
            if layer_config.max_entries > 0
            else False
        )
        over_byte_cap = size_bytes >= layer_config.hard_cap_bytes

        if not over_entry_cap and not over_byte_cap:
            return

        next_layer = self.config.get_next_layer(layer_name)
        if not next_layer:
            if over_byte_cap:
                remaining = size_bytes - layer_config.max_size_bytes
                self._log_consolidation_event(
                    {
                        "event": "hard_cap_no_next_layer",
                        "layer": layer_name,
                        "overflow_bytes": max(0, remaining),
                        "total_size": size_bytes,
                        "hard_cap": layer_config.hard_cap_bytes,
                    }
                )
            return

        # 使用consolidate_batch进行紧急晋升
        overflow_count = max(0, entry_count - int(layer_config.max_entries * 0.8))
        overflow_bytes = max(0, size_bytes - int(layer_config.max_size_bytes * 0.8))
        consolidate_count = max(overflow_count, 50)

        result = self.consolidate_batch(
            from_layer=layer_name,
            to_layer=next_layer.name,
            threshold=0.0,
            max_entries=consolidate_count,
            use_quality_promotion=False,
        )
        promoted = result.get("consolidated", 0)

        self._stats["total_hard_cap_enforcements"] += 1
        self._log_consolidation_event(
            {
                "event": "hard_cap_enforced_sqlite",
                "layer": layer_name,
                "to_layer": next_layer.name,
                "overflow_entries": overflow_count,
                "overflow_bytes": overflow_bytes,
                "promoted_count": promoted,
                "gate_rejected": result.get("gate_rejected", 0),
            }
        )
        self._reset_accumulation(layer_name)
