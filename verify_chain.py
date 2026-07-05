# -*- coding: utf-8-sig -*-
import json
import time
import urllib.error
import urllib.request

PORT = 8771
BASE = f"http://127.0.0.1:{PORT}"


def check(url, is_json=True):
    try:
        req = urllib.request.Request(url)
        resp = urllib.request.urlopen(req, timeout=10)
        body = resp.read().decode("utf-8")
        if is_json:
            data = json.loads(body)
            return True, data
        return True, f"HTTP {resp.status}"
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")[:500]
        return False, f"HTTP {e.code}: {body}"
    except Exception as e:
        return False, str(e)


print("等待容器模块完全初始化（最多120秒）...")
proto_ready = False
event_ready = False
for wait in range(40):
    time.sleep(3)
    ok, data = check(f"{BASE}/api/health")
    if ok:
        proto = data.get("protocol_mode", False)
        event = data.get("event_wiring", False)
        uptime = data.get("uptime_seconds", 0)
        embed = data.get("embedding_ready", False)
        if proto and event:
            print(
                f"  ✓ Protocol+EventWiring激活 (uptime={uptime:.0f}s, embedding={embed})"
            )
            proto_ready = True
            event_ready = True
            break
        elif (wait + 1) % 5 == 0:
            print(
                f"  ...等待中 ({(wait + 1) * 3}s): protocol={proto}, event={event}, embed={embed}"
            )
    else:
        print(f"  health check failed: {data}")
        break

print()
print("=" * 60)
print("全链端点验证")
print("=" * 60)

endpoints = [
    ("/api/health", True),
    ("/api/status/system/stats", True),
    ("/api/mcp/tools", True),
    ("/api/orchestrator/agents", True),
    ("/api/kg/stats", True),
    ("/api/deepseek/models", True),
    ("/api/search?q=%E5%A4%A9%E6%9C%BA&limit=1", True),
    ("/", False),
    ("/docs", False),
]

all_ok = True
results = {}
for path, is_json in endpoints:
    url = BASE + path
    ok, data = check(url, is_json)
    results[path] = ok
    status_mark = "PASS" if ok else "FAIL"
    if ok and is_json:
        extra = ""
        if path == "/api/health":
            layers = data.get("layers") or {}
            total = sum(
                v.get("entry_count", 0) for v in layers.values() if isinstance(v, dict)
            )
            extra = f" (protocol={data.get('protocol_mode')}, event={data.get('event_wiring')}, embed={data.get('embedding_ready')}, memories={total})"
        elif path == "/api/status/system/stats":
            extra = f" (modules={data.get('module_count')}, container={data.get('container_running')}/{data.get('container_total')}, memories={data.get('memory_total')})"
        elif path == "/api/mcp/tools":
            tools = data.get("tools", [])
            extra = f" ({len(tools)} tools)"
        elif path == "/api/orchestrator/agents":
            agents = data.get("agents", [])
            extra = f" ({len(agents)} agents)"
        elif path == "/api/kg/stats":
            extra = f" (nodes={data.get('total_nodes', 0)}, edges={data.get('total_edges', 0)})"
        elif path == "/api/deepseek/models":
            extra = f" (configured={data.get('configured', False)})"
        elif path.startswith("/api/search"):
            r = data.get("results", data.get("data", []))
            extra = f" (results={len(r) if isinstance(r, list) else '?'})"
        print(f"[{status_mark}] {path}: OK{extra}")
    elif ok and not is_json:
        print(f"[{status_mark}] {path}: {data}")
    else:
        print(
            f"[{status_mark}] {path}: {data[:200] if isinstance(data, str) else data}"
        )
        all_ok = False

print()
print("=" * 60)
ok_count = sum(1 for v in results.values() if v)
total_count = len(results)
print(f"验证结果: {ok_count}/{total_count} 通过")
if all_ok:
    print("🎉 全链通过!")
else:
    fail_items = [p for p, v in results.items() if not v]
    print(f"⚠️ 失败项: {fail_items}")
print("=" * 60)
