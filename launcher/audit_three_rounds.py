# -*- coding: utf-8-sig -*-
"""三次全覆盖审计脚本"""
import urllib.request
import json
import subprocess
import sys
import os

TIANJI_ROOT = r"D:\元初系统\天机v9.1"
PYTHON = os.path.join(TIANJI_ROOT, "python", "python.exe")
HEALTH_URL = "http://127.0.0.1:8771/api/health"
MCP_URL = "http://127.0.0.1:8771/api/mcp/"
ORC_URL = "http://127.0.0.1:8771/api/orchestrator/agents"
SEARCH_URL = "http://127.0.0.1:8771/api/search?q=%E5%A4%A9%E6%9C%BA&limit=1"

def http_json(url, timeout=10):
    try:
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        resp = urllib.request.urlopen(req, timeout=timeout)
        return json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        return None

def run_audit():
    print("=" * 60)
    print("天机v9.1 三次全覆盖审计")
    print("=" * 60)

    for round_num in range(1, 4):
        print(f"\n【第 {round_num} 轮审计】")
        print("-" * 40)

        results = {}

        # 1. 健康检查
        h = http_json(HEALTH_URL)
        results["health"] = h is not None and h.get("status") == "healthy"
        print(f"  {'✅' if results['health'] else '❌'} 健康检查: {h.get('status') if h else 'FAIL'}")

        # 2. 引擎就绪
        results["engine_ready"] = h is not None and h.get("engine_ready") == True
        print(f"  {'✅' if results['engine_ready'] else '❌'} 引擎就绪: {h.get('engine_ready') if h else 'FAIL'}")

        # 3. 协议模式
        results["protocol_mode"] = h is not None and h.get("protocol_mode") == True
        print(f"  {'✅' if results['protocol_mode'] else '❌'} 协议模式: {h.get('protocol_mode') if h else 'FAIL'}")

        # 4. 事件连线
        results["event_wiring"] = h is not None and h.get("event_wiring") == True
        print(f"  {'✅' if results['event_wiring'] else '❌'} 事件连线: {h.get('event_wiring') if h else 'FAIL'}")

        # 5. 六层记忆
        layers = h.get("layers", {}) if h else {}
        layer_count = len(layers)
        results["layers_6"] = layer_count >= 6
        print(f"  {'✅' if results['layers_6'] else '❌'} 六层记忆: {layer_count} 层")

        # 6. L3 Episodic有数据
        episodic = layers.get("episodic", {}).get("entry_count", 0) if layers else 0
        results["l3_has_data"] = episodic > 0
        print(f"  {'✅' if results['l3_has_data'] else '❌'} L3 Episodic: {episodic} 条")

        # 7. L4 Semantic有数据
        semantic = layers.get("semantic", {}).get("entry_count", 0) if layers else 0
        results["l4_has_data"] = semantic > 0
        print(f"  {'✅' if results['l4_has_data'] else '❌'} L4 Semantic: {semantic} 条")

        # 8. L5 Meta有数据
        meta = layers.get("meta", {}).get("entry_count", 0) if layers else 0
        results["l5_has_data"] = meta > 0
        print(f"  {'✅' if results['l5_has_data'] else '❌'} L5 Meta: {meta} 条")

        # 9. MCP API可用
        m = http_json(MCP_URL)
        results["mcp_api"] = m is not None and m.get("service") is not None
        tool_count = m.get("total_tools", 0) if m else 0
        print(f"  {'✅' if results['mcp_api'] else '❌'} MCP API: {tool_count} 工具")

        # 10. Agent调度器可用
        o = http_json(ORC_URL)
        agent_count = len(o.get("agents", [])) if o else 0
        results["orchestrator"] = o is not None and agent_count > 0
        print(f"  {'✅' if results['orchestrator'] else '❌'} Agent调度: {agent_count} 个")

        # 11. 搜索功能可用
        s = http_json(SEARCH_URL)
        results["search"] = s is not None and (isinstance(s, list) or isinstance(s.get("results"), list))
        search_count = len(s) if isinstance(s, list) else len(s.get("results", [])) if s else 0
        print(f"  {'✅' if results['search'] else '❌'} 搜索功能: {search_count} 结果")

        passed = sum(1 for v in results.values() if v)
        total = len(results)
        rate = passed / total * 100

        print(f"\n  结果: {passed}/{total} 通过 ({rate:.1f}%)")

        if round_num < 3:
            print("  等待5秒..." )
            import time
            time.sleep(5)

    print("\n" + "=" * 60)
    print("审计完成")
    print("=" * 60)

if __name__ == "__main__":
    run_audit()
