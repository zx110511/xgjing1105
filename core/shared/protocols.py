# -*- coding: utf-8-sig -*-
"""天机v10.0.1 共享内核Protocol接口层 — re-export兼容层  [v10-ready]

本文件为兼容层，将分散到子模块的Protocol接口统一re-export，
确保所有 `from core.shared.protocols import XXX` 导入路径不变。

实际定义已按领域拆分至:
- protocols_base.py: 枚举+数据类 (GateVerdict/MemoryLayer/GateResult等)
- protocols_storage.py: 存储域 (IStorageEngine/ILayerStorage/IBatchStorage/IStorageMigrator)
- protocols_search.py: 搜索域 (ISearchStrategy/IFusionRetriever/IReranker/IQueryExpander)
- protocols_event.py: 事件域 (IEventBus/IEventHandler/IEventFilter)
- protocols_gate.py: 门禁域+晋升域 (IGateStrategy/IQualityGate/IGatePolicy/IConsolidationStrategy等)
- protocols_graph.py: 图谱域+资产域 (IGraphEngine/IGraphQuery/ITripleExtractor/IAssetRegistry等)
- protocols_active.py: 主动记忆域+插件域+调度域 (IActiveMemory/IPlugin/IAgentDispatcher等)
- protocols_strategy.py: LLM/缓存/适配器/验证/防腐层 (ILLMStrategy/ICacheStrategy等)

架构定位: core/shared/ Ω基点层 — 全系统依赖的公共契约
版本: 1.1.0 (SSS-PhaseB拆分后兼容层)
"""

from __future__ import annotations

# 基础类型 (枚举+数据类)
from .protocols_base import (
    ClusterHealth,
    GateResult,
    GateVerdict,
    MemoryLayer,
    PluginInfo,
    SearchResult,
)

# 存储域
from .protocols_storage import (
    IBatchStorage,
    ILayerStorage,
    IStorageEngine,
    IStorageMigrator,
)

# 搜索域
from .protocols_search import (
    IFusionRetriever,
    IQueryExpander,
    IReranker,
    ISearchStrategy,
)

# 事件域
from .protocols_event import (
    IEventBus,
    IEventFilter,
    IEventHandler,
)

# 门禁域+晋升域
from .protocols_gate import (
    IConsolidationScheduler,
    IConsolidationStrategy,
    IGatePolicy,
    IGateStrategy,
    IPromotionGate,
    IQualityGate,
)

# 图谱域+资产域
from .protocols_graph import (
    IAssetBinding,
    IAssetRegistry,
    IAssetSnapshot,
    IGraphEngine,
    IGraphQuery,
    ITripleExtractor,
)

# 主动记忆域+插件域+调度域
from .protocols_active import (
    IActiveMemory,
    IAgentDispatcher,
    IIntentExtractor,
    IInterceptLayer,
    IPlugin,
    IPluginManager,
    ISchedulerStrategy,
    ITaskRouter,
)

# 策略域 (LLM/缓存/适配器/验证/防腐层)
from .protocols_strategy import (
    IAdapterStrategy,
    IAnticorruptionLayer,
    ICacheStrategy,
    IDomainAdapter,
    ILLMStrategy,
    ISerializationStrategy,
    IValidationStrategy,
)

# ============================================================================
# 公开导出符号 (保持与原文件完全一致)
# ============================================================================

__all__ = [
    # 枚举
    "GateVerdict",
    "MemoryLayer",
    # 辅助数据类
    "GateResult",
    "SearchResult",
    "ClusterHealth",
    "PluginInfo",
    # 存储域
    "IStorageEngine",
    "ILayerStorage",
    "IBatchStorage",
    "IStorageMigrator",
    # 搜索域
    "ISearchStrategy",
    "IFusionRetriever",
    "IReranker",
    "IQueryExpander",
    # 事件域
    "IEventBus",
    "IEventHandler",
    "IEventFilter",
    # 门禁域
    "IGateStrategy",
    "IQualityGate",
    "IGatePolicy",
    # 晋升域
    "IConsolidationStrategy",
    "IPromotionGate",
    "IConsolidationScheduler",
    # 图谱域
    "IGraphEngine",
    "IGraphQuery",
    "ITripleExtractor",
    # 资产域
    "IAssetRegistry",
    "IAssetBinding",
    "IAssetSnapshot",
    # 主动记忆域
    "IActiveMemory",
    "IInterceptLayer",
    "IIntentExtractor",
    # 插件域
    "IPlugin",
    "IPluginManager",
    # 调度域
    "IAgentDispatcher",
    "ITaskRouter",
    "ISchedulerStrategy",
    # LLM域
    "ILLMStrategy",
    # 缓存域
    "ICacheStrategy",
    # 适配器域
    "IAdapterStrategy",
    # 验证域
    "ISerializationStrategy",
    "IValidationStrategy",
    # 防腐层域
    "IDomainAdapter",
    "IAnticorruptionLayer",
]
