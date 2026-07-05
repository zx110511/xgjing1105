# -*- coding: utf-8-sig -*-
"""天机v10.0.1 插件协议定义  [v10-ready]

定义插件的生命周期协议和元信息结构。
每个策略插件(搜索/门禁/路由/缓存/调度/LLM/适配器)都实现此协议。

架构定位: core/shared/ Ω基点 — 插件化基础设施
版本: 1.0.0
"""
from __future__ import annotations
from typing import Any
from dataclasses import dataclass, field
from enum import Enum


class PluginState(Enum):
    """插件状态  [v10-ready]"""
    DISCOVERED = "discovered"   # 已发现
    LOADED = "loaded"           # 已加载
    VALIDATED = "validated"     # 已验证
    REGISTERED = "registered"   # 已注册
    ACTIVE = "active"           # 激活中
    INACTIVE = "inactive"       # 已停用
    ERROR = "error"             # 异常


@dataclass
class PluginInfo:
    """插件元信息  [v10-ready]"""
    name: str                          # 插件名 (唯一ID)
    version: str = "1.0.0"             # 版本
    description: str = ""              # 描述
    author: str = ""                   # 作者
    category: str = "general"          # 分类 (search/gate/route/cache/scheduler/llm/adapter)
    dependencies: list[str] = field(default_factory=list)  # 依赖的其他插件
    protocols: list[str] = field(default_factory=list)     # 实现的Protocol名
    state: PluginState = PluginState.DISCOVERED


@dataclass
class PluginResult:
    """插件执行结果  [v10-ready]"""
    success: bool
    data: Any = None
    error: str | None = None
    execution_time_ms: float = 0.0
