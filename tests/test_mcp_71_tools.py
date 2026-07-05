# -*- coding: utf-8-sig -*-
"""测试全部71个MCP工具（基于tool_help返回的真实工具列表）"""
import json
import time
import urllib.error
import urllib.request

BASE = "http://127.0.0.1:8771/api/mcp"

def http_get(url, timeout=10):
    try:
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        resp = urllib.request.urlopen(req, timeout=timeout)
        if resp.status == 200:
            body = resp.read().decode("utf-8")
            return True, json.loads(body)
        return False, {"error": f"HTTP {resp.status}"}
    except urllib.error.HTTPError as e:
        return False, {"error": f"HTTP {e.code}"}
    except Exception as e:
        return False, {"error": str(e)}

def http_post(url, body, timeout=10):
    try:
        data = json.dumps(body).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers={
            "Content-Type": "application/json",
            "Accept": "application/json"
        })
        resp = urllib.request.urlopen(req, timeout=timeout)
        if resp.status == 200:
            body = resp.read().decode("utf-8")
            return True, json.loads(body)
        return False, {"error": f"HTTP {resp.status}"}
    except urllib.error.HTTPError as e:
        return False, {"error": f"HTTP {e.code}"}
    except Exception as e:
        return False, {"error": str(e)}

print("=" * 72)
print("MCP全部71个工具测试")
print("=" * 72)

# Step 1: 获取全部工具列表
print("\n[1/2] 获取全部工具列表...")
ok, result = http_get(f"{BASE}/tools/tool_help", timeout=15)
if not ok:
    print(f"❌ 获取工具列表失败: {result}")
    exit(1)

tools = result.get("tools", [])
print(f"✅ 共 {len(tools)} 个工具")

# Step 2: 提取每个工具的信息
tool_info = []
for t in tools:
    if isinstance(t, str):
        name = t
        path = f"{BASE}/tools/{t}"
        method = "GET"
        desc = ""
        params = {}
    else:
        name = t.get("name", "unknown")
        path = t.get("path", "")
        method = (t.get("method") or "GET").upper()
        desc = t.get("description", "")
        params = t.get("parameters", {})
    tool_info.append({"name": name, "path": path, "method": method, "desc": desc, "params": params})

# Step 3: 逐个测试
print(f"\n[2/2] 逐个测试 {len(tool_info)} 个工具...")
print()

results = []
passed = 0
failed = 0
skipped = 0

for i, tool in enumerate(tool_info):
    name = tool["name"]
    path = tool["path"]
    method = tool["method"]
    params = tool["params"]

    # 构造测试参数（基于schema生成合理的测试值）
    test_params = {}
    if params and isinstance(params, dict):
        for pname, pinfo in params.items():
            ptype = pinfo.get("type", "string")
            if pname in ["content", "text", "query"]:
                test_params[pname] = "测试内容用于验证工具功能"
            elif pname in ["layer", "layers"]:
                test_params[pname] = "episodic"
            elif pname in ["tags"]:
                test_params[pname] = ["test", "mcp"]
            elif pname in ["limit"]:
                test_params[pname] = 5
            elif pname in ["session_id", "session_key"]:
                test_params[pname] = "test-session-001"
            elif pname in ["memory_id", "id"]:
                test_params[pname] = "test-memory-id"
            elif pname in ["command"]:
                test_params[pname] = "echo hello"
            elif pname in ["url"]:
                test_params[pname] = "http://127.0.0.1:8771/api/health"
            elif ptype == "string":
                test_params[pname] = "test_value"
            elif ptype == "number" or ptype == "integer":
                test_params[pname] = 1
            elif ptype == "boolean":
                test_params[pname] = True
            elif ptype == "array":
                test_params[pname] = []
            elif ptype == "object":
                test_params[pname] = {}

    # 跳过有风险的操作
    risky_tools = [
        "memory_forget", "delete_memory", "kill_process", "stop_command",
        "rollback_deployment", "memory_evolve_self", "deploy_service",
        "scale_service", "tianji_export"
    ]
    if name in risky_tools:
        print(f"  [{i+1:3d}] ⏭️  {name} (跳过: 高风险操作)")
        skipped += 1
        results.append({"name": name, "status": "skipped", "reason": "高风险"})
        time.sleep(0.5)
        continue

    # 执行测试
    if method == "GET":
        if test_params:
            query = "&".join(f"{k}={v}" for k, v in test_params.items())
            url = f"{path}?{query}"
        else:
            url = path
        ok, resp = http_get(url, timeout=10)
    else:
        url = path
        ok, resp = http_post(url, test_params, timeout=10)

    if ok:
        passed += 1
        resp_preview = str(resp)[:80].replace("\n", " ")
        print(f"  [{i+1:3d}] ✅ {name}")
        results.append({"name": name, "status": "passed", "method": method})
    else:
        err = resp.get("error", "unknown")
        if "404" in err or "405" in err:
            status = "not_implemented"
            mark = "❌"
        else:
            status = "error"
            mark = "⚠️"
        failed += 1
        print(f"  [{i+1:3d}] {mark} {name} - {err}")
        results.append({"name": name, "status": status, "error": err, "method": method})

    time.sleep(1.5)  # 间隔避免压垮服务

print()
print("=" * 72)
print(f"测试完成: ✅ {passed} 通过 | ❌ {failed} 失败 | ⏭️ {skipped} 跳过")
print(f"通过率: {passed / (passed + failed) * 100:.1f}%")
print("=" * 72)

# 列出失败的工具
if failed > 0:
    print("\n失败的工具:")
    for r in results:
        if r["status"] != "passed" and r["status"] != "skipped":
            print(f"  - {r['name']}: {r.get('error', r['status'])} [{r['method']}]")

# 保存结果
with open(r"d:\元初系统\天机v9.1\tests\mcp_all_71_tools_result.json", "w", encoding="utf-8") as f:
    json.dump({
        "total": len(tool_info),
        "passed": passed,
        "failed": failed,
        "skipped": skipped,
        "results": results
    }, f, ensure_ascii=False, indent=2)

print("\n结果已保存到 tests/mcp_all_71_tools_result.json")
