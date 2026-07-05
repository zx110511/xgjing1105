# -*- coding: utf-8-sig -*-
"""hybrid_engine_remember.py — ICMEStorageEngineRememberMixin (SSS-PhaseB)

从 hybrid_engine.py 拆分的方法组: remember
源文件: hybrid_engine.py
"""

import hashlib
import json
import logging
import time
import uuid
from pathlib import Path

logger = logging.getLogger("tianji.hybrid_engine")  # [FIX-remember-001] 补充缺失的logger定义
from typing import Any
from ..shared.config import ICMEConfig
from .engine import ICMEEngine, MemoryEntry
from .storage.migration import MigrationManager
from .storage.tiered import (  # noqa: F401
    TieredStorageEngine,
)


from typing import Dict

class ICMEStorageEngineRememberMixin:
    """remember方法组Mixin"""

    def remember(
        self,
        content: str,
        layer: str = "working",
        tags: list[str] | None = None,
        priority: str = "medium",
        metadata: dict | None = None,
        use_llm: bool = True,
    ) -> dict:
        actual_layer = layer
        tags = tags or []
        metadata = metadata or {}
        gate_result = None
        llm_enriched = False

        # TCL归一化: 提取canonical_ids写入metadata (始终执行快速匹配，LLM部分由use_llm控制)
        try:
            if self._init_tcl():
                _, canonical_ids = self._tcl_normalizer.normalize_content(
                    content, use_llm=use_llm
                )
                if canonical_ids:
                    metadata["tcl_canonical_ids"] = canonical_ids
        except Exception as e:
            logger.debug(
                f"[HybridEngine] TCL归一化跳过: {e}"
            )  # TCL归一化失败不影响主流程

        if use_llm and self._llm_bridge and self._llm_bridge.is_ready:
            actual_layer, tags, priority, metadata, llm_enriched = (
                self._enrich_with_llm(content, layer, tags, priority, metadata)
            )

        if self._quality_gate:
            # P0-fix: 限制quality_gate查询范围，避免全量扫描导致超时
            existing = self.get_all_entries(limit=10)
            gate_result = self._quality_gate.check(
                content, layer, tags, priority, existing
            )
            actual_layer = gate_result.target_layer

            if gate_result.verdict == "reject":
                self._stats["total_rejected"] += 1
                return {
                    "id": None,
                    "status": "rejected",
                    "reason": gate_result.reason,
                    "gate_verdict": gate_result.verdict,
                    "quality_dimensions": gate_result.quality_dimensions,
                }
            if gate_result.verdict == "downgrade":
                self._stats["total_downgraded"] += 1
            if gate_result.verdict == "conflict":
                self._stats["total_conflicts"] += 1
                if gate_result.conflicts_with and metadata is None:
                    metadata = {}
                if metadata is not None:
                    metadata["conflicts_with"] = gate_result.conflicts_with

        if (
            self._quality_gate
            and actual_layer != layer
            and actual_layer not in ("sensory", "working")
        ):
            try:
                promotion_result = self._quality_gate.check_promotion(
                    content, layer, actual_layer, tags, priority
                )
                if promotion_result.verdict.value == "downgrade":
                    actual_layer = promotion_result.target_layer
                elif promotion_result.verdict.value == "pending_upstream":
                    actual_layer = layer
                if metadata is None:
                    metadata = {}
                metadata["promotion_gate"] = {
                    "verdict": promotion_result.verdict.value,
                    "reason": promotion_result.reason,
                    "source": layer,
                    "target": actual_layer,
                }
            except Exception as e:
                logger.warning(f"[HybridEngine] promotion_gate检查异常: {e}")

        # P0-fix: 缩小锁范围 — 仅覆盖entry创建和insert，其他操作移到锁外
        with self._lock:
            entry_id = hashlib.sha256(
                f"{content}{time.time()}{uuid.uuid4()}".encode()
            ).hexdigest()[:16]
            entry_dict = {
                "id": entry_id,
                "content": content,
                "layer": actual_layer,
                "tags": tags,
                "priority": priority,
                "value_score": self._calc_value_score(priority),
                "access_count": 0,
                "created_at": time.time(),
                "last_accessed": time.time(),
                "size_bytes": len(content.encode("utf-8")),
                "metadata": metadata or {},
                "related_ids": gate_result.conflicts_with
                if gate_result and gate_result.conflicts_with
                else [],
                "changelog": [],
            }

            if self._use_sqlite:
                insert_ok = self._store.insert(entry_dict)
                if not insert_ok:
                    logger.error(
                        f"[HybridEngine] SQLite insert失败, 回退到JSON存储: {entry_id}"
                    )
                    self._fallback_to_json(
                        entry_dict, actual_layer, gate_result, metadata
                    )
                    result["status"] = "stored_json_fallback"
                    result["fallback_reason"] = "sqlite_insert_failed"
                else:
                    self._update_layer_size(
                        actual_layer, len(content.encode("utf-8"))
                    )
            else:
                self._fallback_to_json(entry_dict, actual_layer, gate_result, metadata)

            self._stats["total_entries"] += 1

        # P0-fix: 以下操作全部在锁外执行，避免阻塞其他线程
        result = {
            "id": entry_id,
            "status": gate_result.verdict if gate_result else "stored",
            "actual_layer": actual_layer,
            "requested_layer": layer,
            "size_bytes": len(content.encode("utf-8")),
            "llm_enriched": llm_enriched,
        }
        if gate_result:
            result["gate_verdict"] = gate_result.verdict
            result["gate_reason"] = gate_result.reason
            result["quality_dimensions"] = gate_result.quality_dimensions

        # P0-fix: evo_loop/KG_sync/asset_registry/consolidate全部在后台线程执行
        def _post_insert_hooks():
            """锁外后置钩子: evo_loop + KG_sync + asset_registry + consolidate"""
            try:
                if self._evo_loop is not None:
                    try:
                        self._evo_loop.record_action(
                            "remember",
                            state_before={"total_entries": self._stats["total_entries"] - 1},
                            state_after={
                                "entry_id": entry_id,
                                "status": result["status"],
                                "layer": actual_layer,
                                "total_entries": self._stats["total_entries"],
                            },
                        )
                    except Exception as e:
                        logger.debug(f"[HybridEngine] evo_loop.record_action(remember) 忽略: {e}")

                if self._use_sqlite and entry_id:
                    try:
                        from ..shared.kg_sync_hook import KGSyncHook
                        if not hasattr(self, "_kg_sync"):
                            self._kg_sync = KGSyncHook(
                                str(self._store._db_path)
                                if hasattr(self._store, "_db_path")
                                else "data/.memory/icme.db"
                            )
                        self._kg_sync.on_remember(entry_dict)
                    except Exception as e:
                        logger.debug(f"[HybridEngine] KG同步(on_remember)跳过: {e}")

                if self._asset_registry and entry_id:
                    try:
                        from .asset_atom import AssetAtom, ContentType, Provenance
                        content_hash = self._asset_registry.compute_content_hash(content)
                        content_type = ContentType.UNKNOWN
                        src = (metadata or {}).get("source", "")
                        if "trae_capture" in src or "conversation" in src:
                            content_type = ContentType.CONVERSATION
                        elif "file" in src or "snapshot" in src:
                            content_type = ContentType.FILE
                        elif "decision" in src or actual_layer == "episodic":
                            content_type = ContentType.DECISION
                        elif actual_layer == "semantic":
                            content_type = ContentType.KNOWLEDGE
                        elif actual_layer == "meta":
                            content_type = ContentType.RULE
                        atom = AssetAtom(
                            memory_id=(metadata or {}).get("memory_id", entry_id),
                            layer=actual_layer,
                            content_type=content_type,
                            content_hash=content_hash,
                            provenance=Provenance(
                                created_by="hybrid_engine",
                                created_at=time.time(),
                                reason="Auto-registered from remember()",
                                session_id=(metadata or {}).get("session_id", ""),
                            ),
                        )
                        tcl_ids = (metadata or {}).get("tcl_canonical_ids", [])
                        asset_id = self._asset_registry.register(
                            atom, content=content, tcl_ids=tcl_ids
                        )
                        result["asset_id"] = asset_id
                    except Exception as e:
                        logger.warning(f"[策略D] _register_asset_atom失败: {e}")
                elif entry_id:
                    try:
                        self._init_asset_registry()
                        if self._asset_registry:
                            from .asset_atom import AssetAtom, ContentType, Provenance
                            content_hash = self._asset_registry.compute_content_hash(content)
                            atom = AssetAtom(
                                memory_id=(metadata or {}).get("memory_id", entry_id),
                                layer=actual_layer,
                                content_type=ContentType.UNKNOWN,
                                content_hash=content_hash,
                                provenance=Provenance(
                                    created_by="hybrid_engine(lazy)",
                                    created_at=time.time(),
                                    reason="Auto-registered from remember()",
                                ),
                            )
                            tcl_ids = (metadata or {}).get("tcl_canonical_ids", [])
                            asset_id = self._asset_registry.register(
                                atom, content=content, tcl_ids=tcl_ids
                            )
                            result["asset_id"] = asset_id
                    except Exception as e:
                        logger.warning(f"[策略D] 懒初始化失败: {e}")

                # P0-fix: 延迟3秒执行consolidate，避免与下一个remember请求竞争SQLite锁
                import time as _time
                _time.sleep(3.0)
                try:
                    self._auto_consolidate(actual_layer)
                except Exception as e:
                    logger.debug(f"[HybridEngine] _auto_consolidate异常忽略: {e}")
                try:
                    self._check_hard_cap(actual_layer)
                except Exception as e:
                    logger.debug(f"[HybridEngine] _check_hard_cap异常忽略: {e}")
            except Exception as e:
                logger.debug(f"[HybridEngine] 后置钩子异常忽略: {e}")

        import threading as _threading
        _threading.Thread(
            target=_post_insert_hooks,
            daemon=True,
            name="remember_post_hooks",
        ).start()

        return result

    def remember_batch(self, items: list[dict]) -> list[str]:
        ids = []
        entries = []
        for item in items:
            entry_id = hashlib.sha256(
                f"{item.get('content', '')}{time.time()}{uuid.uuid4()}".encode()
            ).hexdigest()[:16]
            target_layer = item.get("layer", "working")
            entry_dict = {
                "id": entry_id,
                "content": item.get("content", ""),
                "layer": target_layer,
                "tags": item.get("tags", []),
                "priority": item.get("priority", "medium"),
                "value_score": self._calc_value_score(item.get("priority", "medium")),
                "access_count": 0,
                "created_at": time.time(),
                "last_accessed": time.time(),
                "metadata": item.get("metadata", {}),
                "related_ids": [],
                "changelog": [],
            }
            entries.append(entry_dict)
            ids.append(entry_id)

        if self._use_sqlite:
            self._store.insert_batch(entries)
        else:
            for entry_dict in entries:
                entry = MemoryEntry(
                    id=entry_dict["id"],
                    content=entry_dict["content"],
                    layer=entry_dict["layer"],
                    tags=entry_dict["tags"],
                    priority=entry_dict["priority"],
                    metadata=entry_dict["metadata"],
                )
                self._layers[entry_dict["layer"]][entry_dict["id"]] = entry
                self._save_entry(entry)

        with self._lock:
            self._stats["total_entries"] += len(entries)
            for entry_dict in entries:
                self._update_layer_size(
                    entry_dict["layer"], len(entry_dict["content"].encode("utf-8"))
                )

        if self._evo_loop is not None:
            try:
                self._evo_loop.record_action(
                    action="remember_batch",
                    state_before={
                        "total_entries": self._stats["total_entries"] - len(entries)
                    },
                    state_after={
                        "batch_size": len(entries),
                        "total_entries": self._stats["total_entries"],
                    },
                )
            except Exception as e:
                logger.debug(f"[HybridEngine] evo_loop.record_action(batch) 忽略: {e}")

        return ids

    def _fallback_to_json(
        self,
        entry_dict: dict,
        actual_layer: str,
        gate_result: Any | None = None,
        metadata: dict | None = None,
    ) -> None:
        """v9.1 P1-2: SQLite失败时回退到JSON文件存储

        当SQLite insert失败或读回验证失败时调用此方法，
        确保数据不丢失。使用父类ICMEEngine的JSON存储路径。
        """
        try:
            entry = MemoryEntry(
                id=entry_dict["id"],
                content=entry_dict["content"],
                layer=actual_layer,
                tags=entry_dict.get("tags", []),
                priority=entry_dict.get("priority", "medium"),
                metadata=metadata or entry_dict.get("metadata", {}),
            )
            if (
                gate_result
                and hasattr(gate_result, "conflicts_with")
                and gate_result.conflicts_with
            ):
                entry.related_ids = list(
                    set(entry.related_ids + gate_result.conflicts_with)
                )
            self._layers[actual_layer][entry.id] = entry
            self._update_layer_size(actual_layer, entry.size_bytes)
            self._save_entry(entry)
            self._errors += 1
            logger.warning(
                f"[HybridEngine] JSON回退存储成功: {entry.id} "
                f"(layer={actual_layer}, errors累计={self._errors})"
            )
        except Exception as e:
            self._errors += 1
            logger.critical(
                f"[HybridEngine] JSON回退存储也失败: {entry_dict.get('id', '?')} — {e}",
                exc_info=True,
            )

    @staticmethod
    def _calc_value_score(priority: str) -> float:
        weights = {"critical": 0.9, "high": 0.7, "medium": 0.5, "low": 0.3}
        return weights.get(priority, 0.5)
