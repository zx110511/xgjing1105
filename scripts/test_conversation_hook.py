"""
测试对话结束钩子功能
"""

import sys
import time
sys.path.insert(0, r"d:\元初系统\天机v9.1")

from active_memory.conversation_hook import (
    init_hooks,
    on_conversation_end,
    get_hook_manager,
)

print("=" * 60)
print("对话结束钩子系统测试")
print("=" * 60)

# 1. 初始化钩子系统
print("\n[Step 1] 初始化钩子系统")
hook_manager = init_hooks(api_base_url="http://127.0.0.1:8771")
print(f"✅ 钩子管理器已初始化")
print(f"   已注册钩子数: {len(hook_manager._hooks)}")

# 显示已注册的钩子
for hook in hook_manager._hooks:
    stats = hook.get_stats()
    print(f"   - {stats['class']}: priority={stats['priority']}, enabled={stats['enabled']}")

# 2. 测试Trae对话钩子
print("\n[Step 2] 测试Trae对话钩子")
result = on_conversation_end(
    user_input="这是一条测试消息，用于验证对话钩子功能",
    ai_response="这是AI的测试回复，确认钩子已正常工作",
    session_id="test-session-001",
    agent_id="lingxi",
    platform="trae",
    tags=["test", "hook-verification"],
)

print(f"触发结果: {result}")

if result.get("success"):
    print("✅ Trae钩子触发成功")
    print(f"   turn_id: {result.get('turn_id')}")
    print(f"   captured_layers: {result.get('captured_layers')}")
    print(f"   total_captured: {result.get('total_captured')}")
else:
    print("❌ Trae钩子触发失败")
    print(f"   错误: {result.get('error')}")

# 3. 测试Qoder对话钩子
print("\n[Step 3] 测试Qoder对话钩子")
result = on_conversation_end(
    user_input="Qoder平台的测试消息",
    ai_response="Qoder平台的AI回复",
    session_id="test-session-002",
    agent_id="tianshu",
    platform="qoder",
    tags=["test", "qoder"],
)

print(f"触发结果: {result}")

if result.get("success"):
    print("✅ Qoder钩子触发成功")
    print(f"   turn_id: {result.get('turn_id')}")
    print(f"   captured_layers: {result.get('captured_layers')}")
    print(f"   total_captured: {result.get('total_captured')}")
else:
    print("❌ Qoder钩子触发失败")
    print(f"   错误: {result.get('error')}")

# 4. 查看钩子统计信息
print("\n[Step 4] 钩子统计信息")
stats = hook_manager.get_stats()
print(f"总对话数: {stats['total_conversations']}")
print(f"总钩子触发数: {stats['total_hooks_triggered']}")
print(f"成功数: {stats['total_success']}")
print(f"错误数: {stats['total_errors']}")

for hook_stats in stats['hooks']:
    print(f"\n{hook_stats['class']}:")
    print(f"  total_triggers: {hook_stats['total_triggers']}")
    print(f"  success_count: {hook_stats['success_count']}")
    print(f"  error_count: {hook_stats['error_count']}")

# 5. 测试钩子启用/禁用
print("\n[Step 5] 测试钩子启用/禁用")
hook_manager.disable_all()
print("✅ 所有钩子已禁用")

result = on_conversation_end(
    user_input="禁用状态下的测试",
    ai_response="不应该被捕获",
    session_id="test-session-003",
    platform="trae",
)

if not result.get("success"):
    print("✅ 钩子禁用验证成功（预期失败）")
else:
    print("❌ 钩子禁用验证失败（应该失败但成功了）")

hook_manager.enable_all()
print("✅ 所有钩子已重新启用")

print("\n" + "=" * 60)
print("测试完成")
print("=" * 60)
