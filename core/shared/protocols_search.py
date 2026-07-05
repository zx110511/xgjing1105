# -*- coding: utf-8-sig -*-
"""天机v10.0.1 共享内核Protocol搜索域接口  [v10-ready]

定义4个搜索相关Protocol接口：
- ISearchStrategy: 搜索策略接口
- IFusionRetriever: 融合检索接口
- IReranker: 重排序接口
- IQueryExpander: 查询扩展接口

架构定位: core/shared/ Ω基点层 — 搜索聚阵契约
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from .protocols_base import SearchResult


@runtime_checkable
class ISearchStrategy(Protocol):
    """搜索策略接口  [v10-ready]

    本地实现: FTS5SearchStrategy (SQLite FTS5 全文检索, 单进程默认)
    远程实现: RemoteVectorStrategy (灵境向量检索服务)

    切换方式: 多策略由融合检索器按能力与权重并行调度，
    分布式向量策略可作为远程实现热插拔接入。
    """

    def search(
        self, query: str, *, limit: int = 20, **kwargs: Any
    ) -> list[dict[str, Any]]:
        """执行检索。

        Args:
            query: 查询文本。
            limit: 返回条目上限。
            **kwargs: 扩展过滤参数。

        Returns:
            命中的条目字典列表。
        """
        ...

    def get_capabilities(self) -> list[str]:
        """声明本策略具备的检索能力维度。

        Returns:
            能力标识列表，如 ["keyword", "semantic", "graph"]。
        """
        ...


@runtime_checkable
class IFusionRetriever(Protocol):
    """融合检索接口  [v10-ready]

    本地实现: LocalFusionRetriever (进程内多策略加权融合)
    远程实现: RemoteFusionRetriever (灵境聚合检索网关)

    切换方式: 融合器统一编排多个 ISearchStrategy，
    分布式模式下可将打分与归并下推至远程聚合服务。
    """

    def retrieve(self, query: str, *, limit: int = 20, **kwargs: Any) -> SearchResult:
        """执行融合检索。

        Args:
            query: 查询文本。
            limit: 返回条目上限。
            **kwargs: 扩展过滤参数。

        Returns:
            聚合后的 SearchResult。
        """
        ...

    def set_weights(self, weights: dict[str, float]) -> None:
        """设置各策略融合权重。

        Args:
            weights: 策略标识 -> 权重 的映射。
        """
        ...


@runtime_checkable
class IReranker(Protocol):
    """重排序接口  [v10-ready]

    本地实现: LocalReranker (进程内规则/轻量模型重排)
    远程实现: RemoteReranker (灵境 Cross-Encoder 重排服务)

    切换方式: 检索召回后由本接口对候选重排，
    分布式模式下将候选批量送往远程重排模型。
    """

    def rerank(
        self,
        query: str,
        candidates: list[dict[str, Any]],
        *,
        top_k: int = 10,
    ) -> list[dict[str, Any]]:
        """对候选结果重排序。

        Args:
            query: 原始查询文本。
            candidates: 待重排的候选条目列表。
            top_k: 重排后保留的条目数。

        Returns:
            按相关性降序排列的条目列表。
        """
        ...


@runtime_checkable
class IQueryExpander(Protocol):
    """查询扩展接口  [v10-ready]

    本地实现: LocalQueryExpander (同义词/规则扩展)
    远程实现: RemoteQueryExpander (灵境 LLM 查询改写服务)

    切换方式: 检索前对原始查询做语义扩展，
    分布式模式下将改写交由远程大模型服务完成。
    """

    def expand(self, query: str, *, max_variants: int = 3) -> list[str]:
        """扩展查询为多个变体。

        Args:
            query: 原始查询文本。
            max_variants: 生成的扩展变体数量上限。

        Returns:
            扩展后的查询文本列表 (含原始查询)。
        """
        ...


__all__ = [
    "ISearchStrategy",
    "IFusionRetriever",
    "IReranker",
    "IQueryExpander",
]
