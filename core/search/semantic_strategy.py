# -*- coding: utf-8-sig -*-
"""语义向量检索策略  [v10-ready]

通道3: 语义向量搜索 (深) → MiniLM 跨语义匹配。

本地实现 ISearchStrategy 协议，由 FusionRetrievalStrategy 并行调度。
分布式模式下可由灵境远程向量检索服务替换。

架构定位: core/search/ 搜索策略插件层
版本: 1.0.0
"""
from __future__ import annotations

import logging
from typing import Any

from core.shared.plugin_interface import PluginInfo

logger = logging.getLogger("tianji.search.semantic")


class SemanticSearchStrategy:
    """语义向量检索策略  [v10-ready]

    本地实现: 基于 embeddings_service 的向量相似度检索，回退到 engine.recall。
    实现协议: ISearchStrategy (search / get_capabilities)。
    """

    CHANNEL = "SEMANTIC"

    def __init__(self, embeddings_service: Any = None, engine: Any = None) -> None:
        self._embeddings_service = embeddings_service
        self._engine = engine

    def set_embeddings_service(self, service: Any) -> None:
        """注入向量嵌入服务。  [v10-ready]"""
        self._embeddings_service = service

    def set_engine(self, engine: Any) -> None:
        """注入记忆引擎(回退检索)。  [v10-ready]"""
        self._engine = engine

    def search(self, query: str, *, limit: int = 20, **kwargs: Any) -> list[dict[str, Any]]:
        """执行语义向量检索。  [v10-ready]

        Args:
            query: 查询文本。
            limit: 返回条目上限。
            **kwargs: 支持 layers(list[str]) 过滤。

        Returns:
            命中条目字典列表。
        """
        layers = kwargs.get("layers")
        results: list[dict[str, Any]] = []

        if self._embeddings_service:
            try:
                sem_results = self._embeddings_service.search(query, top_k=limit)
                for r in sem_results[:limit]:
                    if isinstance(r, dict):
                        results.append(self._to_dict(r, default_score=0.3))
            except Exception:
                pass

        if not results and self._engine:
            try:
                engine_results = self._engine.recall(query=query, limit=limit,
                                                      min_score=0.1, layers=layers)
                for r in engine_results[:limit]:
                    if isinstance(r, dict):
                        score = r.get("score", 0.3)
                        if score > 0.3:
                            results.append(self._to_dict(r, default_score=score))
            except Exception:
                pass

        return results

    def get_capabilities(self) -> list[str]:
        """声明能力维度。  [v10-ready]"""
        return ["semantic", "vector", "embedding"]

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
    name="semantic_search",
    version="1.0.0",
    description="语义向量相似度检索策略",
    category="search",
    protocols=["ISearchStrategy"],
)
