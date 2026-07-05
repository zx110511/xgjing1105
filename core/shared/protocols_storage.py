# -*- coding: utf-8-sig -*-
"""天机v10.0.1 共享内核Protocol存储域接口  [v10-ready]

定义4个存储相关Protocol接口：
- IStorageEngine: 存储引擎核心接口
- ILayerStorage: 单层存储接口
- IBatchStorage: 批量存储操作接口
- IStorageMigrator: 存储迁移接口

架构定位: core/shared/ Ω基点层 — 存储聚阵契约
"""

from __future__ import annotations

from typing import Any, Protocol, Sequence, runtime_checkable


@runtime_checkable
class IStorageEngine(Protocol):
    """存储引擎核心接口  [v10-ready]

    本地实现: SQLiteStorage (core/sqlite_store.py, 单进程默认)
    远程实现: RemoteStorage (灵境 gRPC 接入, stub 预留)

    切换方式: 由存储工厂依据运行模式返回 Local/Remote 实现，
    上层记忆引擎仅依赖本接口，无需感知数据真实落地位置。
    """

    def insert(self, entry: dict[str, Any]) -> str:
        """写入记忆条目。

        Args:
            entry: 记忆条目字典 (含 content/layer/tags 等字段)。

        Returns:
            生成的 entry_id 字符串。
        """
        ...

    def get(self, entry_id: str) -> dict[str, Any] | None:
        """读取记忆条目。

        Args:
            entry_id: 条目唯一标识。

        Returns:
            条目字典；不存在时返回 None。
        """
        ...

    def search(
        self, query: str, *, limit: int = 20, **kwargs: Any
    ) -> list[dict[str, Any]]:
        """检索记忆。

        Args:
            query: 查询文本。
            limit: 返回条目上限。
            **kwargs: 扩展过滤参数 (layer/tags 等)。

        Returns:
            命中的条目字典列表。
        """
        ...

    def delete(self, entry_id: str) -> bool:
        """软删除记忆。

        Args:
            entry_id: 条目唯一标识。

        Returns:
            删除是否成功。
        """
        ...

    def stats(self) -> dict[str, Any]:
        """获取存储统计。

        Returns:
            统计信息字典 (总量/各层分布/容量占用等)。
        """
        ...


@runtime_checkable
class ILayerStorage(Protocol):
    """单层存储接口  [v10-ready]

    本地实现: LocalLayerStorage (单进程内单层 SQLite/JSON 分区)
    远程实现: RemoteLayerStorage (灵境分布式命名空间分区)

    切换方式: 每层存储由引擎按 MemoryLayer 装配对应实现，
    分布式模式下不同层可路由至不同后端节点。
    """

    def store(self, entry: dict[str, Any]) -> str:
        """在本层存储一条记忆。

        Args:
            entry: 记忆条目字典。

        Returns:
            条目 entry_id。
        """
        ...

    def retrieve(self, entry_id: str) -> dict[str, Any] | None:
        """从本层读取一条记忆。

        Args:
            entry_id: 条目唯一标识。

        Returns:
            条目字典；不存在时返回 None。
        """
        ...

    def count(self) -> int:
        """统计本层条目数量。

        Returns:
            当前层条目总数。
        """
        ...

    def clear(self) -> int:
        """清空本层全部条目。

        Returns:
            被清除的条目数量。
        """
        ...


@runtime_checkable
class IBatchStorage(Protocol):
    """批量存储操作接口  [v10-ready]

    本地实现: LocalBatchStorage (单进程事务批处理)
    远程实现: RemoteBatchStorage (灵境批量 RPC, 管道化提交)

    切换方式: 批量操作在分布式模式下聚合为单次网络往返，
    本地模式下退化为单事务循环，调用方无感知。
    """

    def batch_insert(self, entries: list[dict[str, Any]]) -> list[str]:
        """批量写入记忆条目。

        Args:
            entries: 记忆条目字典列表。

        Returns:
            按输入顺序返回的 entry_id 列表。
        """
        ...

    def batch_delete(self, entry_ids: Sequence[str]) -> int:
        """批量删除记忆条目。

        Args:
            entry_ids: 待删除的条目标识序列。

        Returns:
            成功删除的条目数量。
        """
        ...

    def batch_update(self, updates: dict[str, dict[str, Any]]) -> int:
        """批量更新记忆条目。

        Args:
            updates: entry_id -> 字段更新字典 的映射。

        Returns:
            成功更新的条目数量。
        """
        ...


@runtime_checkable
class IStorageMigrator(Protocol):
    """存储迁移接口  [v10-ready]

    本地实现: LocalStorageMigrator (单进程 schema/数据迁移)
    远程实现: RemoteStorageMigrator (灵境跨节点数据搬迁与一致性校验)

    切换方式: v9.1 单进程升级或 v10.0 由单机迁移至分布式时，
    统一通过本接口执行 migrate/rollback/verify 三段式安全迁移。
    """

    def migrate(self, target_version: str, *, dry_run: bool = False) -> dict[str, Any]:
        """执行迁移到目标版本。

        Args:
            target_version: 目标 schema/数据版本号。
            dry_run: 为 True 时仅预演不落盘。

        Returns:
            迁移结果报告字典。
        """
        ...

    def rollback(self, checkpoint: str) -> bool:
        """回滚到指定检查点。

        Args:
            checkpoint: 迁移前生成的检查点标识。

        Returns:
            回滚是否成功。
        """
        ...

    def verify(self, target_version: str) -> bool:
        """校验迁移结果一致性。

        Args:
            target_version: 期望达到的版本号。

        Returns:
            数据一致性校验是否通过。
        """
        ...


__all__ = [
    "IStorageEngine",
    "ILayerStorage",
    "IBatchStorage",
    "IStorageMigrator",
]
