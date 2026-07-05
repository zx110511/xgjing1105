"""对话持久化API测试脚本"""
import httpx
import json
import time
import sys

base = "http://localhost:8771/api/chat"
results = []

try:
    # 1. 创建对话
    r = httpx.post(f"{base}/conversations", json={"title": "持久化测试对话"}, timeout=10)
    d = r.json()
    conv_id = d.get("conversation_id", "")
    results.append(("创建对话", r.status_code == 200 and conv_id != "", f"status={r.status_code} conv_id={conv_id[:12]}"))

    # 2. 列表对话
    r = httpx.get(f"{base}/conversations", timeout=10)
    d = r.json()
    total = d.get("total", 0)
    results.append(("列表对话", r.status_code == 200 and total >= 1, f"total={total}"))

    # 3. 置顶对话
    r = httpx.patch(f"{base}/conversations/{conv_id}/pin?pinned=true", timeout=10)
    results.append(("置顶对话", r.status_code == 200, f"status={r.status_code}"))

    # 4. 修改标题
    r = httpx.patch(f"{base}/conversations/{conv_id}/title?title=修改后的标题", timeout=10)
    results.append(("修改标题", r.status_code == 200, f"status={r.status_code}"))

    # 5. 搜索对话
    r = httpx.get(f"{base}/conversations/search?q=修改后", timeout=10)
    d = r.json()
    found = d.get("total", 0)
    results.append(("搜索对话", r.status_code == 200 and found >= 1, f"found={found}"))

    # 6. 导出对话(Markdown)
    r = httpx.get(f"{base}/conversations/{conv_id}/export?format=markdown", timeout=10)
    has_title = "修改后的标题" in r.text
    results.append(("导出MD", r.status_code == 200 and has_title, f"len={len(r.text)} has_title={has_title}"))

    # 7. 导出对话(JSON)
    r = httpx.get(f"{base}/conversations/{conv_id}/export?format=json", timeout=10)
    results.append(("导出JSON", r.status_code == 200, f"len={len(r.text)}"))

    # 8. 统计
    r = httpx.get(f"{base}/conversations/stats", timeout=10)
    d = r.json()
    total_conv = d.get("total_conversations", 0)
    results.append(("统计信息", r.status_code == 200 and total_conv >= 1, f"total={total_conv}"))

    # 9. 导出全部
    r = httpx.get(f"{base}/conversations/export-all", timeout=10)
    results.append(("导出全部", r.status_code == 200, f"len={len(r.text)}"))

    # 10. 取消置顶
    r = httpx.patch(f"{base}/conversations/{conv_id}/pin?pinned=false", timeout=30)
    results.append(("取消置顶", r.status_code == 200, f"status={r.status_code}"))

    # 11. 删除对话
    r = httpx.delete(f"{base}/conversations/{conv_id}", timeout=30)
    results.append(("删除对话", r.status_code == 200, f"status={r.status_code}"))

    # 12. 验证删除
    r = httpx.get(f"{base}/conversations", timeout=30)
    d = r.json()
    remaining_ids = [c["id"] for c in d.get("conversations", [])]
    results.append(("验证删除", conv_id not in remaining_ids, f"remaining={d.get('total', 0)}"))

except Exception as e:
    results.append(("异常", False, str(e)))

# 输出结果
print("\n" + "=" * 60)
print("对话持久化API测试结果")
print("=" * 60)
passed = 0
for name, ok, detail in results:
    status = "PASS" if ok else "FAIL"
    if ok:
        passed += 1
    print(f"  [{status}] {name}: {detail}")
print(f"\n通过: {passed}/{len(results)}")
sys.exit(0 if passed == len(results) else 1)
