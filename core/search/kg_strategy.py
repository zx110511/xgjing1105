# -*- coding: utf-8-sig -*-
"""知识图谱拓扑关联策略  [v10-ready]

通道4: KG 拓扑关联 (全) → 知识图谱关联扩展。

本地实现 ISearchStrategy 协议，由 FusionRetrievalStrategy 并行调度。
分布式模式下可由远程图数据库查询服务替换。

架构定位: core/search/ 搜索策略插件层
版本: 1.0.0
"""
from __future__ import annotations

import logging
from typing import Any

from core.shared.plugin_interface import PluginInfo

logger = logging.getLogger("tianji.search.kg")


class KGTopologyStrategy:
    """知识图谱拓扑关联策略  [v10-ready]

    本地实现: 基于 graph_store 的实体关联扩展检索。
    实现协议: ISearchStrategy (search / get_capabilities)。
    """

    CHANNEL = "KG_TOPOLOGY"

    def __init__(self, graph_store: Any = None) -> None:
        self._graph_store = graph_store

    def set_graph_store(self, store: Any) -> None:
        """注入图谱存储。  [v10-ready]"""
        self._graph_store = store

    def search(self, query: str, *, limit: int = 20, **kwargs: Any) -> list[dict[str, Any]]:
        """执行知识图谱拓扑关联检索。  [v10-ready]

        Args:
            query: 查询文本。
            limit: 返回条目上限。
            **kwargs: 预留扩展过滤参数。

        Returns:
            命中条目字典列表。
        """
        results: list[dict[str, Any]] = []

        if self._graph_store:
            try:
                kg_results = self._graph_store.search_entities(query, limit=limit)
                for r in kg_results[:limit]:
                    if isinstance(r, dict):
                        results.append({
                            "channel": self.CHANNEL,
                            "id": r.get("id", ""),
                            "content": r.get("content", ""),
                            "score": r.get("score", 0.2),
                            "layer": r.get("layer", "semantic"),
                            "tags": r.get("tags", []),
                            "metadata": r.get("metadata", {}),
                        })
            except Exception:
                pass

        return results

    def get_capabilities(self) -> list[str]:
        """声明能力维度。  [v10-ready]"""
        return ["graph", "topology", "kg"]


PLUGIN_INFO = PluginInfo(
    name="kg_search",
    version="1.0.0",
    description="知识图谱拓扑关联策略",
    category="search",
    protocols=["ISearchStrategy"],
)
