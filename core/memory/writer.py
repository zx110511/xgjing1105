r"""
天机记忆系统 (TIANJI) - 记忆写入组件 MemoryWriter  [v10-ready]
=============================================================
负责记忆写入全链路：LLM 增强 → 质量门禁 → 创建/存储条目 → 资产注册。

[v10-ready] 组件通过构造函数接收 engine 宿主，所有共享状态（_layers/_stats/
_lock 等）与跨组件协作均经由宿主访问，组件之间不互相 import。
"""

import hashlib
import time
import uuid
from typing import Any

from . import MemoryEntry


class MemoryWriter:
    """记忆写入引擎 — remember / remember_batch / fast_inject 等写入入口。"""

    def __init__(self, engine):
        self._engine = engine

    def _enrich_with_llm(
        self,
        content: str,
        layer: str,
        tags: list[str],
        priority: str,
        metadata: dict | None,
    ) -> tuple[str, list[str], str, dict | None, bool]:
        """LLM增强桥接 — 智能分层+自动标签+价值评估+知识提取+摘要"""
        if not self._engine._llm_bridge or not self._engine._llm_bridge.is_ready:
            return layer, tags, priority, metadata, False

        actual_layer = layer
        llm_enriched = False

        try:
            enrichment = self._engine._llm_bridge.enrich_remember(
                content, layer, tags, priority
            )
            if enrichment.get("llm_enriched"):
                llm_enriched = True
                if not layer or layer == "working":
                    actual_layer = enrichment.get("layer", layer)
                auto_tags = enrichment.get("tags", [])
                if auto_tags and not tags:
                    tags = auto_tags
                elif auto_tags and tags:
                    tags = list(set(tags + auto_tags))
                auto_priority = enrichment.get("priority", "medium")
                if priority == "medium" and auto_priority != "medium":
                    priority = auto_priority
                if enrichment.get("summary"):
                    metadata = metadata or {}
                    metadata["llm_summary"] = enrichment["summary"]
                if enrichment.get("knowledge_triples"):
                    metadata = metadata or {}
                    metadata["knowledge_triples"] = enrichment["knowledge_triples"]
                value_score = enrichment.get("value_score", 0.5)
                if value_score != 0.5:
                    metadata = metadata or {}
                    metadata["llm_value_score"] = value_score
        except Exception:
            pass

        return actual_layer, tags, priority, metadata, llm_enriched

    def _register_asset_atom(
        self,
        result: dict,
        content: str,
        layer: str,
        tags: list[str],
        priority: str,
        metadata: dict | None,
    ) -> str | None:
        """D02: remember()成功后自动注册AssetAtom"""
        try:
            from ..asset_atom import AssetAtom, AssetRegistry, ContentType, Provenance
        except ImportError:
            return None

        registry = self._engine._asset_registry
        if not isinstance(registry, AssetRegistry):
            return None

        memory_id = result.get("id", "")
        if not memory_id:
            return None

        content_hash = AssetRegistry.compute_content_hash(content)

        content_type = ContentType.UNKNOWN
        src = (metadata or {}).get("source", "")
        if "trae_capture" in src or "conversation" in src:
            content_type = ContentType.CONVERSATION
        elif "file" in src or "snapshot" in src:
            content_type = ContentType.FILE
        elif "decision" in src or layer == "episodic":
            content_type = ContentType.DECISION
        elif layer == "semantic":
            content_type = ContentType.KNOWLEDGE
        elif layer == "meta":
            content_type = ContentType.RULE

        atom = AssetAtom(
            memory_id=(metadata or {}).get("memory_id", memory_id),
            layer=layer,
            content_type=content_type,
            content_hash=content_hash,
            provenance=Provenance(
                created_by="engine",
                created_at=time.time(),
                reason="Auto-registered from remember()",
                session_id=(metadata or {}).get("session_id", ""),
            ),
        )
        tcl_ids = (metadata or {}).get("tcl_canonical_ids", [])
        asset_id = registry.register(atom, content=content, tcl_ids=tcl_ids)
        result["asset_id"] = asset_id
        return asset_id

    def _apply_quality_gate(
        self,
        content: str,
        layer: str,
        tags: list[str],
        priority: str,
        metadata: dict | None,
    ) -> tuple[Any | None, str, dict | None]:
        """应用质量门禁检查"""
        gate_result = None
        actual_layer = layer

        if self._engine._quality_gate:
            existing = self._engine.get_all_entries(limit=100)
            gate_result = self._engine._quality_gate.check(
                content, layer, tags, priority, existing
            )
            actual_layer = gate_result.target_layer

            if gate_result.verdict == "reject":
                self._engine._stats["total_rejected"] += 1
            elif gate_result.verdict == "downgrade":
                self._engine._stats["total_downgraded"] += 1
            elif gate_result.verdict == "conflict":
                self._engine._stats["total_conflicts"] += 1
                if gate_result.conflicts_with:
                    metadata = metadata or {}
                    metadata["conflicts_with"] = gate_result.conflicts_with

        return gate_result, actual_layer, metadata

    def _create_memory_entry(
        self,
        content: str,
        layer: str,
        tags: list[str],
        priority: str,
        metadata: dict | None,
        gate_result: Any | None,
    ) -> MemoryEntry:
        """创建记忆条目"""
        entry_id = hashlib.sha256(
            f"{content}{time.time()}{uuid.uuid4()}".encode()
        ).hexdigest()[:16]

        entry = MemoryEntry(
            id=entry_id,
            content=content,
            layer=layer,
            tags=tags,
            priority=priority,
            metadata=metadata or {},
        )

        if (
            gate_result
            and hasattr(gate_result, "conflicts_with")
            and gate_result.conflicts_with
        ):
            entry.related_ids = list(
                set(entry.related_ids + gate_result.conflicts_with)
            )

        return entry

    def _store_memory_entry(self, entry: MemoryEntry) -> None:
        """存储记忆条目到内存和磁盘 — 含MarginManagement余量安全检查"""
        # 余量安全检查: 变化量阈值 + 写入权限
        layer_config = self._engine.config.get_layer(entry.layer)
        if layer_config and hasattr(layer_config, 'margin_management') and layer_config.margin_management:
            mm = layer_config.margin_management
            margin_ratio = self._engine._get_margin_ratio(entry.layer)
            allowed, reason = mm.can_write(
                margin_ratio,
                delta_bytes=entry.size_bytes,
                max_bytes=layer_config.max_size_bytes,
            )
            if not allowed:
                # 尝试降级到更低层级
                lower_layer = self._engine.config.get_prev_layer(entry.layer)
                if lower_layer:
                    entry.layer = lower_layer.name
                    entry.metadata = {**entry.metadata, "margin_downgraded": True, "margin_reason": reason}
                else:
                    entry.metadata = {**entry.metadata, "margin_rejected": True, "margin_reason": reason}

        self._engine._layers[entry.layer][entry.id] = entry
        self._engine._update_layer_size(entry.layer, entry.size_bytes)
        self._engine._index_tags(entry.id, entry.tags)
        self._engine._stats["total_entries"] += 1
        self._engine._save_entry(entry)
        self._engine._auto_consolidate(entry.layer)
        self._engine._check_hard_cap(entry.layer)

    def _build_remember_result(
        self,
        entry: MemoryEntry,
        requested_layer: str,
        llm_enriched: bool,
        gate_result: Any | None,
    ) -> dict:
        """构建remember操作的结果字典"""
        result = {
            "id": entry.id,
            "status": gate_result.verdict if gate_result else "stored",
            "actual_layer": entry.layer,
            "requested_layer": requested_layer,
            "size_bytes": entry.size_bytes,
            "llm_enriched": llm_enriched,
        }

        if gate_result:
            result["gate_verdict"] = gate_result.verdict
            result["gate_reason"] = gate_result.reason
            result["quality_dimensions"] = gate_result.quality_dimensions

        return result

    def remember(
        self,
        content: str,
        layer: str = "working",
        tags: list[str] | None = None,
        priority: str = "medium",
        metadata: dict | None = None,
        use_llm: bool = True,
    ) -> dict:
        """写入记忆 - 主入口函数（重构后）"""
        # [FIX-v9.1-meta-bloat] Meta层容量保护: 超过1000条时跳过非关键写入
        if layer == "meta" and self._engine is not None:
            try:
                meta_count = len(self._engine._layers.get("meta", {}))
                if meta_count > 2000:
                    return {"id": "", "layer": "meta", "skipped": True, "reason": "meta_cap_reached"}
            except Exception:
                pass

        tags = tags or []
        metadata = metadata or {}

        # TCL归一化: 提取canonical_ids写入metadata (快速匹配始终执行，LLM部分由use_llm控制)
        try:
            from ..tcl_normalizer import (
                TCLNormalizer,
                TerminologyStore,
                seed_terminology,
            )

            if not hasattr(self._engine, "_tcl_store"):
                tcl_db = (
                    str(self._engine._data_path / "tcl_terminology.db")
                    if hasattr(self._engine, "_data_path")
                    else "data/tcl_terminology.db"
                )
                self._engine._tcl_store = TerminologyStore(tcl_db)
                if self._engine._tcl_store.get_stats()["total_terms"] == 0:
                    seed_terminology(self._engine._tcl_store)
                self._engine._tcl_normalizer = TCLNormalizer(
                    self._engine._tcl_store,
                    llm_bridge=getattr(self._engine, "_llm_bridge", None),
                )
            _, canonical_ids = self._engine._tcl_normalizer.normalize_content(
                content, use_llm=use_llm
            )
            if canonical_ids:
                metadata["tcl_canonical_ids"] = canonical_ids
        except Exception:
            pass  # TCL归一化失败不影响主流程

        if use_llm and self._engine._llm_bridge and hasattr(
            self._engine, "_enrich_with_llm"
        ):
            actual_layer, tags, priority, metadata, llm_enriched = (
                self._engine._enrich_with_llm(content, layer, tags, priority, metadata)
            )
        else:
            actual_layer = layer
            llm_enriched = False

        gate_result, actual_layer, metadata = self._engine._apply_quality_gate(
            content, layer, tags, priority, metadata
        )

        if gate_result and gate_result.verdict == "reject":
            return {
                "id": None,
                "status": "rejected",
                "reason": gate_result.reason,
                "gate_verdict": gate_result.verdict,
                "quality_dimensions": gate_result.quality_dimensions,
            }

        with self._engine._lock:
            entry = self._engine._create_memory_entry(
                content, actual_layer, tags, priority, metadata, gate_result
            )
            self._engine._store_memory_entry(entry)
            result = self._engine._build_remember_result(
                entry, layer, llm_enriched, gate_result
            )
            if self._engine._learning_bridge:
                try:
                    self._engine._learning_bridge.on_remember(
                        result, content, actual_layer
                    )
                except Exception:
                    pass
            if self._engine._asset_registry and result.get("id"):
                try:
                    self._engine._register_asset_atom(
                        result, content, actual_layer, tags, priority, metadata
                    )
                except Exception as e:
                    print(f"[TCL-DEBUG] _register_asset_atom failed: {e}")
            elif not self._engine._asset_registry:
                pass  # 资产注册表未初始化
            return result

    def remember_batch(
        self,
        entries: list[dict],
        use_llm: bool = False,
    ) -> list[dict]:
        """
        批量写入记忆 — 质量门禁前置 + WAL延迟写盘 + 固结硬上限批量后置

        参数:
          entries: [{"content": str, "layer": str, "tags": list, "priority": str, "metadata": dict}, ...]

        返回: [{"id": str, "status": str, ...}, ...]
        """
        if not entries:
            return []
        results = []
        gate_results = []
        pending_wal: list[MemoryEntry] = []
        affected_layers: set[str] = set()
        with self._engine._lock:
            for e in entries:
                content = e.get("content", "")
                layer = e.get("layer", "working")
                tags = e.get("tags", [])
                priority = e.get("priority", "medium")
                metadata = e.get("metadata", {})
                actual_layer = layer
                gate_result = None
                if self._engine._quality_gate:
                    existing = list(self._engine._layers.get(layer, {}).values())[:50]
                    gate_result = self._engine._quality_gate.check(
                        content, layer, tags, priority, existing
                    )
                    actual_layer = gate_result.target_layer
                    if gate_result.verdict == "reject":
                        self._engine._stats["total_rejected"] += 1
                        gate_results.append(
                            (
                                gate_result,
                                content,
                                actual_layer,
                                tags,
                                priority,
                                metadata,
                                layer,
                            )
                        )
                        continue
                    if gate_result.verdict == "downgrade":
                        self._engine._stats["total_downgraded"] += 1
                    if gate_result.verdict == "conflict":
                        self._engine._stats["total_conflicts"] += 1
                gate_results.append(
                    (
                        gate_result,
                        content,
                        actual_layer,
                        tags,
                        priority,
                        metadata,
                        layer,
                    )
                )
            for item in gate_results:
                (
                    gate_result,
                    content,
                    actual_layer,
                    tags,
                    priority,
                    metadata,
                    requested_layer,
                ) = item
                entry_id = hashlib.sha256(
                    f"{content}{time.time()}{uuid.uuid4()}".encode()
                ).hexdigest()[:16]
                entry = MemoryEntry(
                    id=entry_id,
                    content=content,
                    layer=actual_layer,
                    tags=tags,
                    priority=priority,
                    metadata=metadata or {},
                )
                if gate_result and gate_result.conflicts_with:
                    entry.related_ids = list(
                        set(entry.related_ids + gate_result.conflicts_with)
                    )
                self._engine._layers[actual_layer][entry_id] = entry
                self._engine._update_layer_size(actual_layer, entry.size_bytes)
                self._engine._index_tags(entry_id, entry.tags)
                self._engine._stats["total_entries"] += 1
                pending_wal.append(entry)
                affected_layers.add(actual_layer)
                results.append(
                    {
                        "id": entry_id,
                        "status": gate_result.verdict if gate_result else "stored",
                        "actual_layer": actual_layer,
                        "requested_layer": requested_layer,
                        "size_bytes": entry.size_bytes,
                    }
                )
            for entry in pending_wal:
                self._engine._save_entry(entry)
            for layer_name in affected_layers:
                self._engine._auto_consolidate(layer_name)
                self._engine._check_hard_cap(layer_name)
        return results

    def fast_inject(
        self,
        entries: list[dict],
    ) -> list[dict]:
        """
        极速批量注入 — 跳过质量门禁/文件I/O/固结/硬上限/累积追踪。

        仅用于基准测试/合成数据集场景。每条目约100μs，1000条目<0.1s。

        参数:
          entries: [{"content": str, "layer": str, "tags": list, "priority": str}, ...]

        返回: [{"id": str, "actual_layer": str, "size_bytes": int}, ...]
        """
        if not entries:
            return []
        results = []
        with self._engine._lock:
            for e in entries:
                content = e.get("content", "")
                layer = e.get("layer", "semantic")
                tags = e.get("tags", [])
                priority = e.get("priority", "high")
                entry_id = hashlib.sha256(
                    f"{content}{time.time()}{uuid.uuid4()}".encode()
                ).hexdigest()[:16]
                entry = MemoryEntry(
                    id=entry_id,
                    content=content,
                    layer=layer,
                    tags=tags,
                    priority=priority,
                    metadata={},
                )
                self._engine._layers[layer][entry_id] = entry
                for tag in tags:
                    self._engine._tag_index[tag].add(entry_id)
                size = self._engine._layer_sizes.get(layer, 0)
                self._engine._layer_sizes[layer] = size + entry.size_bytes
                self._engine._stats["total_entries"] += 1
                results.append(
                    {
                        "id": entry_id,
                        "actual_layer": layer,
                        "size_bytes": entry.size_bytes,
                    }
                )
        return results

    def remember_async(
        self,
        content: str,
        layer: str = "working",
        tags: list[str] | None = None,
        priority: str = "medium",
        metadata: dict | None = None,
    ) -> Any:
        """异步写入 — 非阻塞写入，立即返回future"""
        self._engine.ensure_async_executor()
        return self._engine._async_executor.submit(
            self._engine.remember, content, layer, tags, priority, metadata, False
        )

    def ensure_async_executor(self):
        """确保异步执行器就绪"""
        if self._engine._async_executor is None:
            import concurrent.futures

            self._engine._async_executor = concurrent.futures.ThreadPoolExecutor(
                max_workers=4, thread_name_prefix="tianji-write"
            )

    def remember_guarded(
        self,
        content: str,
        layer: str = "working",
        tags: list[str] | None = None,
        priority: str = "medium",
        metadata: dict | None = None,
    ) -> dict:
        return self._engine.remember(content, layer, tags, priority, metadata)
