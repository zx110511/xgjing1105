# -*- coding: utf-8-sig -*-
"""hybrid_engine_init.py — ICMEStorageEngineInitMixin (SSS-PhaseB)

从 hybrid_engine.py 拆分的方法组: init
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


from typing import Dict, Any

# SSS-PhaseE: 安全导入EvolutionLoop (可选依赖)
try:
    from core.processors.evolution_loop import EvolutionLoop
except Exception:
    EvolutionLoop = None

logger = logging.getLogger(__name__)

class ICMEStorageEngineInitMixin:
    """init方法组Mixin"""

    def __init__(
        self,
        config: ICMEConfig = None,
        use_sqlite: bool = True,
        recorder: Any | None = None,
        learning_engine: Any | None = None,
    ):
        self._use_sqlite = use_sqlite
        self._recorder = recorder
        self._learning_engine = learning_engine
        self._errors = 0

        self._evo_loop = None
        if EvolutionLoop is not None:
            try:
                self._evo_loop = EvolutionLoop(
                    module_name="hybrid_engine",
                    effectiveness_fn=self._calc_hybrid_effectiveness,
                    learn_fn=self._learn_from_hybrid,
                    evolve_fn=self._evolve_hybrid_config,
                    mutable_config={
                        "use_sqlite": use_sqlite,
                        "batch_size": 100,
                    },
                    recorder=recorder,
                    learning_engine=learning_engine,
                )
            except Exception as e:
                logger.warning(f"[HybridEngine] EvolutionLoop初始化失败: {e}")

        # SSS-PhaseE: 直接赋值config (MRO链中无接受config的基类)
        self.config = config
        self._quality_gate = None  # SSS-PhaseE: 补充quality_gate属性

        # SSS-PhaseE: 补充缺失的_data_path和_store初始化 (拆分时遗漏)
        self._data_path = getattr(config, 'data_path', Path("data/.memory")) if config else Path("data/.memory")
        self._store = None  # 延迟到_ensure_dirs()中初始化
        self._llm_bridge = None  # SSS-PhaseE: LLM桥接器
        self._layers: dict[str, dict] = {}  # SSS-PhaseE: 层级记忆字典
        self._tcl_normalizer = None  # SSS-PhaseE: TCL规范化器
        self._kg_sync = None  # SSS-PhaseE: 知识图谱同步
        self._stats = {
            "total_entries": 0, "total_accesses": 0, "total_consolidations": 0,
            "total_archivals": 0, "total_restorations": 0, "start_time": time.time(),
            "total_rejected": 0, "total_downgraded": 0, "total_conflicts": 0,
            "total_consolidations_triggered": 0, "total_hard_cap_enforcements": 0,
            # SSS-PhaseE: 补充recall统计键 (拆分时遗漏)
            "total_recall_calls": 0, "total_recall_hits": 0, "total_recall_latency_ms": 0,
        }
        self._consolidation_event_log: list[dict] = []  # stats()引用此属性
        import threading
        self._lock = threading.RLock()

        # 立即确保目录和存储就绪
        try:
            self._ensure_dirs()
        except Exception as e:
            logger.warning(f"[ICME] _ensure_dirs初始化失败: {e}")

        self._asset_registry = None
        try:
            from .asset_atom import AssetRegistry, AssetSnapshotManager

            db_path = (
                self._data_path / "icme.db"
                if self._use_sqlite
                else Path("data/.memory/icme.db")
            )
            self._asset_registry = AssetRegistry(str(db_path))
            # 策略D: 初始化快照管理器并注入到AssetRegistry
            try:
                self._snapshot_mgr = AssetSnapshotManager(str(db_path))
                self._asset_registry.set_snapshot_manager(self._snapshot_mgr)
                logger.info(f"[策略D] AssetSnapshotManager已注入, db_path={db_path}")
            except Exception as e:
                self._snapshot_mgr = None
                logger.warning(f"[策略D] AssetSnapshotManager初始化失败: {e}")
        except Exception as e:
            self._snapshot_mgr = None
            logger.warning(f"[策略D] AssetRegistry初始化失败: {e}")

        # [FIX-AUDIT] 补充ICMEEngineInitMixin未初始化的属性 (super().__init__未调用)
        # 这些属性被 hybrid_engine_stats.get_layer_capacity_info() 和 archiver/promoter 引用
        if not hasattr(self, "_accumulated_bytes"):
            self._accumulated_bytes: dict[str, int] = {
                layer.name: 0 for layer in (self.config.layers if self.config else [])
            }
        if not hasattr(self, "_accumulated_entries"):
            self._accumulated_entries: dict[str, int] = {
                layer.name: 0 for layer in (self.config.layers if self.config else [])
            }
        if not hasattr(self, "_last_consolidation_time"):
            self._last_consolidation_time: dict[str, float] = {
                layer.name: 0.0 for layer in (self.config.layers if self.config else [])
            }
        if not hasattr(self, "_layer_sizes"):
            self._layer_sizes: dict[str, int] = {
                layer.name: 0 for layer in (self.config.layers if self.config else [])
            }
        if not hasattr(self, "_tag_index"):
            from collections import defaultdict
            self._tag_index: dict[str, set[str]] = defaultdict(set)
        if not hasattr(self, "_archive"):
            from collections import OrderedDict
            self._archive = OrderedDict()
        if not hasattr(self, "_archive_max_size"):
            self._archive_max_size = 5 * 1024 * 1024 * 1024

        # [FIX-AUDIT] 补充 _get_accumulation_ratio 和 _get_accumulation_entry_ratio 方法
        # 这些方法被 hybrid_engine_stats.get_layer_capacity_info() 调用
        # 原本在 ICMEEngineCapacityMixin 中通过 self._archiver 代理，但 ICMEStorageEngine 未继承
        if not hasattr(self, "_get_accumulation_ratio"):
            def _get_accumulation_ratio_impl(layer_name: str) -> float:
                try:
                    layer_config = self.config.get_layer(layer_name) if hasattr(self.config, 'get_layer') else None
                    if not layer_config:
                        return 0.0
                    threshold = getattr(layer_config, 'accumulation_threshold_bytes', 0)
                    if threshold <= 0:
                        return 0.0
                    return self._accumulated_bytes.get(layer_name, 0) / threshold
                except Exception:
                    return 0.0
            self._get_accumulation_ratio = _get_accumulation_ratio_impl

        if not hasattr(self, "_get_accumulation_entry_ratio"):
            def _get_accumulation_entry_ratio_impl(layer_name: str) -> float:
                try:
                    layer_config = self.config.get_layer(layer_name) if hasattr(self.config, 'get_layer') else None
                    if not layer_config:
                        return 0.0
                    threshold = getattr(layer_config, 'accumulation_threshold_entries', 0)
                    if threshold <= 0:
                        return 0.0
                    return self._accumulated_entries.get(layer_name, 0) / threshold
                except Exception:
                    return 0.0
            self._get_accumulation_entry_ratio = _get_accumulation_entry_ratio_impl

        # P0-1: 计数器持久化恢复 (consolidations/archivals等不因重启丢失)
        self._load_persisted_counters()

    # P0-1: 需持久化的关键计数器 (会话级recall/access/hit_rate不在此列, 重启归零为预期行为)
    _PERSIST_COUNTER_KEYS = (
        "total_consolidations",
        "total_archivals",
        "total_restorations",
        "total_consolidations_triggered",
        "total_hard_cap_enforcements",
        "total_rejected",
        "total_downgraded",
        "total_conflicts",
    )

    def _stats_counter_path(self) -> Path:
        """计数器持久化文件路径 data/.memory/stats_counters.json"""
        return self._data_path / "stats_counters.json"

    def _load_persisted_counters(self) -> None:
        """从JSON恢复关键计数器, 避免重启丢失 (P0-1)"""
        try:
            p = self._stats_counter_path()
            if p.exists():
                data = json.loads(p.read_text("utf-8"))
                restored = 0
                for k in self._PERSIST_COUNTER_KEYS:
                    v = data.get(k)
                    if isinstance(v, (int, float)) and v > self._stats.get(k, 0):
                        self._stats[k] = int(v)
                        restored += 1
                if restored:
                    logger.info(f"[ICME] 计数器已从持久化恢复 ({restored}项): {p}")
        except Exception as e:
            logger.warning(f"[ICME] 计数器持久化恢复失败: {e}")

    def _persist_stats_counters(self) -> None:
        """将关键计数器写入JSON持久化 (P0-1)"""
        try:
            p = self._stats_counter_path()
            p.parent.mkdir(parents=True, exist_ok=True)
            data = {k: self._stats.get(k, 0) for k in self._PERSIST_COUNTER_KEYS}
            data["_updated_at"] = time.time()
            p.write_text(json.dumps(data, ensure_ascii=False), "utf-8")
        except Exception as e:
            logger.debug(f"[ICME] 计数器持久化写入失败: {e}")

    def _init_asset_registry(self):
        """懒初始化AssetRegistry (兜底启动时初始化失败)"""
        try:
            from .asset_atom import AssetRegistry, AssetSnapshotManager

            db_path = (
                self._data_path / "icme.db"
                if self._use_sqlite
                else Path("data/.memory/icme.db")
            )
            self._asset_registry = AssetRegistry(str(db_path))
            try:
                self._snapshot_mgr = AssetSnapshotManager(str(db_path))
                self._asset_registry.set_snapshot_manager(self._snapshot_mgr)
            except Exception as e:
                self._snapshot_mgr = None
                logger.warning(f"[策略D] 懒初始化SnapshotManager失败: {e}")
        except Exception as e:
            logger.warning(f"[策略D] 懒初始化AssetRegistry失败: {e}")

    def _ensure_dirs(self):
        """确保存储目录和后端就绪 (SSS-PhaseE增强: 多重容错)"""
        try:
            self._data_path.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            logger.warning(f"[ICME] 目录创建失败: {e}, 使用默认路径")
            self._data_path = Path("data/.memory")
            self._data_path.mkdir(parents=True, exist_ok=True)

        if self._use_sqlite:
            try:
                from .sqlite_store import SQLiteMemoryStore
                db_path = self._data_path / "icme.db"  # Path对象
                self._store = SQLiteMemoryStore(db_path, cache_size=1000)
                logger.info(f"[ICME] SQLite存储后端初始化成功: {db_path}")
            except Exception as e:
                logger.error(f"[ICME] SQLite初始化失败: {e}, 尝试内存模式")
                self._store = None  # 将在操作时降级到JSON/内存
        else:
            for layer in getattr(self.config, 'layers', []):
                (self._data_path / layer.name).mkdir(exist_ok=True)

    # SSS-PhaseE: 补充缺失的辅助方法 (拆分时遗漏)
    def _update_layer_size(self, layer_name: str, delta: int, track_accumulation: bool = True):
        """更新层级大小统计"""
        if not hasattr(self, '_layer_sizes'):
            self._layer_sizes = {}
        if layer_name in self._layer_sizes:
            self._layer_sizes[layer_name] = self._layer_sizes.get(layer_name, 0) + delta

    def _save_entry(self, entry_dict: dict):
        """保存条目到存储后端"""
        if self._store and hasattr(self._store, 'insert'):
            try:
                self._store.insert(entry_dict)
            except Exception as e:
                logging.getLogger(__name__).warning(f"[ICME] _save_entry失败: {e}")

    def _fallback_to_json(self, entry_dict: dict, *args, **kwargs):
        """JSON降级存储"""
        import json
        layer = entry_dict.get('layer', 'L3')
        path = self._data_path / layer / f"{entry_dict.get('id', 'unknown')}.json"
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(entry_dict, ensure_ascii=False), 'utf-8')
        except Exception as e:
            logging.getLogger(__name__).warning(f"[ICME] JSON降级失败: {e}")

    def _load_memory_data(self):
        if self._use_sqlite:
            total = self._store.get_total_stats()["total_entries"]
            if total == 0:
                self._migrate_json_to_sqlite()
            else:
                self._sync_json_to_sqlite_incremental()
            self._stats["total_entries"] = self._store.get_total_stats()[
                "total_entries"
            ]
            # [FIX-v9.1-meta-bloat] SQLite模式也需要强制清理Meta层
            self._enforce_meta_cap_on_startup()
            # [FIX-v9.1-meta-bloat] SQLite模式也需要启动MetaGuardian守护线程
            self._start_meta_guardian_daemon()
            return
        super()._load_memory_data()

    def _enforce_meta_cap_on_startup(self, max_keep: int = 500):
        """[FIX-v9.1-meta-bloat] SQLite模式：直接操作数据库清理Meta层"""
        if not self._use_sqlite:
            super()._enforce_meta_cap_on_startup(max_keep)
            return
        try:
            import sqlite3
            conn = sqlite3.connect(str(self._data_path / "icme.db"))
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM memories WHERE layer='meta' AND archived=0")
            count = cur.fetchone()[0]
            import sys; print(f"[MetaCap-SQLite] Meta count in DB: {count}", file=sys.stderr, flush=True)
            if count <= max_keep:
                conn.close(); return
            cur.execute("""
                SELECT id FROM memories WHERE layer='meta' AND archived=0
                ORDER BY created_at DESC LIMIT -1 OFFSET ?
            """, (max_keep,))
            to_delete = [row[0] for row in cur.fetchall()]
            for mid in to_delete:
                cur.execute("UPDATE memories SET archived=1 WHERE id=?", (mid,))
            conn.commit(); conn.close()
            logger.warning("[MetaCap-SQLite] Startup cleanup: removed %d (kept %d)", len(to_delete), max_keep)
        except Exception as e:
            logger.warning("[MetaCap-SQLite] Cleanup failed: %s", e)

    def _start_meta_guardian_daemon(self):
        """[FIX-v9.1-meta-bloat] SQLite模式：直接操作数据库的MetaGuardian"""
        if not self._use_sqlite:
            super()._start_meta_guardian_daemon()
            return
        import logging as _logging
        import threading as _th
        _logger = _logging.getLogger(__name__)
        self._meta_guardian_running = True

        def _sqlite_guardian_loop():
            while self._meta_guardian_running:
                try:
                    time.sleep(60)
                    if not self._meta_guardian_running: break
                    import sqlite3
                    conn = sqlite3.connect(str(self._data_path / "icme.db"))
                    cur = conn.cursor()
                    cur.execute("SELECT COUNT(*) FROM memories WHERE layer='meta' AND archived=0")
                    count = cur.fetchone()[0]
                    if count > 1000:
                        cur.execute("""
                            SELECT id FROM memories WHERE layer='meta' AND archived=0
                            ORDER BY created_at DESC LIMIT -1 OFFSET 500
                        """)
                        to_delete = [row[0] for row in cur.fetchall()]
                        for mid in to_delete:
                            cur.execute("UPDATE memories SET archived=1 WHERE id=?", (mid,))
                        conn.commit()
                        _logger.warning("[MetaGuardian-SQLite] Removed %d entries", len(to_delete))
                    conn.close()
                except Exception as e:
                    _logger.debug("[MetaGuardian-SQLite] Error: %s", e)

        _t = _th.Thread(target=_sqlite_guardian_loop, name="ICME-Meta-Guardian-SQLite", daemon=True)
        _t.start()
        _logger.info("[MetaGuardian-SQLite] Daemon started (interval=60s, direct DB ops)")

    def _get_migration_manager(self) -> MigrationManager:
        """构建 JSON→SQLite 迁移管理器

        迁移逻辑已拆分至 core.storage.migration.MigrationManager (P1-03)。
        """
        return MigrationManager(self._store, self._data_path, self._layers.keys())

    def _sync_json_to_sqlite_incremental(self):
        self._get_migration_manager().sync_json_to_sqlite_incremental()

    def _migrate_json_to_sqlite(self):
        self._get_migration_manager().migrate_json_to_sqlite()

    def _enrich_with_llm(
        self,
        content: str,
        layer: str,
        tags: list[str],
        priority: str,
        metadata: dict | None,
    ) -> tuple:
        """LLM增强桥接 — 智能分层+自动标签+价值评估+知识提取+摘要

        [FIX-B2-001] 添加超时保护(15s), LLM超时时降级为非LLM模式,确保记忆存储永不阻塞
        """
        if not self._llm_bridge or not self._llm_bridge.is_ready:
            return layer, tags, priority, metadata, False

        actual_layer = layer
        llm_enriched = False

        # [FIX-B2-001] 超时保护: LLM调用超过15秒则跳过富化,确保记忆写入不阻塞
        import signal

        def _timeout_handler(signum, frame):
            raise TimeoutError("LLM enrichment timed out")

        try:
            # Windows不支持signal.alarm, 使用线程超时替代
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(
                    self._do_enrich_llm, content, layer, tags, priority, metadata
                )
                try:
                    actual_layer, tags, priority, metadata, llm_enriched = future.result(timeout=15)
                except concurrent.futures.TimeoutError:
                    logger.warning("[HybridEngine] LLM增强超时(15s),降级为非LLM模式")
                    llm_enriched = False
                except Exception as e:
                    logger.debug(f"[HybridEngine] LLM增强跳过: {e}")
                    llm_enriched = False
        except Exception as e:
            logger.debug(f"[HybridEngine] LLM增强异常: {e}")
            llm_enriched = False

        return actual_layer, tags, priority, metadata, llm_enriched

    def _do_enrich_llm(
        self,
        content: str,
        layer: str,
        tags: list[str],
        priority: str,
        metadata: dict | None,
    ) -> tuple:
        """LLM增强实际执行(被_enrich_with_llm的线程池调用)"""
        actual_layer = layer
        llm_enriched = False

        enrichment = self._llm_bridge.enrich_remember(
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

        return actual_layer, tags, priority, metadata, llm_enriched

    def _init_tcl(self):
        """初始化TCL归一化引擎(延迟加载)"""
        if hasattr(self, "_tcl_store") and self._tcl_store is not None:
            return True
        try:
            from .tcl_normalizer import (
                TCLNormalizer,
                TerminologyStore,
                seed_terminology,
            )

            tcl_db = (
                str(self._data_path / "tcl_terminology.db")
                if hasattr(self, "_data_path")
                else "data/tcl_terminology.db"
            )
            self._tcl_store = TerminologyStore(tcl_db)
            if self._tcl_store.get_stats()["total_terms"] == 0:
                seed_terminology(self._tcl_store)
            self._tcl_normalizer = TCLNormalizer(
                self._tcl_store, llm_bridge=getattr(self, "_llm_bridge", None)
            )
            return True
        except Exception as e:
            logger.warning(f"[HybridEngine] TCL初始化失败: {e}")
            self._tcl_store = None
            self._tcl_normalizer = None
            return False

    def set_quality_gate(self, gate):
        """SSS-PhaseE: 设置质量门禁 (deps.py需要)"""
        self._quality_gate = gate

    def set_llm_bridge(self, bridge):
        """[FIX-COUNTER-AUDIT] SSS-PhaseB拆分后缺失: 设置LLM桥接 (deps.py需要)
        原engine_init.py有此方法，拆分到hybrid_engine_init.py时遗漏。
        LLM Bridge负责记忆增强(classify/summarize/extract_knowledge/expand_query)"""
        self._llm_bridge = bridge
