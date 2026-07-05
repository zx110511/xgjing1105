# -*- coding: utf-8-sig -*-
"""[v10-ready] 存储引擎工厂 — core.storage.backends.factory

按名称创建 IStorageEngine 后端、支持自定义引擎注册与引擎热切换, 并提供
按记忆层级选择默认后端的便捷方法。

内置后端 (默认注册):
    sqlite  → LocalSQLiteEngine
    json    → LocalJSONEngine
    tiered  → TieredStorageEngine
    remote  → RemoteStorageEngine

分布式切换说明:
    上层仅依赖工厂返回的 IStorageEngine; 单进程返回 Local*, 分布式返回
    Remote*, 切换对调用方透明。
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from .local_json import LocalJSONEngine
from .local_sqlite import LocalSQLiteEngine
from .remote_stub import RemoteStorageEngine
from .tiered_engine import TieredStorageEngine

if TYPE_CHECKING:  # 仅类型检查期引用, 避免运行时循环依赖
    from core.shared.protocols import IStorageEngine

logger = logging.getLogger("tianji.storage.backends.factory")


# 记忆层级 → 默认后端名称 (L0-L2 用 JSON 轻量, L3-L5 用 SQLite 检索)
_LAYER_BACKEND_MAP: dict[str, str] = {
    "sensory": "json",
    "working": "json",
    "short_term": "json",
    "episodic": "sqlite",
    "semantic": "sqlite",
    "meta": "sqlite",
}


class StorageEngineFactory:
    """存储引擎工厂  [v10-ready]

    支持:
        - 按名称创建引擎 ('sqlite'/'json'/'tiered'/'remote')
        - 自定义引擎注册 (register)
        - 引擎热切换 (create 返回新实例, 旧实例由调用方管理)
        - 按记忆层级创建默认后端 (create_for_layer)
    """

    _registry: dict[str, type] = {}

    # ------------------------------------------------------------------
    # 注册 / 查询
    # ------------------------------------------------------------------
    @classmethod
    def register(cls, name: str, engine_cls: type) -> None:
        """注册 (或覆盖) 一个命名后端  [v10-ready]

        Args:
            name: 后端名称 (大小写不敏感)。
            engine_cls: 实现 IStorageEngine 的引擎类。
        """
        key = (name or "").strip().lower()
        if not key:
            raise ValueError("StorageEngineFactory.register: name 不能为空")
        cls._registry[key] = engine_cls
        logger.debug(f"[StorageEngineFactory] 已注册后端: {key} → {engine_cls.__name__}")

    @classmethod
    def available_backends(cls) -> list[str]:
        """列出已注册后端名称  [v10-ready]

        Returns:
            已注册后端名称的有序列表。
        """
        return sorted(cls._registry.keys())

    # ------------------------------------------------------------------
    # 创建
    # ------------------------------------------------------------------
    @classmethod
    def create(cls, name: str, **kwargs: Any) -> "IStorageEngine":
        """按名称创建引擎实例  [v10-ready]

        每次调用返回新实例, 可用于引擎热切换 (旧实例由调用方负责关闭)。

        Args:
            name: 后端名称 ('sqlite'/'json'/'tiered'/'remote' 或自定义)。
            **kwargs: 透传给引擎构造函数的参数。

        Returns:
            新建的引擎实例 (满足 IStorageEngine)。

        Raises:
            ValueError: 名称未注册时。
        """
        key = (name or "").strip().lower()
        engine_cls = cls._registry.get(key)
        if engine_cls is None:
            raise ValueError(
                f"未知存储后端: '{name}'; 可用: {cls.available_backends()}"
            )
        return engine_cls(**kwargs)

    @classmethod
    def create_for_layer(
        cls, layer: str, config: dict[str, Any] | None = None
    ) -> "IStorageEngine":
        """按记忆层级创建默认后端  [v10-ready]

        依据层级映射选择后端 (L0-L2→json, L3-L5→sqlite), 可经 config 覆盖。

        Args:
            layer: 记忆层级标识。
            config: 可选配置; 支持 ``backend`` 覆盖后端名, 其余键透传构造函数。

        Returns:
            为该层创建的引擎实例。
        """
        cfg = dict(config or {})
        backend_name = cfg.pop("backend", None) or _LAYER_BACKEND_MAP.get(
            layer, "sqlite"
        )
        cfg.setdefault("layer", layer)
        return cls.create(backend_name, **cfg)


# ============================================================================
# 默认注册 4 个内置后端
# ============================================================================
StorageEngineFactory.register("sqlite", LocalSQLiteEngine)
StorageEngineFactory.register("json", LocalJSONEngine)
StorageEngineFactory.register("tiered", TieredStorageEngine)
StorageEngineFactory.register("remote", RemoteStorageEngine)


__all__ = ["StorageEngineFactory"]
