# -*- coding: utf-8-sig -*-
"""[v10-ready] 分层混合存储引擎 — core.storage.backends.tiered_engine

支持每层使用不同后端 (如 L0-L2 用 JSON, L3-L5 用 SQLite), 根据条目的
``layer`` 字段路由到对应 per-layer backend。对外实现共享内核
IStorageEngine 协议 (insert/get/search/delete/stats)。

与 core.storage.tiered.TieredStorageEngine 的区别:
    - core.storage.tiered : 热/冷 tier 分类 + 晋升降级策略 (不直接落地)
    - 本模块             : 按记忆 layer 路由到具体 IStorageEngine 后端落地

分布式切换说明:
    各层后端可独立替换为 RemoteStorageEngine, 实现"部分层远程"混合拓扑。
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # 仅类型检查期引用, 避免运行时循环依赖
    from core.shared.protocols import IStorageEngine

logger = logging.getLogger("tianji.storage.backends.tiered_engine")


class TieredStorageEngine:
    """分层混合存储引擎  [v10-ready]

    将每个记忆层级 (sensory/working/short_term/episodic/semantic/meta) 映射到
    一个独立的 IStorageEngine 后端, 写入/读取按 ``entry['layer']`` 路由。

    Attributes:
        layer_backends: 层级 → 后端实例 的注册表。
    """

    def __init__(
        self, layer_backends: "dict[str, IStorageEngine] | None" = None
    ) -> None:
        """初始化分层混合引擎  [v10-ready]

        Args:
            layer_backends: 预置的 层级→后端 映射; 为 None 时为空, 可后续注册。
        """
        self.layer_backends: dict[str, Any] = dict(layer_backends or {})
        self._default: Any | None = None

    # ------------------------------------------------------------------
    # 后端注册 / 路由
    # ------------------------------------------------------------------
    def register_layer_backend(self, layer: str, backend: "IStorageEngine") -> None:
        """注册某层级的存储后端  [v10-ready]

        Args:
            layer: 记忆层级标识。
            backend: 实现 IStorageEngine 的后端实例。
        """
        self.layer_backends[layer] = backend

    def _get_default(self) -> Any:
        """获取默认后端 (无匹配层级时使用)。

        优先复用任一已注册后端; 全空时惰性创建 LocalSQLiteEngine。
        """
        if self.layer_backends:
            return next(iter(self.layer_backends.values()))
        if self._default is None:
            from .local_sqlite import LocalSQLiteEngine

            self._default = LocalSQLiteEngine()
        return self._default

    def _route(self, layer: str | None) -> Any:
        """根据层级选择后端。

        Args:
            layer: 记忆层级标识。

        Returns:
            匹配的后端实例; 无匹配时返回默认后端。
        """
        if layer and layer in self.layer_backends:
            return self.layer_backends[layer]
        return self._get_default()

    def _all_backends(self) -> list[Any]:
        """返回去重后的全部后端 (含默认)。"""
        seen: list[Any] = []
        for backend in self.layer_backends.values():
            if backend not in seen:
                seen.append(backend)
        if self._default is not None and self._default not in seen:
            seen.append(self._default)
        return seen

    # ------------------------------------------------------------------
    # IStorageEngine 接口
    # ------------------------------------------------------------------
    def insert(self, entry: dict[str, Any]) -> str:
        """按层级路由写入记忆条目  [v10-ready]

        Args:
            entry: 记忆条目字典 (依据 ``layer`` 字段路由)。

        Returns:
            生成或沿用的 entry_id 字符串。
        """
        backend = self._route(entry.get("layer"))
        return backend.insert(entry)

    def get(self, entry_id: str) -> dict[str, Any] | None:
        """跨后端读取记忆条目  [v10-ready]

        Args:
            entry_id: 条目唯一标识。

        Returns:
            首个命中的条目字典; 全部未命中返回 None。
        """
        for backend in self._all_backends():
            try:
                found = backend.get(entry_id)
            except Exception as e:
                logger.debug(f"[TieredStorageEngine] get 子后端异常: {e}")
                continue
            if found is not None:
                return found
        return None

    def search(
        self, query: str, *, limit: int = 20, **kwargs: Any
    ) -> list[dict[str, Any]]:
        """检索记忆  [v10-ready]

        指定 ``layer`` 时仅查询对应后端; 否则聚合全部后端结果并截断。

        Args:
            query: 查询文本。
            limit: 返回条目上限。
            **kwargs: 扩展过滤 (layer/layers/tags 等)。

        Returns:
            命中的条目字典列表 (按 created_at 降序, 去重)。
        """
        layer = kwargs.get("layer")
        if layer and layer in self.layer_backends:
            return self.layer_backends[layer].search(query, limit=limit, **kwargs)

        aggregated: list[dict[str, Any]] = []
        seen_ids: set[str] = set()
        for backend in self._all_backends():
            try:
                rows = backend.search(query, limit=limit, **kwargs)
            except Exception as e:
                logger.debug(f"[TieredStorageEngine] search 子后端异常: {e}")
                continue
            for row in rows:
                rid = str(row.get("id", ""))
                if rid and rid in seen_ids:
                    continue
                if rid:
                    seen_ids.add(rid)
                aggregated.append(row)

        aggregated.sort(key=lambda d: d.get("created_at", 0), reverse=True)
        return aggregated[:limit]

    def delete(self, entry_id: str) -> bool:
        """跨后端软删除记忆  [v10-ready]

        Args:
            entry_id: 条目唯一标识。

        Returns:
            任一后端删除成功即返回 True。
        """
        ok = False
        for backend in self._all_backends():
            try:
                if backend.delete(entry_id):
                    ok = True
            except Exception as e:
                logger.debug(f"[TieredStorageEngine] delete 子后端异常: {e}")
        return ok

    def stats(self) -> dict[str, Any]:
        """聚合各层后端统计  [v10-ready]

        Returns:
            统计信息字典 (含 backend 标识与各层子统计)。
        """
        per_layer: dict[str, Any] = {}
        total = 0
        for layer, backend in self.layer_backends.items():
            try:
                sub = backend.stats()
            except Exception as e:
                sub = {"error": str(e)}
            per_layer[layer] = sub
            try:
                total += int(sub.get("total_entries", 0) or 0)
            except (TypeError, ValueError):
                pass
        return {
            "backend": "tiered",
            "registered_layers": list(self.layer_backends.keys()),
            "total_entries": total,
            "layers": per_layer,
        }


__all__ = ["TieredStorageEngine"]
