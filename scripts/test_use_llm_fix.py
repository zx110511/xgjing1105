"""验证 use_llm=false 快速路径是否解决超时"""
import urllib.request
import json
import time

url = "http://127.0.0.1:8771/api/memory/"
data = json.dumps({
    "content": "[API验证] use_llm=false快速路径 — 绕过MCP直接调API验证根因修复",
    "layer": "episodic",
    "tags": ["api-test", "use-llm-false"],
    "priority": "high",
    "use_llm": False
}).encode("utf-8")

req = urllib.request.Request(
    url, data=data,
    headers={"Content-Type": "application/json"},
    method="POST"
)

t0 = time.time()
try:
    r = urllib.request.urlopen(req, timeout=30)
    elapsed = time.time() - t0
    body = json.loads(r.read().decode("utf-8-sig"))
    print(f"[use_llm=False] 耗时: {elapsed:.2f}s | memory_id: {body.get('id', 'FAIL')}")
except Exception as e:
    elapsed = time.time() - t0
    print(f"[use_llm=False] 耗时: {elapsed:.2f}s | ERROR: {e}")

# 对比: use_llm 不传 (旧行为, content>50会触发LLM)
data2 = json.dumps({
    "content": "[API验证] 不传use_llm字段 — 对比旧路径是否超时（content超过50字符触发LLM增强）",
    "layer": "episodic",
    "tags": ["api-test", "use-llm-auto"],
    "priority": "high"
}).encode("utf-8")

req2 = urllib.request.Request(
    url, data=data2,
    headers={"Content-Type": "application/json"},
    method="POST"
)

t1 = time.time()
try:
    r2 = urllib.request.urlopen(req2, timeout=60)
    elapsed2 = time.time() - t1
    body2 = json.loads(r2.read().decode("utf-8-sig"))
    print(f"[use_llm=auto] 耗时: {elapsed2:.2f}s | memory_id: {body2.get('id', 'FAIL')}")
except Exception as e:
    elapsed2 = time.time() - t1
    print(f"[use_llm=auto] 耗时: {elapsed2:.2f}s | ERROR: {e}")
