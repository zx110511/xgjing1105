# -*- coding: utf-8-sig -*-
"""天机v10.0.1 ICME记忆核心基类  [v10-ready]

MemoryCore — 六层记忆的统一抽象基类：
    - 将 ICME 六层记忆中的每一层封装为独立可运行实例
    - 统一封装存储操作 (write/read/search/delete/count)
    - 统一封装容量管理 (count/should_consolidate)
    - 抽象晋升逻辑 (promote)，由各层子类提供差异化实现

存储策略:
    - 接收可选 storage_engine (实现 IStorageEngine 协议)
    - storage_engine 为 None 时退化为进程内 dict 模拟 (Phase 4-2 注入真实后端)
    - 上层仅依赖 MemoryCore 抽象，无需感知底层存储真实落地位置

架构定位: core/memory_core/ — ICME 六层 → MemoryCore 实例化子包
版本: 1.0.0
"""
from __future__ import annotations

import time
import uuid
from abc import ABC, abstractmethod
from typing import Any

from core.shared.protocols import IStorageEngine, MemoryLayer

try:
    from core.shared.config import DEFAULT_CONFIG
except Exception:  # pragma: no cover - 配置缺失时降级为空默认
    DEFAULT_CONFIG = None


class MemoryCore(ABC):
    """ICME记忆核心基类  [v10-ready]

    每层记忆的独立运行实例。封装存储操作、容量管理、晋升逻辑。

    Attributes:
        _layer:   本核心对应的 MemoryLayer 层级。
        _storage: 可选存储引擎 (IStorageEngine)；None 时使用内存 dict 模拟。
        _config:  合并后的层级配置 (默认配置 + 调用方覆盖)。
        _stats:   运行期操作计数 (writes/reads/searches/deletes/promotions)。
    """

    def __init__(
        self,
        layer: MemoryLayer,
        storage_engine: IStorageEngine | None = None,
        config: dict | None = None,
    ) -> None:
        """初始化记忆核心  [v10-ready]

        Args:
            layer: 本核心对应的记忆层级。
            storage_engine: 可选存储引擎；为 None 时启用内存 dict 模拟。
            config: 可选层级配置覆盖，与默认配置合并。
        """
        self._layer = layer
        self._storage = storage_engine
        merged: dict[str, Any] = dict(self._default_config())
        if config:
            merged.update(config)
        self._config = merged
        self._stats: dict[str, int] = {
            "writes": 0,
            "reads": 0,
            "searches": 0,
            "deletes": 0,
            "promotions": 0,
        }
        # 内存 dict 模拟存储 (storage_engine 为 None 时启用)
        self._mem: dict[str, dict[str, Any]] = {}
        self._seq: int = 0

    # ------------------------------------------------------------------
    # 默认配置
    # ------------------------------------------------------------------
    def _default_config(self) -> dict[str, Any]:
        """读取本层默认配置  [v10-ready]

        优先从 core.config.DEFAULT_CONFIG 读取 MemoryLayerConfig 真实字段；
        配置不可用时回退到保守内置默认值。子类可覆盖以补充层特定阈值。

        Returns:
            默认配置字典 (max_entries/capacity_threshold/priority 等)。
        """
        defaults: dict[str, Any] = {
            "max_entries": 1000,
            "max_size_bytes": 50 * 1024 * 1024,
            "capacity_threshold": 0.80,
            "priority": "medium",
            "promotion_threshold": 0.5,
        }
        if DEFAULT_CONFIG is not None:
            layer_cfg = DEFAULT_CONFIG.get_layer(self._layer.value)
            if layer_cfg is not None:
                defaults.update(
                    {
                        "max_entries": layer_cfg.max_entries,
                        "max_size_bytes": layer_cfg.max_size_bytes,
                        "capacity_threshold": layer_cfg.capacity_threshold,
                        "priority": layer_cfg.priority,
                        "accumulation_threshold_entries": (
                            layer_cfg.accumulation_threshold_entries
                        ),
                        "min_consolidation_interval_seconds": (
                            layer_cfg.min_consolidation_interval_seconds
                        ),
                    }
                )
        return defaults

    # ------------------------------------------------------------------
    # 只读属性
    # ------------------------------------------------------------------
    @property
    def layer(self) -> MemoryLayer:
        """本核心对应的记忆层级  [v10-ready]"""
        return self._layer

    @property
    def layer_name(self) -> str:
        """记忆层级名称 (字符串)  [v10-ready]"""
        return self._layer.value

    @property
    def config(self) -> dict[str, Any]:
        """合并后的层级配置 (只读视图)  [v10-ready]"""
        return dict(self._config)

    # ------------------------------------------------------------------
    # 抽象操作 — 各层差异化实现
    # ------------------------------------------------------------------
    @abstractmethod
    def write(self, entry: dict) -> str:
        """写入条目，返回 entry_id  [v10-ready]"""
        ...

    @abstractmethod
    def read(self, entry_id: str) -> dict | None:
        """读取条目  [v10-ready]"""
        ...

    @abstractmethod
    def search(self, query: str, *, limit: int = 20) -> list[dict]:
        """检索条目  [v10-ready]"""
        ...

    @abstractmethod
    def promote(self) -> int:
        """检查并执行晋升到下一层，返回晋升条目数  [v10-ready]"""
        ...

    # ------------------------------------------------------------------
    # 通用操作 — 各层共享实现
    # ------------------------------------------------------------------
    def delete(self, entry_id: str) -> bool:
        """软删除条目  [v10-ready]

        Args:
            entry_id: 条目唯一标识。

        Returns:
            删除是否成功。
        """
        ok = self._remove(entry_id)
        if ok:
            self._stats["deletes"] += 1
        return ok

    def count(self) -> int:
        """当前条目数  [v10-ready]"""
        return self._count()

    def stats(self) -> dict:
        """层统计信息  [v10-ready]

        Returns:
            含层级标识、操作计数、容量占用的统计字典。
        """
        current = self._count()
        max_entries = int(self._config.get("max_entries", 0) or 0)
        usage = (current / max_entries) if max_entries > 0 else 0.0
        return {
            "layer": self._layer.value,
            "layer_index": self._layer_index(),
            "priority": self._config.get("priority"),
            "count": current,
            "max_entries": max_entries,
            "usage_ratio": round(usage, 4),
            "capacity_threshold": self._config.get("capacity_threshold"),
            "operations": dict(self._stats),
            "backend": "storage_engine" if self._storage is not None else "memory",
        }

    def should_consolidate(self) -> bool:
        """是否需要固结 (达到容量阈值)  [v10-ready]

        Returns:
            当前占用率 >= capacity_threshold 时返回 True。
        """
        max_entries = int(self._config.get("max_entries", 0) or 0)
        if max_entries <= 0:
            return False
        threshold = float(self._config.get("capacity_threshold", 0.8))
        return (self._count() / max_entries) >= threshold

    # ------------------------------------------------------------------
    # 受保护存储助手 — 屏蔽 storage_engine / 内存 dict 差异
    # ------------------------------------------------------------------
    def _gen_id(self) -> str:
        """生成层内唯一 entry_id  [v10-ready]"""
        self._seq += 1
        return f"{self._layer.value}-{int(time.time() * 1000)}-{self._seq}-{uuid.uuid4().hex[:8]}"

    def _normalize(self, entry: dict) -> dict[str, Any]:
        """补齐条目公共字段 (id/layer/timestamp)  [v10-ready]"""
        normalized = dict(entry)
        normalized.setdefault("id", self._gen_id())
        normalized["layer"] = self._layer.value
        normalized.setdefault("timestamp", time.time())
        normalized.setdefault("deleted", False)
        return normalized

    def _persist(self, entry: dict[str, Any]) -> str:
        """持久化一条记忆 (存储引擎优先, 否则内存)  [v10-ready]"""
        if self._storage is not None:
            entry_id = self._storage.insert(entry)
            entry.setdefault("id", entry_id)
            self._stats["writes"] += 1
            return entry_id
        entry_id = str(entry["id"])
        self._mem[entry_id] = entry
        self._stats["writes"] += 1
        return entry_id

    def _fetch(self, entry_id: str) -> dict[str, Any] | None:
        """读取一条记忆  [v10-ready]"""
        self._stats["reads"] += 1
        if self._storage is not None:
            return self._storage.get(entry_id)
        item = self._mem.get(entry_id)
        if item is None or item.get("deleted"):
            return None
        return item

    def _query(self, query: str, *, limit: int = 20) -> list[dict[str, Any]]:
        """检索记忆  [v10-ready]"""
        self._stats["searches"] += 1
        if self._storage is not None:
            return self._storage.search(query, limit=limit, layer=self._layer.value)
        results: list[dict[str, Any]] = []
        for item in self._mem.values():
            if item.get("deleted"):
                continue
            if not query or query in str(item.get("content", "")):
                results.append(item)
            if len(results) >= limit:
                break
        return results

    def _remove(self, entry_id: str) -> bool:
        """软删除一条记忆  [v10-ready]"""
        if self._storage is not None:
            return self._storage.delete(entry_id)
        item = self._mem.get(entry_id)
        if item is None or item.get("deleted"):
            return False
        item["deleted"] = True
        return True

    def _count(self) -> int:
        """统计本层有效条目数  [v10-ready]"""
        if self._storage is not None:
            try:
                stats = self._storage.stats()
                by_layer = stats.get("by_layer") or stats.get("layers") or {}
                if isinstance(by_layer, dict) and self._layer.value in by_layer:
                    val = by_layer[self._layer.value]
                    return int(val if not isinstance(val, dict) else val.get("count", 0))
                return int(stats.get("total", 0))
            except Exception:
                return 0
        return sum(1 for item in self._mem.values() if not item.get("deleted"))

    def _active_entries(self) -> list[dict[str, Any]]:
        """获取内存模式下的有效条目 (晋升候选筛选用)  [v10-ready]"""
        return [item for item in self._mem.values() if not item.get("deleted")]

    def _layer_index(self) -> int:
        """本层在 ICME 序列中的索引  [v10-ready]"""
        order = [
            MemoryLayer.SENSORY,
            MemoryLayer.WORKING,
            MemoryLayer.SHORT_TERM,
            MemoryLayer.EPISODIC,
            MemoryLayer.SEMANTIC,
            MemoryLayer.META,
        ]
        try:
            return order.index(self._layer)
        except ValueError:
            return -1

    def __repr__(self) -> str:  # pragma: no cover - 调试辅助
        return (
            f"<{self.__class__.__name__} layer={self._layer.value} "
            f"count={self._count()} backend="
            f"{'engine' if self._storage is not None else 'memory'}>"
        )
