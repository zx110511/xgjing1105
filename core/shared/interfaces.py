"""天机核心聚阵Protocol接口层 (Tianji Core Cluster Interfaces)

为"六层记忆+L-Asset"核心聚阵提供标准化接口定义。
所有接口支持本地实现和远程实现两种模式，实现分布式就绪。

架构定位: v10.0.1 Phase 0 共享内核层
版本: 1.0.2 (SSS-PhaseE: 7个重复Protocol统一到protocols_*.py，消除重复定义)
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Optional, Protocol, runtime_checkable

# SSS-PhaseE: 7个Protocol接口统一从protocols_*.py导入，消除重复定义
from core.shared.protocols_storage import IStorageEngine
from core.shared.protocols_search import ISearchStrategy
from core.shared.protocols_event import IEventBus
from core.shared.protocols_gate import IGateStrategy, IConsolidationStrategy
from core.shared.protocols_graph import IGraphEngine, IAssetRegistry
from core.shared.protocols_active import IActiveMemory


# ============================================================================
# 枚举定义 (interfaces.py独有，未在protocols_*.py中定义)
# ============================================================================

class GateVerdict(str, Enum):
    """质量门禁判决类型

    单进程模式: 由 QualityGate 三问推演直接产出。
    分布式模式: 由远程门禁服务返回，序列化为字符串值跨进程传输。
    """

    PASS = "PASS"
    DOWNGRADE = "DOWNGRADE"
    REJECT = "REJECT"
    CONFLICT = "CONFLICT"
    PENDING_UPSTREAM = "PENDING_UPSTREAM"


# ============================================================================
# 辅助数据类 (接口返回值载体，interfaces.py独有)
# ============================================================================

@dataclass
class GateResult:
    """质量门禁判决结果

    用于 IGateStrategy.check() 的返回值，承载三问推演的最终判决。

    Attributes:
        verdict: 判决结果 (PASS/DOWNGRADE/REJECT/CONFLICT/PENDING_UPSTREAM)
        confidence: 判决置信度 (0.0 ~ 1.0)
        reason: 判决理由说明
        suggested_layer: 建议写入的记忆层级 (DOWNGRADE 时给出)
    """

    verdict: str
    confidence: float
    reason: str
    suggested_layer: str | None = None


@dataclass
class SearchResult:
    """搜索结果

    用于 ISearchStrategy 聚合搜索的统一返回载体。

    Attributes:
        entries: 命中的记忆条目列表
        total_count: 命中总数
        search_time_ms: 本次搜索耗时 (毫秒)
        strategy_used: 实际使用的搜索策略标识
    """

    entries: list[dict[str, Any]]
    total_count: int
    search_time_ms: float
    strategy_used: str


@dataclass
class ClusterHealth:
    """聚阵健康状态

    描述核心聚阵 (六层记忆+L-Asset) 整体运行状态的快照。

    Attributes:
        status: 总体状态 (healthy/degraded/unhealthy)
        components: 各组件健康标志 (组件名 -> 是否健康)
        memory_usage: 各层内存占用统计
        uptime_seconds: 运行时长 (秒)
    """

    status: str
    components: dict[str, bool]
    memory_usage: dict[str, Any]
    uptime_seconds: float


# ============================================================================
# 公开导出符号
# ============================================================================

__all__ = [
    # 枚举
    "GateVerdict",
    # 辅助数据类
    "GateResult",
    "SearchResult",
    "ClusterHealth",
    # Protocol 接口 (统一从protocols_*.py导入)
    "IStorageEngine",
    "ISearchStrategy",
    "IEventBus",
    "IGateStrategy",
    "IConsolidationStrategy",
    "IGraphEngine",
    "IAssetRegistry",
    "IActiveMemory",
]
