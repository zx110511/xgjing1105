"""直接诊断引擎状态 - 通过deps.py的engine对象"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)) + "/..")

import urllib.request, json

# 写入一条记忆，获取完整result
body = json.dumps({
    "content": "直接诊断result中的asset_id",
    "layer": "working",
    "tags": ["诊断"]
}, ensure_ascii=False).encode('utf-8')

req = urllib.request.Request(
    'http://127.0.0.1:8771/api/platform/remember',
    data=body,
    headers={'Content-Type': 'application/json'}
)
r = urllib.request.urlopen(req)
raw = r.read().decode('utf-8')
data = json.loads(raw)

print("=== 完整响应 ===")
print(json.dumps(data, ensure_ascii=False, indent=2))
print(f"\nasset_id in response: {data.get('asset_id')}")

# 检查asset_routes中的版本链
mid = data.get('id')
print(f"\n=== 检查版本链 for {mid} ===")
try:
    r = urllib.request.urlopen(f'http://127.0.0.1:8771/api/asset/versions/{mid}')
    print(json.dumps(json.loads(r.read()), ensure_ascii=False, indent=2))
except Exception as e:
    print(f"版本链查询失败: {e}")

# 检查asset stats
print(f"\n=== 策略D统计 ===")
try:
    r = urllib.request.urlopen('http://127.0.0.1:8771/api/asset/stats')
    print(json.dumps(json.loads(r.read()), ensure_ascii=False, indent=2))
except Exception as e:
    print(f"统计查询失败: {e}")
