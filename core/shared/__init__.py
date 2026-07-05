# -*- coding: utf-8-sig -*-
"""天机v10.0.1 共享内核层 (core/shared/)  [v10-ready]

Ω基点层 — 全系统依赖的公共契约定义所在。
本包仅承载零依赖的接口契约与共享数据结构，不引入任何业务实现，
确保上层模块可在不形成循环依赖的前提下面向接口编程。
"""
from __future__ import annotations

__all__ = [
    "protocols",
    # 异常
    "TianjiError", "StorageError", "GateError", "RouteError", "SearchError", "PluginError",
    # 类型
    "EntryId", "AssetId", "LayerName", "Metadata", "Tags",
    # 常量
    "ALL_LAYERS", "TIANJI_VERSION", "DEFAULT_PORT",
    # 工具
    "generate_entry_id", "generate_asset_id", "content_hash", "timestamp_ms",
    # 防腐层(ACL)
    "AnticorruptionLayer", "PassthroughAdapter", "LoggingAdapter",
    "DomainAdapter", "CrossDomainCall",
]

# === 基础设施Ω基点导出 ===  [v10-ready]
from core.shared.exceptions import TianjiError, StorageError, GateError, RouteError, SearchError, PluginError
from core.shared.types import EntryId, AssetId, LayerName, Metadata, Tags
from core.shared.constants import ALL_LAYERS, TIANJI_VERSION, DEFAULT_PORT
from core.shared.utils import generate_entry_id, generate_asset_id, content_hash, timestamp_ms

# === 防腐层(ACL)基础设施导出 ===  [v10-ready]
from core.shared.anticorruption import (
    AnticorruptionLayer,
    PassthroughAdapter,
    LoggingAdapter,
    DomainAdapter,
    CrossDomainCall,
)
