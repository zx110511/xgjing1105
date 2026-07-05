# -*- coding: utf-8-sig -*-
"""FTS5 全文检索策略  [v10-ready]

通道1: FTS5 全文搜索 (快) → content_segmented 精确匹配。

本地实现 ISearchStrategy 协议，由 FusionRetrievalStrategy 并行调度。
分布式模式下可被远程检索策略热插拔替换。

架构定位: core/search/ 搜索策略插件层
版本: 1.0.0
"""
from __future__ import annotations

import logging
from typing import Any

from core.shared.plugin_interface import PluginInfo

logger = logging.getLogger("tianji.search.fts5")


class FTS5SearchStrategy:
    """FTS5 全文检索策略  [v10-ready]

    本地实现: 基于 SQLite FTS5 的全文检索，回退到 engine.recall。
    实现协议: ISearchStrategy (search / get_capabilities)。
    """

    CHANNEL = "FTS5"

    def __init__(self, sqlite_store: Any = None, engine: Any = None) -> None:
        self._sqlite_store = sqlite_store
        self._engine = engine

    def set_sqlite_store(self, store: Any) -> None:
        """注入 SQLite 存储。  [v10-ready]"""
        self._sqlite_store = store

    def set_engine(self, engine: Any) -> None:
        """注入记忆引擎(回退检索)。  [v10-ready]"""
        self._engine = engine

    def search(self, query: str, *, limit: int = 20, **kwargs: Any) -> list[dict[str, Any]]:
        """执行 FTS5 全文检索。  [v10-ready]

        Args:
            query: 查询文本。
            limit: 返回条目上限。
            **kwargs: 支持 layers(list[str]) 过滤。

        Returns:
            命中条目字典列表 (含 channel/id/content/score/layer/tags)。
        """
        layers = kwargs.get("layers")
        results: list[dict[str, Any]] = []

        if self._sqlite_store:
            try:
                fts_results = self._sqlite_store.search(query, limit=limit, layers=layers)
                for r in fts_results[:limit]:
                    results.append(self._to_dict(r, default_score=0.5))
            except Exception as e:
                logger.error(f"FTS5搜索失败: {e}")

        if not results and self._engine:
            try:
                engine_results = self._engine.recall(query=query, limit=limit,
                                                      min_score=0.0, layers=layers)
                for r in engine_results[:limit]:
                    if isinstance(r, dict):
                        results.append(self._to_dict(r, default_score=0.5))
            except Exception:
                pass

        return results

    def get_capabilities(self) -> list[str]:
        """声明能力维度。  [v10-ready]"""
        return ["keyword", "fulltext", "fts5"]

    def _to_dict(self, r: dict[str, Any], *, default_score: float) -> dict[str, Any]:
        """将原始命中规整为统一结果字典。  [v10-ready]"""
        return {
            "channel": self.CHANNEL,
            "id": r.get("id", ""),
            "content": r.get("content", ""),
            "score": r.get("score", default_score),
            "layer": r.get("layer", ""),
            "tags": r.get("tags", []),
            "metadata": r.get("metadata", {}),
        }


PLUGIN_INFO = PluginInfo(
    name="fts5_search",
    version="1.0.0",
    description="FTS5全文检索策略",
    category="search",
    protocols=["ISearchStrategy"],
)
