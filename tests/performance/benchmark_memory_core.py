# -*- coding: utf-8-sig -*-
"""MemoryCore性能基准  [v10-ready]

覆盖 ICME 六层 MemoryCore 的核心读写路径 (内存 dict 模拟模式):
    - L0 Sensory / L1 Working 单条写入
    - 按 ID 单条读取
    - 批量写入 100 条
    - 晋升 (promote) 操作

断言仅验证功能正确性 (返回值非空/类型正确)，性能数值仅记录基线。
"""
from __future__ import annotations

import pytest

from core.memory_core import create_core
from core.shared.protocols import MemoryLayer


class TestMemoryCoreBenchmark:
    """MemoryCore 读写性能基准  [v10-ready]"""

    def test_sensory_write(self, benchmark):
        """L0 Sensory 单条写入 (目标 < 100ms)。"""
        core = create_core(MemoryLayer.SENSORY)
        entry = {"content": "benchmark test content", "tags": ["perf"]}
        result = benchmark(core.write, entry)
        assert result  # entry_id 不为空

    def test_working_write(self, benchmark):
        """L1 Working 单条写入 (目标 < 100ms)。"""
        core = create_core(MemoryLayer.WORKING)
        entry = {"content": "benchmark working content", "tags": ["perf"]}
        result = benchmark(core.write, entry)
        assert result

    def test_read_by_id(self, benchmark):
        """按 ID 读取单条 (目标 < 50ms)。"""
        core = create_core(MemoryLayer.WORKING)
        entry_id = core.write({"content": "read target", "tags": ["perf"]})
        assert entry_id

        result = benchmark(core.read, entry_id)
        assert result is not None
        assert result.get("content") == "read target"

    def test_batch_write_100(self, benchmark):
        """批量写入 100 条 (目标 < 2s)。"""

        def _batch_write() -> int:
            core = create_core(MemoryLayer.WORKING)
            for i in range(100):
                core.write({"content": f"batch entry {i}", "tags": ["perf", "batch"]})
            return core.count()

        result = benchmark(_batch_write)
        assert result == 100

    def test_promote(self, benchmark):
        """晋升操作性能 (返回晋升条目数, 阈值未达时为 0)。"""
        core = create_core(MemoryLayer.SENSORY)
        for i in range(50):
            core.write({"content": f"sensory entry {i}", "tags": ["perf"]})

        result = benchmark(core.promote)
        # promote 返回 int (达不到晋升阈值时为 0), 仅验证功能正确性
        assert result >= 0


if __name__ == "__main__":  # pragma: no cover
    pytest.main([__file__, "-v"])
