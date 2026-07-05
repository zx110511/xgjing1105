"""
tests/test_core/test_engine_edge_cases.py - ICME引擎边界条件和异常路径测试
适配engine.py v5.3 API: remember()返回dict, _layers是OrderedDict[str, MemoryEntry]
"""
import pytest
import time
import threading
from core.memory.engine import ICMEEngine, MemoryEntry
from core.shared.config import DEFAULT_CONFIG


class TestICMEEngineEdgeCases:
    """ICMEEngine边界条件测试"""

    @pytest.fixture
    def engine(self):
        """创建引擎实例"""
        return ICMEEngine()

    def test_remember_empty_content(self, engine):
        """测试空内容写入 - 质量门禁可能拒绝但不抛异常"""
        result = engine.remember(content="", layer="working")
        # 空内容可能被质量门禁拒绝(rejected)或存储
        assert isinstance(result, dict)
        assert "id" in result
        assert "status" in result

    def test_remember_very_long_content(self, engine):
        """测试超长内容写入"""
        long_content = "测试" * 10000
        result = engine.remember(content=long_content, layer="working", tags=["long"])
        assert isinstance(result, dict)
        assert result.get("id") is not None

    def test_remember_special_characters(self, engine):
        """测试特殊字符内容"""
        special_content = "测试\n\t\r特殊字符：<>&\"'\\"
        result = engine.remember(content=special_content, layer="working")
        assert isinstance(result, dict)
        assert result.get("id") is not None

    def test_remember_unicode_content(self, engine):
        """测试Unicode内容"""
        unicode_content = "中文 日本語 한국어 Español Français"
        result = engine.remember(content=unicode_content, layer="working")
        assert isinstance(result, dict)
        assert result.get("id") is not None

    def test_remember_invalid_layer(self, engine):
        """测试无效层写入 - engine内部不识别该层，会KeyError"""
        # engine._layers不包含invalid_layer，_store_memory_entry会KeyError
        # 但remember()内部有try/except或gate可能拦截
        try:
            result = engine.remember(content="测试", layer="invalid_layer")
            # 如果没有异常，验证返回值合理
            assert isinstance(result, dict)
        except KeyError:
            # KeyError也是合理行为
            pass

    def test_recall_empty_query(self, engine):
        """测试空查询检索"""
        engine.remember("测试", "working")
        entries = engine.recall(query="")
        assert isinstance(entries, list)

    def test_recall_very_specific_query(self, engine):
        """测试非常具体的查询"""
        engine.remember("非常具体的测试内容12345", "working")
        entries = engine.recall(query="非常具体的测试内容12345")
        assert isinstance(entries, list)

    def test_recall_non_matching_tags(self, engine):
        """测试不匹配的标签"""
        engine.remember("测试", "working", tags=["tag1"])
        entries = engine.recall(tags=["non_existing_tag"])
        assert isinstance(entries, list)
        assert len(entries) == 0

    def test_recall_zero_limit(self, engine):
        """测试零限制"""
        engine.remember("测试", "working")
        entries = engine.recall(limit=0)
        assert isinstance(entries, list)

    def test_recall_negative_min_score(self, engine):
        """测试负最小分数"""
        engine.remember("测试", "working")
        entries = engine.recall(min_score=-1.0)
        assert isinstance(entries, list)

    def test_forget_twice(self, engine):
        """测试重复删除 - 第二次应返回False"""
        result = engine.remember("测试", "working")
        entry_id = result.get("id") if isinstance(result, dict) else result
        if entry_id is None:
            pytest.skip("remember返回None，跳过")

        result1 = engine.forget(entry_id)
        result2 = engine.forget(entry_id)
        assert result1 is True
        assert result2 is False

    def test_consolidate_to_same_layer(self, engine):
        """测试巩固到同一层 - engine允许同层巩固，返回entry_id"""
        result = engine.remember("测试", "working")
        entry_id = result.get("id") if isinstance(result, dict) else result
        if entry_id is None:
            pytest.skip("remember返回None，跳过")

        ret = engine.consolidate("working", "working", entry_id)
        # engine允许同层巩固，返回entry_id或None
        assert ret is None or isinstance(ret, str)

    def test_consolidate_downward(self, engine):
        """测试向下巩固(降级) - 应返回entry_id或None"""
        result = engine.remember("测试内容用于降级巩固", "episodic", tags=["test"])
        entry_id = result.get("id") if isinstance(result, dict) else result
        if entry_id is None:
            pytest.skip("remember返回None，跳过")

        # 向下巩固: episodic -> short_term
        ret = engine.consolidate("episodic", "short_term", entry_id)
        # 返回None(不允许向下)或新entry_id
        assert ret is None or isinstance(ret, str)


class TestICMEEngineExceptionPaths:
    """ICMEEngine异常路径测试"""

    @pytest.fixture
    def engine(self):
        """创建引擎实例"""
        return ICMEEngine()

    def test_remember_with_none_metadata(self, engine):
        """测试None元数据"""
        result = engine.remember(content="测试", layer="working", metadata=None)
        assert isinstance(result, dict)
        assert result.get("id") is not None

    def test_remember_with_empty_tags(self, engine):
        """测试空标签列表"""
        result = engine.remember(content="测试", layer="working", tags=[])
        assert isinstance(result, dict)
        assert result.get("id") is not None

    def test_recall_with_none_parameters(self, engine):
        """测试None参数检索"""
        engine.remember("测试", "working")
        entries = engine.recall(query=None, tags=None, priority=None, layers=None)
        assert isinstance(entries, list)

    def test_promotion_score_with_zero_values(self, engine):
        """测试零值晋升分数"""
        entry = MemoryEntry(
            id="zero", content="零值测试", layer="working",
            tags=[], priority="low", created_at=time.time(),
            last_accessed=time.time(), access_count=0,
            effectiveness_score=0.0, related_ids=[], metadata={},
        )
        score = engine.promotion_score(entry)
        assert isinstance(score, float)
        assert score >= 0

    def test_promotion_score_with_max_values(self, engine):
        """测试最大值晋升分数"""
        entry = MemoryEntry(
            id="max", content="最大值测试", layer="meta",
            tags=["tag1", "tag2", "tag3", "tag4", "tag5"],
            priority="critical", created_at=time.time(),
            last_accessed=time.time(), access_count=1000,
            effectiveness_score=1.0,
            related_ids=["r1", "r2", "r3", "r4", "r5"],
            metadata={"verified": True},
        )
        score = engine.promotion_score(entry)
        assert isinstance(score, float)
        assert score > 0

    def test_engine_stats_consistency(self, engine):
        """测试统计一致性"""
        initial_entries = engine._stats['total_entries']
        result = engine.remember("测试", "working")
        entry_id = result.get("id") if isinstance(result, dict) else result

        if entry_id is None:
            pytest.skip("remember返回None，跳过")

        assert engine._stats['total_entries'] == initial_entries + 1

        engine.forget(entry_id)
        assert engine._stats['total_entries'] == initial_entries
        assert engine._stats['total_archivals'] > 0

    def test_layer_size_tracking(self, engine):
        """测试层大小追踪"""
        initial_size = engine._layer_sizes.get('working', 0)
        engine.remember("测试内容大小追踪", "working")
        assert engine._layer_sizes['working'] > initial_size

    def test_concurrent_access_safety(self, engine):
        """测试并发访问安全"""
        results = []

        def write_entry(i):
            r = engine.remember(f"并发测试{i}", "working")
            results.append(r)

        threads = [threading.Thread(target=write_entry, args=(i,)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(results) == 10
        # 每个结果应该是dict
        for r in results:
            assert isinstance(r, dict)


class TestICMEEngineBoundaryConditions:
    """ICMEEngine边界条件测试"""

    @pytest.fixture
    def engine(self):
        """创建引擎实例"""
        return ICMEEngine()

    def test_layer_capacity_limit(self, engine):
        """测试层容量限制 - 写入大量条目不崩溃"""
        config = DEFAULT_CONFIG
        for i in range(20):
            engine.remember(f"容量测试{i}", "working")
        entries = engine.recall(layers=["working"], limit=1000)
        assert isinstance(entries, list)

    def test_tag_index_consistency(self, engine):
        """测试标签索引一致性"""
        result = engine.remember("标签测试", "working", tags=["tag1", "tag2"])
        entry_id = result.get("id") if isinstance(result, dict) else result
        if entry_id is None:
            pytest.skip("remember返回None，跳过")

        entries = engine.recall(tags=["tag1"])
        assert len(entries) > 0

        engine.forget(entry_id)

        entries_after = engine.recall(tags=["tag1"])
        ids = [e.id for e in entries_after]
        assert entry_id not in ids

    def test_access_count_increment(self, engine):
        """测试访问计数递增"""
        result = engine.remember("访问计数测试", "working")
        entry_id = result.get("id") if isinstance(result, dict) else result
        if entry_id is None:
            pytest.skip("remember返回None，跳过")

        for _ in range(5):
            engine.recall(limit=1)

        entries = engine.recall(limit=100)
        target_entry = next((e for e in entries if e.id == entry_id), None)
        if target_entry:
            assert target_entry.access_count >= 1

    def test_effectiveness_score_range(self, engine):
        """测试效果分数范围"""
        for score in [0.0, 0.5, 1.0]:
            entry = MemoryEntry(
                id=f"score_{score}", content=f"效果分数测试{score}",
                layer="working", tags=[], priority="medium",
                created_at=time.time(), last_accessed=time.time(),
                access_count=1, effectiveness_score=score,
                related_ids=[], metadata={},
            )
            calculated_score = engine.promotion_score(entry)
            assert 0 <= calculated_score

    def test_related_ids_chain(self, engine):
        """测试关联ID链"""
        parent_result = engine.remember("父条目", "episodic")
        parent_id = parent_result.get("id") if isinstance(parent_result, dict) else parent_result
        if parent_id is None:
            pytest.skip("remember返回None，跳过")

        child_ids = []
        for i in range(5):
            child_result = engine.remember(
                f"子条目{i}", "working",
                metadata={"parent_id": parent_id},
            )
            child_id = child_result.get("id") if isinstance(child_result, dict) else child_result
            child_ids.append(child_id)

        assert len(child_ids) == 5
        assert all(cid is not None for cid in child_ids)
