# -*- coding: utf-8-sig -*-
"""搜索性能基线  [v10-ready]

覆盖典型搜索场景的性能基线:
    - MemoryCore 内存模式搜索 (库内 50 条, 取 20 结果)
    - 空库搜索 (无命中)
    - 带标签过滤搜索 (JSON 引擎，支持 tags 过滤)

断言仅验证功能正确性，性能数值仅记录基线。
"""
from __future__ import annotations

import pytest

from core.memory_core import create_core
from core.shared.protocols import MemoryLayer
from core.storage.backends import StorageEngineFactory


class TestSearchBenchmark:
    """搜索性能基准  [v10-ready]"""

    def test_memory_core_search_20(self, benchmark):
        """MemoryCore 搜索 20 条 (库内 50 条, 目标 < 200ms)。"""
        core = create_core(MemoryLayer.WORKING)
        for i in range(50):
            core.write({"content": f"perfdata record {i}", "tags": ["perf"]})

        result = benchmark(core.search, "perfdata", limit=20)
        assert isinstance(result, list)
        assert len(result) == 20

    def test_search_empty(self, benchmark):
        """空库搜索 (无命中, 目标 < 200ms)。"""
        core = create_core(MemoryLayer.WORKING)
        result = benchmark(core.search, "nonexistent", limit=20)
        assert result == []

    def test_search_with_tags(self, benchmark, tmp_path):
        """带标签过滤搜索 (JSON 引擎 tags 过滤, 目标 < 200ms)。"""
        engine = StorageEngineFactory.create("json", data_dir=str(tmp_path / "tags"))
        for i in range(30):
            tag = "alpha" if i % 2 == 0 else "beta"
            engine.insert(
                {"content": f"tagged item {i}", "layer": "sensory", "tags": [tag]}
            )

        result = benchmark(engine.search, "", limit=20, tags=["alpha"])
        assert isinstance(result, list)
        assert len(result) > 0
        # 全部命中条目均应含 alpha 标签
        assert all("alpha" in row.get("tags", []) for row in result)


if __name__ == "__main__":  # pragma: no cover
    pytest.main([__file__, "-v"])
