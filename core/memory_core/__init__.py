# -*- coding: utf-8-sig -*-
"""天机v10.0.1 ICME六层 → MemoryCore 实例化子包  [v10-ready]

将 ICME 六层记忆封装为 6 个独立的 MemoryCore 运行实例：
    L0 SensoryCore    — 感知层 (即时捕获)
    L1 WorkingCore    — 工作层 (会话上下文)
    L2 ShortTermCore  — 短期层 (关键信息保持)
    L3 EpisodicCore   — 情景层 (决策记录/AI经验)
    L4 SemanticCore   — 语义层 (知识图谱/概念关系)
    L5 MetaCore       — 元层   (策略自优化, 顶层)

每个 Core 接收可选 storage_engine (IStorageEngine)：
    - 为 None 时使用进程内 dict 模拟 (Phase 4-2 完成后注入真实后端)
    - 上层仅依赖 MemoryCore 抽象，无需感知底层存储

P4-3 追加: 每层独立配置体系 (CoreConfig / CoreConfigRegistry / DEFAULT_CONFIGS)
    - 见 core/memory_core/config.py

架构定位: core/memory_core/ — Phase 4-1 六层实例化
版本: 1.0.0
"""
from __future__ import annotations

from typing import Any

from core.shared.plugin_interface import PluginInfo
from core.shared.protocols import IStorageEngine, MemoryLayer

from core.memory_core.base import MemoryCore
from core.memory_core.config import (
    CoreConfig,
    CoreConfigRegistry,
    DEFAULT_CONFIGS,
)
from core.memory_core.core_episodic import EpisodicCore
from core.memory_core.core_meta import MetaCore
from core.memory_core.core_semantic import SemanticCore
from core.memory_core.core_sensory import SensoryCore
from core.memory_core.core_short_term import ShortTermCore
from core.memory_core.core_working import WorkingCore

# 插件元信息  [v10-ready]
PLUGIN_INFO = PluginInfo(
    name="memory_core",
    version="1.0.0",
    description="ICME六层记忆核心实例化子包",
    category="memory_core",
    protocols=["IStorageEngine"],
)

# 层级名称 → Core 类的映射  [v10-ready]
_CORE_REGISTRY: dict[str, type[MemoryCore]] = {
    MemoryLayer.SENSORY.value: SensoryCore,
    MemoryLayer.WORKING.value: WorkingCore,
    MemoryLayer.SHORT_TERM.value: ShortTermCore,
    MemoryLayer.EPISODIC.value: EpisodicCore,
    MemoryLayer.SEMANTIC.value: SemanticCore,
    MemoryLayer.META.value: MetaCore,
}


def create_core(
    layer: str | MemoryLayer,
    storage_engine: IStorageEngine | None = None,
    config: dict | None = None,
) -> MemoryCore:
    """创建指定层级的 MemoryCore 实例  [v10-ready]

    Args:
        layer: 层级名称字符串或 MemoryLayer 枚举。
        storage_engine: 可选存储引擎；None 时使用内存 dict 模拟。
        config: 可选层级配置覆盖。

    Returns:
        对应层级的 MemoryCore 实例。

    Raises:
        ValueError: layer 不是合法的 ICME 六层标识。
    """
    layer_name = layer.value if isinstance(layer, MemoryLayer) else str(layer)
    core_cls = _CORE_REGISTRY.get(layer_name)
    if core_cls is None:
        raise ValueError(
            f"未知记忆层级: {layer_name!r}; 合法层级: {sorted(_CORE_REGISTRY)}"
        )
    return core_cls(storage_engine=storage_engine, config=config)


def create_all_cores(
    storage_engine: IStorageEngine | None = None,
    configs: dict[str, dict[str, Any]] | None = None,
) -> dict[str, MemoryCore]:
    """创建全部 6 层 MemoryCore 实例  [v10-ready]

    Args:
        storage_engine: 可选存储引擎；None 时各层使用内存 dict 模拟。
        configs: 可选 {层级名称: 配置覆盖字典} 映射，按层定制配置。

    Returns:
        {层级名称: MemoryCore 实例} 字典，含全部六层。
    """
    configs = configs or {}
    cores: dict[str, MemoryCore] = {}
    for layer_name, core_cls in _CORE_REGISTRY.items():
        cores[layer_name] = core_cls(
            storage_engine=storage_engine,
            config=configs.get(layer_name),
        )
    return cores


__all__ = [
    "PLUGIN_INFO",
    "MemoryCore",
    "SensoryCore",
    "WorkingCore",
    "ShortTermCore",
    "EpisodicCore",
    "SemanticCore",
    "MetaCore",
    "create_core",
    "create_all_cores",
    # P4-3 每层独立配置
    "CoreConfig",
    "CoreConfigRegistry",
    "DEFAULT_CONFIGS",
]
