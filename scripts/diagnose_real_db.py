"""检查真实存储的schema和FTS5索引状态"""

import io
import sqlite3
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

db = r"d:\元初系统\天机v9.1\data\.memory\icme.db"
conn = sqlite3.connect(db)
conn.row_factory = sqlite3.Row

print("=" * 60)
print("1. memories表结构")
print("=" * 60)
rows = conn.execute("PRAGMA table_info(memories)").fetchall()
for r in rows:
    print(f"  {r}")

print()
print("=" * 60)
print("2. FTS5表结构")
print("=" * 60)
rows = conn.execute(
    "SELECT sql FROM sqlite_master WHERE type='table' AND name='memories_fts'"
).fetchall()
for r in rows:
    print(f"  {r[0]}")

print()
print("=" * 60)
print("3. trigger检查")
print("=" * 60)
rows = conn.execute(
    "SELECT name, sql FROM sqlite_master WHERE type='trigger' AND name LIKE 'memories%'"
).fetchall()
if rows:
    for r in rows:
        print(f"  Trigger: {r[0]}")
        print(f"  SQL: {r[1]}")
        print()
else:
    print("  没有memories相关trigger!")

print()
print("=" * 60)
print("4. 补录记录详情")
print("=" * 60)
for mid in ["fb6e53897f9ace36", "749884cc6dbb59cd"]:
    row = conn.execute(
        "SELECT id, layer, content, length(content) as content_len, tags, priority "
        "FROM memories WHERE id=?",
        (mid,),
    ).fetchone()
    if row:
        print(f"ID: {row['id']}")
        print(f"  Layer: {row['layer']}")
        print(f"  Priority: {row['priority']}")
        print(f"  Content长度: {row['content_len']}")
        print(f"  Tags: {row['tags']}")
        print(f"  Content前80字符: {row['content'][:80]}")
        print()
    else:
        print(f"ID: {mid} - 不存在")

print()
print("=" * 60)
print("5. FTS5索引中是否有补录记录")
print("=" * 60)
for mid in ["fb6e53897f9ace36", "749884cc6dbb59cd"]:
    row = conn.execute("SELECT rowid FROM memories WHERE id=?", (mid,)).fetchone()
    if row:
        rowid = row[0]
        fts_row = conn.execute(
            "SELECT rowid FROM memories_fts WHERE rowid=?", (rowid,)
        ).fetchone()
        print(f"  ID:{mid} rowid={rowid} FTS5存在={fts_row is not None}")

print()
print("=" * 60)
print("6. FTS5搜索测试")
print("=" * 60)
test_queries = ["跨会话审计", "10day", "backfill", "系统级策略沉淀", "审计补录"]
for q in test_queries:
    try:
        rows = conn.execute(
            "SELECT m.id, m.layer FROM memories m "
            "INNER JOIN memories_fts f ON m.rowid = f.rowid "
            "WHERE memories_fts MATCH ? "
            "ORDER BY f.rank LIMIT 3",
            (q,),
        ).fetchall()
        print(f"  Query='{q}' -> 命中{len(rows)}条")
        for r in rows:
            print(f"    - {r['id']} (layer={r['layer']})")
    except Exception as e:
        print(f"  Query='{q}' -> 错误: {e}")

print()
print("=" * 60)
print("7. LIKE搜索测试")
print("=" * 60)
for q in ["跨会话审计", "10day-backfill", "系统级策略沉淀"]:
    rows = conn.execute(
        "SELECT id, layer FROM memories WHERE content LIKE ? LIMIT 3", (f"%{q}%",)
    ).fetchall()
    print(f"  LIKE '{q}' -> 命中{len(rows)}条")
    for r in rows:
        print(f"    - {r['id']} (layer={r['layer']})")

print()
print("=" * 60)
print("8. 按layer统计(前20)")
print("=" * 60)
rows = conn.execute(
    "SELECT layer, COUNT(*) as cnt FROM memories GROUP BY layer ORDER BY cnt DESC LIMIT 20"
).fetchall()
for r in rows:
    print(f"  {r['layer']}: {r['cnt']}")

conn.close()
print()
print("诊断完成")
