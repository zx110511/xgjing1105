# -*- coding: utf-8-sig -*-
"""天机v10.0.1 防腐层(ACL)基础设施  [v10-ready]

AnticorruptionLayer (ACL)职责:
1. 隔离: 跨域调用经适配器转换，不暴露内部结构
2. 解耦: 异步调用通过EventBus，同步调用经Adapter直连
3. 降级: EventBus不可用时自动降级为直接调用
4. 审计: 记录跨域调用链路（来源→目标→方法→结果）

架构定位: core/shared/ Ω基点 — 跨域通信基础设施

背景:
    当前系统有227处跨域直接import，Phase 3需要将核心耦合点转为事件驱动。
    ACL作为过渡层，提供跨域调用的统一入口、DomainAdapter适配器模式、
    与EventBus集成（异步调用经EventBus，同步调用经Adapter直连+降级）。

Usage:
    from core.shared.events import LocalEventBus
    from core.shared.anticorruption import AnticorruptionLayer, PassthroughAdapter

    bus = LocalEventBus()
    acl = AnticorruptionLayer(event_bus=bus)

    # 注册适配器
    acl.register_adapter("engine", "driver", PassthroughAdapter())

    # 同步调用(经适配器)
    result = acl.call("engine", "driver", "quick_decide", content="test")

    # 异步调用(经EventBus)
    acl.call_async("engine", "gate", "check", content="test", metadata={})

    # 获取调用历史 / 统计
    history = acl.get_call_history(limit=100)
    stats = acl.get_stats()

版本: 1.0.0
"""
from __future__ import annotations

import time
import logging
import threading
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

logger = logging.getLogger(__name__)

# 跨域事件类型前缀（用于EventBus异步派发）  [v10-ready]
CROSS_DOMAIN_EVENT_PREFIX = "acl.cross_domain"

# 调用历史环形缓冲上限  [v10-ready]
_DEFAULT_HISTORY_CAPACITY = 1000


# ============================================================================
# 域适配器协议
# ============================================================================

@runtime_checkable
class DomainAdapter(Protocol):
    """域适配器协议  [v10-ready]

    每对跨域调用拥有专属适配器，负责:
    - adapt_request: 将源域请求参数转换为目标域可理解的入参字典
    - adapt_response: 将目标域返回结果转换为源域期望的结构
    - get_supported_methods: 声明本适配器支持的方法列表

    本地实现: PassthroughAdapter / LoggingAdapter (进程内透传)
    远程实现: 灵境跨节点适配代理 (stub 预留)
    """

    def adapt_request(self, source_domain: str, method: str, **kwargs: Any) -> dict[str, Any]:
        """转换跨域请求参数。

        Args:
            source_domain: 源域标识。
            method: 目标方法名。
            **kwargs: 原始调用参数。

        Returns:
            转换后的参数字典。
        """
        ...

    def adapt_response(self, raw_response: Any) -> Any:
        """转换目标域返回结果。

        Args:
            raw_response: 目标域原始返回值。

        Returns:
            转换后的返回值。
        """
        ...

    def get_supported_methods(self) -> list[str]:
        """声明本适配器支持的方法。

        Returns:
            支持的方法名列表 (空列表表示不限制)。
        """
        ...


# ============================================================================
# 跨域调用记录
# ============================================================================

@dataclass
class CrossDomainCall:
    """跨域调用记录  [v10-ready]

    记录一次跨域调用的完整链路信息，用于审计与统计。

    Attributes:
        source_domain: 调用来源域。
        target_domain: 调用目标域。
        method: 被调用的方法名。
        args: 调用参数快照 (kwargs)。
        result: 调用结果 (失败时为 None)。
        duration: 调用耗时 (秒)。
        success: 调用是否成功。
        timestamp: 调用发生时间戳 (Unix 秒)。
        error: 失败时的错误描述 (成功时为 None)。
        mode: 调用模式 ("sync" / "async" / "fallback")。
    """

    source_domain: str
    target_domain: str
    method: str
    args: dict[str, Any] = field(default_factory=dict)
    result: Any = None
    duration: float = 0.0
    success: bool = False
    timestamp: float = field(default_factory=time.time)
    error: str | None = None
    mode: str = "sync"

    def to_dict(self) -> dict[str, Any]:
        """转换为字典 (便于序列化/日志)  [v10-ready]"""
        return {
            "source_domain": self.source_domain,
            "target_domain": self.target_domain,
            "method": self.method,
            "args": self.args,
            "result": self.result,
            "duration": self.duration,
            "success": self.success,
            "timestamp": self.timestamp,
            "error": self.error,
            "mode": self.mode,
        }


# ============================================================================
# 防腐层核心
# ============================================================================

class AnticorruptionLayer:
    """跨域调用防腐层  [v10-ready]

    隔离跨域耦合，统一跨域调用入口。同步调用经适配器直连，
    异步调用经EventBus派发；EventBus不可用时自动降级为同步直连。
    所有调用链路记录至环形缓冲区，供审计与统计。

    线程安全: 适配器注册表与调用历史均由 threading.Lock 保护。

    Usage:
        bus = LocalEventBus()
        acl = AnticorruptionLayer(event_bus=bus)
        acl.register_adapter("engine", "driver", PassthroughAdapter())
        result = acl.call("engine", "driver", "quick_decide", content="test")
    """

    def __init__(
        self,
        event_bus: Any = None,
        fallback_enabled: bool = True,
        history_capacity: int = _DEFAULT_HISTORY_CAPACITY,
    ) -> None:
        """初始化防腐层  [v10-ready]

        Args:
            event_bus: 事件总线实例 (实现 IEventBus)，可为 None。
            fallback_enabled: EventBus不可用时是否降级为同步直连。
            history_capacity: 调用历史环形缓冲容量。
        """
        self._event_bus = event_bus
        self._fallback_enabled = fallback_enabled
        # 适配器注册表: (source, target) -> adapter
        self._adapters: dict[tuple[str, str], Any] = {}
        # 调用历史环形缓冲
        self._history: deque[CrossDomainCall] = deque(maxlen=history_capacity)
        # 线程安全锁 (RLock 避免内部嵌套调用死锁)
        self._lock = threading.RLock()
        # 统计计数
        self._total_calls = 0
        self._success_calls = 0
        self._failed_calls = 0
        self._async_calls = 0
        self._fallback_calls = 0

    # ------------------------------------------------------------------
    # 适配器管理
    # ------------------------------------------------------------------

    def register_adapter(self, source: str, target: str, adapter: Any) -> None:
        """注册源→目标域适配器  [v10-ready]

        Args:
            source: 源域标识。
            target: 目标域标识。
            adapter: 适配器实例 (应实现 DomainAdapter)。
        """
        if not isinstance(adapter, DomainAdapter):
            logger.warning(
                "[ACL] 适配器 %s→%s 未完整实现 DomainAdapter 协议，仍尝试注册",
                source, target,
            )
        with self._lock:
            self._adapters[(source, target)] = adapter
        logger.debug("[ACL] 注册适配器: %s→%s", source, target)

    def unregister_adapter(self, source: str, target: str) -> bool:
        """注销适配器  [v10-ready]

        Args:
            source: 源域标识。
            target: 目标域标识。

        Returns:
            是否成功注销 (不存在时返回 False)。
        """
        with self._lock:
            if (source, target) in self._adapters:
                del self._adapters[(source, target)]
                logger.debug("[ACL] 注销适配器: %s→%s", source, target)
                return True
        return False

    def get_adapter(self, source: str, target: str) -> Any | None:
        """获取指定适配器  [v10-ready]

        Args:
            source: 源域标识。
            target: 目标域标识。

        Returns:
            适配器实例；不存在时返回 None。
        """
        with self._lock:
            return self._adapters.get((source, target))

    def list_adapters(self) -> list[tuple[str, str]]:
        """列出已注册的所有 (source, target) 适配器键  [v10-ready]"""
        with self._lock:
            return list(self._adapters.keys())

    # ------------------------------------------------------------------
    # 同步调用
    # ------------------------------------------------------------------

    def call(self, source: str, target: str, method: str, **kwargs: Any) -> Any:
        """同步跨域调用  [v10-ready]

        流程: 查找适配器 → adapt_request → 执行(适配器持有的目标可调用)
        → adapt_response → 记录调用链路。

        适配器执行约定:
            目标方法的实际执行委托给适配器。适配器可选实现 execute(method, params)，
            若未实现则尝试调用适配器上的同名方法；二者皆无则返回 adapt_request 的
            转换结果 (透传语义)，由 adapt_response 收尾。

        Args:
            source: 源域标识。
            target: 目标域标识。
            method: 目标方法名。
            **kwargs: 调用参数。

        Returns:
            经 adapt_response 转换后的调用结果。

        Raises:
            KeyError: 未找到对应适配器。
            Exception: 适配器执行过程中的异常 (已记录后向上抛出)。
        """
        return self._invoke_sync(source, target, method, mode="sync", **kwargs)

    def _invoke_sync(
        self, source: str, target: str, method: str, *, mode: str = "sync", **kwargs: Any
    ) -> Any:
        """同步调用内部实现（含链路记录）  [v10-ready]"""
        start = time.perf_counter()
        adapter = self.get_adapter(source, target)
        if adapter is None:
            duration = time.perf_counter() - start
            self._record_call(
                CrossDomainCall(
                    source_domain=source,
                    target_domain=target,
                    method=method,
                    args=dict(kwargs),
                    success=False,
                    duration=duration,
                    error=f"no adapter registered for {source}->{target}",
                    mode=mode,
                )
            )
            raise KeyError(f"[ACL] 未注册适配器: {source}->{target}")

        try:
            params = adapter.adapt_request(source, method, **kwargs)
            raw = self._dispatch_to_adapter(adapter, method, params)
            result = adapter.adapt_response(raw)
            duration = time.perf_counter() - start
            self._record_call(
                CrossDomainCall(
                    source_domain=source,
                    target_domain=target,
                    method=method,
                    args=dict(kwargs),
                    result=result,
                    success=True,
                    duration=duration,
                    mode=mode,
                )
            )
            return result
        except Exception as exc:
            duration = time.perf_counter() - start
            self._record_call(
                CrossDomainCall(
                    source_domain=source,
                    target_domain=target,
                    method=method,
                    args=dict(kwargs),
                    success=False,
                    duration=duration,
                    error=f"{type(exc).__name__}: {exc}",
                    mode=mode,
                )
            )
            logger.warning("[ACL] 跨域调用失败 %s→%s.%s: %s", source, target, method, exc)
            raise

    @staticmethod
    def _dispatch_to_adapter(adapter: Any, method: str, params: dict[str, Any]) -> Any:
        """将转换后的请求派发给适配器执行  [v10-ready]

        优先级:
            1. adapter.execute(method, params)  显式执行入口
            2. adapter.<method>(**params)       同名方法直连
            3. 透传: 直接返回 params              (无可执行目标)
        """
        execute = getattr(adapter, "execute", None)
        if callable(execute):
            return execute(method, params)
        target_callable = getattr(adapter, method, None)
        if callable(target_callable):
            return target_callable(**params)
        return params

    # ------------------------------------------------------------------
    # 异步调用
    # ------------------------------------------------------------------

    def call_async(self, source: str, target: str, method: str, **kwargs: Any) -> None:
        """异步跨域调用  [v10-ready]

        通过 EventBus 发布跨域事件 (event_type=acl.cross_domain.<source>.<target>)。
        EventBus 不可用时:
            - fallback_enabled=True  → 降级为同步 call()
            - fallback_enabled=False → 记录失败链路并静默返回

        Args:
            source: 源域标识。
            target: 目标域标识。
            method: 目标方法名。
            **kwargs: 调用参数。
        """
        start = time.perf_counter()
        bus = self._event_bus
        if bus is not None and hasattr(bus, "publish"):
            event_type = f"{CROSS_DOMAIN_EVENT_PREFIX}.{source}.{target}"
            payload = {
                "source_domain": source,
                "target_domain": target,
                "method": method,
                "args": dict(kwargs),
            }
            try:
                bus.publish(event_type, payload)
                duration = time.perf_counter() - start
                with self._lock:
                    self._async_calls += 1
                self._record_call(
                    CrossDomainCall(
                        source_domain=source,
                        target_domain=target,
                        method=method,
                        args=dict(kwargs),
                        success=True,
                        duration=duration,
                        mode="async",
                    )
                )
                return
            except Exception as exc:
                logger.warning(
                    "[ACL] 异步发布失败 %s→%s.%s: %s", source, target, method, exc
                )
                # 继续走降级逻辑

        # EventBus 不可用或发布失败 → 降级
        if self._fallback_enabled:
            with self._lock:
                self._fallback_calls += 1
            try:
                self._invoke_sync(source, target, method, mode="fallback", **kwargs)
            except Exception:
                # 降级调用异常已在 _invoke_sync 内记录，异步语义下不再抛出
                pass
            return

        # 不降级: 记录一条失败的异步链路
        duration = time.perf_counter() - start
        self._record_call(
            CrossDomainCall(
                source_domain=source,
                target_domain=target,
                method=method,
                args=dict(kwargs),
                success=False,
                duration=duration,
                error="event bus unavailable and fallback disabled",
                mode="async",
            )
        )

    # ------------------------------------------------------------------
    # 历史与统计
    # ------------------------------------------------------------------

    def _record_call(self, call: CrossDomainCall) -> None:
        """记录一次调用链路并更新统计  [v10-ready]"""
        with self._lock:
            self._history.append(call)
            self._total_calls += 1
            if call.success:
                self._success_calls += 1
            else:
                self._failed_calls += 1

    def get_call_history(self, limit: int = 100) -> list[CrossDomainCall]:
        """返回最近 N 条调用记录  [v10-ready]

        Args:
            limit: 返回的最大记录数 (最近优先)。

        Returns:
            最近 limit 条 CrossDomainCall 列表 (按时间升序)。
        """
        with self._lock:
            if limit <= 0:
                return []
            items = list(self._history)
        return items[-limit:]

    def get_stats(self) -> dict[str, Any]:
        """获取跨域调用统计  [v10-ready]

        Returns:
            统计字典: 总调用数/成功率/平均耗时/按域统计等。
        """
        with self._lock:
            history = list(self._history)
            total = self._total_calls
            success = self._success_calls
            failed = self._failed_calls
            async_calls = self._async_calls
            fallback_calls = self._fallback_calls
            adapter_count = len(self._adapters)

        durations = [c.duration for c in history]
        avg_duration = sum(durations) / len(durations) if durations else 0.0
        success_rate = (success / total) if total else 0.0

        # 按域(source→target)聚合
        per_domain: dict[str, dict[str, Any]] = {}
        for call in history:
            key = f"{call.source_domain}->{call.target_domain}"
            bucket = per_domain.setdefault(
                key, {"total": 0, "success": 0, "failed": 0, "total_duration": 0.0}
            )
            bucket["total"] += 1
            bucket["total_duration"] += call.duration
            if call.success:
                bucket["success"] += 1
            else:
                bucket["failed"] += 1
        for bucket in per_domain.values():
            cnt = bucket["total"]
            bucket["avg_duration"] = bucket["total_duration"] / cnt if cnt else 0.0

        return {
            "total_calls": total,
            "success_calls": success,
            "failed_calls": failed,
            "async_calls": async_calls,
            "fallback_calls": fallback_calls,
            "success_rate": success_rate,
            "avg_duration": avg_duration,
            "adapter_count": adapter_count,
            "history_size": len(history),
            "per_domain": per_domain,
        }

    def reset(self) -> None:
        """重置调用历史与统计 (测试用)  [v10-ready]"""
        with self._lock:
            self._history.clear()
            self._total_calls = 0
            self._success_calls = 0
            self._failed_calls = 0
            self._async_calls = 0
            self._fallback_calls = 0


# ============================================================================
# 预置适配器 (为 Phase 3-3/3-4 准备)
# ============================================================================

class PassthroughAdapter:
    """透传适配器  [v10-ready] — 不做数据转换，直接传递

    实现 DomainAdapter 协议。请求参数原样打包为字典，响应原样返回。
    适用于源域与目标域数据结构一致、无需转换的场景。
    """

    def adapt_request(self, source_domain: str, method: str, **kwargs: Any) -> dict[str, Any]:
        """原样返回调用参数  [v10-ready]"""
        return dict(kwargs)

    def adapt_response(self, raw_response: Any) -> Any:
        """原样返回响应  [v10-ready]"""
        return raw_response

    def get_supported_methods(self) -> list[str]:
        """透传适配器不限制方法，返回空列表  [v10-ready]"""
        return []


class LoggingAdapter:
    """日志适配器  [v10-ready] — 记录调用详情后透传

    实现 DomainAdapter 协议。在透传基础上，对请求与响应输出日志，
    便于跨域调用链路调试与审计。
    """

    def __init__(self, logger_name: str = __name__) -> None:
        """初始化日志适配器  [v10-ready]

        Args:
            logger_name: 使用的 logger 名称。
        """
        self._logger = logging.getLogger(logger_name)

    def adapt_request(self, source_domain: str, method: str, **kwargs: Any) -> dict[str, Any]:
        """记录请求后透传  [v10-ready]"""
        self._logger.info(
            "[ACL][LoggingAdapter] request source=%s method=%s args=%s",
            source_domain, method, kwargs,
        )
        return dict(kwargs)

    def adapt_response(self, raw_response: Any) -> Any:
        """记录响应后透传  [v10-ready]"""
        self._logger.info("[ACL][LoggingAdapter] response=%r", raw_response)
        return raw_response

    def get_supported_methods(self) -> list[str]:
        """日志适配器不限制方法，返回空列表  [v10-ready]"""
        return []


__all__ = [
    "DomainAdapter",
    "CrossDomainCall",
    "AnticorruptionLayer",
    "PassthroughAdapter",
    "LoggingAdapter",
    "CROSS_DOMAIN_EVENT_PREFIX",
]
