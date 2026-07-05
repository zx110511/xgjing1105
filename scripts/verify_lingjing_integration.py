"""
Tianji v8.2 Integration Verification — Lingjing Distributed Readiness
=====================================================================
验证所有新模块在真实容器环境中的集成状态。
与 verify_lingjing_distributed.py 的区别:
  - 独立脚本: 验证模块自身逻辑
  - 本脚本: 验证模块在 TianjiContainer 中正确初始化、依赖注入、健康检查

Usage: python scripts/verify_lingjing_integration.py
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
WARN = "[WARN]"
SEP = "=" * 60

RESULT = {
    "test": "lingjing_integration_verification",
    "timestamp": datetime.now().isoformat(),
    "version": "1.0.0",
}


def test_module_imports():
    """验证所有3个新模块可以被正确导入"""
    print(f"\n{SEP}")
    print("0) Module Import Validation")
    print(f"{SEP}")

    checks = {}
    modules = [
        ("core.evolution_bus", "EvolutionBus + BusEvent"),
        ("core.service_registry", "ServiceRegistry + ServiceRecord"),
        ("core.resilience", "CircuitBreaker + RateLimiter + ResilienceManager"),
    ]

    for mod_path, desc in modules:
        try:
            __import__(mod_path)
            print(f"  {PASS} {mod_path}")
            checks[mod_path] = True
        except Exception as e:
            print(f"  {FAIL} {mod_path}: {e}")
            checks[mod_path] = False

    all_ok = all(checks.values())
    RESULT["imports"] = {"passed": all_ok, "modules": checks}
    return all_ok


def test_container_init():
    """验证TianjiContainer包含3个新模块"""
    print(f"\n{SEP}")
    print("1) TianjiContainer — New Module Registration")
    print(f"{SEP}")

    from core.shared.tianji_container import build_container, set_container

    container = build_container()
    container._modules_cache = {k: mod for k, mod in container._modules.items()}
    all_modules = list(container._modules.keys())

    checks = {}
    expected = ["lingjing_bus", "service_registry", "resilience_manager"]

    for mod_name in expected:
        if mod_name in container._modules:
            mod = container._modules[mod_name]
            checks[mod_name] = {
                "registered": True,
                "name": mod.descriptor.display_name,
                "category": mod.descriptor.category,
                "init_fn": mod.descriptor.init_fn is not None,
                "health_fn": mod.descriptor.health_fn is not None,
            }
            print(f"  {PASS} {mod_name}: registered (category={checks[mod_name]['category']})")
        else:
            checks[mod_name] = {"registered": False}
            print(f"  {FAIL} {mod_name}: NOT FOUND in container")

    expected_bus = [m for m in ["event_bus", "evolution_bus"] if m in container._modules]
    print(f"  {PASS} Existing bus modules: {expected_bus}")

    all_registered = all(v.get("registered") for v in checks.values())
    RESULT["container_registration"] = {"passed": all_registered, "modules": checks, "total_modules": len(all_modules)}
    return all_registered


def test_lingjing_bus_init():
    """验证灵境事件总线在容器中初始化"""
    print(f"\n{SEP}")
    print("2) LingjingBus — Container Initialization Test")
    print(f"{SEP}")

    from core.shared.tianji_container import build_container

    container = build_container()
    mod = container._modules.get("lingjing_bus")

    if not mod or not mod.descriptor.init_fn:
        print(f"  {FAIL} lingjing_bus module not found")
        return False

    try:
        bus = mod.descriptor.init_fn()
        print(f"  {PASS} init_fn executed: type={type(bus).__name__}")

        event_id = bus.publish("test_container", "verification", {"key": "val"}, async_mode=False)
        print(f"  {PASS} publish: event_id={event_id}")

        stats = bus.get_stats()
        assert stats["published"] >= 1
        print(f"  {PASS} stats: published={stats['published']}, queue={stats['queue_size']}")

        recv = []
        bus.subscribe("verify", "test_container", lambda e: recv.append(e))
        bus.publish("test_container", "verification", {"test": True}, async_mode=False)
        assert len(recv) == 1
        print(f"  {PASS} subscribe+publish+deliver: {len(recv)} event(s) received")

        bus.shutdown()
        return True
    except Exception as e:
        print(f"  {FAIL} {type(e).__name__}: {e}")
        return False


def test_service_registry_init():
    """验证服务注册中心在容器中初始化"""
    print(f"\n{SEP}")
    print("3) ServiceRegistry — Container Initialization Test")
    print(f"{SEP}")

    from core.shared.tianji_container import build_container

    container = build_container()
    mod = container._modules.get("service_registry")

    if not mod or not mod.descriptor.init_fn:
        print(f"  {FAIL} service_registry module not found")
        return False

    try:
        registry = mod.descriptor.init_fn()
        print(f"  {PASS} init_fn executed: type={type(registry).__name__}")

        agent_ids = ["tiewei", "yiku", "tianshu", "lianli", "huasheng", "wanxiang"]
        for aid in agent_ids:
            registry.register(aid, name=aid, host="127.0.0.1", port=8800 + hash(aid) % 100,
                            layer="L2", capabilities=["test", aid])

        services = registry.discover()
        assert len(services) == len(agent_ids)
        print(f"  {PASS} register {len(agent_ids)} agents: discovered {len(services)}")

        assert registry.heartbeat("tiewei")
        assert registry.get_service("tiewei").is_alive()
        print(f"  {PASS} heartbeat + alive check")

        stats = registry.get_stats()
        print(f"  {PASS} stats: {stats['total_services']} services, {stats['online_count']} online")

        registry.stop()
        return True
    except Exception as e:
        print(f"  {FAIL} {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_resilience_manager_init():
    """验证韧性管理器在容器中初始化"""
    print(f"\n{SEP}")
    print("4) ResilienceManager — Container Initialization Test")
    print(f"{SEP}")

    from core.shared.tianji_container import build_container

    container = build_container()
    mod = container._modules.get("resilience_manager")

    if not mod or not mod.descriptor.init_fn:
        print(f"  {FAIL} resilience_manager module not found")
        return False

    try:
        rm = mod.descriptor.init_fn()
        print(f"  {PASS} init_fn executed: type={type(rm).__name__}")

        rm.configure_service("tiewei", rate=100, burst=10, failure_threshold=3, fallback={"error": "gate_down"})
        rm.configure_service("yiku", rate=50, burst=5, failure_threshold=2, fallback={"error": "memory_down"})

        assert rm.request("tiewei")
        rm.success("tiewei")
        print(f"  {PASS} tiewei: request+success OK")

        for _ in range(3):
            if rm.request("yiku"):
                rm.failure("yiku")

        cb_state = rm.get_circuit_state("yiku")
        assert cb_state == "open"
        print(f"  {PASS} yiku: circuit open confirmed (state={cb_state})")

        fallback = rm.fallback("yiku")
        assert fallback == {"error": "memory_down"}
        print(f"  {PASS} yiku: fallback returned={fallback}")

        stats = rm.get_stats()
        assert stats["total_services"] == 2
        print(f"  {PASS} stats: {stats['total_services']} services configured")

        return True
    except Exception as e:
        print(f"  {FAIL} {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_cross_module_integration():
    """验证跨模块集成: Events through bus from registry + resilience"""
    print(f"\n{SEP}")
    print("5) Cross-Module Integration: Bus + Registry + Resilience")
    print(f"{SEP}")

    from core.shared.tianji_container import build_container

    container = build_container()

    try:
        bus_mod = container._modules.get("lingjing_bus")
        reg_mod = container._modules.get("service_registry")
        res_mod = container._modules.get("resilience_manager")

        if not all([bus_mod, reg_mod, res_mod]):
            missing = [n for n, m in [("bus", bus_mod), ("reg", reg_mod), ("res", res_mod)] if not m]
            print(f"  {FAIL} Missing modules: {missing}")
            return False

        from core.processors.evolution_bus import EvolutionBus as LB
        from core.shared.service_registry import ServiceRegistry
        from core.enforcement.resilience import ResilienceManager

        bus = LB()
        reg = ServiceRegistry(event_bus=bus)
        rm = ResilienceManager(event_bus=bus)

        captured = {"service_registered": [], "circuit_state_change": [], "rate_limited": []}

        for event_type in captured:
            bus.subscribe(f"cross_{event_type}", event_type, lambda e, et=event_type: captured[et].append(e))

        reg.register("test_mod", name="TestModule", host="127.0.0.1", port=9999, layer="L2")
        time.sleep(0.1)

        rm.configure_service("test_mod", rate=1, burst=0, failure_threshold=2)
        for _ in range(20):
            rm.request("test_mod")
        time.sleep(0.1)

        all_events = sum(len(v) for v in captured.values())
        print(f"  Events captured: service_registered={len(captured['service_registered'])}, "
              f"rate_limited={len(captured['rate_limited'])}, circuit={len(captured['circuit_state_change'])}")
        print(f"  {PASS if all_events > 0 else FAIL} Cross-module events: {all_events} total")

        bus.shutdown()
        reg.stop()
        return all_events > 0
    except Exception as e:
        print(f"  {FAIL} {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_exe_availability():
    """检查已打包的EXE文件"""
    print(f"\n{SEP}")
    print("6) MCP Server EXE Deployment Verification")
    print(f"{SEP}")

    dist_dir = PROJECT_ROOT / "dist"
    exe_locations = {
        "天机-忆库": dist_dir / "天机-忆库" / "天机-忆库.exe",
        "天机-执行器": dist_dir / "天机-执行器" / "天机-执行器.exe",
        "天机-洞察": dist_dir / "天机-洞察" / "天机-洞察.exe",
        "天机-调度": dist_dir / "天机-调度" / "天机-调度.exe",
        "天机-运维": dist_dir / "天机-运维" / "天机-运维.exe",
        "天机-铁卫": dist_dir / "天机-铁卫" / "天机-铁卫.exe",
    }

    checks = {}
    for name, path in exe_locations.items():
        exists = path.exists()
        size_mb = round(path.stat().st_size / 1024 / 1024, 1) if exists else 0
        checks[name] = {"exists": exists, "size_mb": size_mb}
        print(f"  {PASS if exists else FAIL} {name}: {'EXISTS' if exists else 'MISSING'} ({size_mb}MB)")

    existing = sum(1 for c in checks.values() if c["exists"])
    print(f"  Summary: {existing}/{len(exe_locations)} EXEs found")

    RESULT["exe_deployment"] = {"passed": existing >= 1, "exes": checks, "total": len(exe_locations), "found": existing}
    return existing >= 1


def main():
    print(SEP)
    print("Tianji v8.2 Lingjing Distributed — Container Integration Verification")
    print(SEP)
    print(f"Time: {datetime.now().isoformat()}")

    tests = {
        "module_imports": ("Module Imports", test_module_imports),
        "container_registration": ("Container Registration", test_container_init),
        "lingjing_bus_init": ("LingjingBus Init", test_lingjing_bus_init),
        "service_registry_init": ("ServiceRegistry Init", test_service_registry_init),
        "resilience_manager_init": ("ResilienceManager Init", test_resilience_manager_init),
        "cross_module_integration": ("Cross-Module Integration", test_cross_module_integration),
        "exe_availability": ("MCP EXE Deployment", test_exe_availability),
    }

    results = {}
    for key, (label, fn) in tests.items():
        try:
            results[key] = fn()
            results[f"{key}_label"] = label
        except Exception as e:
            print(f"  {FAIL} {label}: CRASH - {e}")
            import traceback
            traceback.print_exc()
            results[key] = False
            results[f"{key}_label"] = label

    RESULT["test_results"] = {k: v for k, v in results.items() if not k.endswith("_label")}

    total = len(tests)
    passed = sum(1 for k, v in results.items() if not k.endswith("_label") and v)
    failed = total - passed

    print(f"\n{SEP}")
    print(f"INTEGRATION VERDICT")
    print(f"{SEP}")

    for key, (label, _fn) in tests.items():
        status = "[OK]" if results[key] else "[FAIL]"
        print(f"  {status} {label}")

    print(f"\n  Total: {passed}/{total} passed, {failed} failed")

    if passed == total:
        print(f"  >>> Lingjing Integration: COMPLETE [100%] <<<")
    elif passed >= total * 0.7:
        print(f"  >>> Lingjing Integration: PARTIAL [{round(passed/total*100)}%] <<<")
    else:
        print(f"  >>> Lingjing Integration: INSUFFICIENT [{round(passed/total*100)}%] <<<")

    report_dir = PROJECT_ROOT / "tests" / "reports"
    report_path = report_dir / f"v8.2_lingjing_integration_audit_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
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
