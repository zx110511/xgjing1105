# -*- coding: utf-8-sig -*-
"""天机v10.0.1 性能基准测试本地配置 (P5-2)  [v10-ready]

核心职责:
    1. 若已安装 pytest-benchmark，直接复用其 ``benchmark`` fixture。
    2. 若未安装，提供基于 ``time.perf_counter`` 的等价回退 fixture，
       使 ``result = benchmark(func, *args, **kwargs)`` 调用方式完全兼容。
    3. 收集每个基准的耗时并在测试结束时打印基线汇总表
       (仅记录基线，PASS/SLOW 仅作参考，不导致用例失败)。

设计原则:
    - 全部内存模式: MemoryCore 默认 dict 模拟; JSON 引擎使用 tmp_path 临时目录。
    - 不硬断性能数值: 阈值仅用于汇总表的视觉标记。
"""
from __future__ import annotations

import time
from typing import Any, Callable

import pytest

# ----------------------------------------------------------------------
# pytest-benchmark 探测
# ----------------------------------------------------------------------
try:  # pragma: no cover - 取决于运行环境
    import pytest_benchmark  # noqa: F401

    HAS_PYTEST_BENCHMARK = True
except ImportError:  # pragma: no cover
    HAS_PYTEST_BENCHMARK = False


# 目标基线阈值 (秒); 键为测试名子串, 命中即套用对应阈值
_THRESHOLDS: dict[str, float] = {
    "batch_write_100": 2.0,    # 批量写入(100条) < 2s
    "batch": 2.0,
    "search": 0.200,           # 搜索(20结果) < 200ms
    "read": 0.050,             # 单条读取 < 50ms
    "write": 0.100,            # 单条写入 < 100ms
    "promote": 0.100,
}

# 基线结果收集器: [(name, stats_dict), ...]
_BASELINE_RESULTS: list[tuple[str, dict[str, float]]] = []


def _match_threshold(name: str) -> float | None:
    """按测试名匹配目标阈值 (取首个命中)。"""
    for key, value in _THRESHOLDS.items():
        if key in name:
            return value
    return None


class _SimpleBenchmark:
    """pytest-benchmark ``benchmark`` fixture 的最小兼容回退实现  [v10-ready]

    支持两种调用方式:
        - ``benchmark(func, *args, **kwargs)``
        - ``benchmark.pedantic(func, args=(), kwargs=None, rounds=N, ...)``

    返回被测函数的真实返回值，便于断言功能正确性。
    """

    def __init__(self, name: str, *, rounds: int = 30, warmup: int = 3) -> None:
        self.name = name
        self.rounds = rounds
        self.warmup = warmup
        self.stats: dict[str, float] = {}

    def _run(self, func: Callable, args: tuple, kwargs: dict) -> Any:
        # 预热 (不计时, 排除冷启动抖动)
        for _ in range(max(0, self.warmup)):
            func(*args, **kwargs)

        timings: list[float] = []
        result: Any = None
        for _ in range(max(1, self.rounds)):
            start = time.perf_counter()
            result = func(*args, **kwargs)
            timings.append(time.perf_counter() - start)

        timings.sort()
        n = len(timings)
        self.stats = {
            "min": timings[0],
            "max": timings[-1],
            "mean": sum(timings) / n,
            "median": timings[n // 2],
            "rounds": float(n),
        }
        _BASELINE_RESULTS.append((self.name, self.stats))
        return result

    def __call__(self, func: Callable, *args: Any, **kwargs: Any) -> Any:
        return self._run(func, args, kwargs)

    def pedantic(
        self,
        func: Callable,
        args: tuple = (),
        kwargs: dict | None = None,
        rounds: int = 30,
        warmup_rounds: int = 3,
        iterations: int = 1,  # noqa: ARG002 - 兼容签名
    ) -> Any:
        """兼容 pytest-benchmark 的 pedantic 调用签名。"""
        self.rounds = rounds
        self.warmup = warmup_rounds
        return self._run(func, args, kwargs or {})


if not HAS_PYTEST_BENCHMARK:

    @pytest.fixture
    def benchmark(request: pytest.FixtureRequest) -> _SimpleBenchmark:
        """time.perf_counter 回退基准 fixture  [v10-ready]

        当未安装 pytest-benchmark 时启用，提供与官方 fixture 一致的调用方式。
        """
        return _SimpleBenchmark(request.node.name)


def pytest_terminal_summary(terminalreporter, exitstatus, config) -> None:  # noqa: ARG001
    """测试结束时打印性能基线汇总表 (仅回退模式下有数据)。"""
    if not _BASELINE_RESULTS:
        return
    write = terminalreporter.write_line
    write("")
    write("=" * 78)
    write("性能基线汇总 (time.perf_counter 回退计时, 单位 ms — 仅记录基线)")
    write("-" * 78)
    write(f"{'基准名称':<40}{'min':>9}{'mean':>9}{'目标':>9}  标记")
    write("-" * 78)
    for name, stats in _BASELINE_RESULTS:
        min_ms = stats["min"] * 1000.0
        mean_ms = stats["mean"] * 1000.0
        threshold = _match_threshold(name)
        if threshold is None:
            target = "-"
            mark = ""
        else:
            target = f"{threshold * 1000.0:.0f}"
            mark = "PASS" if mean_ms <= threshold * 1000.0 else "SLOW"
        write(f"{name:<40}{min_ms:>9.3f}{mean_ms:>9.3f}{target:>9}  {mark}")
    write("=" * 78)
