# -*- coding: utf-8-sig -*-
"""天机v10.0.1 Phase 0~4 全量集成测试 (P5-1)  [v10-ready]

覆盖 Phase 0~4 全部产物的集成验证, 内存模式运行, 不依赖外部服务/数据库:

    Section 1: MemoryCore        — ICME 六层实例化 + CRUD + 晋升 (Phase 4-1)
    Section 2: StorageBackends   — 4 后端策略化 + 工厂 (Phase 4-2)
    Section 3: CoreConfig        — 每层独立配置体系 (Phase 4-3)
    Section 4: AssetBinding      — L-Asset 三重绑定层
    Section 5: Compat Regression — Phase 0-3 兼容层 + 事件接线 + 防腐层
    Section 6: Protocols         — 共享内核 Protocol 完整性

运行方式:
    python\\python.exe -X utf8 -m pytest tests/test_phase4_integration.py -v --tb=short

架构定位: tests/ — Phase 4 全量集成测试
版本: 1.0.0
"""
from __future__ import annotations

import pytest


# ============================================================================
# Section 1: MemoryCore — ICME 六层实例化 (Phase 4-1)
# ============================================================================

class TestMemoryCore:
    """ICME 六层 MemoryCore 实例化与 CRUD/晋升验证。"""

    def test_create_all_cores(self):
        """6 层 MemoryCore 全部实例化。"""
        from core.memory_core import create_all_cores, MemoryCore

        cores = create_all_cores()
        assert len(cores) == 6
        expected = {"sensory", "working", "short_term", "episodic", "semantic", "meta"}
        assert set(cores.keys()) == expected
        for _name, core in cores.items():
            assert isinstance(core, MemoryCore)

    def test_sensory_crud(self):
        """L0 Sensory 层写读搜删。"""
        from core.memory_core import SensoryCore

        core = SensoryCore()  # 内存模式 (storage_engine=None)
        entry_id = core.write({"content": "感知层瞬时输入"})
        assert isinstance(entry_id, str) and entry_id

        got = core.read(entry_id)
        assert got is not None
        assert got["content"] == "感知层瞬时输入"
        assert got["layer"] == "sensory"

        hits = core.search("感知层")
        assert any(h.get("id") == entry_id for h in hits)

        assert core.delete(entry_id) is True
        assert core.read(entry_id) is None

    def test_working_crud(self):
        """L1 Working 层写读搜删。"""
        from core.memory_core import WorkingCore

        core = WorkingCore()
        entry_id = core.write({"content": "工作层会话上下文"})
        assert isinstance(entry_id, str) and entry_id

        got = core.read(entry_id)
        assert got is not None
        assert got["content"] == "工作层会话上下文"
        assert got["layer"] == "working"

        hits = core.search("会话")
        assert any(h.get("id") == entry_id for h in hits)

        assert core.delete(entry_id) is True
        assert core.read(entry_id) is None

    def test_episodic_promotion(self):
        """L3 Episodic 层晋升逻辑 (重要度达阈值条目晋升至 semantic)。"""
        from core.memory_core import EpisodicCore

        core = EpisodicCore()
        # 多标签 + 充足内容 + 新近 → 重要度评分高于晋升阈值 (0.6)
        for i in range(5):
            core.write(
                {
                    "content": f"重要决策记录 #{i} " + "细节" * 50,
                    "tags": ["decision", "ai", "experience", "core"],
                }
            )
        promoted = core.promote()
        assert promoted > 0
        assert core.stats()["operations"]["promotions"] == promoted

    def test_meta_no_promotion(self):
        """L5 Meta 顶层 promote 恒返回 0。"""
        from core.memory_core import MetaCore

        core = MetaCore()
        core.write({"content": "元策略: 顶层无晋升目标", "tags": ["meta"]})
        assert core.promote() == 0

    def test_core_stats(self):
        """统计信息正确性。"""
        from core.memory_core import ShortTermCore

        core = ShortTermCore()
        core.write({"content": "短期关键信息一"})
        core.write({"content": "短期关键信息二"})

        stats = core.stats()
        assert stats["layer"] == "short_term"
        assert stats["count"] == 2
        assert stats["backend"] == "memory"
        assert "operations" in stats
        assert stats["operations"]["writes"] == 2
        assert stats["max_entries"] > 0


# ============================================================================
# Section 2: StorageBackends — 存储后端策略化 (Phase 4-2)
# ============================================================================

class TestStorageBackends:
    """4 个 IStorageEngine 后端 + 工厂验证。"""

    def test_factory_available_backends(self):
        """工厂注册 4 个后端。"""
        from core.storage.backends import StorageEngineFactory

        backends = StorageEngineFactory.available_backends()
        assert {"sqlite", "json", "tiered", "remote"}.issubset(set(backends))

    def test_all_isinstance_storage_engine(self, tmp_path):
        """4 个后端全部满足 IStorageEngine 协议。"""
        from core.shared.protocols import IStorageEngine
        from core.storage.backends import (
            LocalSQLiteEngine,
            LocalJSONEngine,
            TieredStorageEngine,
            RemoteStorageEngine,
        )

        # 文件型后端使用临时路径, 保持内存隔离, 不污染真实数据目录
        engines = [
            LocalSQLiteEngine(db_path=str(tmp_path / "isinstance.db")),
            LocalJSONEngine(data_dir=str(tmp_path / "isinstance_json")),
            TieredStorageEngine(),
            RemoteStorageEngine(),
        ]
        for engine in engines:
            assert isinstance(engine, IStorageEngine)

    def test_json_engine_crud(self, tmp_path):
        """JSON 引擎完整 CRUD。"""
        from core.storage.backends import LocalJSONEngine

        engine = LocalJSONEngine(data_dir=str(tmp_path / "json_store"))
        entry_id = engine.insert(
            {"content": "JSON 引擎落地内容", "layer": "working", "tags": ["json"]}
        )
        assert isinstance(entry_id, str) and entry_id

        got = engine.get(entry_id)
        assert got is not None
        assert got["content"] == "JSON 引擎落地内容"

        hits = engine.search("JSON")
        assert any(h.get("id") == entry_id for h in hits)

        assert engine.delete(entry_id) is True
        assert engine.get(entry_id) is None

    def test_factory_create(self, tmp_path):
        """工厂 create 方法返回满足协议的引擎。"""
        from core.shared.protocols import IStorageEngine
        from core.storage.backends import StorageEngineFactory, LocalJSONEngine

        engine = StorageEngineFactory.create(
            "json", data_dir=str(tmp_path / "factory_json")
        )
        assert isinstance(engine, LocalJSONEngine)
        assert isinstance(engine, IStorageEngine)

        with pytest.raises(ValueError):
            StorageEngineFactory.create("不存在的后端")

    def test_tiered_routing(self, tmp_path):
        """分层引擎按 layer 路由到对应后端。"""
        from core.storage.backends import TieredStorageEngine, LocalJSONEngine

        working_backend = LocalJSONEngine(data_dir=str(tmp_path / "tier_working"))
        episodic_backend = LocalJSONEngine(data_dir=str(tmp_path / "tier_episodic"))

        tiered = TieredStorageEngine()
        tiered.register_layer_backend("working", working_backend)
        tiered.register_layer_backend("episodic", episodic_backend)

        wid = tiered.insert({"content": "working 路由", "layer": "working"})
        eid = tiered.insert({"content": "episodic 路由", "layer": "episodic"})

        # 路由正确性: 各条目分别落在对应后端
        assert working_backend.get(wid) is not None
        assert episodic_backend.get(eid) is not None
        assert working_backend.get(eid) is None
        assert episodic_backend.get(wid) is None

        # 跨后端读取仍可命中
        assert tiered.get(wid) is not None
        assert tiered.get(eid) is not None


# ============================================================================
# Section 3: CoreConfig — 每层独立配置体系 (Phase 4-3)
# ============================================================================

class TestCoreConfig:
    """CoreConfig / CoreConfigRegistry 配置体系验证。"""

    def test_create_default_registry(self):
        """默认 6 层配置注册表。"""
        from core.memory_core.config import CoreConfigRegistry
        from core.shared.protocols import MemoryLayer

        registry = CoreConfigRegistry.create_default()
        for layer in MemoryLayer:
            assert registry.has(layer)
            config = registry.get(layer)
            assert config.layer == layer
            ok, _reason = config.validate()
            assert ok is True
        assert len(registry.all_configs()) == 6

    def test_override_and_reset(self):
        """override 修改 + reset 恢复。"""
        from core.memory_core.config import CoreConfigRegistry
        from core.shared.protocols import MemoryLayer

        registry = CoreConfigRegistry.create_default()
        original = registry.get(MemoryLayer.WORKING).max_entries

        registry.override(MemoryLayer.WORKING, "max_entries", original + 5000)
        assert registry.get(MemoryLayer.WORKING).max_entries == original + 5000

        registry.reset(MemoryLayer.WORKING)
        assert registry.get(MemoryLayer.WORKING).max_entries == original

    def test_export_import_roundtrip(self):
        """配置树导出 → 导入往返一致。"""
        from core.memory_core.config import CoreConfigRegistry
        from core.shared.protocols import MemoryLayer

        src = CoreConfigRegistry.create_default()
        tree = src.export_config_tree()
        assert tree["layer_count"] == 6
        assert set(tree["layers"].keys()) == {m.value for m in MemoryLayer}

        dst = CoreConfigRegistry()
        dst.import_config_tree(tree)
        for layer in MemoryLayer:
            assert dst.has(layer)
            assert dst.get(layer).max_entries == src.get(layer).max_entries
            assert dst.get(layer).capacity_threshold == src.get(layer).capacity_threshold

    def test_validate_invalid_config(self):
        """非法配置被拒。"""
        from core.memory_core.config import CoreConfig, CoreConfigRegistry
        from core.shared.protocols import MemoryLayer

        bad = CoreConfig(layer=MemoryLayer.WORKING, capacity_threshold=2.0)
        ok, reason = bad.validate()
        assert ok is False
        assert reason

        registry = CoreConfigRegistry()
        with pytest.raises(ValueError):
            registry.register(MemoryLayer.WORKING, bad)


# ============================================================================
# Section 4: AssetBinding — L-Asset 三重绑定层
# ============================================================================

class TestAssetBinding:
    """AssetBindingService 三重绑定 (ID映射 / 层级 / 版本链) 验证。"""

    def test_bind_memory_asset(self):
        """绑定1: memory_id ↔ asset_id ID映射。"""
        from core.asset_binding import AssetBindingService, IAssetBindingService

        service = AssetBindingService()  # 内存模式 (无 Registry)
        assert isinstance(service, IAssetBindingService)

        asset = service.bind_memory_asset(
            "mem_001", {"content": "test", "layer": "working"}
        )
        assert asset is not None
        assert asset.memory_id == "mem_001"
        assert asset.layer == "working"

    def test_verify_triple_binding(self):
        """三重绑定验证 (初始绑定应全部合法)。"""
        from core.asset_binding import AssetBindingService

        service = AssetBindingService()
        asset = service.bind_memory_asset(
            "mem_002", {"content": "三重绑定校验", "layer": "episodic"}
        )
        result = service.verify_triple_binding(asset.asset_id)
        assert result["binding_1_valid"] is True
        assert result["binding_2_valid"] is True
        assert result["binding_3_valid"] is True
        assert result["overall_valid"] is True
        assert result["issues"] == []

    def test_repair_binding(self):
        """破损绑定修复 (非法 layer → 修正为 working)。"""
        from core.asset_binding import AssetBindingService

        service = AssetBindingService()
        asset = service.bind_memory_asset(
            "mem_003", {"content": "待修复", "layer": "working"}
        )
        # 人为破坏绑定2: 注入非法 layer (内存模式下 atom 为同一引用)
        asset.layer = "非法层级"
        repaired = service.repair_binding(asset.asset_id)
        assert repaired >= 1
        assert asset.layer == "working"

    def test_remote_stub_isinstance(self):
        """远程 stub 满足 Protocol。"""
        from core.asset_binding import RemoteAssetBinding, IAssetBindingService

        assert isinstance(RemoteAssetBinding(), IAssetBindingService)


# ============================================================================
# Section 5: Phase 0-3 兼容回归
# ============================================================================

class TestCompatRegression:
    """Phase 0-3 兼容层 / 事件接线 / 防腐层回归验证。"""

    def test_nine_compat_imports(self):
        """9 个兼容层全部 import 成功。"""
        from core.memory.engine import ICMEEngine
        from core.shared.deepseek_driver import DeepSeekDriver
        from core.memory.hybrid_engine import ICMEStorageEngine
        from core.orchestration.agent_orchestrator import AgentOrchestrator
        from core.orchestration.intelligent_scheduler import IntelligentScheduler
        from core.processors.quality_gate import QualityGate
        from core.memory.fusion_retriever import FusionRetriever
        from core.shared.llm_bridge import LLMBridge
        from core.shared.layer_router import LayerRouter

        for cls in (
            ICMEEngine,
            DeepSeekDriver,
            ICMEStorageEngine,
            AgentOrchestrator,
            IntelligentScheduler,
            QualityGate,
            FusionRetriever,
            LLMBridge,
            LayerRouter,
        ):
            assert cls is not None

    def test_event_wiring_complete(self):
        """事件接线 6 类 Wiring + 3 工厂全部可用。"""
        from core.event_wiring import (
            EngineEventWiring,
            DriverEventWiring,
            GateEventWiring,
            OrchestrationEventWiring,
            SchedulingEventWiring,
            SearchEventWiring,
            wire_core_domains,
            wire_secondary_domains,
            wire_evolution_domain,
        )

        for sym in (
            EngineEventWiring,
            DriverEventWiring,
            GateEventWiring,
            OrchestrationEventWiring,
            SchedulingEventWiring,
            SearchEventWiring,
        ):
            assert isinstance(sym, type)
        for factory in (
            wire_core_domains,
            wire_secondary_domains,
            wire_evolution_domain,
        ):
            assert callable(factory)

    def test_acl_available(self):
        """ACL 防腐层可用。"""
        from core.shared.anticorruption import AnticorruptionLayer

        acl = AnticorruptionLayer()
        assert acl is not None


# ============================================================================
# Section 6: Protocol 完整性
# ============================================================================

class TestProtocols:
    """共享内核 Protocol 完整性验证。"""

    def test_protocol_count(self):
        """Protocol 总数 ≥ 38。"""
        import core.shared.protocols as protocols

        proto_names = [n for n in protocols.__all__ if n.startswith("I")]
        assert len(proto_names) >= 38

    def test_key_protocols_runtime_checkable(self, tmp_path):
        """关键 Protocol 支持 isinstance 运行时检查。"""
        from core.shared.protocols import IStorageEngine
        from core.storage.backends import LocalJSONEngine
        from core.asset_binding import AssetBindingService, IAssetBindingService

        engine = LocalJSONEngine(data_dir=str(tmp_path / "proto_json"))
        assert isinstance(engine, IStorageEngine)
        assert isinstance(AssetBindingService(), IAssetBindingService)
