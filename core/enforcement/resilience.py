r"""
天机韧性模块 (Circuit Breaker + Rate Limiter) v1.0
==========================================================
灵境分布式就绪 — 熔断/限流/降级 核心

核心特性:
  1. 熔断器: 故障计数→半开→关闭 三态循环
  2. 限流器: 令牌桶算法，支持burst
  3. 降级策略: 熔断触发后返回fallback
  4. 事件通知: 状态变化→EvolutionBus广播
  5. 全局/按服务 粒度控制

与灵境对接:
  灵境Phase 3: CircuitBreaker → Istio/Envoy
  灵境Phase 4: RateLimiter → Redis Lua + Gateway

架构位置: 天机/core/resilience.py
依赖: core/evolution_bus (状态变化事件)

灵境道谱溯源: D7-8【熔断限流煞】· 道七·韧性体道 · 四地煞之制之术
"""

import time
import logging
import threading
from typing import Any, Optional, Dict, List, Callable
from dataclasses import dataclass, field
from enum import Enum
from collections import deque

logger = logging.getLogger(__name__)


class CircuitState(str, Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


@dataclass
class CircuitStats:
    total_calls: int = 0
    successful: int = 0
    failed: int = 0
    last_failure_time: float = 0.0
    last_success_time: float = 0.0
    consecutive_failures: int = 0
    consecutive_successes: int = 0


class CircuitBreaker:
    """
    熔断器 v1.0

    状态转换:
      CLOSED ──(连续失败>=threshold)──> OPEN
      OPEN   ──(超时timeout)─────────> HALF_OPEN
      HALF_OPEN ──(成功)────────────> CLOSED
      HALF_OPEN ──(失败)────────────> OPEN

    用法:
      cb = CircuitBreaker("tianji_memory", failure_threshold=5)
      if cb.allow_request():
          try:
              result = do_work()
              cb.record_success()
          except Exception:
              cb.record_failure()
      else:
          return fallback_result()
    """

    def __init__(
        self,
        service_id: str,
        failure_threshold: int = 5,
        success_threshold: int = 2,
        timeout_seconds: float = 30.0,
        half_open_max_requests: int = 1,
        event_bus=None,
    ):
        self.service_id = service_id
        self.failure_threshold = failure_threshold
        self.success_threshold = success_threshold
        self.timeout_seconds = timeout_seconds
        self.half_open_max_requests = half_open_max_requests
        self._event_bus = event_bus

        self._state = CircuitState.CLOSED
        self._stats = CircuitStats()
        self._lock = threading.RLock()
        self._half_open_requests = 0
        self._state_changed_at = time.time()

    @property
    def state(self) -> CircuitState:
        self._try_transition()
        return self._state

    def allow_request(self) -> bool:
        self._try_transition()
        with self._lock:
            if self._state == CircuitState.CLOSED:
                self._stats.total_calls += 1
                return True
            if self._state == CircuitState.HALF_OPEN:
                if self._half_open_requests < self.half_open_max_requests:
                    self._half_open_requests += 1
                    self._stats.total_calls += 1
                    return True
                return False
            return False

    def record_success(self):
        with self._lock:
            self._stats.successful += 1
            self._stats.consecutive_successes += 1
            self._stats.consecutive_failures = 0
            self._stats.last_success_time = time.time()
            self._half_open_requests = max(0, self._half_open_requests - 1)

    def record_failure(self):
        with self._lock:
            self._stats.failed += 1
            self._stats.consecutive_failures += 1
            self._stats.consecutive_successes = 0
            self._stats.last_failure_time = time.time()
            self._half_open_requests = max(0, self._half_open_requests - 1)

    def _try_transition(self):
        with self._lock:
            if self._state == CircuitState.CLOSED:
                if self._stats.consecutive_failures >= self.failure_threshold:
                    self._transition_to(CircuitState.OPEN)
            elif self._state == CircuitState.OPEN:
                if time.time() - self._state_changed_at >= self.timeout_seconds:
                    self._transition_to(CircuitState.HALF_OPEN)
            elif self._state == CircuitState.HALF_OPEN:
                if self._stats.consecutive_successes >= self.success_threshold:
                    self._transition_to(CircuitState.CLOSED)
                elif self._stats.consecutive_failures >= 1:
                    self._transition_to(CircuitState.OPEN)

    def _transition_to(self, new_state: CircuitState):
        old_state = self._state
        self._state = new_state
        self._state_changed_at = time.time()

        if new_state == CircuitState.HALF_OPEN:
            self._stats.consecutive_successes = 0
            self._stats.consecutive_failures = 0
            self._half_open_requests = 0
        elif new_state == CircuitState.CLOSED:
            self._stats.consecutive_failures = 0

        logger.warning(f"Circuit {self.service_id}: {old_state.value} -> {new_state.value}")

        if self._event_bus:
            try:
                self._event_bus.publish("circuit_state_change", "circuit_breaker", {
                    "service_id": self.service_id,
                    "old_state": old_state.value,
                    "new_state": new_state.value,
                    "consecutive_failures": self._stats.consecutive_failures,
                })
            except Exception:
                pass

    def get_stats(self) -> Dict[str, Any]:
        self._try_transition()
        with self._lock:
            return {
                "service_id": self.service_id,
                "state": self._state.value,
                "total_calls": self._stats.total_calls,
                "successful": self._stats.successful,
                "failed": self._stats.failed,
                "failure_rate": round(self._stats.failed / max(self._stats.total_calls, 1) * 100, 1),
                "consecutive_failures": self._stats.consecutive_failures,
                "consecutive_successes": self._stats.consecutive_successes,
                "state_duration_seconds": round(time.time() - self._state_changed_at, 1),
            }

    def reset(self):
        with self._lock:
            self._state = CircuitState.CLOSED
            self._stats = CircuitStats()
            self._half_open_requests = 0
            self._state_changed_at = time.time()


class RateLimiter:
    """
    令牌桶限流器 v1.0

    用法:
      rl = RateLimiter("api_calls", rate=100, burst=20)
      if rl.allow():
          process_request()
      else:
          return rate_limited_response()

    CPU友好: 仅在allow()时计算填充，无后台线程
    """

    def __init__(
        self,
        limiter_id: str,
        rate: float = 100.0,
        burst: int = 20,
        window_seconds: float = 1.0,
        event_bus=None,
    ):
        """
        Args:
            limiter_id: 限流器ID
            rate: 每秒允许的请求数
            burst: 突发容量 (桶大小)
            window_seconds: 令牌补充窗口
        """
        self.limiter_id = limiter_id
        self.rate = rate
        self.burst = burst
        self.window_seconds = window_seconds
        self._event_bus = event_bus

        self._tokens: float = float(burst)
        self._last_refill: float = time.time()
        self._lock = threading.RLock()

        self._stats = {
            "allowed": 0,
            "denied": 0,
            "total": 0,
        }

    def allow(self, tokens: int = 1) -> bool:
        with self._lock:
            self._refill()
            if self._tokens >= tokens:
                self._tokens -= tokens
                self._stats["allowed"] += 1
                self._stats["total"] += 1
                return True
            self._stats["denied"] += 1
            self._stats["total"] += 1
            self._maybe_alert()
            return False

    def _refill(self):
        now = time.time()
        elapsed = now - self._last_refill
        self._tokens = min(float(self.burst), self._tokens + elapsed * self.rate)
        self._last_refill = now

    def _maybe_alert(self):
        with self._lock:
            total = self._stats["total"]
            denied = self._stats["denied"]
            if total > 0 and denied > 0 and denied >= total * 0.3:
                if self._event_bus:
                    try:
                        self._event_bus.publish("rate_limited", "rate_limiter", {
                            "limiter_id": self.limiter_id,
                            "deny_rate": round(denied / total * 100, 1),
                            "denied": denied,
                            "allowed": self._stats["allowed"],
                        })
                    except Exception:
                        pass

    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            total = max(self._stats["total"], 1)
            return {
                "limiter_id": self.limiter_id,
                "rate": self.rate,
                "burst": self.burst,
                "tokens_available": round(self._tokens, 2),
                "allowed": self._stats["allowed"],
                "denied": self._stats["denied"],
                "deny_rate": round(self._stats["denied"] / total * 100, 1),
            }

    def reset(self):
        with self._lock:
            self._tokens = float(self.burst)
            self._last_refill = time.time()
            self._stats = {"allowed": 0, "denied": 0, "total": 0}


class ResilienceManager:
    """
    韧性管理器 — 聚合CircuitBreaker + RateLimiter

    用法:
      rm = ResilienceManager()
      rm.configure_service("tiewei", rate=50, burst=10, failure_threshold=5)
      if rm.request("tiewei"):
          result = call_tiewei()
          rm.success("tiewei")
      else:
          return rm.fallback("tiewei")
    """

    def __init__(self, event_bus=None):
        self._circuits: Dict[str, CircuitBreaker] = {}
        self._limiters: Dict[str, RateLimiter] = {}
        self._fallbacks: Dict[str, Any] = {}
        self._event_bus = event_bus
        self._lock = threading.RLock()

    def configure_service(
        self,
        service_id: str,
        rate: float = 100.0,
        burst: int = 20,
        failure_threshold: int = 5,
        timeout_seconds: float = 30.0,
        fallback: Any = None,
    ):
        with self._lock:
            self._circuits[service_id] = CircuitBreaker(
                service_id=service_id,
                failure_threshold=failure_threshold,
                timeout_seconds=timeout_seconds,
                event_bus=self._event_bus,
            )
            self._limiters[service_id] = RateLimiter(
                limiter_id=service_id,
                rate=rate,
                burst=burst,
                event_bus=self._event_bus,
            )
            if fallback is not None:
                self._fallbacks[service_id] = fallback
        logger.info(f"Resilience configured for {service_id}: rate={rate}/s, burst={burst}, cb_threshold={failure_threshold}")

    def request(self, service_id: str) -> bool:
        limiter = self._limiters.get(service_id)
        if limiter and not limiter.allow():
            logger.debug(f"Rate limited: {service_id}")
            return False

        circuit = self._circuits.get(service_id)
        if circuit and not circuit.allow_request():
            logger.warning(f"Circuit open: {service_id}")
            return False

        return True

    def success(self, service_id: str):
        circuit = self._circuits.get(service_id)
        if circuit:
            circuit.record_success()

    def failure(self, service_id: str):
        circuit = self._circuits.get(service_id)
        if circuit:
            circuit.record_failure()

    def fallback(self, service_id: str) -> Any:
        return self._fallbacks.get(service_id)

    def get_circuit_state(self, service_id: str) -> str:
        cb = self._circuits.get(service_id)
        return cb.state.value if cb else "unconfigured"

    def get_stats(self) -> Dict[str, Any]:
        return {
            "services": {
                sid: {
                    "circuit": cb.get_stats(),
                    "limiter": self._limiters[sid].get_stats() if sid in self._limiters else {},
                }
                for sid, cb in self._circuits.items()
            },
            "total_services": len(self._circuits),
        }

    def reset_all(self):
        for cb in self._circuits.values():
            cb.reset()
        for rl in self._limiters.values():
            rl.reset()
        logger.info("All circuit breakers and rate limiters reset")


_GLOBAL_RESILIENCE: Optional[ResilienceManager] = None
_RESILIENCE_LOCK = threading.Lock()


def get_resilience_manager() -> ResilienceManager:
    global _GLOBAL_RESILIENCE
    with _RESILIENCE_LOCK:
        if _GLOBAL_RESILIENCE is None:
            _GLOBAL_RESILIENCE = ResilienceManager()
        return _GLOBAL_RESILIENCE


class ConsumerPriority(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass
class ConsumerConfig:
    consumer_id: str
    priority: ConsumerPriority
    rate: float
    burst: int
    failure_threshold: int
    timeout_seconds: float
    capacity_weight: float
    fallback: Any = None
    isolated: bool = False


DEFAULT_CONSUMERS = {
    "tiewei": ConsumerConfig("tiewei", ConsumerPriority.CRITICAL, 200, 30, 3, 15.0, 0.20),
    "yiku": ConsumerConfig("yiku", ConsumerPriority.CRITICAL, 300, 50, 3, 15.0, 0.25),
    "dongcha": ConsumerConfig("dongcha", ConsumerPriority.HIGH, 150, 20, 5, 30.0, 0.15),
    "tianshu": ConsumerConfig("tianshu", ConsumerPriority.CRITICAL, 250, 40, 3, 15.0, 0.22),
    "luling": ConsumerConfig("luling", ConsumerPriority.HIGH, 100, 15, 5, 30.0, 0.10),
    "lingxi": ConsumerConfig("lingxi", ConsumerPriority.MEDIUM, 80, 10, 8, 45.0, 0.08),
    "wenzong": ConsumerConfig("wenzong", ConsumerPriority.MEDIUM, 60, 8, 8, 60.0, 0.06),
    "miaobi": ConsumerConfig("miaobi", ConsumerPriority.LOW, 40, 5, 10, 60.0, 0.04),
    "baiqiao": ConsumerConfig("baiqiao", ConsumerPriority.LOW, 30, 3, 12, 90.0, 0.03),
}


class ConsumerResilienceManager:
    """
    消费者粒度韧性管理器 v1.0

    设计哲学:
      每个Consumer独立熔断+限流，避免单点失败级联
      系统过载时按优先级顺序降级: LOW → MEDIUM → HIGH → CRITICAL
      容量分配: 按capacity_weight加权分配总资源
      隔离模式: isolated=True的Consumer使用独立资源池

    退化策略:
      Level 1: 限流 (限制非关键请求)
      Level 2: 熔断 (关闭单Consumer)
      Level 3: 降级 (关闭优先级低于当前阈值的所有Consumer)
    """

    def __init__(self, event_bus=None, total_capacity: float = 1000.0):
        self._consumers: Dict[str, ConsumerConfig] = {}
        self._circuits: Dict[str, CircuitBreaker] = {}
        self._limiters: Dict[str, RateLimiter] = {}
        self._event_bus = event_bus
        self._total_capacity = total_capacity
        self._degraded_consumers: set = set()
        self._active_degradation_level: int = 0
        self._lock = threading.RLock()
        self._stats = {
            "degradations": 0,
            "isolated_failures": 0,
            "capacity_reallocations": 0,
        }

    def register_consumer(self, config: ConsumerConfig):
        with self._lock:
            self._consumers[config.consumer_id] = config
            self._circuits[config.consumer_id] = CircuitBreaker(
                service_id=config.consumer_id,
                failure_threshold=config.failure_threshold,
                timeout_seconds=config.timeout_seconds,
                event_bus=self._event_bus,
            )
            self._limiters[config.consumer_id] = RateLimiter(
                limiter_id=config.consumer_id,
                rate=config.rate,
                burst=config.burst,
                event_bus=self._event_bus,
            )

    def register_all_defaults(self):
        for cfg in DEFAULT_CONSUMERS.values():
            self.register_consumer(cfg)

    def request(self, consumer_id: str) -> bool:
        with self._lock:
            if consumer_id in self._degraded_consumers:
                return False

            config = self._consumers.get(consumer_id)
            if not config:
                return True

            limiter = self._limiters.get(consumer_id)
            if limiter and not limiter.allow():
                return False

            circuit = self._circuits.get(consumer_id)
            if circuit and not circuit.allow_request():
                if config.isolated:
                    self._stats["isolated_failures"] += 1
                return False

            return True

    def success(self, consumer_id: str):
        cb = self._circuits.get(consumer_id)
        if cb:
            cb.record_success()

    def failure(self, consumer_id: str):
        cb = self._circuits.get(consumer_id)
        if cb:
            cb.record_failure()

    def degrade(self, target_priority: ConsumerPriority):
        """
        降级: 关闭优先级低于target_priority的所有Consumer
        Level 1: degrade(MEDIUM) → 关闭LOW
        Level 2: degrade(HIGH) → 关闭LOW+MEDIUM
        Level 3: degrade(CRITICAL) → 关闭LOW+MEDIUM+HIGH
        """
        priority_order = {
            ConsumerPriority.LOW: 0,
            ConsumerPriority.MEDIUM: 1,
            ConsumerPriority.HIGH: 2,
            ConsumerPriority.CRITICAL: 3,
        }
        threshold = priority_order[target_priority]

        with self._lock:
            self._degraded_consumers.clear()
            for cid, cfg in self._consumers.items():
                if priority_order[cfg.priority] < threshold:
                    self._degraded_consumers.add(cid)
            self._stats["degradations"] += 1
            self._active_degradation_level = 4 - threshold

        self._reallocate_capacity()

    def restore_all(self):
        with self._lock:
            self._degraded_consumers.clear()
            self._active_degradation_level = 0

    def _reallocate_capacity(self):
        with self._lock:
            active = {
                cid: cfg
                for cid, cfg in self._consumers.items()
                if cid not in self._degraded_consumers
            }
            if not active:
                return

            total_weight = sum(cfg.capacity_weight for cfg in active.values())
            for cid, cfg in active.items():
                alloc = (cfg.capacity_weight / total_weight) * self._total_capacity
                if cid in self._limiters:
                    self._limiters[cid].rate = alloc
                    self._limiters[cid].burst = max(3, int(alloc * 0.15))

            self._stats["capacity_reallocations"] += 1

    def isolate(self, consumer_id: str):
        with self._lock:
            if consumer_id in self._consumers:
                self._consumers[consumer_id].isolated = True

    def unisolate(self, consumer_id: str):
        with self._lock:
            if consumer_id in self._consumers:
                self._consumers[consumer_id].isolated = False

    def get_consumer_stats(self) -> Dict[str, Any]:
        with self._lock:
            consumers = {}
            for cid, cfg in self._consumers.items():
                cb = self._circuits.get(cid)
                rl = self._limiters.get(cid)
                consumers[cid] = {
                    "priority": cfg.priority.value,
                    "capacity_weight": cfg.capacity_weight,
                    "isolated": cfg.isolated,
                    "degraded": cid in self._degraded_consumers,
                    "circuit_state": cb.state.value if cb else "unconfigured",
                    "circuit_stats": cb.get_stats() if cb else {},
                    "limiter_stats": rl.get_stats() if rl else {},
                }

            return {
                "consumers": consumers,
                "degradation_level": self._active_degradation_level,
                "degraded_count": len(self._degraded_consumers),
                "total_consumers": len(self._consumers),
                "stats": dict(self._stats),
            }

    def reset_all(self):
        with self._lock:
            for cb in self._circuits.values():
                cb.reset()
            for rl in self._limiters.values():
                rl.reset()
            self._degraded_consumers.clear()
            self._active_degradation_level = 0
            self._stats = {"degradations": 0, "isolated_failures": 0, "capacity_reallocations": 0}
