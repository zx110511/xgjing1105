"""
SLA健康检查框架 v1.0
====================
功能:
  1. 心跳检测 — 每30秒检查所有核心模块状态
  2. 深度健康检查 — 每5分钟执行完整健康评估
  3. 自动恢复 — 检测到故障自动重启/降级
  4. SLA指标计算 — 可用性/延迟/错误率
  5. 告警通知 — 超阈值触发告警
"""

import logging
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger("tianji.sla.health")


class HealthStatus(str, Enum):
    """健康状态枚举"""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


class AlertSeverity(str, Enum):
    """告警严重级别"""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"
    FATAL = "fatal"


class RecoveryAction(str, Enum):
    """恢复动作类型"""
    RESTART = "restart"
    DEGRADE = "degrade"
    SWITCH = "switch"
    NONE = "none"


@dataclass
class HealthCheckResult:
    """单项健康检查结果"""
    component: str
    status: HealthStatus
    message: str = ""
    latency_ms: float = 0.0
    timestamp: float = field(default_factory=time.time)
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SLAMetrics:
    """SLA指标"""
    availability_pct: float = 100.0
    mttr_seconds: float = 0.0
    mtbf_seconds: float = 0.0
    error_rate_pct: float = 0.0
    p99_latency_ms: float = 0.0
    total_checks: int = 0
    failed_checks: int = 0
    uptime_seconds: float = 0.0


@dataclass
class Alert:
    """告警记录"""
    alert_id: str
    severity: AlertSeverity
    component: str
    message: str
    timestamp: float = field(default_factory=time.time)
    resolved: bool = False
    resolved_at: Optional[float] = None


class SLACalculator:
    """SLA指标计算器"""

    def __init__(self) -> None:
        self._check_history: List[HealthCheckResult] = []
        self._incident_history: List[Dict[str, Any]] = []
        self._start_time: float = time.time()
        self._max_history: int = 10000

    def record_check(self, result: HealthCheckResult) -> None:
        """记录一次健康检查结果"""
        self._check_history.append(result)
        if len(self._check_history) > self._max_history:
            self._check_history = self._check_history[-self._max_history:]

    def record_incident(self, start: float, end: float, component: str) -> None:
        """记录一次故障事件"""
        self._incident_history.append({
            "component": component,
            "start": start,
            "end": end,
            "duration": end - start,
        })

    def calculate(self) -> SLAMetrics:
        """计算当前SLA指标"""
        now = time.time()
        uptime = now - self._start_time
        total = len(self._check_history)

        if total == 0:
            return SLAMetrics(uptime_seconds=uptime)

        failed = sum(
            1 for r in self._check_history if r.status == HealthStatus.UNHEALTHY
        )
        availability = ((total - failed) / total) * 100.0
        error_rate = (failed / total) * 100.0

        latencies = [r.latency_ms for r in self._check_history if r.latency_ms > 0]
        p99 = sorted(latencies)[int(len(latencies) * 0.99)] if latencies else 0.0

        mttr = 0.0
        mtbf = 0.0
        if self._incident_history:
            durations = [inc["duration"] for inc in self._incident_history]
            mttr = sum(durations) / len(durations)
            if len(self._incident_history) > 1:
                gaps = []
                for i in range(1, len(self._incident_history)):
                    gap = (
                        self._incident_history[i]["start"]
                        - self._incident_history[i - 1]["end"]
                    )
                    gaps.append(gap)
                mtbf = sum(gaps) / len(gaps) if gaps else uptime

        return SLAMetrics(
            availability_pct=round(availability, 3),
            mttr_seconds=round(mttr, 1),
            mtbf_seconds=round(mtbf, 1),
            error_rate_pct=round(error_rate, 3),
            p99_latency_ms=round(p99, 2),
            total_checks=total,
            failed_checks=failed,
            uptime_seconds=round(uptime, 1),
        )


class AlertManager:
    """告警管理器"""

    def __init__(
        self,
        warning_threshold: float = 95.0,
        critical_threshold: float = 99.0,
        max_alerts: int = 1000,
    ) -> None:
        self._warning_threshold = warning_threshold
        self._critical_threshold = critical_threshold
        self._alerts: List[Alert] = []
        self._max_alerts = max_alerts
        self._handlers: List[Callable[[Alert], None]] = []

    def add_handler(self, handler: Callable[[Alert], None]) -> None:
        """添加告警处理器"""
        self._handlers.append(handler)

    def check_and_alert(
        self, component: str, metrics: SLAMetrics
    ) -> Optional[Alert]:
        """检查指标并触发告警"""
        severity = AlertSeverity.INFO
        message = ""

        if metrics.error_rate_pct > self._critical_threshold:
            severity = AlertSeverity.CRITICAL
            message = f"{component} 错误率 {metrics.error_rate_pct}% 超过临界阈值 {self._critical_threshold}%"
        elif metrics.error_rate_pct > self._warning_threshold:
            severity = AlertSeverity.WARNING
            message = f"{component} 错误率 {metrics.error_rate_pct}% 超过警告阈值 {self._warning_threshold}%"

        if metrics.availability_pct < (100.0 - self._critical_threshold):
            severity = AlertSeverity.CRITICAL
            message = f"{component} 可用性 {metrics.availability_pct}% 低于临界线"

        if severity == AlertSeverity.INFO:
            return None

        alert = Alert(
            alert_id=f"alert-{int(time.time() * 1000)}",
            severity=severity,
            component=component,
            message=message,
        )
        self._alerts.append(alert)
        if len(self._alerts) > self._max_alerts:
            self._alerts = self._alerts[-self._max_alerts:]

        for handler in self._handlers:
            try:
                handler(alert)
            except Exception as e:
                logger.error("告警处理器异常: %s", e)

        return alert

    def resolve_alert(self, alert_id: str) -> bool:
        """解决告警"""
        for alert in self._alerts:
            if alert.alert_id == alert_id and not alert.resolved:
                alert.resolved = True
                alert.resolved_at = time.time()
                return True
        return False

    @property
    def active_alerts(self) -> List[Alert]:
        """获取活跃告警"""
        return [a for a in self._alerts if not a.resolved]

    @property
    def all_alerts(self) -> List[Alert]:
        """获取所有告警"""
        return list(self._alerts)


class AutoRecovery:
    """自动恢复策略"""

    def __init__(
        self,
        max_restart_attempts: int = 3,
        restart_cooldown: float = 60.0,
        degrade_after: int = 3,
    ) -> None:
        self._max_restart_attempts = max_restart_attempts
        self._restart_cooldown = restart_cooldown
        self._degrade_after = degrade_after
        self._attempt_counts: Dict[str, int] = {}
        self._last_restart: Dict[str, float] = {}
        self._recovery_log: List[Dict[str, Any]] = []

    def decide(self, component: str, status: HealthStatus) -> RecoveryAction:
        """根据健康状态决定恢复动作"""
        if status == HealthStatus.HEALTHY:
            self._attempt_counts.pop(component, None)
            return RecoveryAction.NONE

        if status == HealthStatus.DEGRADED:
            return RecoveryAction.DEGRADE

        if status == HealthStatus.UNHEALTHY:
            attempts = self._attempt_counts.get(component, 0)
            now = time.time()
            last = self._last_restart.get(component, 0)

            if now - last < self._restart_cooldown:
                return RecoveryAction.NONE

            if attempts < self._max_restart_attempts:
                self._attempt_counts[component] = attempts + 1
                self._last_restart[component] = now
                self._recovery_log.append({
                    "component": component,
                    "action": RecoveryAction.RESTART.value,
                    "attempt": attempts + 1,
                    "timestamp": now,
                })
                return RecoveryAction.RESTART

            if attempts >= self._degrade_after:
                self._recovery_log.append({
                    "component": component,
                    "action": RecoveryAction.DEGRADE.value,
                    "attempt": attempts,
                    "timestamp": now,
                })
                return RecoveryAction.DEGRADE

        return RecoveryAction.NONE

    @property
    def recovery_log(self) -> List[Dict[str, Any]]:
        """获取恢复日志"""
        return list(self._recovery_log)


class HealthChecker:
    """SLA健康检查调度器"""

    HEARTBEAT_INTERVAL = 30.0
    DEEP_CHECK_INTERVAL = 300.0

    def __init__(
        self,
        engine: Optional[Any] = None,
        heartbeat_interval: float = HEARTBEAT_INTERVAL,
        deep_check_interval: float = DEEP_CHECK_INTERVAL,
    ) -> None:
        self._engine = engine
        self._heartbeat_interval = heartbeat_interval
        self._deep_check_interval = deep_check_interval
        self._sla = SLACalculator()
        self._alerts = AlertManager()
        self._recovery = AutoRecovery()
        self._checkers: Dict[str, Callable[[], HealthCheckResult]] = {}
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._last_results: Dict[str, HealthCheckResult] = {}
        self._lock = threading.Lock()

    def register_checker(
        self, component: str, checker: Callable[[], HealthCheckResult]
    ) -> None:
        """注册组件健康检查器"""
        self._checkers[component] = checker

    def check_component(self, component: str) -> HealthCheckResult:
        """检查单个组件"""
        checker = self._checkers.get(component)
        if checker is None:
            return HealthCheckResult(
                component=component,
                status=HealthStatus.UNKNOWN,
                message="未注册的检查器",
            )
        try:
            start = time.time()
            result = checker()
            result.latency_ms = (time.time() - start) * 1000.0
        except Exception as e:
            result = HealthCheckResult(
                component=component,
                status=HealthStatus.UNHEALTHY,
                message=str(e),
            )
        with self._lock:
            self._last_results[component] = result
            self._sla.record_check(result)
        return result

    def check_all(self) -> Dict[str, HealthCheckResult]:
        """检查所有已注册组件"""
        results: Dict[str, HealthCheckResult] = {}
        for component in list(self._checkers.keys()):
            results[component] = self.check_component(component)
        return results

    def deep_check(self) -> Dict[str, HealthCheckResult]:
        """深度健康检查 — 包含引擎级验证"""
        results = self.check_all()

        if self._engine is not None:
            try:
                health = self._engine.health()
                engine_status = HealthStatus.HEALTHY
                if health.get("error_rate", 0) > 0.05:
                    engine_status = HealthStatus.DEGRADED
                if not health.get("engine_ready", True):
                    engine_status = HealthStatus.UNHEALTHY

                results["icme_engine"] = HealthCheckResult(
                    component="icme_engine",
                    status=engine_status,
                    details=health,
                )
            except Exception as e:
                results["icme_engine"] = HealthCheckResult(
                    component="icme_engine",
                    status=HealthStatus.UNHEALTHY,
                    message=str(e),
                )

        metrics = self._sla.calculate()
        alert = self._alerts.check_and_alert("system", metrics)
        if alert:
            logger.warning("SLA告警: %s", alert.message)

        return results

    def start(self) -> None:
        """启动后台心跳检查"""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._heartbeat_loop, daemon=True)
        self._thread.start()
        logger.info("健康检查已启动, 间隔=%.0fs", self._heartbeat_interval)

    def stop(self) -> None:
        """停止后台心跳检查"""
        self._running = False
        if self._thread is not None:
            self._thread.join(timeout=5.0)
            self._thread = None
        logger.info("健康检查已停止")

    def _heartbeat_loop(self) -> None:
        """心跳检查循环"""
        while self._running:
            try:
                self.check_all()
            except Exception as e:
                logger.error("心跳检查异常: %s", e)
            time.sleep(self._heartbeat_interval)

    def get_sla_metrics(self) -> SLAMetrics:
        """获取当前SLA指标"""
        return self._sla.calculate()

    def get_last_results(self) -> Dict[str, HealthCheckResult]:
        """获取最近一次检查结果"""
        with self._lock:
            return dict(self._last_results)

    @property
    def alert_manager(self) -> AlertManager:
        """获取告警管理器"""
        return self._alerts

    @property
    def auto_recovery(self) -> AutoRecovery:
        """获取自动恢复器"""
        return self._recovery
