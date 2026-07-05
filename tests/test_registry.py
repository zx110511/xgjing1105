import sys

sys.path.insert(0, r"d:\元初系统\天机v9.1")

import pytest

from core.orchestration.registry import (
    CapabilityRegistry,
    _build_unified_matrix,
    _fill_defaults,
)


class TestDeepCopyIndependence:
    """验证deepcopy修复：每个Agent的clear_metrics和topology_preference独立"""

    def test_clear_metrics_independence(self):
        reg = CapabilityRegistry()
        agent1 = reg.get_agent("tianshu")
        agent2 = reg.get_agent("yiku")

        original_value = agent1["clear_metrics"]["cost"]["token_usage"]
        agent1["clear_metrics"]["cost"]["token_usage"] = 100

        assert agent2["clear_metrics"]["cost"]["token_usage"] == original_value, (
            "clear_metrics未独立，deepcopy修复失败"
        )

    def test_topology_preference_independence(self):
        reg = CapabilityRegistry()
        agent1 = reg.get_agent("tianshu")
        agent2 = reg.get_agent("yiku")

        agent1["topology_preference"]["preferred"] = ["parallel"]

        assert agent2["topology_preference"]["preferred"] == ["sequential"], (
            "topology_preference未独立，deepcopy修复失败"
        )


class TestFindBySource:
    """验证按来源过滤功能"""

    def test_find_tianji_agents(self):
        reg = CapabilityRegistry()
        tianji_agents = reg.find_by_source("tianji")
        assert len(tianji_agents) >= 20, f"天机Agent数量不足: {len(tianji_agents)}"
        assert "tianshu" in tianji_agents
        assert "yiku" in tianji_agents

    def test_find_trae_official_agents(self):
        reg = CapabilityRegistry()
        official_agents = reg.find_by_source("trae-official")
        assert len(official_agents) == 7, (
            f"Trae官方Agent数量不对: {len(official_agents)}"
        )
        assert "ui-designer" in official_agents
        assert "frontend-architect" in official_agents
        assert "backend-architect" in official_agents

    def test_find_trae_builtin_agents(self):
        reg = CapabilityRegistry()
        builtin_agents = reg.find_by_source("trae-builtin")
        assert len(builtin_agents) == 2, f"Trae内置Agent数量不对: {len(builtin_agents)}"
        assert "trae-chat" in builtin_agents
        assert "trae-agent" in builtin_agents

    def test_find_invalid_source(self):
        reg = CapabilityRegistry()
        result = reg.find_by_source("invalid-source")
        assert result == [], f"无效来源应返回空列表: {result}"


class TestDefaultValueFilling:
    """验证默认值填充功能"""

    def test_fill_missing_clear_metrics(self):
        agent_info = {"name": "Test"}
        result = _fill_defaults(agent_info)
        assert "clear_metrics" in result
        assert result["clear_metrics"]["cost"]["token_usage"] == 0

    def test_fill_missing_topology_preference(self):
        agent_info = {"name": "Test"}
        result = _fill_defaults(agent_info)
        assert "topology_preference" in result
        assert result["topology_preference"]["preferred"] == ["sequential"]

    def test_fill_missing_source(self):
        agent_info = {"name": "Test"}
        result = _fill_defaults(agent_info)
        assert result["source"] == "tianji"

    def test_fill_missing_workflow_blueprint_ids(self):
        agent_info = {"name": "Test"}
        result = _fill_defaults(agent_info)
        assert result["workflow_blueprint_ids"] == []

    def test_preserve_existing_fields(self):
        agent_info = {
            "name": "Test",
            "source": "trae-official",
            "clear_metrics": {"cost": {"token_usage": 50}},
        }
        result = _fill_defaults(agent_info)
        assert result["source"] == "trae-official"
        assert result["clear_metrics"]["cost"]["token_usage"] == 50


class TestRegistryMethods:
    """验证CapabilityRegistry各种方法"""

    def test_exists(self):
        reg = CapabilityRegistry()
        assert reg.exists("tianshu") is True
        assert reg.exists("nonexistent-agent") is False

    def test_get_name(self):
        reg = CapabilityRegistry()
        assert reg.get_name("tianshu") == "天枢"
        assert reg.get_name("nonexistent") == "nonexistent"

    def test_get_emoji(self):
        reg = CapabilityRegistry()
        assert reg.get_emoji("tianji") == "🏛️"
        assert reg.get_emoji("nonexistent") == "🤖"

    def test_get_source(self):
        reg = CapabilityRegistry()
        assert reg.get_source("tianshu") == "tianji"
        assert reg.get_source("ui-designer") == "trae-official"
        assert reg.get_source("trae-chat") == "trae-builtin"

    def test_get_clear_metrics(self):
        reg = CapabilityRegistry()
        metrics = reg.get_clear_metrics("tianshu")
        assert "cost" in metrics
        assert "latency" in metrics
        assert "efficacy" in metrics
        assert "assurance" in metrics
        assert "reliability" in metrics

    def test_get_topology_preference(self):
        reg = CapabilityRegistry()
        pref = reg.get_topology_preference("tianshu")
        assert "preferred" in pref
        assert "compatible" in pref
        assert "avoid" in pref

    def test_find_by_capability(self):
        reg = CapabilityRegistry()
        agents = reg.find_by_capability("编排")
        assert "tianshu" in agents

    def test_find_by_layer(self):
        reg = CapabilityRegistry()
        l2_agents = reg.find_by_layer("L2")
        assert "tianshu" in l2_agents
        assert "wenzong" in l2_agents

    def test_find_by_tool(self):
        reg = CapabilityRegistry()
        agents = reg.find_by_tool("memory_recall")
        assert len(agents) > 0


class TestRegistryLoadFailure:
    """验证注册表加载失败时的回退机制"""

    def test_load_empty_registry(self):
        import os
        import shutil
        import tempfile

        original_dir = os.path.join(os.path.dirname(__file__), "..", ".trae", "agents")
        backup_dir = tempfile.mkdtemp()

        try:
            registry_path = os.path.join(original_dir, "_AGENT_REGISTRY.json")
            backup_path = os.path.join(backup_dir, "_AGENT_REGISTRY.json")
            shutil.copy(registry_path, backup_path)

            os.remove(registry_path)
            matrix = _build_unified_matrix()

            assert len(matrix) >= 24, f"回退矩阵Agent数量不足: {len(matrix)}"
            assert "tianshu" in matrix
            assert "yiku" in matrix
        finally:
            if os.path.exists(backup_path):
                shutil.copy(backup_path, registry_path)
            shutil.rmtree(backup_dir, ignore_errors=True)


class TestRegistryIntegration:
    """集成测试：验证完整注册表加载"""

    def test_total_agent_count(self):
        reg = CapabilityRegistry()
        total = len(reg.list_agents())
        assert total == 33, f"总Agent数量不对: {total}"

    def test_all_agents_have_required_fields(self):
        reg = CapabilityRegistry()
        required_fields = [
            "source",
            "clear_metrics",
            "topology_preference",
            "workflow_blueprint_ids",
        ]
        for aid in reg.list_agents():
            agent = reg.get_agent(aid)
            for field in required_fields:
                assert field in agent, f"{aid} 缺失字段: {field}"

    def test_list_all_with_source(self):
        reg = CapabilityRegistry()
        result = reg.list_all_with_source()
        assert len(result) == 33
        for item in result:
            assert "agent_id" in item
            assert "name" in item
            assert "source" in item


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
