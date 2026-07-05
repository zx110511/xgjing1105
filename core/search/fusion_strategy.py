# -*- coding: utf-8-sig -*-
"""四通道融合检索策略  [v10-ready]

编排 FTS5 / TagIndex / Semantic / KGTopology 四个搜索策略，
按通道权重 + RRF (Reciprocal Rank Fusion) 融合去重后返回。

检索优先级: FTS5(快) → tag_index(准) → 语义(深) → KG(全)
融合策略: RRF 加权融合

本地实现 IFusionRetriever / ISearchStrategy 协议。
分布式模式下可将打分与归并下推至远程聚合服务。

架构定位: core/search/ 搜索策略插件层
版本: 1.0.0
"""
from __future__ import annotations

import time
import logging
import threading
from enum import Enum
from typing import Any
from dataclasses import dataclass, field
from concurrent.futures import ThreadPoolExecutor, as_completed

from core.shared.plugin_interface import PluginInfo
from core.search.fts5_strategy import FTS5SearchStrategy
from core.search.tag_strategy import TagIndexStrategy
from core.search.semantic_strategy import SemanticSearchStrategy
from core.search.kg_strategy import KGTopologyStrategy

logger = logging.getLogger("tianji.search.fusion")


class ChannelPriority(int, Enum):
    """通道优先级枚举  [v10-ready]"""
    FTS5 = 1
    TAG_INDEX = 2
    SEMANTIC = 3
    KG_TOPOLOGY = 4


CHANNEL_WEIGHTS = {
    ChannelPriority.FTS5: 0.35,
    ChannelPriority.TAG_INDEX: 0.25,
    ChannelPriority.SEMANTIC: 0.25,
    ChannelPriority.KG_TOPOLOGY: 0.15,
}

RRF_K = 60


@dataclass
class ChannelResult:
    """单通道命中结果  [v10-ready]"""
    channel: str
    entry_id: str
    content: str
    score: float
    layer: str = ""
    tags: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)


@dataclass
class FusionResult:
    """融合检索结果  [v10-ready]"""
    query: str
    results: list[dict]
    channel_stats: dict[str, int]
    total_time_ms: float
    fusion_method: str = "rrf_weighted"


class FusionRetrievalStrategy:
    """四通道融合检索策略  [v10-ready]

    本地实现: 并行调度四个 ISearchStrategy + RRF 加权融合。
    实现协议: ISearchStrategy (search / get_capabilities)
              兼容 IFusionRetriever (retrieve / set_weights)。
    """

    def __init__(self, engine: Any = None, sqlite_store: Any = None,
                 graph_store: Any = None, embeddings_service: Any = None) -> None:
        self._engine = engine
        self._sqlite_store = sqlite_store
        self._graph_store = graph_store
        self._embeddings_service = embeddings_service
        self._lock = threading.Lock()

        # 四通道策略实例 (按通道名索引)
        self._strategies: dict[str, Any] = {
            ChannelPriority.FTS5.name: FTS5SearchStrategy(sqlite_store, engine),
            ChannelPriority.TAG_INDEX.name: TagIndexStrategy(sqlite_store),
            ChannelPriority.SEMANTIC.name: SemanticSearchStrategy(embeddings_service, engine),
            ChannelPriority.KG_TOPOLOGY.name: KGTopologyStrategy(graph_store),
        }
        self._weights: dict[str, float] = {
            c.name: CHANNEL_WEIGHTS[c] for c in ChannelPriority
        }

        self._stats = {
            "total_queries": 0,
            "channel_hits": {c.name: 0 for c in ChannelPriority},
            "channel_errors": {c.name: 0 for c in ChannelPriority},
            "fusion_count": 0,
        }

    # ------------------------------------------------------------------
    # 依赖注入 (兼容原 FusionRetriever 接口)
    # ------------------------------------------------------------------
    def set_engine(self, engine: Any) -> None:
        """注入记忆引擎并下发到相关通道。  [v10-ready]"""
        self._engine = engine
        self._strategies[ChannelPriority.FTS5.name].set_engine(engine)
        self._strategies[ChannelPriority.SEMANTIC.name].set_engine(engine)

    def set_sqlite_store(self, store: Any) -> None:
        """注入 SQLite 存储并下发到相关通道。  [v10-ready]"""
        self._sqlite_store = store
        self._strategies[ChannelPriority.FTS5.name].set_sqlite_store(store)
        self._strategies[ChannelPriority.TAG_INDEX.name].set_sqlite_store(store)

    def set_graph_store(self, store: Any) -> None:
        """注入图谱存储并下发到 KG 通道。  [v10-ready]"""
        self._graph_store = store
        self._strategies[ChannelPriority.KG_TOPOLOGY.name].set_graph_store(store)

    def set_embeddings_service(self, service: Any) -> None:
        """注入向量服务并下发到语义通道。  [v10-ready]"""
        self._embeddings_service = service
        self._strategies[ChannelPriority.SEMANTIC.name].set_embeddings_service(service)

    def set_weights(self, weights: dict[str, float]) -> None:
        """设置各通道融合权重 (IFusionRetriever)。  [v10-ready]"""
        self._weights.update(weights)

    # ------------------------------------------------------------------
    # 核心检索
    # ------------------------------------------------------------------
    def retrieve(self, query: str, limit: int = 10,
                 layers: list[str] | None = None,
                 min_score: float = 0.0) -> FusionResult:
        """四通道融合检索 — 核心入口。  [v10-ready]

        Args:
            query: 查询文本。
            limit: 返回条目上限。
            layers: 可选层级过滤。
            min_score: 融合分数下限过滤。

        Returns:
            FusionResult 融合检索结果。
        """
        start = time.time()
        self._stats["total_queries"] += 1

        all_channel_results: dict[str, list[dict[str, Any]]] = {}

        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = {
                executor.submit(strategy.search, query, limit=limit, layers=layers): name
                for name, strategy in self._strategies.items()
            }
            for future in as_completed(futures):
                name = futures[future]
                try:
                    results = future.result()
                    all_channel_results[name] = results
                    self._stats["channel_hits"][name] += len(results)
                except Exception as e:
                    logger.error(f"通道 {name} 检索失败: {e}")
                    all_channel_results[name] = []
                    self._stats["channel_errors"][name] += 1

        fused = self._rrf_weighted_fusion(all_channel_results, limit)

        if min_score > 0:
            fused = [r for r in fused if r.get("score", 0) >= min_score]

        elapsed = (time.time() - start) * 1000
        channel_stats = {name: len(results) for name, results in all_channel_results.items()}
        self._stats["fusion_count"] += 1

        return FusionResult(
            query=query,
            results=fused,
            channel_stats=channel_stats,
            total_time_ms=elapsed,
        )

    def search(self, query: str, *, limit: int = 20, **kwargs: Any) -> list[dict[str, Any]]:
        """ISearchStrategy 入口 — 返回融合后的结果列表。  [v10-ready]

        Args:
            query: 查询文本。
            limit: 返回条目上限。
            **kwargs: 支持 layers / min_score 过滤。

        Returns:
            融合后的条目字典列表。
        """
        result = self.retrieve(
            query,
            limit=limit,
            layers=kwargs.get("layers"),
            min_score=kwargs.get("min_score", 0.0),
        )
        return result.results

    def get_capabilities(self) -> list[str]:
        """声明融合能力维度。  [v10-ready]"""
        return ["fusion", "keyword", "tag", "semantic", "graph", "rrf"]

    # ------------------------------------------------------------------
    # RRF 加权融合
    # ------------------------------------------------------------------
    def _rrf_weighted_fusion(self, all_results: dict[str, list[dict[str, Any]]],
                             limit: int) -> list[dict]:
        """RRF 加权融合 — 通道权重 × RRF 分数。  [v10-ready]

        Args:
            all_results: 通道名 -> 该通道结果字典列表。
            limit: 融合后返回上限。

        Returns:
            融合去重并按分数降序的结果字典列表。
        """
        scores: dict[str, tuple[float, dict[str, Any]]] = {}

        for channel_name, channel_results in all_results.items():
            weight = self._weights.get(channel_name, 0.1)

            for rank, result in enumerate(channel_results, start=1):
                rrf_score = weight / (RRF_K + rank)
                entry_id = result.get("id", "")
                if not entry_id:
                    continue

                if entry_id in scores:
                    old_score, old_result = scores[entry_id]
                    scores[entry_id] = (old_score + rrf_score, old_result)
                else:
                    scores[entry_id] = (rrf_score, result)

        sorted_results = sorted(scores.values(), key=lambda x: x[0], reverse=True)

        fused = []
        for score, result in sorted_results[:limit]:
            fused.append({
                "id": result.get("id", ""),
                "content": result.get("content", ""),
                "score": round(score, 6),
                "layer": result.get("layer", ""),
                "tags": result.get("tags", []),
                "metadata": result.get("metadata", {}),
            })

        return fused

    def get_stats(self) -> dict:
        """获取检索统计。  [v10-ready]"""
        return {
            **self._stats,
            "engine_connected": self._engine is not None,
            "sqlite_connected": self._sqlite_store is not None,
            "graph_connected": self._graph_store is not None,
            "embeddings_connected": self._embeddings_service is not None,
            "channel_weights": dict(self._weights),
        }


PLUGIN_INFO = PluginInfo(
    name="fusion_search",
    version="1.0.0",
    description="四通道RRF加权融合检索策略",
    category="search",
    protocols=["ISearchStrategy", "IFusionRetriever"],
)
