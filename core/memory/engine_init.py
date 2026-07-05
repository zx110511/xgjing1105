# -*- coding: utf-8-sig -*-
"""engine_init.py — ICMEEngineInitMixin (SSS-PhaseB)

从 engine.py 拆分的方法组: init
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

class ICMEEngineInitMixin:
    """init方法组Mixin"""

    def __init__(
        self,
        config: ICMEConfig | None = None,
        dependencies: dict[str, Any] | None = None,
    ):
        self.config = config or DEFAULT_CONFIG
        self._dependencies = dependencies or {}

        self._layers: dict[str, OrderedDict[str, MemoryEntry]] = {
            layer.name: OrderedDict() for layer in self.config.layers
        }
        self._archive: OrderedDict[str, MemoryEntry] = OrderedDict()
        self._archive_max_size = 5 * 1024 * 1024 * 1024
        self._tag_index: dict[str, set[str]] = defaultdict(set)
        self._layer_sizes: dict[str, int] = {
            layer.name: 0 for layer in self.config.layers
        }
        self._accumulated_bytes: dict[str, int] = {
            layer.name: 0 for layer in self.config.layers
        }
        self._accumulated_entries: dict[str, int] = {
            layer.name: 0 for layer in self.config.layers
        }
        self._last_consolidation_time: dict[str, float] = {
            layer.name: 0.0 for layer in self.config.layers
        }
        self._consolidation_event_log: list[dict] = []
        self._consolidation_event_log_max = 500
        self._stats = {
            "total_entries": 0,
            "total_accesses": 0,
            "total_consolidations": 0,
            "total_archivals": 0,
            "total_restorations": 0,
            "start_time": time.time(),
            "total_rejected": 0,
            "total_downgraded": 0,
            "total_conflicts": 0,
            "total_consolidations_triggered": 0,
            "total_hard_cap_enforcements": 0,
            "total_recall_calls": 0,
            "total_recall_hits": 0,
            "total_recall_latency_ms": 0,
        }
        self._rate_tracker: dict[str, list[tuple[float, int]]] = {
            layer.name: [] for layer in self.config.layers
        }
        self._rate_window_seconds = getattr(
            self.config, "rate_tracking_window_seconds", 300
        )
        self._data_path = self.config.data_path
        self._lock = threading.RLock()

        self._quality_gate = self._dependencies.get("quality_gate")
        self._llm_bridge = self._dependencies.get("llm_bridge")
        self._consolidation_processor = self._dependencies.get(
            "consolidation_processor"
        )
        self._conflict_resolver = self._dependencies.get("conflict_resolver")
        self._preference_drift_detector = self._dependencies.get(
            "preference_drift_detector"
        )
        self._learning_bridge = self._dependencies.get("learning_bridge")
        self._asset_registry = self._dependencies.get("asset_registry")
        if self._learning_bridge is None:
            self._learning_bridge = ClosedLoopLearningBridge(engine=self)

        self._sqlite_store = self._dependencies.get("sqlite_store")
        self._async_executor = self._dependencies.get("async_executor")

        if _PROCESSORS_AVAILABLE and self._consolidation_processor is None:
            self._consolidation_processor = ConsolidationProcessor(engine=self)
        if _PROCESSORS_AVAILABLE and self._conflict_resolver is None:
            self._conflict_resolver = ConflictResolver()
        if _PROCESSORS_AVAILABLE and self._preference_drift_detector is None:
            self._preference_drift_detector = PreferenceDriftDetector()

        if self._sqlite_store is None:
            try:
                from .sqlite_store import SQLiteMemoryStore

                self._sqlite_store = SQLiteMemoryStore(self._data_path / "icme.db")
            except Exception:
                pass

        self._evo_loop = self._dependencies.get("evolution_loop")
        if self._evo_loop is None:
            try:
                from ..processors.evolution_loop import EvolutionLoop

                self._evo_loop = EvolutionLoop(
                    module_name="engine",
                    effectiveness_fn=self._calc_engine_effectiveness,
                    learn_fn=self._learn_from_engine_ops,
                    evolve_fn=self._evolve_engine_config,
                    mutable_config={
                        "consolidation_threshold": 0.8,
                        "archive_age_days": 30,
                        "hard_cap_ratio": 0.95,
                        "promotion_min_score": 0.6,
                    },
                    health_metrics_fn=self._get_engine_health,
                )
            except ImportError:
                pass

        # [v10-ready] 职责拆分: 组合四个记忆子组件 (writer/promoter/archiver/indexer)
        # 子组件持有 engine 宿主引用作为共享上下文与依赖注入入口。
        self._writer = MemoryWriter(self)
        self._promoter = PromotionEngine(self)
        self._archiver = ArchiveManager(self)
        self._indexer = MemoryIndex(self)

        # [v10-ready] v9.1 Protocol 模式: 优先委派到 MemoryCore 六层实例。
        # 开关关闭或初始化失败时静默降级到旧 SQLite/JSON 路径 (行为完全不变)。
        self._protocol_mode: bool = bool(TIANJI_V91_PROTOCOL_MODE)
        self._memory_cores: dict[str, Any] | None = None
        self._event_bus: Any = None
        if self._protocol_mode:
            self._init_memory_cores()

        self._ensure_dirs()
        self._load_memory_data()
        self._start_consolidation_daemon()

    # ====================================================================
    # 依赖注入 / 进化闭环 (engine 自身职责)
    # ====================================================================
    def set_quality_gate(self, gate):
        self._quality_gate = gate

    def set_llm_bridge(self, bridge):
        self._llm_bridge = bridge

    def _init_memory_cores(self) -> None:
        """[v10-ready] 创建六层 MemoryCore 实例，失败时静默降级。"""
        try:
            from .memory_core import create_all_cores

            self._memory_cores = create_all_cores()
        except Exception as exc:  # ImportError 或其他初始化异常
            import logging as _logging

            self._memory_cores = None
            _logging.getLogger(__name__).warning(
                "[v9.1-Protocol] MemoryCore 初始化失败，降级到旧路径: %s", exc
            )

    def _get_event_bus(self) -> Any:
        """[v10-ready] 延迟获取事件总线单例 (避免循环导入)。"""
        if self._event_bus is not None:
            return self._event_bus
        try:
            from server.deps import get_event_bus

            self._event_bus = get_event_bus()
        except Exception:
            self._event_bus = None
        return self._event_bus

    def _ensure_dirs(self):
        self._data_path.mkdir(parents=True, exist_ok=True)
        for layer in self.config.layers:
            (self._data_path / layer.name).mkdir(exist_ok=True)

    def _load_memory_data(self):
        for layer_name in self._layers.keys():
            layer_dir = self._data_path / layer_name
            if not layer_dir.exists():
                continue
            for entry_file in layer_dir.glob("*.json"):
                try:
                    data = json.loads(entry_file.read_text(encoding="utf-8-sig"))
                    entry = MemoryEntry(
                        id=data["id"],
                        content=data["content"],
                        layer=data["layer"],
                        tags=data.get("tags", []),
                        priority=data.get("priority", "medium"),
                        created_at=data.get("created_at", time.time()),
                        last_accessed=data.get("last_accessed", time.time()),
                        access_count=data.get("access_count", 0),
                        effectiveness_score=data.get("effectiveness_score", 0.5),
                        related_ids=data.get("related_ids", []),
                        metadata=data.get("metadata", {}),
                        changelog=data.get("changelog", []),
                    )
                    self._layers[layer_name][entry.id] = entry
                    self._update_layer_size(
                        layer_name, entry.size_bytes, track_accumulation=False
                    )
                    self._index_tags(entry.id, entry.tags)
                    self._stats["total_entries"] += 1
                except Exception:
                    pass
