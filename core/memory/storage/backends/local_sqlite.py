# -*- coding: utf-8-sig -*-
"""[v10-ready] 本地 SQLite 存储引擎 — core.storage.backends.local_sqlite

基于 SQLite FTS5 + WAL 模式, 封装 core.sqlite_store.SQLiteMemoryStore 的能力,
对外实现共享内核 IStorageEngine 协议 (insert/get/search/delete/stats)。

分布式切换说明:
    单进程默认实现, 进程内直接读写本地 SQLite 文件。
    分布式模式由 StorageEngineFactory 替换为 RemoteStorageEngine。

委托策略:
    优先委托给 SQLiteMemoryStore (FTS5 全文 + 标签索引 + 连接池)。
    当其不可用时 (导入失败), 回退到进程内字典存储, 保证接口可用与
    isinstance(engine, IStorageEngine) 始终成立。
"""
from __future__ import annotations

import logging
import time
import uuid
from pathlib import Path
from typing import Any

logger = logging.getLogger("tianji.storage.backends.local_sqlite")

try:  # 委托目标 (如可用)
    from core.memory.sqlite_store import SQLiteMemoryStore
except Exception:  # pragma: no cover - 回退路径
    try:
        from ...sqlite_store import SQLiteMemoryStore  # type: ignore
    except Exception:
        SQLiteMemoryStore = None  # type: ignore


class LocalSQLiteEngine:
    """本地 SQLite 存储引擎  [v10-ready]

    委托给 SQLiteMemoryStore (如可用) 或回退至独立的进程内实现。
    实现 IStorageEngine 接口。

    Attributes:
        db_path: SQLite 数据库文件路径。
        layer: 默认记忆层级 (写入/检索缺省过滤)。
    """

    def __init__(self, db_path: str = "data/.memory/icme.db", layer: str = "") -> None:
        """初始化本地 SQLite 引擎  [v10-ready]

        Args:
            db_path: SQLite 数据库文件路径。
            layer: 默认记忆层级 (写入时缺省填充, 检索时缺省过滤)。
        """
        self.db_path = str(db_path)
        self.layer = layer or ""
        self._store: Any | None = None
        self._fallback: dict[str, dict] | None = None

        if SQLiteMemoryStore is not None:
            try:
                self._store = SQLiteMemoryStore(Path(self.db_path))
            except Exception as e:  # pragma: no cover - 初始化异常回退
                logger.warning(
                    f"[LocalSQLiteEngine] SQLiteMemoryStore 初始化失败, 回退字典存储: {e}"
                )
                self._store = None

        if self._store is None:
            self._fallback = {}

    # ------------------------------------------------------------------
    # IStorageEngine 接口
    # ------------------------------------------------------------------
    def insert(self, entry: dict[str, Any]) -> str:
        """写入记忆条目  [v10-ready]

        Args:
            entry: 记忆条目字典 (含 content/layer/tags 等字段)。

        Returns:
            生成或沿用的 entry_id 字符串。
        """
        data = dict(entry)
        entry_id = str(data.get("id") or data.get("entry_id") or uuid.uuid4().hex)
        data["id"] = entry_id
        data.setdefault("content", "")
        if not data.get("layer"):
            data["layer"] = self.layer or "working"
        data.setdefault("created_at", time.time())
        data.setdefault("last_accessed", time.time())

        if self._store is not None:
            try:
                self._store.insert(data)
            except Exception as e:
                logger.error(f"[LocalSQLiteEngine] insert 失败: {e}", exc_info=True)
            return entry_id

        # 回退实现
        assert self._fallback is not None
        self._fallback[entry_id] = data
        return entry_id

    def get(self, entry_id: str) -> dict[str, Any] | None:
        """读取记忆条目  [v10-ready]

        Args:
            entry_id: 条目唯一标识。

        Returns:
            条目字典; 不存在时返回 None。
        """
        if self._store is not None:
            try:
                return self._store.get(entry_id)
            except Exception as e:
                logger.error(f"[LocalSQLiteEngine] get 失败: {e}")
                return None

        assert self._fallback is not None
        item = self._fallback.get(entry_id)
        if item and not item.get("archived"):
            return dict(item)
        return None

    def search(
        self, query: str, *, limit: int = 20, **kwargs: Any
    ) -> list[dict[str, Any]]:
        """检索记忆  [v10-ready]

        Args:
            query: 查询文本。
            limit: 返回条目上限。
            **kwargs: 扩展过滤 (layer/layers/tags 等)。

        Returns:
            命中的条目字典列表。
        """
        layers = kwargs.get("layers")
        single_layer = kwargs.get("layer")
        if single_layer and not layers:
            layers = [single_layer]
        tags = kwargs.get("tags")

        if self._store is not None:
            try:
                return self._store.search(
                    query=query or "",
                    layers=layers,
                    tags=tags,
                    limit=limit,
                )
            except Exception as e:
                logger.error(f"[LocalSQLiteEngine] search 失败: {e}")
                return []

        # 回退实现: 简易子串匹配
        assert self._fallback is not None
        q = (query or "").lower()
        results: list[dict[str, Any]] = []
        for item in self._fallback.values():
            if item.get("archived"):
                continue
            if layers and item.get("layer") not in layers:
                continue
            if q and q not in str(item.get("content", "")).lower():
                continue
            results.append(dict(item))
            if len(results) >= limit:
                break
        return results

    def delete(self, entry_id: str) -> bool:
        """软删除记忆  [v10-ready]

        Args:
            entry_id: 条目唯一标识。

        Returns:
            删除是否成功。
        """
        if self._store is not None:
            try:
                return bool(self._store.delete(entry_id))
            except Exception as e:
                logger.error(f"[LocalSQLiteEngine] delete 失败: {e}")
                return False

        assert self._fallback is not None
        item = self._fallback.get(entry_id)
        if item is None:
            return False
        item["archived"] = True
        return True

    def stats(self) -> dict[str, Any]:
        """获取存储统计  [v10-ready]

        Returns:
            统计信息字典 (含 backend 标识/总量/各层分布等)。
        """
        info: dict[str, Any] = {
            "backend": "local_sqlite",
            "db_path": self.db_path,
            "layer": self.layer,
            "delegated": self._store is not None,
        }
        if self._store is not None:
            try:
                info.update(self._store.get_total_stats())
            except Exception as e:
                logger.debug(f"[LocalSQLiteEngine] stats 获取失败: {e}")
            try:
                info["layer_stats"] = self._store.get_layer_stats()
            except Exception:
                pass
        else:
            assert self._fallback is not None
            active = [e for e in self._fallback.values() if not e.get("archived")]
            info["total_entries"] = len(active)
            info["archived_entries"] = len(self._fallback) - len(active)
        return info

    def close(self) -> None:
        """关闭引擎, 释放底层连接  [v10-ready]"""
        if self._store is not None:
            try:
                self._store.close()
            except Exception:
                pass


__all__ = ["LocalSQLiteEngine"]
