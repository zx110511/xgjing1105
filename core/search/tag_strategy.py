# -*- coding: utf-8-sig -*-
"""标签索引检索策略  [v10-ready]

通道2: tag_index 标签索引 (准) → 精确匹配 tags。

本地实现 ISearchStrategy 协议，由 FusionRetrievalStrategy 并行调度。

架构定位: core/search/ 搜索策略插件层
版本: 1.0.0
"""
from __future__ import annotations

import logging
from typing import Any

from core.shared.plugin_interface import PluginInfo

logger = logging.getLogger("tianji.search.tag")


class TagIndexStrategy:
    """标签索引检索策略  [v10-ready]

    本地实现: 基于 SQLite tag_index 的标签精确匹配。
    实现协议: ISearchStrategy (search / get_capabilities)。
    """

    CHANNEL = "TAG_INDEX"

    def __init__(self, sqlite_store: Any = None) -> None:
        self._sqlite_store = sqlite_store

    def set_sqlite_store(self, store: Any) -> None:
        """注入 SQLite 存储。  [v10-ready]"""
        self._sqlite_store = store

    def search(self, query: str, *, limit: int = 20, **kwargs: Any) -> list[dict[str, Any]]:
        """执行标签精确匹配检索。  [v10-ready]

        Args:
            query: 查询文本 (按空白切分为候选标签)。
            limit: 返回条目上限。
            **kwargs: 支持 layers(list[str]) 过滤。

        Returns:
            命中条目字典列表。
        """
        layers = kwargs.get("layers")
        results: list[dict[str, Any]] = []
        query_tags = [t.strip().lower() for t in query.split() if len(t.strip()) > 1]

        if self._sqlite_store and query_tags:
            try:
                tag_results = self._sqlite_store.search_by_tags(query_tags, limit=limit,
                                                                layers=layers)
                for r in tag_results[:limit]:
                    results.append({
                        "channel": self.CHANNEL,
                        "id": r.get("id", ""),
                        "content": r.get("content", ""),
                        "score": r.get("score", 0.4),
                        "layer": r.get("layer", ""),
                        "tags": r.get("tags", []),
                        "metadata": r.get("metadata", {}),
                    })
            except Exception:
                pass

        return results

    def get_capabilities(self) -> list[str]:
        """声明能力维度。  [v10-ready]"""
        return ["tag", "exact_match"]


PLUGIN_INFO = PluginInfo(
    name="tag_search",
    version="1.0.0",
    description="标签索引精确匹配策略",
    category="search",
    protocols=["ISearchStrategy"],
)
