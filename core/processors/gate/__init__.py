# -*- coding: utf-8-sig -*-
"""天机v10.0.1 门禁策略子包 core.gate  [v10-ready]

将原 core/quality_gate.py (936行) 的门禁逻辑插件化拆分为:
    - NoiseFilter        : Q3 反向过滤 (冗余/矛盾/过期/噪声)
    - PolicyEngine       : Q1/Q2 评分 + 7因子 + 阈值管理 (IGatePolicy)
    - LocalGateStrategy  : 三问推演本地策略 (IGateStrategy)
    - RemoteGateStrategy : 灵境分布式远程策略 (gRPC stub)

所有判决载体 (GateResult/GateVerdict) 统一来自 core.shared.protocols。
v9.1 单进程默认装配 LocalGateStrategy；v10.0 分布式可平滑切换 Remote。

架构定位: core/gate/ 门禁策略子包入口
版本: 1.0.0
"""

from __future__ import annotations

try:
    from ..shared.plugin_interface import PluginInfo
except ImportError:  # pragma: no cover - 兼容直接执行
    from core.shared.plugin_interface import PluginInfo  # type: ignore

from .local_gate_strategy import LocalGateStrategy
from .noise_filter import (
    NoiseFilter,
    char_ngrams,
    has_semantic_overlap,
    longest_common_substring,
)
from .policy_engine import PolicyEngine
from .remote_stub import RemoteGateStrategy

#: 插件管理器注册元信息 (PluginManager 通过 category="gate" 发现)
PLUGIN_INFO = PluginInfo(
    name="local_gate",
    version="1.0.0",
    description="本地三问推演门禁策略",
    category="gate",
    protocols=["IGateStrategy"],
)

__all__ = [
    "NoiseFilter",
    "PolicyEngine",
    "LocalGateStrategy",
    "RemoteGateStrategy",
    "char_ngrams",
    "has_semantic_overlap",
    "longest_common_substring",
    "PLUGIN_INFO",
]
