# -*- coding: utf-8-sig -*-
"""四通道融合检索器 — 兼容层 (thin wrapper)  [v10-ready]

v10.0 重构: 四通道融合逻辑已拆分至 core/search/ 子包的独立策略插件。
本模块降级为瘦身兼容层，re-export 新实现以保持 v9.1 既有导入路径可用：

    from core.memory.fusion_retriever import FusionRetriever   # 仍然有效

实际实现见:
    core/search/fts5_strategy.py      FTS5SearchStrategy
    core/search/tag_strategy.py       TagIndexStrategy
    core/search/semantic_strategy.py  SemanticSearchStrategy
    core/search/kg_strategy.py        KGTopologyStrategy
    core/search/fusion_strategy.py    FusionRetrievalStrategy

架构定位: core/ 兼容层
版本: 2.0.0 (compat)
"""

from __future__ import annotations

from core.search.fusion_strategy import (
    CHANNEL_WEIGHTS,
    RRF_K,
    ChannelPriority,
    ChannelResult,
    FusionResult,
    FusionRetrievalStrategy,
)


class FusionRetriever(FusionRetrievalStrategy):
    """四通道融合检索器 (兼容别名)  [v10-ready]

    完全等价于 core.search.FusionRetrievalStrategy，保留原类名与
    构造签名 (engine/sqlite_store/graph_store/embeddings_service)，
    以及 retrieve / get_stats / set_* 方法，确保 v9.1 调用方无感知。
    """


__all__ = [
    "FusionRetriever",
    "ChannelPriority",
    "ChannelResult",
    "FusionResult",
    "CHANNEL_WEIGHTS",
    "RRF_K",
]
