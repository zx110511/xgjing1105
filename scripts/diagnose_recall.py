"""诊断memory_recall搜索不到的根因"""

import io
import sqlite3
import sys

# 强制UTF-8输出
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

db = r"d:\元初系统\天机v9.1\data\icme.db"
conn = sqlite3.connect(db)
conn.row_factory = sqlite3.Row

print("=" * 60)
print("诊断1: 检查补录记录的content_segmented字段")
print("=" * 60)

for mid in ["fb6e53897f9ace36", "749884cc6dbb59cd"]:
    row = conn.execute(
        "SELECT id, layer, content_segmented, length(content_segmented) as seg_len, "
        "length(content) as content_len, tags FROM memories WHERE id=?",
        (mid,),
    ).fetchone()
    if row:
        print(f"ID: {row['id']}")
        print(f"  Layer: {row['layer']}")
        print(f"  Content长度: {row['content_len']}")
        print(f"  Segmented长度: {row['seg_len']}")
        seg = row["content_segmented"] or ""
        print(f"  Segmented前80字符: {seg[:80] if seg else '(EMPTY)'}")
        print(f"  Tags: {row['tags']}")
        print()
    else:
        print(f"ID: {mid} - 不存在!")
        print()

print("=" * 60)
print("诊断2: FTS5索引存在性检查")
print("=" * 60)
for mid in ["fb6e53897f9ace36", "749884cc6dbb59cd"]:
    row = conn.execute(
        "SELECT rowid, content FROM memories WHERE id=?", (mid,)
    ).fetchone()
    if row:
        rowid = row[0]
        fts_row = conn.execute(
            "SELECT rowid FROM memories_fts WHERE rowid=?", (rowid,)
        ).fetchone()
        print(f"ID:{mid} rowid={rowid} FTS5存在={fts_row is not None}")

print()
print("=" * 60)
print("诊断3: FTS5搜索测试（用补录内容关键词）")
print("=" * 60)
test_queries = ["跨会话审计", "10day", "backfill", "系统级策略沉淀"]
for q in test_queries:
    try:
        rows = conn.execute(
            "SELECT m.id, m.layer FROM memories m "
            "INNER JOIN memories_fts f ON m.rowid = f.rowid "
            "WHERE memories_fts MATCH ? "
            "ORDER BY f.rank LIMIT 3",
            (q,),
        ).fetchall()
        print(f"Query='{q}' -> 命中{len(rows)}条")
        for r in rows:
            print(f"  - {r['id']} (layer={r['layer']})")
    except Exception as e:
        print(f"Query='{q}' -> 错误: {e}")

print()
print("=" * 60)
print("诊断4: LIKE搜索测试（绕过FTS5）")
print("=" * 60)
for q in ["跨会话审计", "10day-backfill", "系统级策略沉淀"]:
    rows = conn.execute(
        "SELECT id, layer FROM memories WHERE content LIKE ? LIMIT 3", (f"%{q}%",)
    ).fetchall()
    print(f"LIKE '{q}' -> 命中{len(rows)}条")
    for r in rows:
        print(f"  - {r['id']} (layer={r['layer']})")

print()
print("=" * 60)
print("诊断5: 全库content_segmented空值统计")
print("=" * 60)
total = conn.execute("SELECT COUNT(*) FROM memories").fetchone()[0]
empty_seg = conn.execute(
    "SELECT COUNT(*) FROM memories WHERE content_segmented IS NULL OR content_segmented=''"
).fetchone()[0]
print(f"总记录: {total}")
print(f"content_segmented为空: {empty_seg} ({100 * empty_seg / total:.1f}%)")

# 按layer分组统计
print()
print("按layer分组:")
rows = conn.execute(
    "SELECT layer, COUNT(*) as total, "
    "SUM(CASE WHEN content_segmented IS NULL OR content_segmented='' THEN 1 ELSE 0 END) as empty_count "
    "FROM memories GROUP BY layer"
).fetchall()
for r in rows:
    pct = 100 * r["empty_count"] / r["total"] if r["total"] > 0 else 0
    print(f"  {r['layer']}: 总{r['total']} / 空{r['empty_count']} ({pct:.1f}%)")

conn.close()
print()
print("诊断完成")
