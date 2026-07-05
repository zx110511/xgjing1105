r"""
天机v9.1 — AMIM一致性验证脚本
===============================
验证 AMIM ↔ _AGENT_REGISTRY.json ↔ agent_orchestrator.py 三方一致。
"""

import sys
import os
import json
import importlib
from pathlib import Path
from typing import List, Tuple

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

PROJECT_ROOT = Path(__file__).parent.parent
REGISTRY_PATH = PROJECT_ROOT / ".trae" / "agents" / "_AGENT_REGISTRY.json"
ORCHESTRATOR_PATH = PROJECT_ROOT / "core" / "agent_orchestrator.py"


class ConsistencyValidator:
    def __init__(self):
        self.issues: List[str] = []
        self.warnings: List[str] = []
        self.passed: List[str] = []

    def check(self, label: str, condition: bool, detail: str = ""):
        if condition:
            self.passed.append(f"✅ {label}")
        else:
            self.issues.append(f"❌ {label}" + (f" — {detail}" if detail else ""))

    def warn(self, label: str, detail: str = ""):
        self.warnings.append(f"⚠️ {label}" + (f" — {detail}" if detail else ""))


def verify_amim_internal(v: ConsistencyValidator):
    print("\n" + "=" * 60)
    print("  [1/4] AMIM内部一致性")
    print("=" * 60)

    try:
        from core.memory.amim import (
            AgentMCPIntegrationManager, TOOL_AGENT_MAPPING,
            LINGJING_FUTURE_TOOLS, KNOWN_TOOLS, KNOWN_MCP_SERVERS
        )

        amim = AgentMCPIntegrationManager()
        v.check("AMIM实例化", True)

        v.check("Agent数量=20", amim.agent_count == 20,
                f"实际: {amim.agent_count}")

        issues = amim.validate()
        v.check("AMIM.validate()无问题", len(issues) == 0,
                f"发现问题 {len(issues)} 条: {issues[:5]}")

        agent_ids = {a.agent_id for a in amim.AGENT_DEFINITIONS}
        v.check("所有Agent ID唯一", len(agent_ids) == 20,
                f"期望20, 实际{len(agent_ids)}")

        for agent in amim.AGENT_DEFINITIONS:
            v.check(f"  {agent.name}({agent.agent_id}) runtime_class已设置",
                    agent.runtime_class is not None)
            v.check(f"  {agent.name} lingjing_service_id已设置",
                    agent.lingjing_service_id is not None)
            v.check(f"  {agent.name} lingjing_port已设置",
                    agent.lingjing_port is not None)
            v.check(f"  {agent.name} 至少绑定1个工具", len(agent.tools) > 0,
                    f"当前: {len(agent.tools)}")

        tool_count = len(TOOL_AGENT_MAPPING)
        v.check(f"TOOL_AGENT_MAPPING覆盖{tool_count}个工具", tool_count >= 24,
                f"期望 >= 24, 实际 {tool_count}")

        for tool_name, info in TOOL_AGENT_MAPPING.items():
            owner = info["owner"]
            v.check(f"  工具 '{tool_name}' 归属'{owner}'存在",
                    owner in agent_ids,
                    f"归属Agent '{owner}' 不在Agent列表中")

        mcp_covered = {a.mcp_server for a in amim.AGENT_DEFINITIONS}
        for s in KNOWN_MCP_SERVERS:
            v.check(f"  MCP服务器 '{s}' 有Agent绑定", s in mcp_covered)

        future_count = len(LINGJING_FUTURE_TOOLS)
        v.check(f"灵境预留工具 {future_count} 个", future_count == 17,
                f"期望17, 实际 {future_count}")

    except Exception as e:
        v.check(f"AMIM模块加载", False, str(e))


def verify_registry_consistency(v: ConsistencyValidator):
    print("\n" + "=" * 60)
    print("  [2/4] AMIM ↔ Registry文件一致性")
    print("=" * 60)

    try:
        from core.memory.amim import AgentMCPIntegrationManager

        amim = AgentMCPIntegrationManager()

        if not REGISTRY_PATH.exists():
            v.warn("Registry文件不存在，将由AMIM生成", str(REGISTRY_PATH))
            registry_json = amim.generate_registry_json()
            v.check("AMIM.generate_registry_json()成功", registry_json is not None)
            v.check("Registry agents数量=20",
                    len(registry_json.get("agents", {})) == 20,
                    f"实际: {len(registry_json.get('agents', {}))}")
            return

        with open(REGISTRY_PATH, "r", encoding="utf-8") as f:
            existing = json.load(f)

        v.check("Registry文件可读取", True)

        existing_agents = existing.get("agents", {})
        v.check(f"Registry中有 {len(existing_agents)} 个Agent定义", len(existing_agents) > 0)

        amim_ids = {a.agent_id for a in amim.AGENT_DEFINITIONS}
        registry_ids = set(existing_agents.keys())

        only_in_amim = amim_ids - registry_ids
        only_in_registry = registry_ids - amim_ids

        if only_in_amim:
            v.warn(f"AMIM中有但Registry中无: {only_in_amim}")
        if only_in_registry:
            v.warn(f"Registry中有但AMIM中无(旧Agent): {only_in_registry}")

        common = amim_ids & registry_ids
        v.check(f"共同Agent: {len(common)} 个", len(common) >= 19,
                f"期望 >= 19, 实际 {len(common)}")

        mismatches = 0
        for agent in amim.AGENT_DEFINITIONS:
            if agent.agent_id not in registry_ids:
                continue
            reg_agent = existing_agents[agent.agent_id]
            reg_name = reg_agent.get("name") or reg_agent.get("name_cn", "")
            if reg_name and reg_name != agent.name:
                mismatches += 1
                v.warn(f"  {agent.agent_id} 名称不一致: AMIM={agent.name}, Registry={reg_name}")

        v.check(f"名称一致性检查", mismatches == 0,
                f"{mismatches} 处名称不一致" if mismatches else "")

        result = amim.verify_consistency_with_existing(str(REGISTRY_PATH))
        if result["issues"]:
            for issue in result["issues"]:
                v.warn(f"  {issue}")

        v.check("AMIM ↔ Registry 深度比对",
                result["consistent"], f"发现问题 {len(result['issues'])} 条" if result["issues"] else "")

    except Exception as e:
        v.check("Registry一致性检查", False, str(e))


def verify_orchestrator_consistency(v: ConsistencyValidator):
    print("\n" + "=" * 60)
    print("  [3/4] AMIM ↔ Orchestrator一致性")
    print("=" * 60)

    try:
        from core.memory.amim import AgentMCPIntegrationManager
        from core.orchestration.agent_orchestrator import AGENT_CAPABILITY_MATRIX

        amim = AgentMCPIntegrationManager()

        v.check("Orchestrator导入成功", True)
        cap_count = len(AGENT_CAPABILITY_MATRIX)
        v.check(f"AGENT_CAPABILITY_MATRIX 有 {cap_count} 个条目", cap_count >= 19,
                f"期望 >= 19, 实际 {cap_count}")

        amim_ids = {a.agent_id for a in amim.AGENT_DEFINITIONS}
        orch_ids = set(AGENT_CAPABILITY_MATRIX.keys())

        only_in_amim = amim_ids - orch_ids
        only_in_orch = orch_ids - amim_ids

        if only_in_amim:
            v.warn(f"AMIM中有但Orchestrator中无: {only_in_amim}")
        if only_in_orch:
            v.warn(f"Orchestrator中有但AMIM中无: {only_in_orch}")

        common = amim_ids & orch_ids
        v.check(f"共同Agent: {len(common)} 个", len(common) >= 19,
                f"期望 >= 19, 实际 {len(common)}")

        tool_mismatches = 0
        for agent in amim.AGENT_DEFINITIONS:
            if agent.agent_id not in orch_ids:
                continue
            orch_entry = AGENT_CAPABILITY_MATRIX[agent.agent_id]
            amim_tools = set(agent.tools)
            orch_tools = set(orch_entry.get("tools", []))
            if amim_tools != orch_tools:
                tool_mismatches += 1
                diff_amim = amim_tools - orch_tools
                diff_orch = orch_tools - amim_tools
                detail = f"AMIM独有: {diff_amim}, Orch独有: {diff_orch}" if diff_amim or diff_orch else ""
                v.warn(f"  {agent.agent_id} 工具列表不一致", detail)

        v.check(f"工具列表一致性", tool_mismatches == 0,
                f"{tool_mismatches} 处不一致" if tool_mismatches else "")

        generated = amim.generate_capability_matrix()
        v.check("AMIM.generate_capability_matrix()成功",
                generated is not None and "AGENT_CAPABILITY_MATRIX" in generated)

    except Exception as e:
        v.check("Orchestrator一致性检查", False, str(e))


def verify_mcp_tool_coverage(v: ConsistencyValidator):
    print("\n" + "=" * 60)
    print("  [4/4] MCP工具覆盖验证")
    print("=" * 60)

    try:
        from core.memory.amim import AgentMCPIntegrationManager, TOOL_AGENT_MAPPING, KNOWN_MCP_SERVERS

        amim = AgentMCPIntegrationManager()

        for tool_name, info in TOOL_AGENT_MAPPING.items():
            agents = amim.get_agents_for_tool(tool_name)
            v.check(f"  工具 '{tool_name}' 可路由到Agent",
                    len(agents) > 0,
                    f"归属: {info['owner']}, 委托: {info.get('delegates', [])}")

            router = amim.get_tool_owner(tool_name)
            v.check(f"  工具 '{tool_name}' 主归属Agent: {router}",
                    router is not None and router == info["owner"])

        mcp_stats = {}
        for agent in amim.AGENT_DEFINITIONS:
            server = agent.mcp_server
            if server not in mcp_stats:
                mcp_stats[server] = []
            mcp_stats[server].append(agent.agent_id)

        print(f"\n  MCP服务器 → Agent分配:")
        for server, agents in sorted(mcp_stats.items()):
            print(f"    {server}: {', '.join(agents)} ({len(agents)}个)")

        for server in KNOWN_MCP_SERVERS:
            v.check(f"  MCP服务器 '{server}' 分配",
                    server in mcp_stats,
                    f"绑定 {len(mcp_stats.get(server, []))} 个Agent")

    except Exception as e:
        v.check("MCP工具覆盖验证", False, str(e))


if __name__ == "__main__":
    print("=" * 60)
    print("  天机v9.1 AMIM一致性验证")
    print("=" * 60)

    v = ConsistencyValidator()

    verify_amim_internal(v)
    verify_registry_consistency(v)
    verify_orchestrator_consistency(v)
    verify_mcp_tool_coverage(v)

    print(f"\n{'=' * 60}")
    print(f"  📊 验证结果汇总")
    print(f"{'=' * 60}")
    for p in v.passed:
        print(f"  {p}")

    total = len(v.passed) + len(v.issues)
    print(f"\n  🏁 通过: {len(v.passed)}/{total}, "
          f"失败: {len(v.issues)}/{total}, "
          f"警告: {len(v.warnings)}")

    if v.warnings:
        print(f"\n  ⚠️ 警告项({len(v.warnings)}):")
        for w in v.warnings:
            print(f"  {w}")

    if v.issues:
        print(f"\n  ❌ 失败项({len(v.issues)}):")
        for issue in v.issues:
            print(f"  {issue}")
        sys.exit(1)
    else:
        print(f"\n  ✅ 全部验证通过！AMIM一致性无问题。")
        sys.exit(0)
