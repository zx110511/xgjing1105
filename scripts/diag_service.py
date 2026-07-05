"""通过API诊断运行中引擎的_asset_registry状态"""
import urllib.request, json

# 调用一个内部诊断端点
try:
    r = urllib.request.urlopen('http://127.0.0.1:8771/api/health')
    health = json.loads(r.read().decode('utf-8'))
    print(f"引擎状态: {health.get('status')}")
    print(f"版本: {health.get('edition')}")
except Exception as e:
    print(f"健康检查失败: {e}")

# 检查asset_routes是否工作
try:
    r = urllib.request.urlopen('http://127.0.0.1:8771/api/asset/stats')
    stats = json.loads(r.read().decode('utf-8'))
    print(f"\n策略D统计: {json.dumps(stats, ensure_ascii=False, indent=2)}")
except Exception as e:
    print(f"策略D统计失败: {e}")

# 通过MCP工具检查
try:
    body = json.dumps({"tool_name": "memory_remember"}, ensure_ascii=False).encode('utf-8')
    req = urllib.request.Request(
        'http://127.0.0.1:8771/api/mcp/tools',
        data=body,
        headers={'Content-Type': 'application/json'}
    )
    # 先用简单方式
    r = urllib.request.urlopen('http://127.0.0.1:8771/api/mcp/tools')
    tools = json.loads(r.read().decode('utf-8'))
    print(f"\nMCP工具数: {len(tools) if isinstance(tools, list) else 'N/A'}")
except Exception as e:
    print(f"MCP工具列表失败: {e}")

# 关键: 直接写入并检查返回的完整JSON
try:
    body = json.dumps({
        "content": "策略D合体诊断-检查asset_id字段",
        "layer": "working",
        "tags": ["诊断"]
    }, ensure_ascii=False).encode('utf-8')
    req = urllib.request.Request(
        'http://127.0.0.1:8771/api/platform/remember',
        data=body,
        headers={'Content-Type': 'application/json'}
    )
    r = urllib.request.urlopen(req)
    result = json.loads(r.read().decode('utf-8'))
    print(f"\n写入结果完整JSON:")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    print(f"\nasset_id: {result.get('asset_id')}")
    print(f"metadata中的tcl_canonical_ids: {result.get('metadata', {}).get('tcl_canonical_ids', 'N/A')}")
except Exception as e:
    print(f"写入失败: {e}")
