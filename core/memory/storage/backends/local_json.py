# -*- coding: utf-8-sig -*-
"""[v10-ready] 本地 JSON 文件存储引擎 — core.storage.backends.local_json

文件系统 JSON 存储, 支持分层目录与原子写入。对外实现共享内核
IStorageEngine 协议 (insert/get/search/delete/stats)。

适用场景:
    - 降级模式 (SQLite 不可用时的兜底落地)
    - 轻量部署 (无需 SQLite 的最小环境)
    - 数据迁移 (与 core.storage.migration 配合的 JSON 中转)

分布式切换说明:
    单进程本地文件实现; 分布式模式由工厂替换为 RemoteStorageEngine。
"""
from __future__ import annotations

import json
import logging
import os
import time
import uuid
from pathlib import Path
from typing import Any

logger = logging.getLogger("tianji.storage.backends.local_json")


class LocalJSONEngine:
    """本地 JSON 文件存储引擎  [v10-ready]

    每条记忆以 ``<data_dir>/<layer>/<id>.json`` 落地, 写入采用临时文件 +
    原子替换, 删除采用软删除 (archived 标记)。

    Attributes:
        data_dir: JSON 存储根目录。
        layer: 默认记忆层级。
    """

    def __init__(self, data_dir: str = "data/json_store", layer: str = "") -> None:
        """初始化本地 JSON 引擎  [v10-ready]

        Args:
            data_dir: JSON 存储根目录 (不存在则自动创建)。
            layer: 默认记忆层级 (写入缺省填充, 检索缺省过滤)。
        """
        self.data_dir = Path(data_dir)
        self.layer = layer or ""
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self._index: dict[str, Path] = {}
        self._rebuild_index()

    # ------------------------------------------------------------------
    # 内部辅助
    # ------------------------------------------------------------------
    def _rebuild_index(self) -> None:
        """扫描磁盘重建 entry_id → 文件路径 索引。"""
        self._index.clear()
        for path in self.data_dir.rglob("*.json"):
            self._index[path.stem] = path

    def _layer_dir(self, layer: str) -> Path:
        """返回 (并确保存在) 指定层级目录。"""
        target = self.data_dir / (layer or self.layer or "working")
        target.mkdir(parents=True, exist_ok=True)
        return target

    @staticmethod
    def _atomic_write(path: Path, data: dict[str, Any]) -> None:
        """原子写入 JSON 文件 (临时文件 + os.replace)。"""
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8-sig"
        )
        os.replace(tmp, path)

    def _load(self, path: Path) -> dict[str, Any] | None:
        """读取并解析单个 JSON 文件, 失败返回 None。"""
        try:
            return json.loads(path.read_text(encoding="utf-8-sig"))
        except Exception as e:
            logger.debug(f"[LocalJSONEngine] 解析跳过 {path.name}: {e}")
            return None

    # ------------------------------------------------------------------
    # IStorageEngine 接口
    # ------------------------------------------------------------------
    def insert(self, entry: dict[str, Any]) -> str:
        """写入记忆条目  [v10-ready]

        Args:
            entry: 记忆条目字典。

        Returns:
            生成或沿用的 entry_id 字符串。
        """
        data = dict(entry)
        entry_id = str(data.get("id") or data.get("entry_id") or uuid.uuid4().hex)
        data["id"] = entry_id
        data.setdefault("content", "")
        layer = data.get("layer") or self.layer or "working"
        data["layer"] = layer
        data.setdefault("created_at", time.time())
        data.setdefault("last_accessed", time.time())
        data.setdefault("archived", False)

        path = self._layer_dir(layer) / f"{entry_id}.json"
        try:
            self._atomic_write(path, data)
            self._index[entry_id] = path
        except Exception as e:
            logger.error(f"[LocalJSONEngine] insert 失败: {e}", exc_info=True)
        return entry_id

    def get(self, entry_id: str) -> dict[str, Any] | None:
        """读取记忆条目  [v10-ready]

        Args:
            entry_id: 条目唯一标识。

        Returns:
            条目字典; 不存在或已软删除时返回 None。
        """
        path = self._index.get(entry_id)
        if path is None or not path.exists():
            return None
        data = self._load(path)
        if data is None or data.get("archived"):
            return None
        return data

    def search(
        self, query: str, *, limit: int = 20, **kwargs: Any
    ) -> list[dict[str, Any]]:
        """检索记忆  [v10-ready]

        Args:
            query: 查询文本 (子串匹配 content/tags)。
            limit: 返回条目上限。
            **kwargs: 扩展过滤 (layer/layers/tags 等)。

        Returns:
            命中的条目字典列表 (按 created_at 降序)。
        """
        layers = kwargs.get("layers")
        single_layer = kwargs.get("layer")
        if single_layer and not layers:
            layers = [single_layer]
        want_tags = set(kwargs.get("tags") or [])
        q = (query or "").lower()

        results: list[dict[str, Any]] = []
        for path in list(self._index.values()):
            data = self._load(path)
            if data is None or data.get("archived"):
                continue
            if layers and data.get("layer") not in layers:
                continue
            if want_tags and not want_tags.issubset(set(data.get("tags", []))):
                continue
            if q:
                hay = (
                    str(data.get("content", ""))
                    + " "
                    + " ".join(str(t) for t in data.get("tags", []))
                ).lower()
                if q not in hay:
                    continue
            results.append(data)

        results.sort(key=lambda d: d.get("created_at", 0), reverse=True)
        return results[:limit]

    def delete(self, entry_id: str) -> bool:
        """软删除记忆 (标记 archived)  [v10-ready]

        Args:
            entry_id: 条目唯一标识。

        Returns:
            删除是否成功。
        """
        path = self._index.get(entry_id)
        if path is None or not path.exists():
            return False
        data = self._load(path)
        if data is None:
            return False
        data["archived"] = True
        data["last_accessed"] = time.time()
        try:
            self._atomic_write(path, data)
            return True
        except Exception as e:
            logger.error(f"[LocalJSONEngine] delete 失败: {e}")
            return False

    def stats(self) -> dict[str, Any]:
        """获取存储统计  [v10-ready]

        Returns:
            统计信息字典 (含 backend 标识/各层分布/容量占用)。
        """
        layer_counts: dict[str, int] = {}
        total = 0
        archived = 0
        total_bytes = 0
        for path in list(self._index.values()):
            data = self._load(path)
            if data is None:
                continue
            try:
                total_bytes += path.stat().st_size
            except OSError:
                pass
            if data.get("archived"):
                archived += 1
                continue
            total += 1
            layer = data.get("layer", "")
            layer_counts[layer] = layer_counts.get(layer, 0) + 1
        return {
            "backend": "local_json",
            "data_dir": str(self.data_dir),
            "layer": self.layer,
            "total_entries": total,
            "archived_entries": archived,
            "total_size_bytes": total_bytes,
            "total_size_mb": round(total_bytes / (1024 * 1024), 4),
            "layer_counts": layer_counts,
        }


__all__ = ["LocalJSONEngine"]
