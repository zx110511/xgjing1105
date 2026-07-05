# -*- coding: utf-8-sig -*-
"""TianjiContainer 健康检查子系统 — 从core.py拆分 [SSS-PhaseB]

包含: health() / health_parallel() / benchmark() / capacity_report()
      / dependency_graph() / _MonitorBridge
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from typing import Any

logger = logging.getLogger("tianji.container.health")


class ContainerHealthChecker:
    """容器健康检查器 — 从TianjiContainer拆分的健康子系统"""

    def __init__(self, container):
        self._container = container
        self._perf_stats: dict[str, Any] = {
            "last_health_check_ms": 0.0,
            "parallel_health_used": False,
        }

    def health(self) -> dict[str, Any]:
        """串行健康检查 — 遍历所有模块收集状态"""
        c = self._container
        with c._lock:
            t0 = time.time()
            running = sum(
                1 for m in c._modules.values()
                if m.state.__class__.__name__ in ("RUNNING", "DEGRADED")
                if hasattr(m.state, 'value') and m.state.value in ("running", "degraded")
                or True
            )
            # 简化: 直接统计状态
            running = sum(1 for m in c._modules.values() if hasattr(m.state, 'value') and m.state.value == "running")
            degraded = sum(1 for m in c._modules.values() if hasattr(m.state, 'value') and m.state.value == "degraded")
            failed = sum(1 for m in c._modules.values() if hasattr(m.state, 'value') and m.state.value == "failed")
            total = len(c._modules)

            overall = "healthy"
            if failed > 0:
                critical_failed = any(
                    m.descriptor.critical and hasattr(m.state, 'value') and m.state.value == "failed"
                    for m in c._modules.values()
                )
                overall = "unhealthy" if critical_failed else "degraded"
            elif degraded > 0:
                overall = "degraded"

            self._perf_stats["last_health_check_ms"] = (time.time() - t0) * 1000
            return {
                "container": {
                    "name": getattr(c, 'CONTAINER_NAME', 'TianjiContainer'),
                    "version": getattr(c, 'VERSION', '1.0.0'),
                    "state": c._state.value if hasattr(c._state, 'value') else str(c._state),
                    "overall_health": overall,
                    "uptime_seconds": (time.time() - c._start_time) if c._start_time else 0,
                },
                "modules": {"total": total, "running": running, "degraded": degraded, "failed": failed},
                "perf": {"health_check_ms": self._perf_stats["last_health_check_ms"], "parallel": False},
            }

    def health_parallel(self, timeout: float = 10.0) -> dict[str, Any]:
        """并行健康检查 — ThreadPoolExecutor并发"""
        import concurrent.futures

        c = self._container
        with c._lock:
            t0 = time.time()
            module_health = {}
            health_fns = []
            for name, mod in c._modules.items():
                if mod.descriptor.health_fn and mod.instance is not None:
                    health_fns.append((name, mod))
                else:
                    state_val = mod.state.value if hasattr(mod.state, 'value') else str(mod.state)
                    module_health[name] = {"status": state_val}

            if health_fns:
                self._perf_stats["parallel_health_used"] = True
                with concurrent.futures.ThreadPoolExecutor(
                    max_workers=min(len(health_fns), 8)
                ) as executor:
                    futures = {}
                    for name, mod in health_fns:
                        futures[executor.submit(mod.descriptor.health_fn, mod.instance)] = name
                    done, not_done = concurrent.futures.wait(futures.keys(), timeout=timeout)
                    for future in done:
                        name = futures[future]
                        try:
                            module_health[name] = future.result(timeout=0)
                        except Exception as e:
                            module_health[name] = {"status": "error", "error": str(e)}
                    for future in not_done:
                        name = futures[future]
                        module_health[name] = {"status": "timeout", "timeout_s": timeout}

            running = sum(1 for m in c._modules.values() if hasattr(m.state, 'value') and m.state.value == "running")
            degraded = sum(1 for m in c._modules.values() if hasattr(m.state, 'value') and m.state.value == "degraded")
            failed = sum(1 for m in c._modules.values() if hasattr(m.state, 'value') and m.state.value == "failed")
            total = len(c._modules)

            overall = "healthy"
            if failed > 0:
                critical_failed = any(
                    m.descriptor.critical and hasattr(m.state, 'value') and m.state.value == "failed"
                    for m in c._modules.values()
                )
                overall = "unhealthy" if critical_failed else "degraded"
            elif degraded > 0:
                overall = "degraded"

            self._perf_stats["last_health_check_ms"] = (time.time() - t0) * 1000
            return {
                "container": {
                    "name": getattr(c, 'CONTAINER_NAME', 'TianjiContainer'),
                    "version": getattr(c, 'VERSION', '1.0.0'),
                    "state": c._state.value if hasattr(c._state, 'value') else str(c._state),
                    "overall_health": overall,
                    "uptime_seconds": (time.time() - c._start_time) if c._start_time else 0,
                },
                "modules": {"total": total, "running": running, "degraded": degraded, "failed": failed},
                "module_details": module_health,
                "perf": {"health_check_ms": self._perf_stats["last_health_check_ms"], "parallel": True},
            }

    def benchmark(self, iterations: int = 10) -> dict[str, Any]:
        """性能基准测试"""
        results = {"version": getattr(self._container, 'VERSION', '1.0.0'), "iterations": iterations, "tests": {}}

        t0 = time.perf_counter()
        for _ in range(iterations):
            self._container._topological_sort()
        results["tests"]["topological_sort_ms"] = ((time.perf_counter() - t0) * 1000) / iterations

        t0 = time.perf_counter()
        for _ in range(iterations):
            self._container.snapshot()
        results["tests"]["snapshot_ms"] = ((time.perf_counter() - t0) * 1000) / iterations

        health_iters = min(iterations, 3)
        t0 = time.perf_counter()
        for _ in range(health_iters):
            self.health()
        results["tests"]["health_serial_ms"] = ((time.perf_counter() - t0) * 1000) / health_iters

        t0 = time.perf_counter()
        for _ in range(health_iters):
            self.health_parallel()
        results["tests"]["health_parallel_ms"] = ((time.perf_counter() - t0) * 1000) / health_iters

        speedup = results["tests"]["health_serial_ms"] / max(results["tests"]["health_parallel_ms"], 0.01)
        results["tests"]["health_parallel_speedup"] = round(speedup, 2)
        results["capacity"] = self.capacity_report()
        results["perf_stats"] = dict(self._perf_stats)
        return results

    def capacity_report(self) -> dict[str, Any]:
        """容量报告"""
        c = self._container
        now = time.time()
        categories: dict[str, list[str]] = {}
        for name, mod in c._modules.items():
            cat = getattr(mod.descriptor, 'category', 'unknown')
            categories.setdefault(cat, []).append(name)

        init_times = {name: mod.init_time_ms for name, mod in c._modules.items() if getattr(mod, 'init_time_ms', 0) > 0}
        avg_init = sum(init_times.values()) / max(len(init_times), 1)
        max_init_name = max(init_times, key=init_times.get) if init_times else "N/A"

        critical_count = sum(1 for m in c._modules.values() if getattr(m.descriptor, 'critical', False))
        dep_count = sum(len(getattr(m.descriptor, 'depends_on', [])) for m in c._modules.values())

        return {
            "total_modules": len(c._modules),
            "categories": {cat: len(mods) for cat, mods in categories.items()},
            "critical_modules": critical_count,
            "total_dependencies": dep_count,
            "avg_init_time_ms": round(avg_init, 1),
            "max_init_time": {"module": max_init_name, "ms": round(init_times.get(max_init_name, 0), 1)},
            "uptime_seconds": now - c._start_time if c._start_time else 0,
        }

    def dependency_graph(self) -> dict[str, Any]:
        """依赖关系图"""
        c = self._container
        nodes, edges = [], []
        for name, mod in c._modules.items():
            nodes.append({
                "id": name, "display_name": getattr(mod.descriptor, 'display_name', name),
                "category": getattr(mod.descriptor, 'category', 'unknown'),
                "critical": getattr(mod.descriptor, 'critical', False),
                "state": mod.state.value if hasattr(mod.state, 'value') else str(mod.state),
            })
            for dep in getattr(mod.descriptor, 'depends_on', []):
                if dep in c._modules:
                    edges.append({"from": dep, "to": name})

        return {"nodes": nodes, "edges": edges, "total_nodes": len(nodes), "total_edges": len(edges)}
