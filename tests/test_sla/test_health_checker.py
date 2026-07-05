"""D1: SLA健康检查框架测试"""
import time
import threading
from unittest.mock import MagicMock

import pytest

from core.sla.health_checker import (
    AlertManager,
    AlertSeverity,
    AutoRecovery,
    HealthChecker,
    HealthCheckResult,
    HealthStatus,
    RecoveryAction,
    SLACalculator,
    SLAMetrics,
    Alert,
)


# === SLACalculator ===

class TestSLACalculator:
    def test_empty_metrics(self):
        calc = SLACalculator()
        metrics = calc.calculate()
        assert metrics.total_checks == 0
        assert metrics.availability_pct == 100.0
        assert metrics.uptime_seconds >= 0

    def test_record_check(self):
        calc = SLACalculator()
        calc.record_check(HealthCheckResult(
            component="test", status=HealthStatus.HEALTHY
        ))
        metrics = calc.calculate()
        assert metrics.total_checks == 1
        assert metrics.failed_checks == 0

    def test_availability_calculation(self):
        calc = SLACalculator()
        for _ in range(9):
            calc.record_check(HealthCheckResult(
                component="test", status=HealthStatus.HEALTHY
            ))
        calc.record_check(HealthCheckResult(
            component="test", status=HealthStatus.UNHEALTHY
        ))
        metrics = calc.calculate()
        assert metrics.availability_pct == 90.0
        assert metrics.error_rate_pct == 10.0

    def test_mttr_calculation(self):
        calc = SLACalculator()
        # 需要先记录check才能计算incident指标
        calc.record_check(HealthCheckResult(
            component="test", status=HealthStatus.UNHEALTHY
        ))
        calc.record_incident(100.0, 160.0, "comp")
        calc.record_incident(300.0, 400.0, "comp")
        metrics = calc.calculate()
        assert metrics.mttr_seconds == 80.0  # (60+100)/2

    def test_mtbf_calculation(self):
        calc = SLACalculator()
        calc.record_check(HealthCheckResult(
            component="test", status=HealthStatus.UNHEALTHY
        ))
        calc.record_incident(100.0, 160.0, "comp")
        calc.record_incident(360.0, 400.0, "comp")
        metrics = calc.calculate()
        assert metrics.mtbf_seconds == 200.0  # 360-160

    def test_history_trimming(self):
        calc = SLACalculator()
        calc._max_history = 5
        for i in range(10):
            calc.record_check(HealthCheckResult(
                component="test", status=HealthStatus.HEALTHY
            ))
        assert len(calc._check_history) == 5


# === AlertManager ===

class TestAlertManager:
    def test_no_alert_when_healthy(self):
        am = AlertManager()
        metrics = SLAMetrics(error_rate_pct=1.0)
        alert = am.check_and_alert("comp", metrics)
        assert alert is None

    def test_warning_alert(self):
        am = AlertManager(warning_threshold=5.0)
        metrics = SLAMetrics(error_rate_pct=10.0)
        alert = am.check_and_alert("comp", metrics)
        assert alert is not None
        assert alert.severity == AlertSeverity.WARNING

    def test_critical_alert(self):
        am = AlertManager(critical_threshold=50.0)
        metrics = SLAMetrics(error_rate_pct=60.0)
        alert = am.check_and_alert("comp", metrics)
        assert alert is not None
        assert alert.severity == AlertSeverity.CRITICAL

    def test_resolve_alert(self):
        am = AlertManager(critical_threshold=50.0)
        metrics = SLAMetrics(error_rate_pct=60.0)
        alert = am.check_and_alert("comp", metrics)
        assert alert is not None
        assert am.resolve_alert(alert.alert_id) is True
        assert alert.resolved is True
        assert len(am.active_alerts) == 0

    def test_alert_handler(self):
        received = []
        am = AlertManager(critical_threshold=50.0)
        am.add_handler(lambda a: received.append(a))
        metrics = SLAMetrics(error_rate_pct=60.0)
        am.check_and_alert("comp", metrics)
        assert len(received) == 1

    def test_alert_history_limit(self):
        am = AlertManager(critical_threshold=50.0, max_alerts=3)
        for i in range(5):
            am.check_and_alert("comp", SLAMetrics(error_rate_pct=60.0))
        assert len(am.all_alerts) == 3


# === AutoRecovery ===

class TestAutoRecovery:
    def test_no_action_when_healthy(self):
        ar = AutoRecovery()
        assert ar.decide("comp", HealthStatus.HEALTHY) == RecoveryAction.NONE

    def test_degrade_action(self):
        ar = AutoRecovery()
        assert ar.decide("comp", HealthStatus.DEGRADED) == RecoveryAction.DEGRADE

    def test_restart_action(self):
        ar = AutoRecovery()
        action = ar.decide("comp", HealthStatus.UNHEALTHY)
        assert action == RecoveryAction.RESTART

    def test_max_restart_then_degrade(self):
        ar = AutoRecovery(max_restart_attempts=2, degrade_after=2, restart_cooldown=0.0)
        ar.decide("comp", HealthStatus.UNHEALTHY)
        ar.decide("comp", HealthStatus.UNHEALTHY)
        action = ar.decide("comp", HealthStatus.UNHEALTHY)
        assert action == RecoveryAction.DEGRADE

    def test_restart_cooldown(self):
        ar = AutoRecovery(restart_cooldown=10.0)
        ar.decide("comp", HealthStatus.UNHEALTHY)
        action = ar.decide("comp", HealthStatus.UNHEALTHY)
        assert action == RecoveryAction.NONE

    def test_recovery_log(self):
        ar = AutoRecovery()
        ar.decide("comp", HealthStatus.UNHEALTHY)
        assert len(ar.recovery_log) == 1


# === HealthChecker ===

class TestHealthChecker:
    def test_register_and_check(self):
        hc = HealthChecker()
        hc.register_checker("db", lambda: HealthCheckResult(
            component="db", status=HealthStatus.HEALTHY
        ))
        result = hc.check_component("db")
        assert result.status == HealthStatus.HEALTHY

    def test_check_unregistered(self):
        hc = HealthChecker()
        result = hc.check_component("unknown")
        assert result.status == HealthStatus.UNKNOWN

    def test_check_all(self):
        hc = HealthChecker()
        hc.register_checker("a", lambda: HealthCheckResult(
            component="a", status=HealthStatus.HEALTHY
        ))
        hc.register_checker("b", lambda: HealthCheckResult(
            component="b", status=HealthStatus.DEGRADED
        ))
        results = hc.check_all()
        assert len(results) == 2
        assert results["a"].status == HealthStatus.HEALTHY
        assert results["b"].status == HealthStatus.DEGRADED

    def test_check_with_exception(self):
        hc = HealthChecker()

        def bad_checker():
            raise RuntimeError("boom")

        hc.register_checker("bad", bad_checker)
        result = hc.check_component("bad")
        assert result.status == HealthStatus.UNHEALTHY
        assert "boom" in result.message

    def test_sla_metrics(self):
        hc = HealthChecker()
        hc.register_checker("db", lambda: HealthCheckResult(
            component="db", status=HealthStatus.HEALTHY
        ))
        hc.check_all()
        metrics = hc.get_sla_metrics()
        assert metrics.total_checks >= 1

    def test_start_stop(self):
        hc = HealthChecker(heartbeat_interval=0.1)
        hc.register_checker("db", lambda: HealthCheckResult(
            component="db", status=HealthStatus.HEALTHY
        ))
        hc.start()
        time.sleep(0.3)
        hc.stop()
        results = hc.get_last_results()
        assert "db" in results

    def test_deep_check_with_engine(self):
        engine = MagicMock()
        engine.health.return_value = {"engine_ready": True, "error_rate": 0.01}
        hc = HealthChecker(engine=engine)
        hc.register_checker("db", lambda: HealthCheckResult(
            component="db", status=HealthStatus.HEALTHY
        ))
        results = hc.deep_check()
        assert "icme_engine" in results
        assert results["icme_engine"].status == HealthStatus.HEALTHY

    def test_deep_check_engine_degraded(self):
        engine = MagicMock()
        engine.health.return_value = {"engine_ready": True, "error_rate": 0.1}
        hc = HealthChecker(engine=engine)
        results = hc.deep_check()
        assert results["icme_engine"].status == HealthStatus.DEGRADED

    def test_deep_check_engine_unhealthy(self):
        engine = MagicMock()
        engine.health.return_value = {"engine_ready": False, "error_rate": 0.5}
        hc = HealthChecker(engine=engine)
        results = hc.deep_check()
        assert results["icme_engine"].status == HealthStatus.UNHEALTHY

    def test_deep_check_engine_exception(self):
        engine = MagicMock()
        engine.health.side_effect = RuntimeError("engine down")
        hc = HealthChecker(engine=engine)
        results = hc.deep_check()
        assert results["icme_engine"].status == HealthStatus.UNHEALTHY

    def test_alert_manager_accessible(self):
        hc = HealthChecker()
        assert isinstance(hc.alert_manager, AlertManager)

    def test_auto_recovery_accessible(self):
        hc = HealthChecker()
        assert isinstance(hc.auto_recovery, AutoRecovery)
