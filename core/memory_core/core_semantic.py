# -*- coding: utf-8-sig -*-
"""天机v10.0.1 L4 语义层记忆核心  [v10-ready]

SemanticCore — ICME L4 语义记忆层 (semantic)：
    - 知识图谱 / 概念关系，承接 episodic 晋升
    - 写入前需要质量评分 (knowledge scoring)，要求带标签与上游锚点
    - 晋升策略: 知识价值评分达阈值且关联度高的条目晋升至 meta

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
    name="semantic_core",
    version="1.0.0",
    description="L4语义层记忆核心 (知识图谱/概念关系→meta)",
    category="memory_core",
    protocols=["IStorageEngine"],
)


class SemanticCore(MemoryCore):
    """L4 语义层记忆核心  [v10-ready]

    特征: 写入前知识评分, 维护概念关系, 按知识价值晋升至元层。
    """

    def __init__(
        self,
        storage_engine: IStorageEngine | None = None,
        config: dict | None = None,
    ) -> None:
        """初始化 L4 语义层核心  [v10-ready]"""
        super().__init__(MemoryLayer.SEMANTIC, storage_engine, config)

    def _default_config(self) -> dict[str, Any]:
        """L4 默认配置: 写入评分 + 知识价值晋升  [v10-ready]"""
        cfg = super()._default_config()
        cfg.setdefault("promote_batch", 30)
        cfg.setdefault("promotion_threshold", 0.7)
        cfg.setdefault("require_tags", True)
        cfg.setdefault("require_upstream", True)
        return cfg

    def write(self, entry: dict) -> str:
        """写入语义条目 (写入前知识评分)  [v10-ready]

        L4 要求带标签与上游锚点，并在写入路径上计算知识价值评分。

        Args:
            entry: 记忆条目字典。

        Returns:
            生成的 entry_id。
        """
        normalized = self._normalize(entry)
        normalized.setdefault("tags", [])
        normalized.setdefault("upstream", [])
        normalized["knowledge_score"] = self._knowledge_score(normalized)
        normalized.setdefault("score", normalized["knowledge_score"])
        return self._persist(normalized)

    def read(self, entry_id: str) -> dict | None:
        """读取语义条目  [v10-ready]"""
        return self._fetch(entry_id)

    def search(self, query: str, *, limit: int = 20) -> list[dict]:
        """检索语义条目  [v10-ready]"""
        return self._query(query, limit=limit)

    def promote(self) -> int:
        """按知识价值评分晋升条目至 meta  [v10-ready]

        Returns:
            本次晋升的条目数。
        """
        threshold = float(self._config.get("promotion_threshold", 0.7))
        batch = int(self._config.get("promote_batch", 30))
        candidates = [
            e
            for e in self._active_entries()
            if float(e.get("knowledge_score", e.get("score", 0.0))) >= threshold
        ]
        candidates.sort(
            key=lambda e: e.get("knowledge_score", e.get("score", 0.0)), reverse=True
        )
        candidates = candidates[:batch]
        for item in candidates:
            item["promote_to"] = MemoryLayer.META.value
        promoted = len(candidates)
        self._stats["promotions"] += promoted
        return promoted

    def _knowledge_score(self, entry: dict[str, Any]) -> float:
        """知识价值评分: 标签 + 上游锚点 + 内容的多因子启发式  [v10-ready]"""
        tags = entry.get("tags") or []
        upstream = entry.get("upstream") or []
        content = str(entry.get("content", ""))
        score = 0.2
        score += min(0.3, 0.1 * len(tags))
        score += min(0.3, 0.15 * len(upstream))
        score += min(0.2, len(content) / 2000.0)
        return round(min(1.0, score), 4)
