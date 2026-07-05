# -*- coding: utf-8-sig -*-
"""天机v10.0.1 L2 短期层记忆核心  [v10-ready]

ShortTermCore — ICME L2 短期记忆层 (short_term)：
    - 关键信息保持，承接 working 晋升
    - 写入时计算保持评分 (retention_score)
    - 晋升策略: 保持评分达阈值的条目晋升至 episodic

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
    name="short_term_core",
    version="1.0.0",
    description="L2短期层记忆核心 (关键信息保持→episodic)",
    category="memory_core",
    protocols=["IStorageEngine"],
)


class ShortTermCore(MemoryCore):
    """L2 短期层记忆核心  [v10-ready]

    特征: 保持关键信息, 基于保持评分晋升至情景层。
    """

    def __init__(
        self,
        storage_engine: IStorageEngine | None = None,
        config: dict | None = None,
    ) -> None:
        """初始化 L2 短期层核心  [v10-ready]"""
        super().__init__(MemoryLayer.SHORT_TERM, storage_engine, config)

    def _default_config(self) -> dict[str, Any]:
        """L2 默认配置: 保持评分晋升  [v10-ready]"""
        cfg = super()._default_config()
        cfg.setdefault("promote_batch", 50)
        cfg.setdefault("promotion_threshold", 0.5)
        return cfg

    def write(self, entry: dict) -> str:
        """写入短期条目并计算保持评分  [v10-ready]"""
        normalized = self._normalize(entry)
        if "score" not in normalized:
            normalized["score"] = self._retention_score(normalized)
        return self._persist(normalized)

    def read(self, entry_id: str) -> dict | None:
        """读取短期条目  [v10-ready]"""
        return self._fetch(entry_id)

    def search(self, query: str, *, limit: int = 20) -> list[dict]:
        """检索短期条目  [v10-ready]"""
        return self._query(query, limit=limit)

    def promote(self) -> int:
        """按保持评分晋升条目至 episodic  [v10-ready]

        Returns:
            本次晋升的条目数。
        """
        threshold = float(self._config.get("promotion_threshold", 0.5))
        batch = int(self._config.get("promote_batch", 50))
        candidates = [
            e
            for e in self._active_entries()
            if float(e.get("score", 0.0)) >= threshold
        ]
        candidates.sort(key=lambda e: e.get("score", 0.0), reverse=True)
        candidates = candidates[:batch]
        for item in candidates:
            item["promote_to"] = MemoryLayer.EPISODIC.value
        promoted = len(candidates)
        self._stats["promotions"] += promoted
        return promoted

    def _retention_score(self, entry: dict[str, Any]) -> float:
        """计算保持评分: 标签数 + 内容长度的轻量启发式  [v10-ready]"""
        tags = entry.get("tags") or []
        content = str(entry.get("content", ""))
        score = 0.3
        score += min(0.4, 0.1 * len(tags))
        score += min(0.3, len(content) / 1000.0)
        return round(min(1.0, score), 4)
