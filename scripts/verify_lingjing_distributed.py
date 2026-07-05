"""
Tianji v8.2 Lingjing Distributed Readiness Verification
========================================================
验证: EvolutionBus + ServiceRegistry + CircuitBreaker + RateLimiter

Usage: python scripts/verify_lingjing_distributed.py
"""

import json
import sys
import time
from pathlib import Path
from datetime import datetime

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

PASS = "[PASS]"
FAIL = "[FAIL]"
SEP = "=" * 60

RESULT = {
    "test": "lingjing_distributed_readiness",
    "timestamp": datetime.now().isoformat(),
    "version": "1.0.0",
    "modules": {},
}


def test_evolution_bus():
    print(f"\n{SEP}")
    print("1) EvolutionBus - Event Bus Test")
    print(f"{SEP}")

    from core.processors.evolution_bus import EvolutionBus, BusEvent, get_evolution_bus

    bus = EvolutionBus(db_path="data/test_evolution_bus.db")
    received_events = []

    def on_agent_action(event):
        received_events.append(event)

    bus.subscribe("test_module", "agent_action", on_agent_action)
    bus.subscribe("test_module_all", "*", lambda e: received_events.append(e))

    event_id = bus.publish("agent_action", "test_source", {"action": "test", "param": 42}, async_mode=False)

    checks = {
        "publish_returns_id": bool(event_id),
        "event_delivered": len(received_events) > 0,
        "correct_type": any(e.event_type == "agent_action" for e in received_events),
        "wildcard_delivered": len(received_events) >= 2,
        "stats_updating": bus.get_stats()["published"] >= 1,
    }

    for check, result in checks.items():
        print(f"  {PASS if result else FAIL} {check}")
    print(f"  Event ID: {event_id}")
    print(f"  Stats: {bus.get_stats()}")

    bus.shutdown()
    all_passed = all(checks.values())
    return {"passed": all_passed, "checks": checks}


def test_circuit_breaker():
    print(f"\n{SEP}")
    print("2) CircuitBreaker - Three-State Test")
    print(f"{SEP}")

    from core.enforcement.resilience import CircuitBreaker, CircuitState

    cb = CircuitBreaker("test_service", failure_threshold=3, timeout_seconds=0.5)

    assert cb.state == CircuitState.CLOSED
    assert cb.allow_request()
    print(f"  {PASS} Initial state: CLOSED")

    for i in range(3):
        cb.record_failure()
        cb.allow_request()
    cb._try_transition()
    assert cb.state == CircuitState.OPEN
    print(f"  {PASS} After 3 failures: OPEN")

    assert not cb.allow_request()
    print(f"  {PASS} Requests blocked in OPEN state")

    time.sleep(0.6)
    cb._try_transition()
    assert cb.state == CircuitState.HALF_OPEN
    print(f"  {PASS} After timeout: HALF_OPEN")

    assert cb.allow_request()
    cb.record_success()
    cb.allow_request()
    cb.record_success()
    cb._try_transition()
    assert cb.state == CircuitState.CLOSED
    print(f"  {PASS} After 2 successes: CLOSED (recovered)")

    stats = cb.get_stats()
    print(f"  Stats: state={stats['state']}, failures={stats['failed']}, success={stats['successful']}")

    return {"passed": True}


def test_rate_limiter():
    print(f"\n{SEP}")
    print("3) RateLimiter - Token Bucket Test")
    print(f"{SEP}")

    from core.enforcement.resilience import RateLimiter

    rl = RateLimiter("test_api", rate=10, burst=3)

    allowed = sum(1 for _ in range(10) if rl.allow())
    assert allowed >= 3, f"Expected >=3 burst, got {allowed}"
    print(f"  {PASS} Burst tokens: {allowed} allowed")

    rl = RateLimiter("slow_api", rate=2, burst=0)
    allowed = sum(1 for _ in range(10) if rl.allow())
    assert allowed <= 3, f"Expected <=3, got {allowed}"
    print(f"  {PASS} Slow rate limiting: {allowed} allowed")

    stats = rl.get_stats()
    print(f"  Stats: {stats}")

    return {"passed": True}


def test_service_registry():
    print(f"\n{SEP}")
    print("4) ServiceRegistry - Register + Heartbeat + Discover")
    print(f"{SEP}")

    from core.shared.service_registry import ServiceRegistry, ServiceStatus

    registry = ServiceRegistry(db_path="data/test_service_registry.db")

    registry.register("agent_a", name="TestAgentA", host="127.0.0.1", port=8801, layer="L2", capabilities=["test", "orchestrate"])
    registry.register("agent_b", name="TestAgentB", host="127.0.0.1", port=8810, layer="L0", capabilities=["test", "gate"])
    registry.register("agent_c", name="TestAgentC", host="127.0.0.1", port=8820, layer="L1", capabilities=["test", "memory"])

    all_services = registry.discover()
    assert len(all_services) == 3
    print(f"  {PASS} Register 3 services: {len(all_services)}")

    l1_services = registry.discover(layer="L1")
    assert len(l1_services) == 1
    assert l1_services[0].service_id == "agent_c"
    print(f"  {PASS} Layer L1 discovery: {len(l1_services)} service(s)")

    test_services = registry.discover(capability="test")
    assert len(test_services) == 3
    print(f"  {PASS} Capability discovery: {len(test_services)} service(s)")

    assert registry.heartbeat("agent_a")
    record = registry.get_service("agent_a")
    assert record.is_alive()
    print(f"  {PASS} Heartbeat + alive check")

    stats = registry.get_stats()
    assert stats["total_services"] == 3
    assert stats["online_count"] == 3
    print(f"  {PASS} Stats: {stats['total_services']} services, {stats['online_count']} online")
    print(f"  Uptime: {stats['uptime_seconds']}s")

    return {"passed": True}


def test_resilience_manager():
    print(f"\n{SEP}")
    print("5) ResilienceManager - Integrated Test")
    print(f"{SEP}")

    from core.enforcement.resilience import ResilienceManager

    rm = ResilienceManager()
    rm.configure_service("tiewei", rate=100, burst=10, failure_threshold=3, fallback={"error": "gate_degraded"})
    rm.configure_service("yiku", rate=50, burst=5, failure_threshold=2, fallback={"error": "memory_degraded"})

    assert rm.request("tiewei")
    rm.success("tiewei")
    print(f"  {PASS} tiewei: request OK + success")

    for _ in range(3):
        rm.request("yiku")
        rm.failure("yiku")

    cb_state = rm.get_circuit_state("yiku")
    assert cb_state == "open", f"Expected open, got {cb_state}"
    print(f"  {PASS} yiku: circuit opens after 2 failures (state={cb_state})")

    assert not rm.request("yiku")
    print(f"  {PASS} yiku: requests blocked when circuit open")

    fallback = rm.fallback("yiku")
    assert fallback == {"error": "memory_degraded"}
    print(f"  {PASS} yiku: fallback returned correctly")

    stats = rm.get_stats()
    total = stats["total_services"]
    print(f"  {PASS} Total managed services: {total}")
    print(f"  Stats: {json.dumps(stats, indent=2, ensure_ascii=False)[:200]}")

    return {"passed": True}


def test_evolution_bus_integration():
    print(f"\n{SEP}")
    print("6) Integration: EvolutionBus + Resilience + Registry")
    print(f"{SEP}")

    from core.processors.evolution_bus import EvolutionBus
    from core.enforcement.resilience import ResilienceManager
    from core.shared.service_registry import ServiceRegistry

    bus = EvolutionBus(db_path="data/test_lingjing_integration.db")
    registry = ServiceRegistry(db_path="data/test_lingjing_registry.db", event_bus=bus)
    rm = ResilienceManager(event_bus=bus)

    events_captured = []
    bus.subscribe("integration_test", "*", lambda e: events_captured.append(e))

    registry.register("test_agent", name="IntegrationAgent", host="127.0.0.1", port=9999, layer="L2")

    rm.configure_service("test_agent", rate=10, burst=2, failure_threshold=2)

    for _ in range(3):
        if rm.request("test_agent"):
            rm.failure("test_agent")

    registry.heartbeat("test_agent")
    registry.deregister("test_agent")

    total_events = len(events_captured)
    print(f"  Events captured: {total_events}")
    print(f"  {PASS if total_events > 0 else FAIL} Events flowing through bus")

    for evt in events_captured:
        print(f"    -> {evt.event_type:25s} from {evt.source}")

    bus.shutdown()
    return {"passed": total_events > 0, "events_count": total_events}


def main():
    print(SEP)
    print("Tianji v8.2 Lingjing Distributed Readiness Verification")
    print(SEP)
    print(f"Time: {datetime.now().isoformat()}")

    results = {}

    for test_name, test_fn in [
        ("evolution_bus", test_evolution_bus),
        ("circuit_breaker", test_circuit_breaker),
        ("rate_limiter", test_rate_limiter),
        ("service_registry", test_service_registry),
        ("resilience_manager", test_resilience_manager),
        ("integration", test_evolution_bus_integration),
    ]:
        try:
            results[test_name] = test_fn()
            results[test_name]["error"] = None
        except Exception as e:
            results[test_name] = {"passed": False, "error": str(e)}
            print(f"  {FAIL} {test_name}: {e}")

    RESULT["modules"] = results

    total = len(results)
    passed = sum(1 for r in results.values() if r.get("passed", False))
    failed_list = [k for k, r in results.items() if not r.get("passed", False)]

    print(f"\n{SEP}")
    print(f"FINAL VERDICT - Lingjing Distributed Readiness")
    print(f"{SEP}")

    verdicts = [
        ("1) EvolutionBus (Event-driven)", "evolution_bus"),
        ("2) CircuitBreaker (3-state)", "circuit_breaker"),
        ("3) RateLimiter (Token Bucket)", "rate_limiter"),
        ("4) ServiceRegistry (Register/Heartbeat/Discover)", "service_registry"),
        ("5) ResilienceManager (Integration)", "resilience_manager"),
        ("6) EvolutionBus + Registry + Resilience (Integration)", "integration"),
    ]

    for label, key in verdicts:
        r = results.get(key, {})
        status = "[OK]" if r.get("passed") else "[FAIL]"
        error = f" -> {r.get('error', '')}" if r.get("error") else ""
        print(f"  {status} {label}{error}")

    print(f"\n  Total: {passed}/{total} passed")
    if passed == total:
        print(f"  >>> Lingjing Distributed Core Ready: [YES] <<<")
        print(f"  EvolutionBus + ServiceRegistry + CircuitBreaker + RateLimiter: ALL VERIFIED")
    else:
        print(f"  >>> Lingjing Distributed: INCOMPLETE ({failed_list}) <<<")

    report_dir = PROJECT_ROOT / "tests" / "reports"
    report_path = report_dir / f"v8.2_lingjing_distributed_audit_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    try:
        with open(report_path, 'w', encoding='utf-8') as f:
            json.dump(RESULT, f, ensure_ascii=False, indent=2)
        print(f"\n  Report saved: {report_path}")
    except Exception:
        pass

    return passed == total


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
