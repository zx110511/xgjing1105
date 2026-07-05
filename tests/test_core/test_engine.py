"""
tests/test_core/test_engine.py - ICME引擎单元测试
测试engine.py的关键函数
"""
import pytest
from core.memory.engine import ICMEEngine


class TestICMEEngineInit:
    """ICMEEngine初始化测试"""

    def test_engine_creation_default(self):
        engine = ICMEEngine()
        assert engine is not None
        assert isinstance(engine, ICMEEngine)


class TestICMEEngineRemember:
    """remember()函数测试"""

    @pytest.fixture
    def engine(self):
        return ICMEEngine()

    def test_remember_basic(self, engine):
        result = engine.remember(
            content="测试记忆内容",
            layer="working",
            tags=["test"],
            priority="medium"
        )
        assert result is not None
        assert isinstance(result, dict)
        assert "entry_id" in result or "id" in result

    def test_remember_with_metadata(self, engine):
        result = engine.remember(
            content="带元数据的记忆",
            layer="episodic",
            tags=["test", "metadata"],
            priority="high",
            metadata={"source": "test"}
        )
        assert result is not None

    def test_remember_different_layers(self, engine):
        layers = ['sensory', 'working', 'short_term', 'episodic', 'semantic', 'meta']
        for layer in layers:
            result = engine.remember(
                content=f"测试层 {layer}",
                layer=layer,
                tags=[layer],
                priority="medium"
            )
            assert result is not None


class TestICMEEngineRecall:
    """recall()函数测试"""

    @pytest.fixture
    def engine_with_data(self):
        engine = ICMEEngine()
        for i in range(5):
            engine.remember(
                content=f"测试内容 #{i}",
                layer="working",
                tags=["test"],
                priority="medium"
            )
        return engine

    def test_recall_basic(self, engine_with_data):
        entries = engine_with_data.recall()
        assert isinstance(entries, list)

    def test_recall_with_limit(self, engine_with_data):
        entries = engine_with_data.recall(limit=3)
        assert len(entries) <= 3

    def test_recall_with_tags(self, engine_with_data):
        entries = engine_with_data.recall(tags=["test"])
        assert isinstance(entries, list)


class TestICMEEngineForget:
    """forget()函数测试"""

    @pytest.fixture
    def engine(self):
        return ICMEEngine()

    def test_forget_non_existing(self, engine):
        result = engine.forget("non_existing_id")
        assert result is False


class TestICMEEngineStats:
    """引擎统计测试"""

    def test_engine_stats(self):
        engine = ICMEEngine()
        stats = engine.stats()
        assert isinstance(stats, dict)


class TestICMEEnginePurge:
    """引擎清理测试"""

    def test_purge_layer(self):
        engine = ICMEEngine()
        count = engine.purge_layer("working")
        assert count >= 0
