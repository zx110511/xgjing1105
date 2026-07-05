# -*- coding: utf-8-sig -*-
"""天机v10.0.1 L5 元层记忆核心  [v10-ready]

MetaCore — ICME L5 元记忆层 (meta)：
    - 策略自优化，记忆金字塔顶端，承接 semantic 晋升
    - 写入前需要质量评分 (strategy scoring)
    - 晋升策略: 无上层目标 (顶层)，promote() 恒返回 0；改为内部固结

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
    name="meta_core",
    version="1.0.0",
    description="L5元层记忆核心 (策略自优化, 顶层无晋升)",
    category="memory_core",
    protocols=["IStorageEngine"],
)


class MetaCore(MemoryCore):
    """L5 元层记忆核心  [v10-ready]

    特征: 记忆金字塔顶端, 策略自优化, 无晋升目标 (promote 恒为 0)。
    """

    def __init__(
        self,
        storage_engine: IStorageEngine | None = None,
        config: dict | None = None,
    ) -> None:
        """初始化 L5 元层核心  [v10-ready]"""
        super().__init__(MemoryLayer.META, storage_engine, config)

    def _default_config(self) -> dict[str, Any]:
        """L5 默认配置: 写入评分 + 无晋升目标  [v10-ready]"""
        cfg = super()._default_config()
        cfg.setdefault("is_terminal", True)
        return cfg

    def write(self, entry: dict) -> str:
        """写入元策略条目 (写入前策略评分)  [v10-ready]

        Args:
            entry: 记忆条目字典。

        Returns:
            生成的 entry_id。
        """
        normalized = self._normalize(entry)
        normalized.setdefault("tags", [])
        normalized["strategy_score"] = self._strategy_score(normalized)
        normalized.setdefault("score", normalized["strategy_score"])
        return self._persist(normalized)

    def read(self, entry_id: str) -> dict | None:
        """读取元策略条目  [v10-ready]"""
        return self._fetch(entry_id)

    def search(self, query: str, *, limit: int = 20) -> list[dict]:
        """检索元策略条目  [v10-ready]"""
        return self._query(query, limit=limit)

    def promote(self) -> int:
        """元层为顶层, 无晋升目标, 恒返回 0  [v10-ready]

        Returns:
            始终为 0 (顶层无上一层级)。
        """
        return 0

    def _strategy_score(self, entry: dict[str, Any]) -> float:
        """策略价值评分: 标签 + 内容的轻量启发式  [v10-ready]"""
        tags = entry.get("tags") or []
        content = str(entry.get("content", ""))
        score = 0.4
        score += min(0.3, 0.1 * len(tags))
        score += min(0.3, len(content) / 2000.0)
        return round(min(1.0, score), 4)
