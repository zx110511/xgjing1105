"""验证归档器端点"""
import io
import json
import sys
import urllib.request

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

print("=" * 60)
print("归档器端点验证")
print("=" * 60)

# 1. 健康检查
print("\n[1] 归档器健康检查")
try:
    req = urllib.request.Request('http://127.0.0.1:8771/api/conversation/health')
    r = opener.open(req, timeout=10)
    data = json.loads(r.read().decode('utf-8'))
    print(f"  status: {data.get('status')}")
    print(f"  initialized: {data.get('archiver_initialized')}")
    print(f"  total_archives: {data.get('total_archives')}")
    print("  [PASS]")
except Exception as e:
    print(f"  [FAIL] {e}")

# 2. 统计
print("\n[2] 归档统计")
try:
    req = urllib.request.Request('http://127.0.0.1:8771/api/conversation/stats')
    r = opener.open(req, timeout=10)
    data = json.loads(r.read().decode('utf-8'))
    stats = data.get('archiver_stats', {})
    print(f"  total_archives: {stats.get('total_archives')}")
    print(f"  total_bytes: {stats.get('total_bytes')}")
    print(f"  l3_success: {stats.get('l3_success')}")
    print(f"  l4_success: {stats.get('l4_success')}")
    print(f"  l5_success: {stats.get('l5_success')}")
    print(f"  offline_queued: {stats.get('offline_queued')}")
    print(f"  offline_queue_size: {data.get('offline_queue_size')}")
    print("  [PASS]")
except Exception as e:
    print(f"  [FAIL] {e}")

# 3. 完整归档测试(4要素)
print("\n[3] 完整对话归档测试(4要素)")
import time

archive_data = {
    "session_id": f"verify-{int(time.time())}",
    "turn_number": 1,
    "user_message": "[用户消息原文] 验证归档器4要素全记录功能。这是完整的用户消息,包含技术细节: POST /api/conversation/archive端点,4要素(user_message+agent_response+decisions+file_changes),L3+L4+L5三层归档。",
    "agent_response": "[Agent回复原文] 归档器已开发完成并集成到启动链路。架构: conversation_archiver.py(核心) + conversation_archive_routes.py(HTTP端点) + main.py(路由注册) + launcher(全链验证) + project_rules.md(规范)。集成路径: 桌面快捷方式→start_tianji.bat→launcher→server→archiver→L3+L4+L5。",
    "decisions": [
        {
            "step": "Step1-识别",
            "agent": "tianji",
            "decision": "complexity=critical",
            "reason": "系统集成任务",
            "evidence": "6文件修改"
        },
        {
            "step": "Step4-生成",
            "agent": "tianji",
            "decision": "创建归档器+HTTP端点",
            "reason": "需要4要素全记录",
            "evidence": "新文件conversation_archiver.py"
        }
    ],
    "file_changes": [
        {
            "file_path": "core/memory/conversation_archiver.py",
            "change_type": "create",
            "summary": "归档器核心模块",
            "lines_added": 280,
            "lines_removed": 0,
            "diff_preview": "+class ConversationArchive"
        },
        {
            "file_path": "server/api/conversation_archive_routes.py",
            "change_type": "create",
            "summary": "HTTP端点",
            "lines_added": 310,
            "lines_removed": 0,
            "diff_preview": "+@router.post('/archive')"
        }
    ],
    "agent_id": "tianji",
    "complexity": "critical",
    "mcp_tools_used": ["tianji_health", "memory_recall", "agent_dispatch"],
    "tvp_declarations": ["[TVP] Agent: @tianji"]
}

try:
    payload = json.dumps(archive_data, ensure_ascii=False).encode('utf-8')
    req = urllib.request.Request(
        'http://127.0.0.1:8771/api/conversation/archive',
        data=payload,
        headers={'Content-Type': 'application/json'},
        method='POST'
    )
    t0 = time.time()
    r = opener.open(req, timeout=120)
    elapsed = time.time() - t0
    resp = json.loads(r.read().decode('utf-8'))
    print(f"  耗时: {elapsed:.2f}s")
    print(f"  L3 ID: {resp.get('l3_id')}")
    print(f"  L4 IDs: {resp.get('l4_ids')}")
    print(f"  L5 ID: {resp.get('l5_id')}")
    print(f"  离线队列: {resp.get('offline_queued')}")
    print(f"  content_hash: {resp.get('content_hash')}")
    print(f"  total_bytes: {resp.get('total_bytes')}")

    l3_id = resp.get('l3_id')
    l4_count = len(resp.get('l4_ids', []))
    l5_id = resp.get('l5_id')

    if l3_id and l4_count == 2 and l5_id and resp.get('offline_queued') == 0:
        print(f"  [PASS] 4要素全归档成功(L3+{l4_count}条L4+L5)")
    else:
        print("  [WARN] 归档不完整")
except Exception as e:
    print(f"  [FAIL] {e}")

# 4. 验证可检索性
print("\n[4] 验证归档内容可检索性")
if l3_id:
    try:
        from urllib.parse import quote
        query = quote("归档器4要素全记录")
        req = urllib.request.Request(
            f'http://127.0.0.1:8771/api/platform/recall?query={query}&limit=3'
        )
        r = opener.open(req, timeout=15)
        data = json.loads(r.read().decode('utf-8'))
        found = any(item.get('id') == l3_id for item in data) if isinstance(data, list) else False
        print(f"  搜索'归档器4要素全记录' -> {len(data) if isinstance(data, list) else 0}条")
        print(f"  找到归档记录 {l3_id}: {found}")
        if found:
            print("  [PASS] 可检索")
        else:
            print("  [WARN] 未在搜索结果(可能FTS5索引延迟)")
    except Exception as e:
        print(f"  [FAIL] {e}")

print("\n" + "=" * 60)
print("验证完成")
print("=" * 60)
