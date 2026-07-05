"""
测试IDE集成 — 验证对话捕获功能
"""

import requests
import time
import json

print("=" * 80)
print("IDE集成测试 — 对话捕获验证")
print("=" * 80)

# 测试1: 对话捕获
print("\n[测试1] 对话捕获API")
print("-" * 80)

payload = {
    "user_input": "这是一条测试消息，来自IDE集成测试",
    "ai_response": "这是AI的测试回复，验证集成是否正常工作",
    "agent_id": "lingxi",
    "session_id": "test-session-ide-001",
    "platform": "trae",
    "mcp_calls": [
        {
            "tool_name": "memory_recall",
            "arguments": {"query": "测试"},
            "result": "找到3条记录",
            "timestamp": time.time()
        }
    ],
    "file_operations": [
        {
            "operation": "write",
            "path": "/test/file.txt",
            "content_preview": "测试内容",
            "timestamp": time.time()
        }
    ],
    "tags": ["test", "ide-integration"]
}

try:
    response = requests.post(
        "http://127.0.0.1:8771/api/active/capture_conversation",
        json=payload,
        timeout=5
    )

    print(f"状态码: {response.status_code}")
    result = response.json()
    print(f"响应: {json.dumps(result, indent=2, ensure_ascii=False)}")

    if result.get("success"):
        print("\n✅ 对话捕获成功")
        print(f"   turn_id: {result.get('turn_id')}")
        print(f"   captured_layers: {result.get('captured_layers')}")
    else:
        print("\n❌ 对话捕获失败")

except Exception as e:
    print(f"\n❌ 测试失败: {e}")

# 测试2: 捕获统计
print("\n\n[测试2] 捕获统计API")
print("-" * 80)

try:
    response = requests.get(
        "http://127.0.0.1:8771/api/active/capture_stats",
        timeout=5
    )

    print(f"状态码: {response.status_code}")
    stats = response.json()
    print(f"响应: {json.dumps(stats, indent=2, ensure_ascii=False)}")

    if stats.get("success"):
        print("\n✅ 统计查询成功")
        print(f"   总捕获数: {stats.get('total_captured')}")
        print(f"   按平台: {stats.get('by_platform')}")
        print(f"   按层级: {stats.get('by_layer')}")
        print(f"   捕获率: {stats.get('capture_rate')}")

except Exception as e:
    print(f"\n❌ 测试失败: {e}")

# 测试3: 健康检查
print("\n\n[测试3] 健康检查API")
print("-" * 80)

try:
    response = requests.get(
        "http://127.0.0.1:8771/api/active/capture_health",
        timeout=5
    )

    print(f"状态码: {response.status_code}")
    health = response.json()
    print(f"响应: {json.dumps(health, indent=2, ensure_ascii=False)}")

    if health.get("status") == "healthy":
        print("\n✅ 系统健康")
    else:
        print(f"\n⚠️ 系统状态: {health.get('status')}")
        if health.get("issues"):
            print(f"   问题: {health.get('issues')}")

except Exception as e:
    print(f"\n❌ 测试失败: {e}")

# 测试4: Qoder平台捕获
print("\n\n[测试4] Qoder平台对话捕获")
print("-" * 80)

qoder_payload = {
    "user_input": "Qoder测试消息",
    "ai_response": "Qoder AI回复",
    "agent_id": "tianshu",
    "session_id": "qoder-test-001",
    "platform": "qoder",
    "tags": ["test", "qoder"]
}

try:
    response = requests.post(
        "http://127.0.0.1:8771/api/active/capture_conversation",
        json=qoder_payload,
        timeout=5
    )

    result = response.json()
    if result.get("success"):
        print("✅ Qoder对话捕获成功")
        print(f"   turn_id: {result.get('turn_id')}")
    else:
        print("❌ Qoder对话捕获失败")

except Exception as e:
    print(f"❌ 测试失败: {e}")

print("\n" + "=" * 80)
print("测试完成")
print("=" * 80)
