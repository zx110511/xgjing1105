# -*- coding: utf-8-sig -*-
"""查看tool_help返回的实际数据结构"""

import json
import urllib.request

BASE = "http://127.0.0.1:8771/api/mcp"

req = urllib.request.Request(
    f"{BASE}/tools/tool_help", headers={"Accept": "application/json"}
)
resp = urllib.request.urlopen(req, timeout=15)
data = json.loads(resp.read().decode("utf-8"))

tools = data.get("tools", [])
print(f"工具总数: {len(tools)}")
print()

# 查看前3个工具的结构
for i, t in enumerate(tools[:5]):
    print(f"--- 工具 {i + 1} ---")
    print(f"  type: {type(t).__name__}")
    if isinstance(t, dict):
        print(f"  keys: {list(t.keys())}")
        print(f"  name: {t.get('name')}")
        print(f"  path: {t.get('path')}")
        print(f"  method: {t.get('method')}")
    else:
        print(f"  value: {t}")
    print()
