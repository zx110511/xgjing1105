# -*- coding: utf-8-sig -*-
"""天机v10.0.1 L3 情景层记忆核心  [v10-ready]

EpisodicCore — ICME L3 情景记忆层 (episodic)：
    - 决策记录 / AI 经验沉淀，承接 short_term 晋升
    - 写入前需要质量评分 (importance scoring)，要求带标签
    - 晋升策略: 重要度评分达阈值的条目晋升至 semantic

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
    name="episodic_core",
    version="1.0.0",
    description="L3情景层记忆核心 (决策记录/AI经验→semantic)",
    category="memory_core",
    protocols=["IStorageEngine"],
)


class EpisodicCore(MemoryCore):
    """L3 情景层记忆核心  [v10-ready]

    特征: 写入前评分, 沉淀决策与经验, 按重要度晋升至语义层。
    """

    def __init__(
        self,
        storage_engine: IStorageEngine | None = None,
        config: dict | None = None,
    ) -> None:
        """初始化 L3 情景层核心  [v10-ready]"""
        super().__init__(MemoryLayer.EPISODIC, storage_engine, config)

    def _default_config(self) -> dict[str, Any]:
        """L3 默认配置: 写入评分 + 重要度晋升  [v10-ready]"""
        cfg = super()._default_config()
        cfg.setdefault("promote_batch", 50)
        cfg.setdefault("promotion_threshold", 0.6)
        cfg.setdefault("require_tags", True)
        return cfg

    def write(self, entry: dict) -> str:
        """写入情景条目 (写入前评分)  [v10-ready]

        L3 要求带标签，并在写入路径上计算重要度评分。

        Args:
            entry: 记忆条目字典。

        Returns:
            生成的 entry_id。
        """
        normalized = self._normalize(entry)
        normalized.setdefault("tags", [])
        normalized["importance"] = self._importance_score(normalized)
        normalized.setdefault("score", normalized["importance"])
        return self._persist(normalized)

    def read(self, entry_id: str) -> dict | None:
        """读取情景条目  [v10-ready]"""
        return self._fetch(entry_id)

    def search(self, query: str, *, limit: int = 20) -> list[dict]:
        """检索情景条目  [v10-ready]"""
        return self._query(query, limit=limit)

    def promote(self) -> int:
        """按重要度评分晋升条目至 semantic  [v10-ready]

        Returns:
            本次晋升的条目数。
        """
        threshold = float(self._config.get("promotion_threshold", 0.6))
        batch = int(self._config.get("promote_batch", 50))
        candidates = [
            e
            for e in self._active_entries()
            if float(e.get("importance", e.get("score", 0.0))) >= threshold
        ]
        candidates.sort(
            key=lambda e: e.get("importance", e.get("score", 0.0)), reverse=True
        )
        candidates = candidates[:batch]
        for item in candidates:
            item["promote_to"] = MemoryLayer.SEMANTIC.value
        promoted = len(candidates)
        self._stats["promotions"] += promoted
        return promoted

    def _importance_score(self, entry: dict[str, Any]) -> float:
        """重要度评分: 标签 + 内容 + 新近度的多因子启发式  [v10-ready]"""
        tags = entry.get("tags") or []
        content = str(entry.get("content", ""))
        score = 0.2
        score += min(0.4, 0.1 * len(tags))
        score += min(0.2, len(content) / 1500.0)
        age = max(0.0, time.time() - float(entry.get("timestamp", time.time())))
        # 越新近重要度加成越高 (1 天内线性衰减)
        score += max(0.0, 0.2 * (1.0 - min(1.0, age / 86400.0)))
        return round(min(1.0, score), 4)
