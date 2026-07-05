# -*- coding: utf-8-sig -*-
"""TianjiContainer 核心类 — SSS-PhaseB 瘦身后 (4026→~400行)

职责(仅保留):
  1. 模块注册与依赖拓扑排序
  2. 启动/停止/重启生命周期管理
  3. 热插拔API (unregister/dynamic_load/hot_reload)
  4. 全局状态查询与快照

已拆分至:
  - container/health.py     → 健康检查/基准测试/容量报告
  - container/signal_bus.py → 事件发射/订阅/广播
  - container/boot_registry.py → 模块启动注册配置
"""

from __future__ import annotations

import importlib
import logging
import os
import sys
import threading
import time
from collections import OrderedDict
from collections.abc import Callable
from typing import Any

from .module_lifecycle import ModuleDescriptor, ModuleInstance, ModuleState

logger = logging.getLogger("tianji.container.core")


def _log(msg: str) -> None:
    """UTF-8安全日志输出"""
    try:
        os.write(2, (msg + "\n").encode("utf-8", errors="replace"))
    except Exception:
        try:
            print(msg, file=sys.stderr, flush=True)
        except Exception:
            pass


class TianjiContainer:
    """
    天机总控容器 — 模块生命周期管理中心

    [SSS-PhaseB] 从4026行精简至~400行，健康/信号/启动注册均已拆分。
    """

    VERSION = "2.0.0"
    CONTAINER_NAME = "天机总控容器"

    def __init__(self):
        self._modules: dict[str, ModuleInstance] = {}
        self._state = ModuleState.UNINITIALIZED
        self._start_time: float | None = None
        self._lock = threading.RLock()

        # 运行时缓存 (FIFO上限100条)
        self._rt_cache: OrderedDict[str, dict] = OrderedDict()
        self._RT_CACHE_MAX_SIZE = 100

        # 性能统计
        self._perf_stats: dict[str, Any] = {
            "start_time_ms": 0.0,
            "stop_time_ms": 0.0,
            "parallel_start_used": False,
            "benchmark_results": None,
        }

        # 组合子系统 (延迟初始化)
        self._health_checker: Any = None
        self._signal_bus: Any = None

    # ──────────────────────────────────────────────
    # 子系统访问器 (懒加载委托)
    # ──────────────────────────────────────────────

    @property
    def _hc(self):
        """健康检查器 (lazy)"""
        if self._health_checker is None:
            from .health import ContainerHealthChecker
            self._health_checker = ContainerHealthChecker(self)
        return self._health_checker

    @property
    def _sb(self):
        """信号总线 (lazy)"""
        if self._signal_bus is None:
            from .signal_bus import ContainerSignalBus
            self._signal_bus = ContainerSignalBus(self)
        return self._signal_bus

    # ──────────────────────────────────────────────
    # 模块注册
    # ──────────────────────────────────────────────

    def register(self, descriptor: ModuleDescriptor) -> bool:
        with self._lock:
            if descriptor.name in self._modules:
                _log(f"[Container] 模块'{descriptor.name}'已注册，跳过")
                return False
            missing_deps = [
                dep for dep in descriptor.depends_on
                if dep not in self._modules
                and dep not in (d.descriptor.name for d in self._modules.values())
            ]
            if missing_deps:
                _log(f"[Container] '{descriptor.name}'依赖未注册: {missing_deps}")
            self._modules[descriptor.name] = ModuleInstance(descriptor=descriptor)
            _log(
                f"[Container] + {descriptor.display_name} ({descriptor.name}) "
                f"deps={descriptor.depends_on or '无'} "
                f"critical={'Y' if descriptor.critical else 'N'}"
            )
            return True

    # ──────────────────────────────────────────────
    # 依赖拓扑
    # ──────────────────────────────────────────────

    def _topological_sort(self) -> list[str]:
        """Kahn算法拓扑排序"""
        in_degree: dict[str, int] = dict.fromkeys(self._modules, 0)
        graph: dict[str, list[str]] = {name: [] for name in self._modules}

        for name, mod in self._modules.items():
            for dep in mod.descriptor.depends_on:
                if dep in self._modules:
                    graph[dep].append(name)
                    in_degree[name] += 1

        queue = [n for n, d in in_degree.items() if d == 0]
        result = []
        while queue:
            node = queue.pop(0)
            result.append(node)
            for dependent in graph.get(node, []):
                in_degree[dependent] -= 1
                if in_degree[dependent] == 0:
                    queue.append(dependent)

        if len(result) != len(self._modules):
            cycle_victims = set(self._modules.keys()) - set(result)
            _log(f"[Container] ⚠️ 检测到循环依赖，涉及: {cycle_victims}")
            result.extend(cycle_victims)  # 尽力而为

        return result

    def _compute_parallel_layers(self) -> list[list[str]]:
        """计算并行启动层级"""
        order = self._topological_sort()
        resolved = set()
        layers: list[list[str]] = []
        for name in order:
            mod = self._modules[name]
            deps_resolved = all(d in resolved for d in mod.descriptor.depends_on if d in self._modules)
            if not layers or not deps_resolved:
                layers.append([name])
            else:
                layers[-1].append(name)
            resolved.add(name)
        return layers

    # ──────────────────────────────────────────────
    # 启动 / 停止 / 重启
    # ──────────────────────────────────────────────

    def start(self, parallel: bool = True) -> bool:
        """启动所有已注册模块"""
        with self._lock:
            if self._state == ModuleState.RUNNING:
                _log("[Container] 已在运行中")
                return True
            self._state = ModuleState.INITIALIZING  # SSS-PhaseE: STARTING→INITIALIZING (枚举定义)
            self._start_time = time.time()
            self._perf_stats["start_time_ms"] = 0.0

        t0 = time.perf_counter()

        if parallel and len(self._modules) > 3:
            result = self._start_parallel()
        else:
            result = self._start_serial()

        self._perf_stats["start_time_ms"] = (time.perf_counter() - t0) * 1000
        return result

    def _start_serial(self) -> bool:
        """串行按拓扑顺序启动"""
        order = self._topological_sort()
        _log(f"[Container] 串行启动: {' → '.join(order)}")
        critical_failed = False
        for name in order:
            if not self._init_single_module(name):
                mod = self._modules[name]
                if mod.descriptor.critical:
                    critical_failed = True
        self._state = ModuleState.DEGRADED if critical_failed else ModuleState.RUNNING
        return not critical_failed

    def _start_parallel(self) -> bool:
        """并行分层启动"""
        import concurrent.futures

        layers = self._compute_parallel_layers()
        _log(f"[Container] 并行启动: {len(layers)}层, 总{len(self._modules)}模块")
        self._perf_stats["parallel_start_used"] = True
        critical_failed = False

        for layer_idx, layer in enumerate(layers):
            _log(f"[Container]   第{layer_idx + 1}层: {layer}")
            if len(layer) <= 1:
                for name in layer:
                    if not self._init_single_module(name):
                        if self._modules[name].descriptor.critical:
                            critical_failed = True
            else:
                with concurrent.futures.ThreadPoolExecutor(max_workers=min(len(layer), 8)) as exec_:
                    futures = {exec_.submit(self._init_single_module, name): name for name in layer}
                    for future in concurrent.futures.as_completed(futures):
                        # [FIX] _init_single_module返回3元组(bool,float,str)，非4元组
                        success, _, error = future.result()
                        name = futures[future]
                        if not success and self._modules[name].descriptor.critical:
                            critical_failed = True

        self._state = ModuleState.DEGRADED if critical_failed else ModuleState.RUNNING
        return not critical_failed

    def _init_single_module(self, name: str) -> tuple[bool, float, str]:
        """初始化单个模块 → (成功, 耗时ms, 错误信息)"""
        mod = self._modules[name]
        mod.state = ModuleState.INITIALIZING
        self._sb._emit_event("module_initializing", name)
        t0 = time.time()
        try:
            mod.instance = mod.descriptor.init_fn()
            mod.init_time_ms = (time.time() - t0) * 1000
            if mod.descriptor.start_fn and mod.instance is not None:
                mod.descriptor.start_fn(mod.instance)
            mod.state = ModuleState.RUNNING
            mod.error = None
            self._sb._emit_event("module_started", name)
            _log(f"[Container] ✅ {mod.descriptor.display_name} ({mod.init_time_ms:.0f}ms)")
            return True, mod.init_time_ms, ""
        except Exception as e:
            mod.state = ModuleState.FAILED
            mod.error = str(e)
            self._sb._emit_event("module_failed", name, str(e))
            _log(f"[Container] ❌ {mod.descriptor.display_name}: {e}")
            return False, (time.time() - t0) * 1000, str(e)

    def stop(self, module_stop_timeout: float = 30.0) -> bool:
        """逆序停止所有模块"""
        import concurrent.futures

        order = reversed(self._topological_sort())
        for name in order:
            mod = self._modules.get(name)
            if not mod or mod.state.__class__.__name__ not in ("RUNNING",):
                continue
            # 简化状态检查
            state_val = getattr(mod.state, 'value', None) or str(mod.state)
            if state_val not in ("running",):
                continue

            mod.state = ModuleState.STOPPING
            self._sb._emit_event("module_stopping", name)
            try:
                if mod.descriptor.stop_fn and mod.instance is not None:
                    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as _exec:
                        fut = _exec.submit(mod.descriptor.stop_fn, mod.instance)
                        try:
                            fut.result(timeout=module_stop_timeout)
                        except concurrent.futures.TimeoutError:
                            _log(f"[Container] {mod.descriptor.display_name} 停止超时")
                mod.state = ModuleState.STOPPED
                self._sb._emit_event("module_stopped", name)
                self._sb.unsubscribe_module(name)
                _log(f"[Container] ✅ {mod.descriptor.display_name} 已停止")
            except Exception as e:
                mod.state = ModuleState.FAILED
                mod.error = str(e)
                _log(f"[Container] ⚠️ {mod.descriptor.display_name} 停止异常: {e}")

        failed = sum(1 for m in self._modules.values() if getattr(m.state, 'value', '') == "failed")
        self._state = ModuleState.FAILED if failed > 0 else ModuleState.STOPPED
        _log(f"[Container] {'⚠️' if failed > 0 else ''} {self.CONTAINER_NAME} 已停止")
        return failed == 0

    def restart_failed_modules(self, include_degraded: bool = True) -> int:
        """自愈重启FAILED/DEGRADED模块"""
        with self._lock:
            candidates = [
                (n, m) for n, m in self._modules.items()
                if getattr(m.state, 'value', '') == "failed"
                or (include_degraded and getattr(m.state, 'value', '') == "degraded")
            ]
            if not candidates:
                return 0
            restored = 0
            for name, mod in candidates:
                mod.state = ModuleState.INITIALIZING
                try:
                    if mod.descriptor.init_fn:
                        mod.instance = mod.descriptor.init_fn()
                    if mod.descriptor.start_fn and mod.instance is not None:
                        mod.descriptor.start_fn(mod.instance)
                    mod.state = ModuleState.RUNNING
                    mod.error = None
                    self._sb._emit_event("module_restarted", name)
                    restored += 1
                except Exception as e:
                    mod.state = ModuleState.FAILED
                    mod.error = str(e)
            if restored:
                self._state = ModuleState.DEGRADED
            return restored

    # ──────────────────────────────────────────────
    # 热插拔 API
    # ──────────────────────────────────────────────

    def unregister(self, name: str, force: bool = False) -> bool:
        """卸载模块"""
        with self._lock:
            mod = self._modules.get(name)
            if not mod:
                return False
            reverse_deps = [
                n for n, m in self._modules.items()
                if name in getattr(m.descriptor, 'depends_on', []) and n != name
            ]
            if reverse_deps and not force:
                _log(f"[HotSwap] '{name}' 被{len(reverse_deps)}个模块依赖")
                return False
            if mod.state not in (ModuleState.STOPPED,) and mod.descriptor.stop_fn:
                try:
                    mod.descriptor.stop_fn(mod.instance)
                except Exception:
                    pass
            del self._modules[name]
            self._sb._emit_event("module_unregistered", name)
            self._recalc_state()
            return True

    def dynamic_load(self, descriptor: ModuleDescriptor) -> bool:
        """动态加载模块"""
        with self._lock:
            if descriptor.name in self._modules:
                return False
            self._modules[descriptor.name] = ModuleInstance(descriptor=descriptor)
            mod = self._modules[descriptor.name]
            mod.state = ModuleState.INITIALIZING
            try:
                mod.instance = descriptor.init_fn()
                if descriptor.start_fn and mod.instance is not None:
                    descriptor.start_fn(mod.instance)
                mod.state = ModuleState.RUNNING
                self._sb._emit_event("module_dynamic_loaded", descriptor.name)
                self._recalc_state()
                return True
            except Exception as e:
                mod.state = ModuleState.FAILED
                mod.error = str(e)
                self._recalc_state()
                return False

    def hot_reload(self, name: str) -> bool:
        """热重载模块"""
        with self._lock:
            mod = self._modules.get(name)
            if not mod:
                return False
            desc = mod.descriptor
            if getattr(mod.state, 'value', '') == "running" and desc.stop_fn:
                try:
                    desc.stop_fn(mod.instance)
                except Exception:
                    pass
            mod.state = ModuleState.INITIALIZING
            try:
                module_name = desc.init_fn.__module__
                if module_name in sys.modules:
                    importlib.reload(sys.modules[module_name])
                mod.instance = desc.init_fn()
                if desc.start_fn and mod.instance is not None:
                    desc.start_fn(mod.instance)
                mod.state = ModuleState.RUNNING
                self._sb._emit_event("module_hot_reloaded", name)
                return True
            except Exception as e:
                mod.state = ModuleState.FAILED
                mod.error = str(e)
                return False

    def _recalc_state(self) -> None:
        """重新计算容器整体状态"""
        states = [getattr(m.state, 'value', '') for m in self._modules.values()]
        if states.count("running") == len(self._modules):
            self._state = ModuleState.RUNNING
        elif "failed" in states:
            self._state = ModuleState.DEGRADED
        elif states:
            self._state = ModuleState.RUNNING
        else:
            self._state = ModuleState.STOPPED

    # ──────────────────────────────────────────────
    # 状态查询
    # ──────────────────────────────────────────────

    @property
    def state(self) -> ModuleState:
        return self._state

    @property
    def is_running(self) -> bool:
        s = getattr(self._state, 'value', '')
        return s in ("running", "degraded")

    def snapshot(self) -> dict[str, Any]:
        """全量快照"""
        now = time.time()
        with self._lock:
            return {
                "timestamp": now,
                "container_state": getattr(self._state, 'value', ''),
                "uptime_seconds": now - self._start_time if self._start_time else 0,
                "modules": {
                    name: {
                        "name": name,
                        "display_name": mod.descriptor.display_name,
                        "state": getattr(mod.state, 'value', ''),
                        "critical": mod.descriptor.critical,
                        "error": mod.error,
                    }
                    for name, mod in self._modules.items()
                },
                "total": len(self._modules),
            }

    # ──────────────────────────────────────────────
    # 委托方法 (健康/信号 — 实际实现在子模块)
    # ──────────────────────────────────────────────

    def health(self) -> dict[str, Any]:
        return self._hc.health()

    def health_parallel(self, timeout: float = 10.0) -> dict[str, Any]:
        return self._hc.health_parallel(timeout)

    def benchmark(self, iterations: int = 10) -> dict[str, Any]:
        return self._hc.benchmark(iterations)

    def capacity_report(self) -> dict[str, Any]:
        return self._hc.capacity_report()

    def dependency_graph(self) -> dict[str, Any]:
        return self._hc.dependency_graph()

    def _emit_event(self, event_type: str, target: str = "", detail: str = "") -> None:
        self._sb._emit_event(event_type, target, detail)

    def subscribe(self, listener: Callable) -> None:
        self._sb.subscribe(listener)

    def unsubscribe(self, listener: Callable) -> None:
        self._sb.unsubscribe(listener)

    # ──────────────────────────────────────────────
    # 运行时缓存
    # ──────────────────────────────────────────────

    def cache_put(self, key: str, value: dict) -> None:
        """FIFO运行时缓存写入"""
        if key in self._rt_cache:
            del self._rt_cache[key]
        self._rt_cache[key] = value
        while len(self._rt_cache) > self._RT_CACHE_MAX_SIZE:
            self._rt_cache.popitem(last=False)

    def cache_get(self, key: str, default=None):
        return self._rt_cache.get(key, default)

    def __len__(self) -> int:
        return len(self._modules)

    def __contains__(self, name: str) -> bool:
        return name in self._modules

    def __iter__(self):
        return iter(self._modules)
