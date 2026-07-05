# -*- coding: utf-8-sig -*-
"""TianjiContainer 信号/事件总线 — 从core.py拆分 [SSS-PhaseB]

包含: _emit_event / subscribe / unsubscribe / broadcast
      / 信号深度控制 / 事件监听器管理
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from typing import Any

logger = logging.getLogger("tianji.container.signal")


class ContainerSignalBus:
    """容器信号总线 — 管理模块间事件通信"""

    MAX_SIGNAL_DEPTH = 5

    def __init__(self, container):
        self._container = container
        self._event_listeners: list[Callable] = []
        self._module_subscriptions: dict[str, str] = {}
        self._signal_depth_counter: dict[str, int] = {}
        self._event_bus_ref: Any = None

    def set_event_bus(self, bus_ref: Any) -> None:
        """设置外部事件总线引用"""
        self._event_bus_ref = bus_ref

    def emit(self, event_type: str, target: str = "", detail: str = "") -> None:
        """发射容器级事件"""
        self._emit_event(event_type, target, detail)

    def _emit_event(self, event_type: str, target: str = "", detail: str = "") -> None:
        """内部事件发射 — 带深度防循环"""
        if self._signal_depth_counter.get(event_type, 0) >= self.MAX_SIGNAL_DEPTH:
            logger.warning("[SignalBus] 事件深度超限: %s (depth=%d)", event_type, self.MAX_SIGNAL_DEPTH)
            return

        self._signal_depth_counter[event_type] = self._signal_depth_counter.get(event_type, 0) + 1
        try:
            # 通知本地监听器
            for listener in list(self._event_listeners):
                try:
                    listener(event_type, target, detail)
                except Exception as e:
                    logger.warning("[SignalBus] 监听器异常: %s", e)

            # 转发到外部事件总线
            if self._event_bus_ref and hasattr(self._event_bus_ref, 'publish'):
                try:
                    from core.shared.deepseek_driver import TianjiEvent
                    evt = TianjiEvent(
                        event_type=f"container.{event_type}",
                        source="tianji_container",
                        data={"target": target, "detail": detail},
                    )
                    self._event_bus_ref.publish(evt)
                except Exception:
                    pass
        finally:
            self._signal_depth_counter[event_type] = self._signal_depth_counter.get(event_type, 0) - 1

    def subscribe(self, listener: Callable) -> None:
        """注册事件监听器"""
        if listener not in self._event_listeners:
            self._event_listeners.append(listener)

    def unsubscribe(self, listener: Callable) -> None:
        """注销事件监听器"""
        if listener in self._event_listeners:
            self._event_listeners.remove(listener)

    def subscribe_module(self, module_name: str, subscription_id: str) -> None:
        """记录模块的事件订阅ID（用于停止时清理）"""
        self._module_subscriptions[module_name] = subscription_id

    def unsubscribe_module(self, module_name: str) -> None:
        """清理模块订阅"""
        sub_id = self._module_subscriptions.pop(module_name, None)
        if sub_id and self._event_bus_ref and hasattr(self._event_bus_ref, 'unsubscribe'):
            try:
                self._event_bus_ref.unsubscribe(sub_id)
            except Exception:
                pass

    def list_listeners(self) -> int:
        """返回当前监听器数量"""
        return len(self._event_listeners)

    def list_subscriptions(self) -> dict[str, str]:
        """返回当前模块订阅映射"""
        return dict(self._module_subscriptions)
