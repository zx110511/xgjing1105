"""验证对话归档器"""

import io
import json
import sys
import time
import urllib.request

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

print("=" * 60)
print("对话归档器验证")
print("=" * 60)

# 测试1: 健康检查
print("\n[测试1] 归档器健康检查")
try:
    req = urllib.request.Request("http://127.0.0.1:8771/api/conversation/health")
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    r = opener.open(req, timeout=10)
    data = json.loads(r.read().decode("utf-8"))
    print(f"  状态: {data.get('status')}")
    print(f"  初始化: {data.get('archiver_initialized')}")
    print(f"  总归档数: {data.get('total_archives')}")
    print("  [PASS] 归档器健康检查通过")
except Exception as e:
    print(f"  [FAIL] 归档器健康检查失败: {e}")
    print("  (需要重启天机服务加载新代码)")

# 测试2: 完整归档(4要素)
print("\n[测试2] 完整对话归档(4要素)")
archive_data = {
    "session_id": f"verify-{int(time.time())}",
    "turn_number": 1,
    "user_message": "[完整用户消息] 验证对话归档器是否真实记录4要素。这是测试用户消息原文,包含技术细节: 集成到start_tianji.bat启动链路,通过POST /api/conversation/archive端点,实现L3+L4+L5三层自动归档。",
    "agent_response": "[完整Agent回复] 对话归档器已开发完成。架构: core/memory/conversation_archiver.py(核心) + server/api/conversation_archive_routes.py(HTTP端点) + main.py路由注册 + launcher全链验证 + project_rules.md第0节规范。归档4要素: 完整用户消息+Agent回复+决策过程+文件变更。集成路径: 桌面快捷方式→start_tianji.bat→launcher→server→archiver。失败降级: 离线队列自动暂存。",
    "decisions": [
        {
            "step": "Step1-识别",
            "agent": "tianji",
            "decision": "complexity=critical(系统集成任务)",
            "reason": "涉及HTTP API+启动器+规则系统多模块集成",
            "evidence": "5个文件修改+2个新文件创建",
        },
        {
            "step": "Step2-检索",
            "agent": "tianji",
            "decision": "复用现有trae_capture架构,新增完整归档器",
            "reason": "现有trae_capture是摘要式,需新建完整记录版本",
            "evidence": "trae_capture.py第7-16行注释明确摘要化设计",
        },
        {
            "step": "Step4-生成",
            "agent": "tianji",
            "decision": "创建conversation_archiver.py+conversation_archive_routes.py",
            "reason": "需要独立模块支持4要素全记录+HTTP API+离线队列",
            "evidence": "新文件d:/元初系统/天机v9.1/core/memory/conversation_archiver.py",
        },
    ],
    "file_changes": [
        {
            "file_path": "core/memory/conversation_archiver.py",
            "change_type": "create",
            "summary": "对话归档器核心模块,实现4要素全记录+L3/L4/L5三层归档+离线队列降级",
            "lines_added": 280,
            "lines_removed": 0,
            "diff_preview": "+class ConversationArchive: 完整对话归档(4要素)...",
        },
        {
            "file_path": "server/api/conversation_archive_routes.py",
            "change_type": "create",
            "summary": "对话归档HTTP端点,提供archive/session/stats/recent/sync_offline/health 6个端点",
            "lines_added": 310,
            "lines_removed": 0,
            "diff_preview": "+@router.post('/archive') 归档单轮对话(4要素)...",
        },
        {
            "file_path": "server/main.py",
            "change_type": "modify",
            "summary": "注册conversation_archive_router到FastAPI app",
            "lines_added": 6,
            "lines_removed": 0,
            "diff_preview": "+from server.api.conversation_archive_routes import router as conversation_archive_router",
        },
        {
            "file_path": "launcher/tianji_v91_launcher.py",
            "change_type": "modify",
            "summary": "添加conversation_archiver端点到全链验证列表",
            "lines_added": 1,
            "lines_removed": 0,
            "diff_preview": "+('conversation_archiver', f'{BASE_URL}/api/conversation/health', '对话归档器'),",
        },
        {
            "file_path": ".trae/rules/project_rules.md",
            "change_type": "modify",
            "summary": "第0节归档规范升级,新增0.2.1归档器集成路径",
            "lines_added": 50,
            "lines_removed": 20,
            "diff_preview": "+### 0.2.1 归档器集成路径 (新增·v3.1)",
        },
    ],
    "agent_id": "tianji",
    "complexity": "critical",
    "mcp_tools_used": ["tianji_health", "memory_recall", "agent_dispatch"],
    "tvp_declarations": [
        "[TVP] Agent: @tianji (L0总控直接执行, @kuangshi降级)",
        "[TVP-MCP] tianji_health | healthy",
        "[TVP-MCP] memory_recall | 找到历史归档记录",
        "[TVP-MCP] agent_dispatch | 推荐@kuangshi score=1",
    ],
}

try:
    payload = json.dumps(archive_data, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        "http://127.0.0.1:8771/api/conversation/archive",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    t0 = time.time()
    r = opener.open(req, timeout=30)
    elapsed = time.time() - t0
    resp = json.loads(r.read().decode("utf-8"))
    print(f"  耗时: {elapsed:.2f}s")
    print(f"  L3 ID: {resp.get('l3_id')}")
    print(f"  L4 IDs: {resp.get('l4_ids')}")
    print(f"  L5 ID: {resp.get('l5_id')}")
    print(f"  离线队列: {resp.get('offline_queued')}")
    print(f"  content_hash: {resp.get('content_hash')}")
    print(f"  total_bytes: {resp.get('total_bytes')}")

    l3_id = resp.get("l3_id")
    l4_count = len(resp.get("l4_ids", []))
    l5_id = resp.get("l5_id")

    if l3_id and l4_count == 5 and l5_id and resp.get("offline_queued") == 0:
        print(f"  [PASS] 4要素全归档成功(L3+{l4_count}条L4+L5)")
    else:
        print(
            f"  [WARN] 归档不完整: L3={'YES' if l3_id else 'NO'} L4={l4_count}/5 L5={'YES' if l5_id else 'NO'}"
        )
except Exception as e:
    print(f"  [FAIL] 归档失败: {e}")

# 测试3: 归档统计
print("\n[测试3] 归档统计")
try:
    req = urllib.request.Request("http://127.0.0.1:8771/api/conversation/stats")
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    r = opener.open(req, timeout=10)
    data = json.loads(r.read().decode("utf-8"))
    stats = data.get("archiver_stats", {})
    print(f"  总归档数: {stats.get('total_archives')}")
    print(f"  总字节数: {stats.get('total_bytes')}")
    print(f"  L3成功: {stats.get('l3_success')}")
    print(f"  L4成功: {stats.get('l4_success')}")
    print(f"  L5成功: {stats.get('l5_success')}")
    print(f"  离线队列: {stats.get('offline_queued')}")
    print(f"  离线队列大小: {data.get('offline_queue_size')}")
except Exception as e:
    print(f"  [FAIL] 获取统计失败: {e}")

# 测试4: 验证归档内容可检索
print("\n[测试4] 验证归档内容可检索")
if l3_id:
    try:
        from urllib.parse import quote

        query = quote("完整对话归档 L3 验证对话归档器")
        req = urllib.request.Request(
            f"http://127.0.0.1:8771/api/platform/recall?query={query}&limit=3"
        )
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        r = opener.open(req, timeout=15)
        data = json.loads(r.read().decode("utf-8"))
        found = (
            any(item.get("id") == l3_id for item in data)
            if isinstance(data, list)
            else False
        )
        print(
            f"  搜索'完整对话归档 L3' -> {len(data) if isinstance(data, list) else 0}条"
        )
        print(f"  找到归档记录 {l3_id}: {found}")
        if found:
            print("  [PASS] 归档内容可检索")
        else:
            print("  [WARN] 归档内容未在搜索结果中(可能FTS5索引延迟)")
    except Exception as e:
        print(f"  [FAIL] 检索失败: {e}")

print("\n" + "=" * 60)
print("验证完成")
print("=" * 60)
print("\n注意: 如归档器健康检查失败,需重启天机服务加载新代码:")
print("  1. 关闭天机托盘")
print("  2. 删除 .daemon/tianji.pid")
print("  3. 重新双击桌面快捷方式启动")
