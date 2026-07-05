# -*- coding: utf-8-sig -*-
"""天机v10.0.1 L1 工作层记忆核心  [v10-ready]

WorkingCore — ICME L1 工作记忆层 (working)：
    - 会话上下文管理，承接 sensory 晋升
    - 写入时记录访问元数据，晋升基于访问活跃度
    - 晋升策略: 访问次数 + 新近度达阈值的条目晋升至 short_term

架构定位: core/memory_core/ — ICME 六层 → MemoryCore 实例化
版本: 1.0.0
"""
from __future__ import annotations

import time
from typing import Any

from core.memory_core.base import MemoryCore
from core.shared.plugin_interface import PluginInfo
from core.shared.protocols import IStorageEngine, MemoryLayer

# 插件元信息  [v10-ready]
PLUGIN_INFO = PluginInfo(
    name="working_core",
    version="1.0.0",
    description="L1工作层记忆核心 (会话上下文→short_term)",
    category="memory_core",
    protocols=["IStorageEngine"],
)


class WorkingCore(MemoryCore):
    """L1 工作层记忆核心  [v10-ready]

    特征: 维护会话上下文, 记录访问活跃度, 按活跃度晋升。
    """

    def __init__(
        self,
        storage_engine: IStorageEngine | None = None,
        config: dict | None = None,
    ) -> None:
        """初始化 L1 工作层核心  [v10-ready]"""
        super().__init__(MemoryLayer.WORKING, storage_engine, config)

    def _default_config(self) -> dict[str, Any]:
        """L1 默认配置: 访问活跃度晋升  [v10-ready]"""
        cfg = super()._default_config()
        cfg.setdefault("promote_batch", 50)
        cfg.setdefault("min_access_count", 2)
        cfg.setdefault("promotion_threshold", 0.80)
        return cfg

    def write(self, entry: dict) -> str:
        """写入工作条目并初始化访问元数据  [v10-ready]"""
        normalized = self._normalize(entry)
        normalized.setdefault("access_count", 0)
        normalized.setdefault("last_access", normalized.get("timestamp", time.time()))
        return self._persist(normalized)

    def read(self, entry_id: str) -> dict | None:
        """读取工作条目并累加访问计数  [v10-ready]"""
        item = self._fetch(entry_id)
        if item is not None and self._storage is None:
            item["access_count"] = int(item.get("access_count", 0)) + 1
            item["last_access"] = time.time()
        return item

    def search(self, query: str, *, limit: int = 20) -> list[dict]:
        """检索工作条目  [v10-ready]"""
        return self._query(query, limit=limit)

    def promote(self) -> int:
        """按访问活跃度晋升条目至 short_term  [v10-ready]

        选取访问次数达 min_access_count 的条目晋升 (本阶段仅标记)。

        Returns:
            本次晋升的条目数。
        """
        min_access = int(self._config.get("min_access_count", 2))
        batch = int(self._config.get("promote_batch", 50))
        candidates = [
            e
            for e in self._active_entries()
            if int(e.get("access_count", 0)) >= min_access
        ]
        candidates.sort(key=lambda e: e.get("access_count", 0), reverse=True)
        candidates = candidates[:batch]
        for item in candidates:
            item["promote_to"] = MemoryLayer.SHORT_TERM.value
        promoted = len(candidates)
        self._stats["promotions"] += promoted
        return promoted
