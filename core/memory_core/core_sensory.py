# -*- coding: utf-8-sig -*-
"""天机v10.0.1 L0 感知层记忆核心  [v10-ready]

SensoryCore — ICME L0 感知记忆层 (sensory)：
    - 即时输入捕获，写入路径最短 (快速写入, 不做评分)
    - 容量小、流动快，按时间顺序整体晋升至 working
    - 晋升策略: 达到累积阈值或容量阈值时，将最早条目批量晋升

架构定位: core/memory_core/ — ICME 六层 → MemoryCore 实例化
版本: 1.0.0
"""
from __future__ import annotations

from typing import Any

from core.memory_core.base import MemoryCore
from core.shared.plugin_interface import PluginInfo
from core.shared.protocols import IStorageEngine, MemoryLayer

# 插件元信息  [v10-ready]
PLUGIN_INFO = PluginInfo(
    name="sensory_core",
    version="1.0.0",
    description="L0感知层记忆核心 (即时捕获→working)",
    category="memory_core",
    protocols=["IStorageEngine"],
)


class SensoryCore(MemoryCore):
    """L0 感知层记忆核心  [v10-ready]

    特征: 快速写入、容量小、整体顺序晋升。不在写入路径上做质量评分。
    """

    def __init__(
        self,
        storage_engine: IStorageEngine | None = None,
        config: dict | None = None,
    ) -> None:
        """初始化 L0 感知层核心  [v10-ready]"""
        super().__init__(MemoryLayer.SENSORY, storage_engine, config)

    def _default_config(self) -> dict[str, Any]:
        """L0 默认配置: 快速写入, 低优先级, 高累积晋升  [v10-ready]"""
        cfg = super()._default_config()
        cfg.setdefault("promote_batch", 100)
        # 容量占用达 75% 即触发晋升, 保持感知层流动性
        cfg.setdefault("promotion_threshold", 0.75)
        return cfg

    def write(self, entry: dict) -> str:
        """快速写入感知条目 (无评分)  [v10-ready]

        Args:
            entry: 记忆条目字典。

        Returns:
            生成的 entry_id。
        """
        normalized = self._normalize(entry)
        normalized.setdefault("score", 0.0)
        return self._persist(normalized)

    def read(self, entry_id: str) -> dict | None:
        """读取感知条目  [v10-ready]"""
        return self._fetch(entry_id)

    def search(self, query: str, *, limit: int = 20) -> list[dict]:
        """检索感知条目  [v10-ready]"""
        return self._query(query, limit=limit)

    def promote(self) -> int:
        """顺序晋升最早的感知条目至 working  [v10-ready]

        当占用率达到 promotion_threshold 时，按时间顺序选取最早的一批
        条目晋升 (本阶段仅标记，真实跨层写入由 Phase 4-2 调度器接入)。

        Returns:
            本次晋升的条目数。
        """
        if not self.should_promote():
            return 0
        batch = int(self._config.get("promote_batch", 100))
        candidates = sorted(
            self._active_entries(), key=lambda e: e.get("timestamp", 0.0)
        )[:batch]
        for item in candidates:
            item["promote_to"] = MemoryLayer.WORKING.value
        promoted = len(candidates)
        self._stats["promotions"] += promoted
        return promoted

    def should_promote(self) -> bool:
        """是否达到感知层晋升阈值  [v10-ready]"""
        max_entries = int(self._config.get("max_entries", 0) or 0)
        if max_entries <= 0:
            return False
        threshold = float(self._config.get("promotion_threshold", 0.75))
        return (self._count() / max_entries) >= threshold
