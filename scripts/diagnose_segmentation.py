"""检查中文分词是否正常工作"""

import io
import sqlite3
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

db = r"d:\元初系统\天机v9.1\data\.memory\icme.db"
conn = sqlite3.connect(db)
conn.row_factory = sqlite3.Row

# 检查content_segmented字段是否存在
print("=" * 60)
print("1. 检查content_segmented字段")
print("=" * 60)
cols = conn.execute("PRAGMA table_info(memories)").fetchall()
col_names = [c[1] for c in cols]
print(f"字段列表: {col_names}")
print(f"content_segmented存在: {'content_segmented' in col_names}")

print()
print("=" * 60)
print("2. 检查补录记录的content_segmented内容")
print("=" * 60)
for mid in ["fb6e53897f9ace36", "749884cc6dbb59cd"]:
    row = conn.execute(
        "SELECT id, content, content_segmented FROM memories WHERE id=?", (mid,)
    ).fetchone()
    if row:
        print(f"ID: {row['id']}")
        print(f"  content前80: {row['content'][:80]}")
        seg = row["content_segmented"] or ""
        print(f"  content_segmented前80: {seg[:80]}")
        print(f"  content_segmented长度: {len(seg)}")
        print()

print("=" * 60)
print("3. FTS5搜索中文测试（不同分词方式）")
print("=" * 60)
test_queries = [
    "跨会话",
    "审计",
    "补录",
    "10day",
    "跨 AND 会话",
    "审计 AND 补录",
    "跨 会话 审计",
    '"跨会话审计"',
    "cross session audit",
]
for q in test_queries:
    try:
        rows = conn.execute(
            "SELECT m.id FROM memories m "
            "INNER JOIN memories_fts f ON m.rowid = f.rowid "
            "WHERE memories_fts MATCH ? "
            "ORDER BY f.rank LIMIT 2",
            (q,),
        ).fetchall()
        print(f"  Q='{q}' -> {len(rows)}条")
    except Exception as e:
        print(f"  Q='{q}' -> 错误: {e}")

print()
print("=" * 60)
print("4. jieba分词测试")
print("=" * 60)
try:
    from core.shared.chinese_tokenizer import tokenize_for_fts

    test_text = "跨会话审计补录 10day-backfill 系统级策略沉淀"
    result = tokenize_for_fts(test_text)
    print(f"原文: {test_text}")
    print(f"分词: {result}")
except Exception as e:
    print(f"jieba分词错误: {e}")

print()
print("=" * 60)
print("5. 检查layer错误: 第二条记录应该是meta")
print("=" * 60)
# 我补录时用了 layer='meta'，但实际存为 episodic
# 检查API是否对layer做了转换
import json
import urllib.request

req = urllib.request.Request("http://127.0.0.1:8771/api/memory/749884cc6dbb59cd")
r = urllib.request.urlopen(req, timeout=10)
data = json.loads(r.read().decode("utf-8"))
print(f"API返回的layer: {data.get('layer')}")
print(f"API返回的tags: {data.get('tags')}")

conn.close()
