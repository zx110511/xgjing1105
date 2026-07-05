r"""
天机v9.1 — 20Agent导入验证脚本
================================
验证所有Agent运行类可正确导入，AMIM桥接完整。
"""

import sys
import os
import traceback

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

EXPECTED_AGENTS = {
    "L0": [("tiewei", "TieweiAgent", "铁卫")],
    "L1": [
        ("yiku", "YikuAgent", "忆库"),
        ("dongcha", "DongchaAgent", "洞察"),
        ("luling", "LulingAgent", "律令"),
        ("lingxi", "LingxiAgent", "灵犀"),
    ],
    "L2": [
        ("tianshu", "TianshuAgent", "天枢"),
        ("wenzong", "WenzongAgent", "文宗"),
        ("jingwei", "JingweiAgent", "经纬"),
        ("miaobi", "MiaobiAgent", "妙笔"),
        ("mingjing", "MingjingAgent", "明镜"),
        ("tiansuan", "TiansuanAgent", "天算"),
        ("kuangshi", "KuangshiAgent", "矿师"),
    ],
    "L3": [
        ("baiqiao", "BaiqiaoAgent", "百巧"),
        ("shiguan", "ShiguanAgent", "史官"),
        ("jinshu", "JinshuAgent", "锦书"),
    ],
    "L4": [
        ("qianli", "QianliAgent", "千里"),
        ("gongzao", "GongzaoAgent", "工造"),
        ("zhenshan", "ZhenshanAgent", "镇山"),
        ("zhuiguang", "ZhuiguangAgent", "追光"),
    ],
}


def test_individual_imports():
    print("=" * 60)
    print("  20Agent导入验证 — 独立导入测试")
    print("=" * 60)

    passed = 0
    failed = 0
    failures = []

    for layer, agents in EXPECTED_AGENTS.items():
        print(f"\n  [{layer}]")
        for module_name, class_name, cn_name in agents:
            try:
                mod = __import__(f"agents.{module_name}", fromlist=[class_name])
                agent_cls = getattr(mod, class_name)
                assert agent_cls.AGENT_ID == module_name, \
                    f"AGENT_ID 不匹配: {agent_cls.AGENT_ID} != {module_name}"
                print(f"    ✅ {cn_name}({class_name}) — AGENT_ID={agent_cls.AGENT_ID}")
                passed += 1
            except Exception as e:
                msg = f"    ❌ {cn_name}({class_name}) — {e}"
                print(msg)
                traceback.print_exc()
                failed += 1
                failures.append((layer, module_name, class_name, str(e)))

    print(f"\n  {'─' * 50}")
    print(f"  独立导入: {passed}/{passed + failed} PASS, {failed} FAIL")
    return passed, failed, failures


def test_package_import():
    print(f"\n{'=' * 60}")
    print("  20Agent导入验证 — 包级导入测试")
    print("=" * 60)

    passed = 0
    failed = 0
    failures = []

    expected_names = []
    for agents_list in EXPECTED_AGENTS.values():
        for _, class_name, _ in agents_list:
            expected_names.append(class_name)

    try:
        import agents

        for class_name in expected_names:
            if hasattr(agents, class_name):
                print(f"    ✅ agents.{class_name}")
                passed += 1
            else:
                print(f"    ❌ agents.{class_name} 不在包导出中")
                failed += 1
                failures.append(class_name)
    except Exception as e:
        print(f"    ❌ 包导入失败: {e}")
        traceback.print_exc()
        failed = len(expected_names)
        failures = [str(e)]

    print(f"\n  {'─' * 50}")
    print(f"  包级导入: {passed}/{passed + failed} PASS, {failed} FAIL")
    return passed, failed, failures


def test_amim_integration():
    print(f"\n{'=' * 60}")
    print("  20Agent导入验证 — AMIM集成测试")
    print("=" * 60)

    passed = 0
    failed = 0
    failures = []

    try:
        from core.memory.amim import AgentMCPIntegrationManager

        amim = AgentMCPIntegrationManager()

        for layer, agents in EXPECTED_AGENTS.items():
            for module_name, class_name, cn_name in agents:
                defn = amim.get_agent(module_name)
                if defn is None:
                    print(f"    ❌ {cn_name} — AMIM中无定义")
                    failed += 1
                    failures.append((module_name, "AMIM中无定义"))
                    continue

                if defn.runtime_class != class_name:
                    print(f"    ⚠️ {cn_name} — runtime_class不匹配: "
                          f"{defn.runtime_class} != {class_name}")
                    failures.append((module_name, f"runtime_class: {defn.runtime_class} != {class_name}"))

                print(f"    ✅ {cn_name} — AMIM: {defn.to_tvp()}")
                passed += 1

        issues = amim.validate()
        if issues:
            print(f"\n  ⚠️ AMIM验证发现问题 {len(issues)} 条:")
            for issue in issues:
                print(f"      - {issue}")
        else:
            print(f"\n  ✅ AMIM.validate() → 无问题")

        status = amim.health()
        print(f"  AMIM状态: {status['status']} | "
              f"Agent: {status['agent_count']} | "
              f"工具: {status['tool_count']} | "
              f"MCP: {status['mcp_server_count']}")

    except Exception as e:
        print(f"  ❌ AMIM集成测试失败: {e}")
        traceback.print_exc()
        failed = 20
        failures = [str(e)]

    print(f"\n  {'─' * 50}")
    print(f"  AMIM集成: {passed}/{passed + failed} PASS, {failed} FAIL")
    return passed, failed, failures


if __name__ == "__main__":
    total_pass = 0
    total_fail = 0

    p, f, _ = test_individual_imports()
    total_pass += p
    total_fail += f

    p, f, _ = test_package_import()
    total_pass += p
    total_fail += f

    p, f, _ = test_amim_integration()
    total_pass += p
    total_fail += f

    print(f"\n{'=' * 60}")
    print(f"  🏁 最终结果: {total_pass}/{total_pass + total_fail} PASS, "
          f"{total_fail} FAIL")
    print(f"{'=' * 60}")

    sys.exit(0 if total_fail == 0 else 1)
