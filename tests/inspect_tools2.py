# -*- coding: utf-8-sig -*-
"""查看tool_help返回的工具结构"""

import json
import time
import urllib.request

BASE = "http://127.0.0.1:8771/api/mcp"

time.sleep(2)

req = urllib.request.Request(
    f"{BASE}/tools/tool_help", headers={"Accept": "application/json"}
)
resp = urllib.request.urlopen(req, timeout=15)
data = json.loads(resp.read().decode("utf-8"))

tools = data.get("tools", [])
print(f"工具总数: {len(tools)}")
print()

# 查看每个工具的字段
for i, t in enumerate(tools[:10]):
    print(
        f"--- 工具 {i + 1}: {t.get('name', 'UNKNOWN') if isinstance(t, dict) else t} ---"
    )
    if isinstance(t, dict):
        print("  type: dict")
        print(f"  keys: {list(t.keys())}")
        print(f"  name: {t.get('name')}")
        print(f"  path: {t.get('path')}")
        print(f"  method: {t.get('method')}")
        print(f"  description: {str(t.get('description', ''))[:80]}")
        params = t.get("parameters", {})
        if params:
            print(f"  parameters ({len(params)}):")
            for pname, pinfo in list(params.items())[:3]:
                print(f"    - {pname}: {pinfo.get('type', '?')}")
    else:
        print(f"  type: {type(t).__name__}")
        print(f"  value: {t}")
    print()

# 统计有多少个是dict，多少个是str
dict_count = sum(1 for t in tools if isinstance(t, dict))
str_count = sum(1 for t in tools if isinstance(t, str))
print(f"字典格式工具: {dict_count}")
print(f"字符串格式工具: {str_count}")

# 保存完整工具列表
with open(r"d:\元初系统\天机v9.1\tests\tools_list.json", "w", encoding="utf-8") as f:
    json.dump(tools, f, ensure_ascii=False, indent=2)
print("\n工具列表已保存到 tests/tools_list.json")
