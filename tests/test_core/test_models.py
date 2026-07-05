"""
tests/test_core/test_models.py - Pydantic数据模型完整测试套件
覆盖: MemoryLayer/Priority/MemoryCreate/MemoryResponse/MemorySearchQuery/MemoryStats等
"""

import pytest
from core.shared.models import (
    AgentInfo,
    HealthStatus,
    MemoryCreate,
    MemoryLayer,
    MemoryResponse,
    MemorySearchQuery,
    MemoryStats,
    PlatformEvent,
    Priority,
)
from pydantic import ValidationError

# ============================================================
# TestMemoryLayer
# ============================================================


class TestMemoryLayer:
    """MemoryLayer枚举测试"""

    def test_six_layers(self):
        assert MemoryLayer.sensory == "sensory"
        assert MemoryLayer.working == "working"
        assert MemoryLayer.short_term == "short_term"
        assert MemoryLayer.episodic == "episodic"
        assert MemoryLayer.semantic == "semantic"
        assert MemoryLayer.meta == "meta"

    def test_string_conversion(self):
        assert str(MemoryLayer.working) == "MemoryLayer.working"
        assert MemoryLayer.working.value == "working"

    def test_from_string(self):
        assert MemoryLayer("working") == MemoryLayer.working
        assert MemoryLayer("episodic") == MemoryLayer.episodic


# ============================================================
# TestPriority
# ============================================================


class TestPriority:
    """Priority枚举测试"""

    def test_four_levels(self):
        assert Priority.low == "low"
        assert Priority.medium == "medium"
        assert Priority.high == "high"
        assert Priority.critical == "critical"

    def test_from_string(self):
        assert Priority("high") == Priority.high


# ============================================================
# TestMemoryCreate
# ============================================================


class TestMemoryCreate:
    """MemoryCreate请求模型测试"""

    def test_minimal_create(self):
        mc = MemoryCreate(content="测试内容")
        assert mc.content == "测试内容"
        assert mc.layer == MemoryLayer.working
        assert mc.tags == []
        assert mc.priority == Priority.medium
        assert mc.metadata == {}
        assert mc.session_id is None

    def test_full_create(self):
        mc = MemoryCreate(
            content="完整创建测试",
            layer=MemoryLayer.episodic,
            tags=["test", "full"],
            priority=Priority.high,
            metadata={"source": "unit_test"},
            session_id="sess_001",
        )
        assert mc.layer == MemoryLayer.episodic
        assert mc.priority == Priority.high
        assert mc.session_id == "sess_001"

    def test_content_required(self):
        with pytest.raises(ValidationError):
            MemoryCreate()

    def test_serialization(self):
        mc = MemoryCreate(content="序列化测试", tags=["ser"])
        data = mc.model_dump()
        assert "content" in data
        assert data["content"] == "序列化测试"


# ============================================================
# TestMemoryResponse
# ============================================================


class TestMemoryResponse:
    """MemoryResponse响应模型测试"""

    def test_create_response(self):
        resp = MemoryResponse(
            id="resp_001",
            content="响应内容",
            layer="working",
            tags=["test"],
            priority="medium",
            value_score=0.8,
            access_count=5,
            created_at=1000000.0,
            last_accessed=1000100.0,
            size_bytes=100,
        )
        assert resp.id == "resp_001"
        assert resp.value_score == 0.8

    def test_extra_fields_ignored(self):
        resp = MemoryResponse(
            id="resp_002",
            content="额外字段",
            layer="working",
            tags=[],
            priority="medium",
            value_score=0.5,
            access_count=0,
            created_at=0.0,
            last_accessed=0.0,
            size_bytes=0,
            extra_field="should_be_ignored",
        )
        assert not hasattr(resp, "extra_field")

    def test_default_metadata(self):
        resp = MemoryResponse(
            id="resp_003",
            content="默认元数据",
            layer="working",
            tags=[],
            priority="medium",
            value_score=0.5,
            access_count=0,
            created_at=0.0,
            last_accessed=0.0,
            size_bytes=0,
        )
        assert resp.metadata == {}


# ============================================================
# TestMemorySearchQuery
# ============================================================


class TestMemorySearchQuery:
    """MemorySearchQuery搜索模型测试"""

    def test_default_values(self):
        sq = MemorySearchQuery(query="test")
        assert sq.limit == 20
        assert sq.min_score == 0.1
        assert sq.semantic is True
        assert sq.layers is None
        assert sq.tags is None

    def test_custom_values(self):
        sq = MemorySearchQuery(
            query="Python",
            layers=["working", "episodic"],
            tags=["lang"],
            limit=50,
            min_score=0.5,
            semantic=False,
        )
        assert sq.limit == 50
        assert sq.min_score == 0.5

    def test_limit_range(self):
        sq = MemorySearchQuery(query="test", limit=100)
        assert sq.limit == 100
        with pytest.raises(ValidationError):
            MemorySearchQuery(query="test", limit=0)
        with pytest.raises(ValidationError):
            MemorySearchQuery(query="test", limit=101)

    def test_min_score_range(self):
        with pytest.raises(ValidationError):
            MemorySearchQuery(query="test", min_score=-0.1)
        with pytest.raises(ValidationError):
            MemorySearchQuery(query="test", min_score=1.1)


# ============================================================
# TestMemoryStats
# ============================================================


class TestMemoryStats:
    """MemoryStats统计模型测试"""

    def test_create_stats(self):
        stats = MemoryStats(
            total_entries=100,
            total_accesses=500,
            uptime_seconds=3600.0,
            layers={"working": 50, "episodic": 30, "semantic": 20},
            archive_entries=10,
            consolidations=5,
            archivals=10,
            data_path="/tmp/test",
        )
        assert stats.total_entries == 100
        assert stats.layers["working"] == 50

    def test_extra_fields_ignored(self):
        stats = MemoryStats(
            total_entries=0,
            total_accesses=0,
            uptime_seconds=0.0,
            layers={},
            archive_entries=0,
            consolidations=0,
            archivals=0,
            data_path="/tmp",
            extra="ignored",
        )
        assert not hasattr(stats, "extra")


# ============================================================
# TestAgentInfo
# ============================================================


class TestAgentInfo:
    """AgentInfo模型测试"""

    def test_create(self):
        info = AgentInfo(id="a1", name="天枢", role="orchestrator")
        assert info.name == "天枢"
        assert info.description is None

    def test_with_description(self):
        info = AgentInfo(id="a2", name="忆库", role="memory", description="记忆管理")
        assert info.description == "记忆管理"


# ============================================================
# TestPlatformEvent
# ============================================================


class TestPlatformEvent:
    """PlatformEvent模型测试"""

    def test_create(self):
        event = PlatformEvent(event_type="message", payload={"text": "hello"})
        assert event.event_type == "message"
        assert event.source == "generic"
        assert event.timestamp is None

    def test_with_timestamp(self):
        import time

        now = time.time()
        event = PlatformEvent(event_type="message", payload={}, timestamp=now)
        assert event.timestamp == now


# ============================================================
# TestHealthStatus
# ============================================================


class TestHealthStatus:
    """HealthStatus模型测试"""

    def test_create(self):
        hs = HealthStatus(
            status="healthy",
            version="9.1.0",
            engine_ready=True,
            embedding_ready=False,
            layers={},
            uptime_seconds=100.0,
        )
        assert hs.status == "healthy"
        assert hs.edition == "source"

    def test_extra_ignored(self):
        hs = HealthStatus(
            status="ok",
            version="9.0",
            engine_ready=True,
            embedding_ready=True,
            layers={},
            uptime_seconds=0.0,
            extra="ignored",
        )
        assert not hasattr(hs, "extra")
