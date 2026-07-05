# -*- coding: utf-8 -*-
"""
Tianji v8.2 Agent Serialization Verification v1.0
==================================================
Verifies round-trip serialization for all 23 Agents.

Usage: python scripts/verify_agent_serialization.py
"""

import json
import sys
from pathlib import Path
from datetime import datetime

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from core.memory.amim import AgentMCPIntegrationManager
from core.orchestration.agent_serializer import (
    AgentSerializer, AgentIntrospector, AgentServiceDescriptor
)

PASS = "[PASS]"
FAIL = "[FAIL]"
SEP = "=" * 60
SEP2 = "-" * 40

RESULT = {
    "test": "agent_serialization_roundtrip",
    "timestamp": datetime.now().isoformat(),
    "version": "1.0.0",
    "agents": {}
}


def test_amim_serialization(amim):
    serializer = AgentSerializer(amim)
    verify = serializer.verify_all_agents()

    print(f"\n{SEP}")
    print(f"AMIM Serialization: {verify['passed']}/{verify['total']} passed ({verify['rate']}%)")
    print(f"{SEP}")

    for agent_id, result in verify["results"].items():
        status = PASS if result["passed"] else FAIL
        failed = [k for k, v in result["checks"].items() if not v]
        detail = "PASS" if result["passed"] else f"FAIL {failed}"
        print(f"  {status} {agent_id}: {detail}")
        RESULT["agents"][agent_id] = result

    return verify


def test_introspector():
    print(f"\n{SEP}")
    print(f"AgentIntrospector Compatibility Test")
    print(f"{SEP}")

    test_agents = []

    try:
        from agents.multimodal import MultimodalAgent
        instance = MultimodalAgent()
        data = AgentIntrospector.inspect_agent_instance(instance)
        json_str = AgentIntrospector.serialize_instance(instance)
        parsed = json.loads(json_str)
        test_agents.append(("wanxiang(MultimodalAgent)", PASS, parsed.get("AGENT_ID", "?")))
    except Exception as e:
        test_agents.append(("wanxiang(MultimodalAgent)", FAIL, str(e)[:60]))

    try:
        from agents.graphbuilder import GraphBuilderAgent
        instance = GraphBuilderAgent()
        data = AgentIntrospector.inspect_agent_instance(instance)
        json_str = AgentIntrospector.serialize_instance(instance)
        parsed = json.loads(json_str)
        test_agents.append(("lianli(GraphBuilderAgent)", PASS, parsed.get("AGENT_ID", "?")))
    except Exception as e:
        test_agents.append(("lianli(GraphBuilderAgent)", FAIL, str(e)[:60]))

    try:
        from agents.evolver import EvolverAgent
        instance = EvolverAgent()
        data = AgentIntrospector.inspect_agent_instance(instance)
        json_str = AgentIntrospector.serialize_instance(instance)
        parsed = json.loads(json_str)
        test_agents.append(("huasheng(EvolverAgent)", PASS, parsed.get("AGENT_ID", "?")))
    except Exception as e:
        test_agents.append(("huasheng(EvolverAgent)", FAIL, str(e)[:60]))

    for name, status, detail in test_agents:
        print(f"  {status} {name}: {detail}")

    return test_agents


def test_lingjing_registry(amim):
    serializer = AgentSerializer(amim)
    registry = serializer.generate_lingjing_service_registry()

    print(f"\n{SEP}")
    print(f"Lingjing Service Registry: {registry['_meta']['service_count']} services")
    print(f"{SEP}")

    for aid, svc in registry["services"].items():
        port_ok = PASS if svc["port"] > 0 else FAIL
        health_ok = PASS if svc["health_endpoint"] else FAIL
        print(f"  {svc['name']:6s} ({aid:10s}): port={svc['port']:<5d} {port_ok} health={svc['health_endpoint']:<25s} {health_ok}")

    RESULT["registry"] = registry["_meta"]
    return registry


def test_agent_serializable_mixin():
    print(f"\n{SEP}")
    print(f"AgentSerializable Mixin Test")
    print(f"{SEP}")

    from core.orchestration.agent_serializer import AgentSerializable

    class TestAgent(AgentSerializable):
        AGENT_ID = "test_agent"
        AGENT_NAME = "TestAgent"
        LAYER = "L0"
        ROLE = "TestRole"
        EMOJI = "T"
        CAPABILITIES = ["test_cap_1", "test_cap_2"]
        TOOLS = ["tool_a", "tool_b"]
        MCP_SERVER = "test-server"

    agent = TestAgent()

    try:
        d = agent.to_dict()
        assert d["AGENT_ID"] == "test_agent", "AGENT_ID mismatch"
        assert d["AGENT_NAME"] == "TestAgent", "AGENT_NAME mismatch"
        print(f"  {PASS} to_dict(): {len(d)} keys")

        j = agent.to_json()
        parsed = json.loads(j)
        assert parsed["AGENT_ID"] == "test_agent", "to_json AGENT_ID mismatch"
        print(f"  {PASS} to_json(): {len(j)} chars")

        tvp = agent.to_tvp()
        assert "test_agent" in tvp, "TVP missing agent_id"
        print(f"  {PASS} to_tvp(): {tvp}")

        return True
    except Exception as e:
        print(f"  {FAIL} AgentSerializable failed: {e}")
        return False


def main():
    print(SEP)
    print("Tianji v8.2 Agent Serialization Audit - Lingjing Distributed Readiness")
    print(SEP)
    print(f"Time: {datetime.now().isoformat()}")
    print(f"Path: {PROJECT_ROOT}")

    amim = AgentMCPIntegrationManager()
    print(f"\nAMIM: {amim.agent_count} Agents, {amim.tool_count} Tools")

    mixin_ok = test_agent_serializable_mixin()
    intro = test_introspector()
    amim_result = test_amim_serialization(amim)
    registry = test_lingjing_registry(amim)

    total_passed = amim_result["passed"]
    total_agents = amim_result["total"]
    intro_passed = sum(1 for _, s, _ in intro if s == PASS)

    print(f"\n{SEP}")
    print(f"FINAL VERDICT")
    print(f"{SEP}")
    print(f"  Mixin Basic Test:       {'[OK]' if mixin_ok else '[FAIL]'}")
    print(f"  Introspector Compat:    {intro_passed}/{len(intro)} passed")
    print(f"  AMIM Roundtrip:         {total_passed}/{total_agents} ({amim_result['rate']}%)")
    print(f"  Lingjing Registry:      {registry['_meta']['service_count']} services")

    if total_passed == total_agents:
        print(f"\n  >>> CONCLUSION: All {total_agents} Agents pass serialization roundtrip <<<")
        print(f"  Lingjing Distributed Ready: [YES] (Module interface serializable standard implemented)")
    else:
        failed_agents = [aid for aid, r in amim_result["results"].items() if not r["passed"]]
        print(f"\n  >>> CONCLUSION: {total_passed}/{total_agents} passed <<<")
        print(f"  Failed: {failed_agents}")

    report_dir = PROJECT_ROOT / "tests" / "reports"
    report_path = report_dir / f"v8.2_agent_serialization_audit_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    try:
        with open(report_path, 'w', encoding='utf-8') as f:
            json.dump(RESULT, f, ensure_ascii=False, indent=2)
        print(f"\n  Report saved: {report_path}")
    except Exception:
        pass

    return total_passed == total_agents


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
