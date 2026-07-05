"""
[v10-ready] JSON → SQLite 迁移管理器 — core.storage.migration

从 core/hybrid_engine.py 拆分而来 (P1-03)
  - 职责: 全量迁移 / 增量同步 / 条目格式转换
  - 源方法: ICMEStorageEngine._migrate_json_to_sqlite
            ICMEStorageEngine._sync_json_to_sqlite_incremental

行为约束: 与原 hybrid_engine 内联实现完全一致 (UTF-8-SIG 读取 / 默认值填充
          / 批量写入 / 异常静默跳过), 不改变存储 API 与迁移语义。
"""

import json
import logging
import time
from pathlib import Path
from typing import Any

logger = logging.getLogger("tianji.storage.migration")


class MigrationManager:
    """
    [v10-ready] JSON 文件存储 → SQLite 后端的迁移协调器。

    用法:
        mgr = MigrationManager(store, data_path, layer_names)
        mgr.migrate_json_to_sqlite()           # 首次全量迁移
        mgr.sync_json_to_sqlite_incremental()  # 后续增量补齐

    参数:
        store:       存储后端 (需实现 insert_batch / 暴露 _conn 供增量比对)
        data_path:   JSON 分层目录根路径
        layer_names: 需扫描的分层名称集合 (如 sensory/working/...)
    """

    def __init__(
        self,
        store: Any,
        data_path: Path | str,
        layer_names: Any,
        log: logging.Logger | None = None,
    ):
        self._store = store
        self._data_path = Path(data_path)
        self._layer_names = list(layer_names)
        self._logger = log or logger

    @staticmethod
    def convert_entry(data: dict) -> dict:
        """将 JSON 条目转换为 SQLite 写入所需的标准字典结构。

        与原 hybrid_engine 实现一致: id/content/layer 为必需字段(缺失则由
        调用方 try/except 跳过), 其余字段提供默认值。
        """
        return {
            "id": data["id"],
            "content": data["content"],
            "layer": data["layer"],
            "tags": data.get("tags", []),
            "priority": data.get("priority", "medium"),
            "value_score": data.get("value_score", 0.5),
            "access_count": data.get("access_count", 0),
            "created_at": data.get("created_at", time.time()),
            "last_accessed": data.get("last_accessed", time.time()),
            "metadata": data.get("metadata", {}),
            "related_ids": data.get("related_ids", []),
            "changelog": data.get("changelog", []),
        }

    def _iter_layer_dirs(self):
        """生成存在的分层目录路径。"""
        for layer_name in self._layer_names:
            layer_dir = self._data_path / layer_name
            if layer_dir.exists():
                yield layer_dir

    def migrate_json_to_sqlite(self) -> int:
        """全量迁移: 扫描所有分层 JSON 文件, 批量写入 SQLite。

        返回迁移成功的条目数。
        """
        entries_to_migrate: list[dict] = []
        for layer_dir in self._iter_layer_dirs():
            for entry_file in list(layer_dir.glob("*.json")):
                try:
                    data = json.loads(entry_file.read_text(encoding="utf-8-sig"))
                    entries_to_migrate.append(self.convert_entry(data))
                except Exception as e:
                    self._logger.debug(
                        f"[Migration] 迁移条目解析跳过 {entry_file.name}: {e}"
                    )

        if entries_to_migrate:
            count = self._store.insert_batch(entries_to_migrate)
            self._logger.info(f"[ICME] JSON→SQLite迁移完成: {count} 条记录")
            return count
        return 0

    def sync_json_to_sqlite_incremental(self) -> int:
        """增量同步: 仅补入 SQLite 中缺失的 JSON 条目。

        返回补入的条目数。
        """
        json_ids = set()
        for layer_dir in self._iter_layer_dirs():
            for entry_file in layer_dir.glob("*.json"):
                try:
                    data = json.loads(entry_file.read_text(encoding="utf-8-sig"))
                    json_ids.add(data.get("id", ""))
                except Exception as e:
                    self._logger.debug(
                        f"[Migration] JSON解析跳过 {entry_file.name}: {e}"
                    )

        if not json_ids:
            return 0

        sqlite_ids = set()
        try:
            conn = self._store._get_conn() if hasattr(self._store, '_get_conn') else getattr(self._store, '_conn', None)
            if conn is None:
                self._logger.warning("[Migration] SQLite连接不可用, 跳过增量同步")
                return 0
            for row in conn.execute(
                "SELECT id FROM memories"
            ).fetchall():
                sqlite_ids.add(row[0])
        except Exception as e:
            self._logger.warning(f"[Migration] SQLite查询失败, 跳过增量同步: {e}")
            return 0

        missing_ids = json_ids - sqlite_ids
        if not missing_ids:
            return 0

        entries_to_sync: list[dict] = []
        for layer_dir in self._iter_layer_dirs():
            for entry_file in layer_dir.glob("*.json"):
                try:
                    data = json.loads(entry_file.read_text(encoding="utf-8-sig"))
                    if data.get("id") in missing_ids:
                        entries_to_sync.append(self.convert_entry(data))
                except Exception as e:
                    self._logger.debug(
                        f"[Migration] 同步条目解析跳过 {entry_file.name}: {e}"
                    )

        if entries_to_sync:
            count = self._store.insert_batch(entries_to_sync)
            self._logger.info(
                f"[ICME] JSON→SQLite增量同步完成: {count} 条缺失记录已补入"
            )
            return count
        return 0
