"""直接SQL修复被错误降级的meta层记录"""

import io
import sqlite3
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

db = r"d:\元初系统\天机v9.1\data\.memory\icme.db"
conn = sqlite3.connect(db)

print("=" * 60)
print("1. 修复被错误降级的L5 Meta记录")
print("=" * 60)

# 修复749884cc6dbb59cd (L5 Meta策略沉淀被降级到episodic)
fix_id = "749884cc6dbb59cd"
row = conn.execute(
    "SELECT id, layer, content FROM memories WHERE id=?", (fix_id,)
).fetchone()
if row:
    print(f"  修复前: id={row[0]} layer={row[1]}")
    print(f"  content前60: {row[2][:60]}")
    # 更新layer为meta
    conn.execute("UPDATE memories SET layer='meta' WHERE id=?", (fix_id,))
    conn.commit()
    # 验证
    row2 = conn.execute(
        "SELECT id, layer FROM memories WHERE id=?", (fix_id,)
    ).fetchone()
    print(f"  修复后: id={row2[0]} layer={row2[1]}")
    print(f"  修复结果: {'PASS' if row2[1] == 'meta' else 'FAIL'}")

print()
print("=" * 60)
print("2. 修复最近被错误降级的meta层测试记录")
print("=" * 60)

# 修复刚才测试时被降级的记录(072f64c5278b67e9)
fix_id2 = "072f64c5278b67e9"
row = conn.execute(
    "SELECT id, layer, content FROM memories WHERE id=?", (fix_id2,)
).fetchone()
if row:
    print(f"  修复前: id={row[0]} layer={row[1]}")
    conn.execute("UPDATE memories SET layer='meta' WHERE id=?", (fix_id2,))
    conn.commit()
    row2 = conn.execute(
        "SELECT id, layer FROM memories WHERE id=?", (fix_id2,)
    ).fetchone()
    print(f"  修复后: id={row2[0]} layer={row2[1]}")
    print(f"  修复结果: {'PASS' if row2[1] == 'meta' else 'FAIL'}")

print()
print("=" * 60)
print("3. FTS5索引同步检查")
print("=" * 60)
# 检查FTS5是否需要重建（layer变更后FTS5是否同步）
for mid in [fix_id, fix_id2]:
    row = conn.execute("SELECT rowid FROM memories WHERE id=?", (mid,)).fetchone()
    if row:
        rowid = row[0]
        # 检查FTS5中是否有这条记录
        fts_row = conn.execute(
            "SELECT rowid FROM memories_fts WHERE rowid=?", (rowid,)
        ).fetchone()
        print(f"  id={mid} rowid={rowid} FTS5存在={fts_row is not None}")

print()
print("=" * 60)
print("4. 按layer统计(修复后)")
print("=" * 60)
rows = conn.execute(
    "SELECT layer, COUNT(*) as cnt FROM memories GROUP BY layer ORDER BY cnt DESC"
).fetchall()
for r in rows:
    print(f"  {r[0]}: {r[1]}")

conn.close()
print()
print("SQL修复完成")
