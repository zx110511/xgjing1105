# -*- coding: utf-8-sig -*-
"""存储后端性能对比  [v10-ready]

对比 IStorageEngine 后端的读写检索性能 (全部使用 tmp_path 临时目录，不污染
真实数据目录):
    - LocalJSONEngine: 写入 / 读取 / 搜索
    - TieredStorageEngine: 按层路由写入 (sensory → JSON 后端)

断言仅验证功能正确性，性能数值仅记录基线。
"""
from __future__ import annotations

import pytest

from core.storage.backends import (
    LocalJSONEngine,
    StorageEngineFactory,
    TieredStorageEngine,
)


class TestStorageBenchmark:
    """存储后端读写检索性能基准  [v10-ready]"""

    def test_json_engine_write(self, benchmark, tmp_path):
        """JSON 引擎写入 (目标 < 100ms)。"""
        engine = StorageEngineFactory.create("json", data_dir=str(tmp_path / "w"))
        entry = {"content": "benchmark", "layer": "sensory", "tags": ["perf"]}
        result = benchmark(engine.insert, entry)
        assert result  # entry_id 不为空

    def test_json_engine_read(self, benchmark, tmp_path):
        """JSON 引擎读取 (目标 < 50ms)。"""
        engine = StorageEngineFactory.create("json", data_dir=str(tmp_path / "r"))
        entry_id = engine.insert(
            {"content": "read target", "layer": "sensory", "tags": ["perf"]}
        )
        assert entry_id

        result = benchmark(engine.get, entry_id)
        assert result is not None
        assert result.get("content") == "read target"

    def test_json_engine_search(self, benchmark, tmp_path):
        """JSON 引擎搜索 (目标 < 200ms)。"""
        engine = StorageEngineFactory.create("json", data_dir=str(tmp_path / "s"))
        for i in range(50):
            engine.insert(
                {"content": f"searchable item {i}", "layer": "sensory", "tags": ["perf"]}
            )

        result = benchmark(engine.search, "searchable", limit=20)
        assert isinstance(result, list)
        assert len(result) > 0

    def test_tiered_engine_write(self, benchmark, tmp_path):
        """分层引擎写入 (按 layer 路由到 JSON 后端, 目标 < 100ms)。"""
        engine = TieredStorageEngine()
        engine.register_layer_backend(
            "sensory", LocalJSONEngine(data_dir=str(tmp_path / "tiered"))
        )
        entry = {"content": "tiered benchmark", "layer": "sensory", "tags": ["perf"]}
        result = benchmark(engine.insert, entry)
        assert result


if __name__ == "__main__":  # pragma: no cover
    pytest.main([__file__, "-v"])
