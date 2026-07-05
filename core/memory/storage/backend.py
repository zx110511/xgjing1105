"""
[v10-ready] 存储后端抽象接口 — core.storage.backend

从 core/hybrid_engine.py 拆分而来 (P1-03)
  - 职责: 定义存储后端契约 (StorageBackend 抽象基类)
  - 现有实现: core.sqlite_store.SQLiteMemoryStore (SQLite + FTS5 + WAL + 连接池)
  - 该抽象用于解耦上层引擎与具体存储实现, 便于 v10 多后端扩展

注意: SQLiteMemoryStore 通过鸭子类型(duck typing)满足本契约, 无需显式继承,
      故引入本抽象不改变现有运行时行为与存储 API。
"""

from abc import ABC, abstractmethod
from typing import Any


class StorageBackend(ABC):
    """
    [v10-ready] 记忆存储后端抽象契约。

    定义所有存储后端必须实现的最小公共接口, 与 SQLiteMemoryStore 的公开
    API 对齐 (insert / search / get / update / delete / 统计 / 维护)。
    """

    @abstractmethod
    def insert(self, entry: dict) -> bool:
        """写入单条记忆, 返回是否成功。"""
        raise NotImplementedError

    @abstractmethod
    def insert_batch(self, entries: list[dict]) -> int:
        """批量写入记忆, 返回成功写入条数。"""
        raise NotImplementedError

    @abstractmethod
    def get(self, entry_id: str) -> dict | None:
        """按 ID 读取单条记忆, 不存在返回 None。"""
        raise NotImplementedError

    @abstractmethod
    def search(
        self,
        query: str | None = None,
        layers: list[str] | None = None,
        tags: list[str] | None = None,
        priority: list[str] | None = None,
        limit: int = 20,
        offset: int = 0,
        min_score: float = 0.0,
        use_fts: bool = True,
        include_archived: bool = False,
    ) -> list[dict]:
        """多条件检索, 支持 FTS5 全文 + 分层/标签/优先级过滤。"""
        raise NotImplementedError

    @abstractmethod
    def update(self, entry_id: str, updates: dict) -> bool:
        """更新单条记忆字段, 返回是否成功。"""
        raise NotImplementedError

    @abstractmethod
    def delete(self, entry_id: str) -> bool:
        """删除单条记忆, 返回是否成功。"""
        raise NotImplementedError

    @abstractmethod
    def get_layer_stats(self) -> dict[str, dict]:
        """返回各分层的统计信息 (条数/字节/均分等)。"""
        raise NotImplementedError

    @abstractmethod
    def get_total_stats(self) -> dict:
        """返回全局统计信息 (总条数/归档数/库大小等)。"""
        raise NotImplementedError

    @abstractmethod
    def vacuum(self) -> Any:
        """执行数据库压缩/碎片整理。"""
        raise NotImplementedError

    @abstractmethod
    def get_storage_stats(self) -> Any:
        """返回存储引擎运行时统计。"""
        raise NotImplementedError

    @abstractmethod
    def close(self) -> None:
        """关闭后端, 释放连接/资源。"""
        raise NotImplementedError
