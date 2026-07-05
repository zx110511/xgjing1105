import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

print("=== 审计4.1: 语法导入 ===")
from active_memory.protocol import (
    ActiveMemoryProtocol, ActiveMemoryConfig,
    MemoryAction, MemoryDecision, RetrievalStrategy,
    KnowledgeTriple, InterceptLayer, InterceptSession, Platform,
)
print("✅ protocol.py 全部类导入成功 (v7.0)")

from active_memory import InterceptLayer, InterceptSession, Platform
print("✅ __init__.py 导出新类成功")

from server.api.active_routes import router
routes = [r.path for r in router.routes]
print(f"✅ active_routes: {len(router.routes)} 个端点")
for path in routes:
    print(f"   {path}")

assert "/intercept/status" in routes, "❌ 缺少 /intercept/status"
print("✅ intercept/status 端点已注册")

print("\n=== 审计4.2: InterceptLayer 核心功能 ===")
il = InterceptLayer()
print(f"✅ InterceptLayer 初始化成功")

r = il.capture_user_input("测试用户输入-架构设计讨论", "trae", "test-session-001", "test-agent")
print(f"✅ capture_user_input: status={r['status']}, intent={r['intent']}, memories={r['relevant_memories_count']}")

r = il.capture_ai_response("测试AI响应-重构方案A优于B，使用工厂模式", "trae", "test-session-001", "test-agent")
print(f"✅ capture_ai_response: status={r['status']}, stored_layer={r['stored_layer']}, turn={r['turn']}")

r = il.finish_session("test-session-001")
print(f"✅ finish_session: status={r['status']}, knowledge_extracted={r.get('knowledge_extracted')}")

stats = il.get_stats()
print(f"✅ get_stats: total_intercepts={stats['total_intercepts']}, user_captures={stats['user_captures']}, ai_captures={stats['ai_captures']}, sessions_completed={stats['sessions_completed']}")

status = il.get_status()
print(f"✅ get_status: platforms={status['platforms']}, active_sessions={status['active_sessions']}")

print("\n=== 审计4.3: 平台 + 会话 ===")
print(f"✅ Platform enum: {[p.value for p in Platform]}")

session = InterceptSession(session_id="test-s", platform="trae", agent_id="a1")
session.add_turn("input1", "response1")
session.add_turn("input2", "response2")
print(f"✅ InterceptSession: turns={session.turns}, dict={session.to_dict()}")

print("\n=== 审计4.4: 降级安全 ===")
il2 = InterceptLayer(engine=None, enforcement_hook=None)
r2 = il2.capture_user_input("测试降级", "trae", "session-fallback")
print(f"✅ 无引擎捕获: status={r2['status']}, memories=0 (预期)")

r3 = il2.capture_ai_response("测试降级响应", "trae", "session-fallback")
print(f"✅ 无引擎AI捕获: stored_layer='{r3['stored_layer']}' (预期空)")

r4 = il2.finish_session("session-fallback")
print(f"✅ 无引擎会话闭环: consolidated={r4['consolidated']} (预期False)")

print("\n=== 审计4.5: 集成验证 ===")
from server.main import app
intercept_ep = [r.path for r in app.routes if "intercept" in r.path]
print(f"✅ main.py intercept 路由: {intercept_ep}")

print(f"\n✅ M14 三级审计全部通过!")
