# -*- coding: utf-8-sig -*-
"""[v10-ready] core.storage.backends — 存储后端策略化子包 (P4-2)

提供 4 个实现 IStorageEngine 协议的存储后端及统一工厂:

后端实现:
    - LocalSQLiteEngine    : 本地 SQLite (FTS5+WAL), 委托 SQLiteMemoryStore
    - LocalJSONEngine      : 本地 JSON 文件 (分层目录 + 原子写入)
    - TieredStorageEngine  : 分层混合 (按 layer 路由到 per-layer 后端)
    - RemoteStorageEngine  : 远程存储 Stub (灵境分布式预留, 带降级逻辑)

工厂:
    - StorageEngineFactory : 按名称创建 / 自定义注册 / 热切换 / 按层创建

设计原则:
    所有引擎均通过鸭子类型满足 @runtime_checkable 的 IStorageEngine,
    故 isinstance(engine, IStorageEngine) 对全部 4 个引擎为 True。
"""
from __future__ import annotations

from .factory import StorageEngineFactory
from .local_json import LocalJSONEngine
from .local_sqlite import LocalSQLiteEngine
from .remote_stub import RemoteStorageEngine
from .tiered_engine import TieredStorageEngine

# 插件元信息 (供插件域 / 治理流水线发现)
PLUGIN_INFO: dict = {
    "name": "storage_backends",
    "version": "1.0.0",
    "category": "storage_backend",
    "description": "存储后端策略化: 4 实现 (sqlite/json/tiered/remote) + 工厂",
    "protocol": "core.shared.protocols.IStorageEngine",
    "engines": [
        "LocalSQLiteEngine",
        "LocalJSONEngine",
        "TieredStorageEngine",
        "RemoteStorageEngine",
    ],
    "factory": "StorageEngineFactory",
    "backends": ["sqlite", "json", "tiered", "remote"],
    "v10_ready": True,
}

__all__ = [
    "LocalSQLiteEngine",
    "LocalJSONEngine",
    "TieredStorageEngine",
    "RemoteStorageEngine",
    "StorageEngineFactory",
    "PLUGIN_INFO",
]
