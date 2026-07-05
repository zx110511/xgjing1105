# -*- coding: utf-8-sig -*-
"""记忆域事件接线 — 为MemoryWriter/PromotionEngine/ArchiveManager/MemoryIndex添加事件发布  [v10-ready]

功能核心：主动 + 自动化
- 所有记忆写入、晋升、归档、检索操作自动发布事件
- 事件流供DeepSeek决策循环和evolution_loop消费
- 接线失败静默降级，不中断服务

设计原则:
- **主动**: 接线后的组件能主动发布事件，驱动下游自动响应
- **自进化**: 事件流可供evolution_loop消费，形成学习闭环
- **自动化**: 接线完成后自动生效，无需手动注册每个事件
- **DeepSeek核心**: 事件数据可供DeepSeek分析决策

事件类型:
- memory.written      — 记忆写入成功
- memory.promoted     — 记忆晋升到更高层
- memory.archived     — 记忆归档/驱逐
- memory.recalled     — 记忆被检索命中
- memory.invalidated  — 记忆被失效（CascadeInvalidator）
- memory.consolidated — 记忆被固结（DualProcessConsolidator）

实现要点:
- 非侵入式: 不修改 MemoryWriter/PromotionEngine/ArchiveManager/MemoryIndex 原实现
- 装饰器模式: functools.wraps 包装原方法，保持接口不变(非全局 monkey-patch)
- 降级友好: event_bus=None 时各组件均不接线(返回 False)
- 异常静默: 所有事件发布异常静默捕获，不影响原操作
- 复用基础设施: 沿用 engine_wiring 的 safe_publish / pick_arg / MethodWiringMixin

架构定位: core/event_wiring/ — 领域事件接线层(v10事件驱动过渡)
版本: 1.0.0
[v10-ready]
"""
from __future__ import annotations

import time
import logging
from typing import Any, Callable

from core.event_wiring.engine_wiring import (
    MethodWiringMixin,
    safe_publish,
    pick_arg,
)

logger = logging.getLogger("tianji.event_wiring.memory")

# 本接线器所属源域标识(用于事件 source)
_DOMAIN = "memory"

# 记忆域事件类型常量  [v10-ready]
EVENT_WRITTEN = "memory.written"
EVENT_PROMOTED = "memory.promoted"
EVENT_ARCHIVED = "memory.archived"
EVENT_RECALLED = "memory.recalled"
EVENT_INVALIDATED = "memory.invalidated"
EVENT_CONSOLIDATED = "memory.consolidated"

# 内容预览截断长度
_PREVIEW_LIMIT = 200


def _summarize_result(result: Any) -> Any:
    """将原方法返回值压缩为可序列化的事件摘要  [v10-ready]

    Args:
        result: 原方法返回值(dict/list/标量/对象)。

    Returns:
        适合放入事件 payload 的轻量摘要。
    """
    if isinstance(result, dict):
        keys = ("id", "status", "actual_layer", "promoted_count", "evicted")
        summary = {k: result[k] for k in keys if k in result}
        return summary or {"type": "dict", "size": len(result)}
    if isinstance(result, (list, tuple)):
        return {"type": "list", "count": len(result)}
    if isinstance(result, (str, int, float, bool)) or result is None:
        return result
    return {"type": type(result).__name__}


def _build_payload(
    event_type: str,
    layer: Any,
    content_preview: Any,
    result: Any,
    duration_ms: float,
) -> dict[str, Any]:
    """构建标准记忆域事件载荷  [v10-ready]

    Args:
        event_type: 事件类型标识。
        layer: 涉及的记忆层(可为复合字符串)。
        content_preview: 内容预览(自动截断)。
        result: 原方法返回值(自动摘要)。
        duration_ms: 原方法执行耗时(毫秒)。

    Returns:
        事件载荷 dict。
    """
    return {
        "event_type": event_type,
        "timestamp": time.time(),
        "layer": str(layer) if layer is not None else "",
        "content_preview": str(content_preview)[:_PREVIEW_LIMIT],
        "result": _summarize_result(result),
        "duration_ms": duration_ms,
    }


class MemoryEventWiring(MethodWiringMixin):
    """记忆域事件接线器  [v10-ready]

    为四个记忆协调组件的关键方法包装事件发布。
    采用装饰器模式(非全局 monkey-patch)，保持原组件接口不变。

    组件 → 事件映射:
        writer.remember      → memory.written
        promoter.consolidate → memory.promoted
        archiver.forget      → memory.archived
        indexer.recall       → memory.recalled

    Usage:
        wiring = MemoryEventWiring(bus, writer=w, promoter=p)
        status = wiring.wire()   # {"writer": True, "promoter": True, ...}
        wiring.unwire()          # 还原全部包装

    降级: event_bus=None 时不包装任何方法，wire() 各项返回 False。
    """

    def __init__(
        self,
        event_bus: Any,
        writer: Any = None,
        promoter: Any = None,
        archiver: Any = None,
        indexer: Any = None,
        acl: Any = None,
    ) -> None:
        """初始化记忆域接线器  [v10-ready]

        Args:
            event_bus: IEventBus 实例(实现 publish/subscribe)；None 则透传。
            writer: MemoryWriter 实例(可选)。
            promoter: PromotionEngine 实例(可选)。
            archiver: ArchiveManager 实例(可选)。
            indexer: MemoryIndex 实例(可选)。
            acl: 可选 AnticorruptionLayer(预留)。
        """
        self.event_bus = event_bus
        self.writer = writer
        self.promoter = promoter
        self.archiver = archiver
        self.indexer = indexer
        self.acl = acl
        # MethodWiringMixin 复用 _bus 字段执行 unwire 退订
        self._bus = event_bus
        self._init_wiring_state()
        self._wired: dict[str, bool] = {}

    # ------------------------------------------------------------------
    # 包装基础设施
    # ------------------------------------------------------------------
    def _wrap_publish(
        self,
        obj: Any,
        method_name: str,
        event_type: str,
        layer_picker: Callable[[tuple, dict, Any], Any],
        content_picker: Callable[[tuple, dict, Any], Any],
    ) -> bool:
        """包装实例方法，在原方法返回后发布记忆域事件  [v10-ready]

        Args:
            obj: 目标组件实例。
            method_name: 待包装方法名(不存在则跳过)。
            event_type: 发布的事件类型。
            layer_picker: 从 (args, kwargs, result) 提取 layer 的回调。
            content_picker: 从 (args, kwargs, result) 提取内容预览的回调。

        Returns:
            是否成功包装。
        """
        if obj is None:
            return False
        original = getattr(obj, method_name, None)
        if original is None or not callable(original):
            logger.debug("[MemoryWiring] 跳过不存在的方法: %s.%s", type(obj).__name__, method_name)
            return False
        if getattr(original, "_tianji_wired", False):
            return False  # 幂等: 已包装

        bus = self._bus

        def wrapper(*args: Any, **kwargs: Any) -> Any:
            start = time.perf_counter()
            result = original(*args, **kwargs)
            duration_ms = (time.perf_counter() - start) * 1000.0
            try:
                payload = _build_payload(
                    event_type,
                    layer_picker(args, kwargs, result),
                    content_picker(args, kwargs, result),
                    result,
                    duration_ms,
                )
                safe_publish(bus, event_type, payload, _DOMAIN)
            except Exception as exc:  # noqa: BLE001 — 接线绝不破坏业务
                logger.debug("[MemoryWiring] %s 事件发布失败: %s", event_type, exc)
            return result

        wrapper._tianji_wired = True  # type: ignore[attr-defined]
        wrapper._tianji_original = original  # type: ignore[attr-defined]
        try:
            wrapper.__name__ = getattr(original, "__name__", method_name)
            wrapper.__doc__ = getattr(original, "__doc__", None)
        except Exception:  # noqa: BLE001
            pass
        setattr(obj, method_name, wrapper)
        self._wrapped.append((obj, method_name, original))
        return True

    # ------------------------------------------------------------------
    # 接线 / 解接线
    # ------------------------------------------------------------------
    def wire(self) -> dict[str, bool]:
        """执行接线，返回各组件接线状态  [v10-ready]

        为每个非 None 组件注册事件发布包装:
            writer → memory.written
            promoter → memory.promoted
            archiver → memory.archived
            indexer → memory.recalled

        event_bus 为 None 时全部返回 False(透传降级)。

        Returns:
            dict: {"writer": bool, "promoter": bool, "archiver": bool, "indexer": bool}
        """
        if self._bus is None:
            logger.debug("[MemoryWiring] event_bus 为空，进入透传模式(不接线)")
            self._wired = {
                "writer": False,
                "promoter": False,
                "archiver": False,
                "indexer": False,
            }
            return dict(self._wired)

        self._wired["writer"] = self._wire_writer()
        self._wired["promoter"] = self._wire_promoter()
        self._wired["archiver"] = self._wire_archiver()
        self._wired["indexer"] = self._wire_indexer()
        return dict(self._wired)

    def _wire_writer(self) -> bool:
        """接线 MemoryWriter.remember → memory.written  [v10-ready]"""
        return self._wrap_publish(
            self.writer,
            "remember",
            EVENT_WRITTEN,
            layer_picker=lambda a, k, r: (
                r.get("actual_layer") if isinstance(r, dict) else None
            )
            or pick_arg(a, k, 1, "layer", "working"),
            content_picker=lambda a, k, r: pick_arg(a, k, 0, "content", ""),
        )

    def _wire_promoter(self) -> bool:
        """接线 PromotionEngine.consolidate → memory.promoted  [v10-ready]"""
        return self._wrap_publish(
            self.promoter,
            "consolidate",
            EVENT_PROMOTED,
            layer_picker=lambda a, k, r: pick_arg(a, k, 1, "to_layer", ""),
            content_picker=lambda a, k, r: pick_arg(a, k, 2, "entry_id", ""),
        )

    def _wire_archiver(self) -> bool:
        """接线 ArchiveManager.forget → memory.archived  [v10-ready]"""
        return self._wrap_publish(
            self.archiver,
            "forget",
            EVENT_ARCHIVED,
            layer_picker=lambda a, k, r: "",
            content_picker=lambda a, k, r: pick_arg(a, k, 0, "entry_id", ""),
        )

    def _wire_indexer(self) -> bool:
        """接线 MemoryIndex.recall → memory.recalled  [v10-ready]"""
        return self._wrap_publish(
            self.indexer,
            "recall",
            EVENT_RECALLED,
            layer_picker=lambda a, k, r: ",".join(
                str(x) for x in (pick_arg(a, k, 1, "layers", None) or [])
            ),
            content_picker=lambda a, k, r: pick_arg(a, k, 0, "query", "") or "",
        )

    @property
    def is_wired(self) -> bool:
        """是否至少有一个组件成功接线  [v10-ready]"""
        return any(self._wired.values())

    def get_status(self) -> dict[str, bool]:
        """返回当前接线状态快照  [v10-ready]"""
        return dict(self._wired)

    def unwire(self) -> None:
        """解除接线，还原全部方法包装并退订(幂等)  [v10-ready]"""
        super().unwire()
        self._wired = {}


def wire_memory(
    event_bus: Any,
    writer: Any = None,
    promoter: Any = None,
    archiver: Any = None,
    indexer: Any = None,
    acl: Any = None,
) -> dict[str, bool]:
    """一键接线记忆域  [v10-ready]

    Args:
        event_bus: IEventBus 实例。
        writer: MemoryWriter 实例(可选)。
        promoter: PromotionEngine 实例(可选)。
        archiver: ArchiveManager 实例(可选)。
        indexer: MemoryIndex 实例(可选)。
        acl: 访问控制规则(可选)。

    Returns:
        接线状态字典 {"writer": True/False, "promoter": True/False, ...}
    """
    wiring = MemoryEventWiring(event_bus, writer, promoter, archiver, indexer, acl)
    return wiring.wire()


__all__ = [
    "MemoryEventWiring",
    "wire_memory",
    "EVENT_WRITTEN",
    "EVENT_PROMOTED",
    "EVENT_ARCHIVED",
    "EVENT_RECALLED",
    "EVENT_INVALIDATED",
    "EVENT_CONSOLIDATED",
]
