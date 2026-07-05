# -*- coding: utf-8-sig -*-
"""天机v10.0.1 共享内核Protocol基础层 — 枚举+数据类  [v10-ready]

定义Protocol接口层的基础类型：
- 枚举: GateVerdict, MemoryLayer
- 数据类: GateResult, SearchResult, ClusterHealth, PluginInfo

架构定位: core/shared/ Ω基点层 — 全系统依赖的公共契约
版本: 1.0.0
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

# ============================================================================
# 枚举定义
# ============================================================================


class GateVerdict(str, Enum):
    """质量门禁判决类型  [v10-ready]

    本地实现: 由 QualityGate 三问推演直接产出。
    远程实现: 由灵境门禁服务返回，序列化为字符串值跨进程传输。
    """

    PASS = "PASS"
    DOWNGRADE = "DOWNGRADE"
    REJECT = "REJECT"
    CONFLICT = "CONFLICT"
    PENDING_UPSTREAM = "PENDING_UPSTREAM"


class MemoryLayer(str, Enum):
    """ICME 六层记忆层级标识  [v10-ready]

    本地实现: 单进程内以字符串标识各层 SQLite/JSON 存储分区。
    远程实现: 灵境侧映射为分布式存储命名空间。
    """

    SENSORY = "sensory"
    WORKING = "working"
    SHORT_TERM = "short_term"
    EPISODIC = "episodic"
    SEMANTIC = "semantic"
    META = "meta"


# ============================================================================
# 辅助数据类 (接口返回值载体)
# ============================================================================


@dataclass
class GateResult:
    """质量门禁判决结果  [v10-ready]

    用于门禁域接口的统一返回载体，承载三问推演的最终判决。

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
    """搜索结果  [v10-ready]

    用于搜索域接口聚合搜索的统一返回载体。

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
    """聚阵健康状态  [v10-ready]

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


@dataclass
class PluginInfo:
    """插件元信息  [v10-ready]

    用于插件域接口描述插件身份与能力。

    Attributes:
        name: 插件唯一名称
        version: 插件版本号
        capabilities: 插件提供的能力标识列表
        enabled: 当前是否处于激活状态
    """

    name: str
    version: str
    capabilities: list[str] = field(default_factory=list)
    enabled: bool = False


__all__ = [
    "GateVerdict",
    "MemoryLayer",
    "GateResult",
    "SearchResult",
    "ClusterHealth",
    "PluginInfo",
]
