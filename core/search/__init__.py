# -*- coding: utf-8-sig -*-
"""天机v10.0.1 搜索策略子包  [v10-ready]

将四通道融合检索拆分为独立的 ISearchStrategy 策略插件：

- FTS5SearchStrategy      — FTS5 全文检索 (快)
- TagIndexStrategy        — 标签索引精确匹配 (准)
- SemanticSearchStrategy  — 语义向量相似度 (深)
- KGTopologyStrategy      — 知识图谱拓扑关联 (全)
- FusionRetrievalStrategy — 四通道编排 + RRF 加权融合
- RemoteSearchStrategy    — 灵境远程检索 (gRPC stub, 预留)

所有本地策略实现 core.shared.protocols.ISearchStrategy，
并携带 PLUGIN_INFO (category="search") 供 PluginManager 注册。

架构定位: core/search/ 搜索策略插件层
版本: 1.0.0
"""
from __future__ import annotations

from core.search.fts5_strategy import FTS5SearchStrategy
from core.search.tag_strategy import TagIndexStrategy
from core.search.semantic_strategy import SemanticSearchStrategy
from core.search.kg_strategy import KGTopologyStrategy
from core.search.fusion_strategy import (
    FusionRetrievalStrategy,
    ChannelPriority,
    ChannelResult,
    FusionResult,
    CHANNEL_WEIGHTS,
    RRF_K,
)
from core.search.remote_stub import RemoteSearchStrategy

__all__ = [
    # 本地策略
    "FTS5SearchStrategy",
    "TagIndexStrategy",
    "SemanticSearchStrategy",
    "KGTopologyStrategy",
    "FusionRetrievalStrategy",
    # 远程策略 (stub)
    "RemoteSearchStrategy",
    # 融合相关类型与常量
    "ChannelPriority",
    "ChannelResult",
    "FusionResult",
    "CHANNEL_WEIGHTS",
    "RRF_K",
]
