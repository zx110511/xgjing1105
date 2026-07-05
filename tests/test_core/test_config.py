"""
tests/test_core/test_config.py - 配置模块完整测试套件
覆盖: ICMEConfig/MemoryLayerConfig/QualityGateConfig/StoragePathConfig/ConfigManager/SYSTEM_IDENTITY
"""
import pytest
import os
from pathlib import Path
from unittest.mock import patch

from core.shared.config import (
    ICMEConfig, DEFAULT_CONFIG, MemoryLayerConfig, QualityGateConfig,
    PromotionScoreWeights, StoragePathConfig, ConfigManager,
    SYSTEM_IDENTITY, AI_MEMORY_ROOT, MEMORY_DATA_PATH,
    get_python_executable,
)


# ============================================================
# TestMemoryLayerConfig
# ============================================================

class TestMemoryLayerConfig:
    """MemoryLayerConfig数据类测试"""

    def test_create(self):
        layer = MemoryLayerConfig(
            name="test_layer", layer_index=0,
            max_size_bytes=1024, max_entries=100,
            capacity_threshold=0.8,
            accumulation_threshold_bytes=512,
            accumulation_threshold_entries=50,
            hard_cap_bytes=2048,
            min_consolidation_interval_seconds=30.0,
            priority="medium",
            description="测试层",
        )
        assert layer.name == "test_layer"
        assert layer.max_size_bytes == 1024

    def test_max_size_mb(self):
        layer = MemoryLayerConfig(
            name="test", layer_index=0,
            max_size_bytes=10 * 1024 * 1024,
            max_entries=100, capacity_threshold=0.8,
            accumulation_threshold_bytes=1024,
            accumulation_threshold_entries=10,
            hard_cap_bytes=20 * 1024 * 1024,
            min_consolidation_interval_seconds=30,
            priority="medium", description="",
        )
        assert abs(layer.max_size_mb - 10.0) < 0.01

    def test_accumulation_threshold_mb(self):
        layer = MemoryLayerConfig(
            name="test", layer_index=0,
            max_size_bytes=1024, max_entries=100,
            capacity_threshold=0.8,
            accumulation_threshold_bytes=5 * 1024 * 1024,
            accumulation_threshold_entries=10,
            hard_cap_bytes=2048,
            min_consolidation_interval_seconds=30,
            priority="medium", description="",
        )
        assert abs(layer.accumulation_threshold_mb - 5.0) < 0.01

    def test_hard_cap_mb(self):
        layer = MemoryLayerConfig(
            name="test", layer_index=0,
            max_size_bytes=1024, max_entries=100,
            capacity_threshold=0.8,
            accumulation_threshold_bytes=512,
            accumulation_threshold_entries=10,
            hard_cap_bytes=50 * 1024 * 1024,
            min_consolidation_interval_seconds=30,
            priority="medium", description="",
        )
        assert abs(layer.hard_cap_mb - 50.0) < 0.01


# ============================================================
# TestQualityGateConfig
# ============================================================

class TestQualityGateConfig:
    """QualityGateConfig测试"""

    def test_defaults(self):
        qg = QualityGateConfig()
        assert qg.min_content_length >= 0
        assert 0 < qg.max_similarity_for_duplicate <= 1
        assert 0 < qg.minimum_value_score_for_direct_write <= 1
        assert isinstance(qg.noise_patterns, list)
        assert isinstance(qg.require_tags_for_layers, list)

    def test_custom_values(self):
        qg = QualityGateConfig(
            min_content_length=20,
            max_similarity_for_duplicate=0.9,
            minimum_value_score_for_direct_write=0.5,
        )
        assert qg.min_content_length == 20
        assert qg.max_similarity_for_duplicate == 0.9


# ============================================================
# TestICMEConfig
# ============================================================

class TestICMEConfig:
    """ICMEConfig核心配置测试"""

    def test_default_config_exists(self):
        assert DEFAULT_CONFIG is not None
        assert isinstance(DEFAULT_CONFIG, ICMEConfig)

    def test_six_layers(self):
        assert len(DEFAULT_CONFIG.layers) == 6
        names = [l.name for l in DEFAULT_CONFIG.layers]
        assert names == ["sensory", "working", "short_term", "episodic", "semantic", "meta"]

    def test_get_layer(self):
        layer = DEFAULT_CONFIG.get_layer("working")
        assert layer is not None
        assert layer.name == "working"

    def test_get_layer_nonexistent(self):
        layer = DEFAULT_CONFIG.get_layer("nonexistent")
        assert layer is None

    def test_get_next_layer(self):
        next_layer = DEFAULT_CONFIG.get_next_layer("sensory")
        assert next_layer is not None
        assert next_layer.name == "working"

    def test_get_next_layer_meta(self):
        next_layer = DEFAULT_CONFIG.get_next_layer("meta")
        assert next_layer is None

    def test_get_prev_layer(self):
        prev = DEFAULT_CONFIG.get_prev_layer("episodic")
        assert prev is not None
        assert prev.name == "short_term"

    def test_get_prev_layer_sensory(self):
        prev = DEFAULT_CONFIG.get_prev_layer("sensory")
        assert prev is None

    def test_get_layer_index(self):
        assert DEFAULT_CONFIG.get_layer_index("sensory") == 0
        assert DEFAULT_CONFIG.get_layer_index("meta") == 5
        assert DEFAULT_CONFIG.get_layer_index("nonexistent") == -1

    def test_data_path(self):
        assert DEFAULT_CONFIG.data_path is not None

    def test_quality_gate_config(self):
        assert isinstance(DEFAULT_CONFIG.quality_gate, QualityGateConfig)

    def test_promotion_weights(self):
        assert isinstance(DEFAULT_CONFIG.promotion_weights, PromotionScoreWeights)

    def test_custom_config(self, tmp_path):
        config = ICMEConfig(data_path=tmp_path / "custom_memory")
        assert config.data_path == tmp_path / "custom_memory"
        assert len(config.layers) == 6


# ============================================================
# TestStoragePathConfig
# ============================================================

class TestStoragePathConfig:
    """StoragePathConfig存储路径测试"""

    def test_15_sub_paths(self):
        sp = StoragePathConfig()
        assert len(sp.sub_paths) == 15

    def test_ensure_creates_dirs(self, tmp_path):
        sp = StoragePathConfig(root=tmp_path / "storage_test")
        created = sp.ensure()
        assert len(created) == 15
        for name, path in created.items():
            assert path.exists()

    def test_validate(self, tmp_path):
        sp = StoragePathConfig(root=tmp_path / "val_test")
        sp.ensure()
        result = sp.validate()
        assert "root" in result
        assert "issues" in result

    def test_audit(self, tmp_path):
        sp = StoragePathConfig(root=tmp_path / "audit_test")
        sp.ensure()
        result = sp.audit()
        assert "violations" in result
        assert "clean" in result


# ============================================================
# TestConfigManager
# ============================================================

class TestConfigManager:
    """ConfigManager配置管理器测试"""

    def test_create_default(self):
        cm = ConfigManager()
        assert cm.config is not None
        assert isinstance(cm.config, ICMEConfig)

    def test_create_custom(self, tmp_path):
        config = ICMEConfig(data_path=tmp_path / "cm_test")
        cm = ConfigManager(config=config)
        assert cm.config.data_path == tmp_path / "cm_test"

    def test_storage_property(self, tmp_path):
        config = ICMEConfig(data_path=tmp_path / "cm_storage")
        cm = ConfigManager(config=config)
        assert isinstance(cm.storage, StoragePathConfig)

    def test_ensure_storage(self, tmp_path):
        config = ICMEConfig(data_path=tmp_path / "cm_ensure")
        cm = ConfigManager(config=config)
        paths = cm.ensure_storage()
        assert isinstance(paths, dict)

    def test_validate_storage(self, tmp_path):
        config = ICMEConfig(data_path=tmp_path / "cm_validate")
        cm = ConfigManager(config=config)
        cm.ensure_storage()
        result = cm.validate_storage()
        assert isinstance(result, dict)

    def test_audit_storage(self, tmp_path):
        config = ICMEConfig(data_path=tmp_path / "cm_audit")
        cm = ConfigManager(config=config)
        cm.ensure_storage()
        result = cm.audit_storage()
        assert isinstance(result, dict)

    def test_update_config(self, tmp_path):
        config = ICMEConfig(data_path=tmp_path / "cm_update")
        cm = ConfigManager(config=config)
        result = cm.update_config({"consolidation_interval_minutes": 10})
        assert isinstance(result, dict)
        assert config.consolidation_interval_minutes == 10

    def test_update_config_multiple_keys(self, tmp_path):
        config = ICMEConfig(data_path=tmp_path / "cm_update2")
        cm = ConfigManager(config=config)
        result = cm.update_config({
            "consolidation_interval_minutes": 15,
            "session_timeout_minutes": 120,
        })
        assert result["changes"] == 2
        assert config.consolidation_interval_minutes == 15
        assert config.session_timeout_minutes == 120

    def test_update_config_invalid_key(self, tmp_path):
        config = ICMEConfig(data_path=tmp_path / "cm_update3")
        cm = ConfigManager(config=config)
        result = cm.update_config({"nonexistent_key": 999})
        assert result["changes"] == 1  # hasattr returns False, but dict len is still 1

    def test_get_layer_config(self, tmp_path):
        config = ICMEConfig(data_path=tmp_path / "cm_layer")
        cm = ConfigManager(config=config)
        layer = cm.get_layer_config("working")
        assert layer is not None
        assert layer.name == "working"

    def test_get_layer_config_nonexistent(self, tmp_path):
        config = ICMEConfig(data_path=tmp_path / "cm_layer2")
        cm = ConfigManager(config=config)
        layer = cm.get_layer_config("nonexistent")
        assert layer is None

    def test_health(self, tmp_path):
        config = ICMEConfig(data_path=tmp_path / "cm_health")
        cm = ConfigManager(config=config)
        health = cm.health()
        assert health["status"] == "healthy"
        assert health["storage_accessible"] is True
        assert health["layers_configured"] == 6
        assert "version" in health
        assert "edition" in health
        assert "consolidation_interval_minutes" in health

    def test_get_stats(self, tmp_path):
        config = ICMEConfig(data_path=tmp_path / "cm_stats")
        cm = ConfigManager(config=config)
        stats = cm.get_stats()
        assert stats["version"] == "8.1"
        assert "change_count" in stats
        assert "error_count" in stats
        assert "layers" in stats
        assert "quality_gate" in stats
        assert "health" in stats

    def test_tick(self, tmp_path):
        config = ICMEConfig(data_path=tmp_path / "cm_tick")
        cm = ConfigManager(config=config)
        cm.tick()  # 不应崩溃

    def test_calc_config_effectiveness_ensure_storage(self, tmp_path):
        config = ICMEConfig(data_path=tmp_path / "cm_eff1")
        cm = ConfigManager(config=config)
        score = cm._calc_config_effectiveness(
            "ensure_storage", {},
            {"path_count": 20},
        )
        assert score == 0.5

    def test_calc_config_effectiveness_ensure_storage_low(self, tmp_path):
        config = ICMEConfig(data_path=tmp_path / "cm_eff2")
        cm = ConfigManager(config=config)
        score = cm._calc_config_effectiveness(
            "ensure_storage", {},
            {"path_count": 5},
        )
        assert score == -0.3

    def test_calc_config_effectiveness_validate_with_issues(self, tmp_path):
        config = ICMEConfig(data_path=tmp_path / "cm_eff3")
        cm = ConfigManager(config=config)
        score = cm._calc_config_effectiveness(
            "validate_storage", {},
            {"issues": 3},
        )
        assert abs(score - (-0.3)) < 0.01

    def test_calc_config_effectiveness_validate_no_issues(self, tmp_path):
        config = ICMEConfig(data_path=tmp_path / "cm_eff4")
        cm = ConfigManager(config=config)
        score = cm._calc_config_effectiveness(
            "validate_storage", {},
            {"issues": 0},
        )
        assert score == 0.3

    def test_calc_config_effectiveness_audit_with_violations(self, tmp_path):
        config = ICMEConfig(data_path=tmp_path / "cm_eff5")
        cm = ConfigManager(config=config)
        score = cm._calc_config_effectiveness(
            "audit_storage", {},
            {"violations": 2},
        )
        assert score == -0.3

    def test_calc_config_effectiveness_audit_clean(self, tmp_path):
        config = ICMEConfig(data_path=tmp_path / "cm_eff6")
        cm = ConfigManager(config=config)
        score = cm._calc_config_effectiveness(
            "audit_storage", {},
            {"violations": 0},
        )
        assert score == 0.4

    def test_calc_config_effectiveness_update_config(self, tmp_path):
        config = ICMEConfig(data_path=tmp_path / "cm_eff7")
        cm = ConfigManager(config=config)
        score = cm._calc_config_effectiveness(
            "update_config",
            {"session_timeout_minutes": 60},
            {"session_timeout_minutes": 70},
        )
        assert score > 0

    def test_calc_config_effectiveness_update_config_no_change(self, tmp_path):
        config = ICMEConfig(data_path=tmp_path / "cm_eff8")
        cm = ConfigManager(config=config)
        score = cm._calc_config_effectiveness(
            "update_config",
            {"session_timeout_minutes": 60},
            {"session_timeout_minutes": 60},
        )
        assert score == 0.0

    def test_calc_config_effectiveness_unknown_action(self, tmp_path):
        config = ICMEConfig(data_path=tmp_path / "cm_eff9")
        cm = ConfigManager(config=config)
        score = cm._calc_config_effectiveness("unknown_action", {}, {})
        assert score == 0.0

    def test_learn_from_config(self, tmp_path):
        config = ICMEConfig(data_path=tmp_path / "cm_learn")
        cm = ConfigManager(config=config)
        result = cm._learn_from_config(
            [1, 2, 3],
            {"avg_effectiveness": 0.5},
        )
        assert result["patterns_found"] == 3
        assert result["avg_effectiveness"] == 0.5

    def test_evolve_config_low_effectiveness(self, tmp_path):
        config = ICMEConfig(data_path=tmp_path / "cm_evo1")
        cm = ConfigManager(config=config)
        result = cm._evolve_config(
            {"avg_effectiveness": -0.5},
            {"consolidation_interval_minutes": 5},
        )
        assert "consolidation_interval_minutes" in result["rules_modified"]

    def test_evolve_config_high_effectiveness(self, tmp_path):
        config = ICMEConfig(data_path=tmp_path / "cm_evo2")
        cm = ConfigManager(config=config)
        result = cm._evolve_config(
            {"avg_effectiveness": 0.5},
            {"consolidation_interval_minutes": 10},
        )
        assert "consolidation_interval_minutes" in result["rules_modified"]

    def test_evolve_config_neutral(self, tmp_path):
        config = ICMEConfig(data_path=tmp_path / "cm_evo3")
        cm = ConfigManager(config=config)
        result = cm._evolve_config(
            {"avg_effectiveness": 0.1},
            {"consolidation_interval_minutes": 5},
        )
        assert result["rules_modified"] == {}


# ============================================================
# TestStoragePathConfigAdvanced
# ============================================================

class TestStoragePathConfigAdvanced:
    """StoragePathConfig高级测试 - 覆盖validate/audit边界"""

    def test_validate_nonexistent_root(self, tmp_path):
        """验证不存在的根目录"""
        sp = StoragePathConfig(root=tmp_path / "nonexistent")
        result = sp.validate()
        assert "issues" in result

    def test_audit_with_violations(self, tmp_path):
        """审计发现违规文件"""
        sp = StoragePathConfig(root=tmp_path / "audit_viol")
        sp.ensure()
        # 创建违规文件
        (tmp_path / "audit_viol" / "rogue_file.txt").write_text("rogue")
        result = sp.audit()
        assert result["violation_count"] >= 1
        assert not result["clean"]

    def test_audit_clean(self, tmp_path):
        """审计干净目录"""
        sp = StoragePathConfig(root=tmp_path / "audit_clean")
        sp.ensure()
        result = sp.audit()
        assert result["clean"]

    def test_ensure_idempotent(self, tmp_path):
        """重复ensure不报错"""
        sp = StoragePathConfig(root=tmp_path / "ensure_idem")
        sp.ensure()
        created2 = sp.ensure()
        assert len(created2) == 15


# ============================================================
# TestSystemIdentity
# ============================================================

class TestSystemIdentity:
    """系统身份常量测试"""

    def test_name(self):
        assert SYSTEM_IDENTITY["name"] == "天机"

    def test_version(self):
        assert SYSTEM_IDENTITY["version"] is not None
        assert len(SYSTEM_IDENTITY["version"]) > 0

    def test_port(self):
        assert SYSTEM_IDENTITY["port"] == 8771

    def test_consistency(self):
        assert "天机" in SYSTEM_IDENTITY["name"]


# ============================================================
# TestPathConstants
# ============================================================

class TestPathConstants:
    """路径常量测试"""

    def test_ai_memory_root(self):
        assert AI_MEMORY_ROOT is not None
        assert isinstance(AI_MEMORY_ROOT, Path)

    def test_memory_data_path(self):
        assert MEMORY_DATA_PATH is not None
        assert isinstance(MEMORY_DATA_PATH, Path)

    def test_get_python_executable(self):
        exe = get_python_executable()
        assert exe is not None
        assert isinstance(exe, Path)
