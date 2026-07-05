# -*- coding: utf-8-sig -*-
"""L-Asset绑定层子包  [v10-ready]

统一 L-Asset 的三重绑定 (ID映射 + 层级 + 版本链) 为 AssetBindingService。

子包结构:
    binding_protocol.py  — IAssetBindingService Protocol (契约)
    binding_service.py   — AssetBindingService 本地实现 (单进程默认)
    remote_stub.py       — RemoteAssetBinding 灵境分布式 stub (预留)

三重绑定:
    绑定1: memory_id ↔ asset_id ID映射
    绑定2: asset.layer = memory.layer 层级标识
    绑定3: version + parent_version_id 版本链 DAG

架构定位: core/asset_binding/ L-Asset绑定层
版本: 1.0.0
"""
from __future__ import annotations

from core.asset_binding.binding_protocol import IAssetBindingService
from core.asset_binding.binding_service import AssetBindingService
from core.asset_binding.binding_service import PLUGIN_INFO as SERVICE_PLUGIN_INFO
from core.asset_binding.remote_stub import PLUGIN_INFO as REMOTE_PLUGIN_INFO
from core.asset_binding.remote_stub import RemoteAssetBinding

# 子包主插件元信息 (指向本地实现)  [v10-ready]
PLUGIN_INFO = SERVICE_PLUGIN_INFO

__all__ = [
    # 协议契约
    "IAssetBindingService",
    # 本地实现
    "AssetBindingService",
    # 远程实现 (stub)
    "RemoteAssetBinding",
    # 插件元信息
    "PLUGIN_INFO",
    "SERVICE_PLUGIN_INFO",
    "REMOTE_PLUGIN_INFO",
]
