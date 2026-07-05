import sys

sys.path.insert(0, r"d:\元初系统\天机v9.1")

import pytest

from core.orchestration.registry import CapabilityRegistry


class TestClearMetricsEvaluation:
    """验证CLEAR评估框架：Cost/Latency/Efficacy/Assurance/Reliability"""

    def test_evaluate_cost_metrics(self):
        reg = CapabilityRegistry()

        def evaluate_cost(agent_id: str) -> float:
            metrics = reg.get_clear_metrics(agent_id)
            return (
                metrics["cost"]["token_usage"] * 0.001
                + metrics["cost"]["api_calls"] * 0.1
                + metrics["cost"]["model_cost"]
            )

        tianshu_cost = evaluate_cost("tianshu")
        yiku_cost = evaluate_cost("yiku")

        assert isinstance(tianshu_cost, float)
        assert isinstance(yiku_cost, float)

    def test_evaluate_latency_metrics(self):
        reg = CapabilityRegistry()

        def evaluate_latency(agent_id: str) -> int:
            metrics = reg.get_clear_metrics(agent_id)
            return metrics["latency"]["total_ms"]

        for aid in reg.list_agents():
            latency = evaluate_latency(aid)
            assert isinstance(latency, int)
            assert latency >= 0

    def test_evaluate_efficacy_metrics(self):
        reg = CapabilityRegistry()

        def evaluate_efficacy(agent_id: str) -> float:
            metrics = reg.get_clear_metrics(agent_id)
            return (
                metrics["efficacy"]["success_rate"] * 0.5
                + metrics["efficacy"]["quality_score"] * 0.3
                + metrics["efficacy"]["coverage"] * 0.2
            )

        for aid in reg.list_agents():
            efficacy = evaluate_efficacy(aid)
            assert 0.0 <= efficacy <= 1.0

    def test_evaluate_assurance_metrics(self):
        reg = CapabilityRegistry()

        def evaluate_assurance(agent_id: str) -> float:
            metrics = reg.get_clear_metrics(agent_id)
            vulnerabilities = metrics["assurance"]["security_vulnerabilities"]
            compliance = 1.0 if metrics["assurance"]["compliance_passed"] else 0.0
            privacy_risk = metrics["assurance"]["privacy_risk"]
            return compliance - vulnerabilities * 0.1 - privacy_risk * 0.5

        for aid in reg.list_agents():
            assurance = evaluate_assurance(aid)
            assert isinstance(assurance, float)

    def test_evaluate_reliability_metrics(self):
        reg = CapabilityRegistry()

        def evaluate_reliability(agent_id: str) -> float:
            metrics = reg.get_clear_metrics(agent_id)
            return (
                metrics["reliability"]["consistency_rate"] * 0.4
                + metrics["reliability"]["recovery_rate"] * 0.3
                + metrics["reliability"]["sla_compliance"] * 0.3
            )

        for aid in reg.list_agents():
            reliability = evaluate_reliability(aid)
            assert 0.0 <= reliability <= 1.0

    def test_comprehensive_clear_score(self):
        reg = CapabilityRegistry()

        def calculate_clear_score(agent_id: str) -> float:
            metrics = reg.get_clear_metrics(agent_id)

            cost_score = 1.0 / (
                1.0
                + metrics["cost"]["token_usage"] * 0.001
                + metrics["cost"]["api_calls"] * 0.01
                + metrics["cost"]["model_cost"]
            )

            latency_score = 1.0 / (1.0 + metrics["latency"]["total_ms"] * 0.001)

            efficacy_score = (
                metrics["efficacy"]["success_rate"] * 0.5
                + metrics["efficacy"]["quality_score"] * 0.3
                + metrics["efficacy"]["coverage"] * 0.2
            )

            assurance_score = (
                (1.0 if metrics["assurance"]["compliance_passed"] else 0.5)
                - metrics["assurance"]["security_vulnerabilities"] * 0.2
                - metrics["assurance"]["privacy_risk"] * 0.3
            )

            reliability_score = (
                metrics["reliability"]["consistency_rate"] * 0.4
                + metrics["reliability"]["recovery_rate"] * 0.3
                + metrics["reliability"]["sla_compliance"] * 0.3
            )

            return (
                cost_score * 0.15
                + latency_score * 0.15
                + efficacy_score * 0.3
                + assurance_score * 0.2
                + reliability_score * 0.2
            )

        scores = {}
        for aid in reg.list_agents():
            score = calculate_clear_score(aid)
            scores[aid] = score
            assert 0.0 <= score <= 1.0, f"{aid} CLEAR分数超出范围: {score}"

        assert len(scores) == 33


class TestTopologyPreferenceMatching:
    """验证拓扑偏好匹配：根据任务特征选择最优协作模式"""

    def test_match_sequential_pattern(self):
        reg = CapabilityRegistry()

        sequential_agents = []
        for aid in reg.list_agents():
            pref = reg.get_topology_preference(aid)
            if "sequential" in pref["preferred"]:
                sequential_agents.append(aid)

        assert len(sequential_agents) > 0

    def test_match_parallel_pattern(self):
        reg = CapabilityRegistry()

        parallel_compatible = []
        for aid in reg.list_agents():
            pref = reg.get_topology_preference(aid)
            if "parallel" in pref["compatible"]:
                parallel_compatible.append(aid)

        assert len(parallel_compatible) > 0

    def test_topology_route_selection(self):
        reg = CapabilityRegistry()

        def select_topology(task_type: str):
            if task_type == "code_review":
                return "sequential"
            elif task_type == "performance_analysis":
                return "parallel"
            elif task_type == "system_design":
                return "hierarchical"
            elif task_type == "event_processing":
                return "event_driven"
            elif task_type == "continuous_improvement":
                return "evolution_loop"
            return "sequential"

        topologies = [
            "sequential",
            "parallel",
            "hierarchical",
            "event_driven",
            "evolution_loop",
        ]
        for task in [
            "code_review",
            "performance_analysis",
            "system_design",
            "event_processing",
            "continuous_improvement",
        ]:
            topology = select_topology(task)
            assert topology in topologies

    def test_agent_compatibility_check(self):
        reg = CapabilityRegistry()

        def check_compatibility(agent_id: str, topology: str) -> bool:
            pref = reg.get_topology_preference(agent_id)
            if topology in pref["avoid"]:
                return False
            if topology in pref["preferred"]:
                return True
            if topology in pref["compatible"]:
                return True
            return False

        assert check_compatibility("tianshu", "sequential") is True
        assert check_compatibility("tianshu", "parallel") is True


class TestCrossSourceCollaboration:
    """验证跨来源Agent协作：天机+Trae官方+Trae内置"""

    def test_tianji_trae_official_collaboration(self):
        reg = CapabilityRegistry()

        tianji_agents = reg.find_by_source("tianji")
        official_agents = reg.find_by_source("trae-official")

        assert len(tianji_agents) >= 20
        assert len(official_agents) == 7

        can_collaborate = False
        for tj_agent in tianji_agents:
            info = reg.get_agent(tj_agent)
            partners = info.get("collaboration_partners", [])
            for partner in partners:
                if partner in official_agents:
                    can_collaborate = True
                    break

        assert can_collaborate, "天机Agent与Trae官方Agent无法协作"

    def test_traffic_routing_between_sources(self):
        reg = CapabilityRegistry()

        routes = [
            ("tianshu", "ui-designer"),
            ("jingwei", "frontend-architect"),
            ("tiewei", "api-test-pro"),
            ("tianji", "compliance-checker"),
        ]

        for source, target in routes:
            assert reg.exists(source), f"源Agent不存在: {source}"
            assert reg.exists(target), f"目标Agent不存在: {target}"

            source_info = reg.get_agent(source)
            partners = source_info.get("collaboration_partners", [])
            assert target in partners or source in reg.get_agent(target).get(
                "collaboration_partners", []
            ), f"{source}与{target}无法路由"

    def test_hybrid_agent_team(self):
        reg = CapabilityRegistry()

        team = {
            "tianji": ["tianshu", "yiku", "tiewei"],
            "trae-official": ["ui-designer", "frontend-architect", "backend-architect"],
            "trae-builtin": ["trae-chat", "trae-agent"],
        }

        for source, agents in team.items():
            for agent_id in agents:
                assert reg.exists(agent_id), f"{agent_id}不存在"
                assert reg.get_source(agent_id) == source, (
                    f"{agent_id}来源不匹配: 期望{source}, 实际{reg.get_source(agent_id)}"
                )


class TestSchedulingSimulation:
    """模拟调度系统：完整路由选择流程"""

    def test_task_based_agent_selection(self):
        reg = CapabilityRegistry()

        def select_agents(task_description: str) -> list[str]:
            capabilities_map = {
                "设计": ["ui-designer", "jingwei"],
                "前端": ["frontend-architect", "performance-expert"],
                "后端": ["backend-architect", "api-test-pro"],
                "测试": ["tiewei", "api-test-pro"],
                "安全": ["zhenshan", "compliance-checker"],
                "性能": ["zhuiguang", "performance-expert"],
                "AI": ["ai-integration-engineer", "yiku"],
                "架构": ["jingwei", "backend-architect"],
                "记忆": ["yiku", "lianli"],
                "调度": ["tianshu", "tianji"],
            }

            selected = []
            for keyword, agents in capabilities_map.items():
                if keyword in task_description:
                    selected.extend(agents)

            return list(set(selected))

        task = "设计一个前端界面，需要考虑后端API和安全性"
        selected = select_agents(task)

        assert len(selected) > 0
        assert "ui-designer" in selected
        assert "frontend-architect" in selected
        assert "backend-architect" in selected
        assert "zhenshan" in selected

    def test_clear_aware_routing(self):
        reg = CapabilityRegistry()

        def route_with_clear(task_type: str, priority: str) -> str:
            candidates = []

            if task_type == "security":
                candidates = ["zhenshan", "compliance-checker"]
            elif task_type == "performance":
                candidates = ["zhuiguang", "performance-expert"]
            elif task_type == "memory":
                candidates = ["yiku", "lianli"]
            elif task_type == "orchestration":
                candidates = ["tianshu", "tianji"]

            if priority == "critical" or priority == "high":
                return candidates[0]
            else:
                return candidates[1] if len(candidates) > 1 else candidates[0]

        assert route_with_clear("security", "critical") == "zhenshan"
        assert route_with_clear("performance", "medium") == "performance-expert"
        assert route_with_clear("memory", "high") == "yiku"

    def test_workflow_blueprint_dispatch(self):
        reg = CapabilityRegistry()

        workflows = {
            "frontend_development": [
                "ui-designer",
                "frontend-architect",
                "api-test-pro",
                "tiewei",
            ],
            "backend_development": [
                "backend-architect",
                "api-test-pro",
                "zhenshan",
                "tiewei",
            ],
            "ai_integration": [
                "ai-integration-engineer",
                "yiku",
                "frontend-architect",
                "backend-architect",
            ],
            "security_audit": ["zhenshan", "compliance-checker", "tiewei"],
        }

        for workflow_name, agent_sequence in workflows.items():
            for agent_id in agent_sequence:
                assert reg.exists(agent_id), f"工作流{workflow_name}中{agent_id}不存在"


class TestSchedulingEdgeCases:
    """调度系统边界条件测试"""

    def test_empty_task_handling(self):
        reg = CapabilityRegistry()

        def handle_empty_task(task: str) -> list[str]:
            if not task or task.strip() == "":
                return ["trae-chat"]
            return []

        assert handle_empty_task("") == ["trae-chat"]
        assert handle_empty_task("   ") == ["trae-chat"]
        assert handle_empty_task("设计") == []

    def test_agent_not_found_fallback(self):
        reg = CapabilityRegistry()

        def get_agent_with_fallback(agent_id: str) -> str:
            if reg.exists(agent_id):
                return agent_id
            return "trae-chat"

        assert get_agent_with_fallback("nonexistent") == "trae-chat"
        assert get_agent_with_fallback("tianshu") == "tianshu"

    def test_overload_protection(self):
        max_concurrent = 3
        active_tasks = 5

        assert active_tasks > max_concurrent

        def check_overload(active_count: int, max_count: int) -> bool:
            return active_count >= max_count

        assert check_overload(active_tasks, max_concurrent) is True


class TestSchedulingIntegration:
    """调度系统集成测试"""

    def test_full_scheduling_pipeline(self):
        reg = CapabilityRegistry()

        task = {
            "description": "构建一个安全的前端Dashboard，包含性能监控和AI分析功能",
            "priority": "high",
            "complexity": "high",
        }

        selected_agents = []

        if "前端" in task["description"]:
            selected_agents.extend(["ui-designer", "frontend-architect"])
        if "安全" in task["description"]:
            selected_agents.extend(["zhenshan", "compliance-checker"])
        if "性能" in task["description"]:
            selected_agents.extend(["zhuiguang", "performance-expert"])
        if "AI" in task["description"]:
            selected_agents.extend(["ai-integration-engineer", "yiku"])

        selected_agents = list(set(selected_agents))

        assert len(selected_agents) >= 6
        assert "ui-designer" in selected_agents
        assert "frontend-architect" in selected_agents
        assert "zhenshan" in selected_agents
        assert "zhuiguang" in selected_agents
        assert "ai-integration-engineer" in selected_agents
        assert "yiku" in selected_agents

        for agent_id in selected_agents:
            assert reg.exists(agent_id), f"{agent_id}不存在"

    def test_mcp_tool_coverage(self):
        reg = CapabilityRegistry()

        mcp_tools = [
            "agent_dispatch",
            "system_status",
            "memory_recall",
            "memory_remember",
            "rule_evaluate",
            "security-scanner",
            "performance-profiler",
            "execute_command",
            "ops-engine",
            "context_extract",
        ]

        tool_coverage = dict.fromkeys(mcp_tools, False)

        for aid in reg.list_agents():
            tools = reg.get_tools(aid)
            for tool in tools:
                if tool in tool_coverage:
                    tool_coverage[tool] = True

        for tool, covered in tool_coverage.items():
            assert covered, f"MCP工具{tool}未被任何Agent覆盖"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
