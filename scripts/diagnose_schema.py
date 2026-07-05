"""查看实际数据库schema"""

import io
import sqlite3
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

db = r"d:\元初系统\天机v9.1\data\icme.db"
conn = sqlite3.connect(db)

print("=" * 60)
print("memories表结构")
print("=" * 60)
rows = conn.execute("PRAGMA table_info(memories)").fetchall()
for r in rows:
    print(f"  {r}")

print()
print("=" * 60)
print("FTS5表结构")
print("=" * 60)
try:
    rows = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='memories_fts'"
    ).fetchall()
    for r in rows:
        print(f"  {r[0]}")
except Exception as e:
    print(f"错误: {e}")

print()
print("=" * 60)
print("所有trigger")
print("=" * 60)
rows = conn.execute(
    "SELECT name, sql FROM sqlite_master WHERE type='trigger' AND name LIKE 'memories%'"
).fetchall()
for r in rows:
    print(f"  Trigger: {r[0]}")
    print(f"  SQL: {r[1]}")
    print()

print()
print("=" * 60)
print("FTS5表数据量")
print("=" * 60)
try:
    count = conn.execute("SELECT COUNT(*) FROM memories_fts").fetchone()[0]
    print(f"  memories_fts 记录数: {count}")
except Exception as e:
    print(f"  错误: {e}")

print()
print("=" * 60)
print("memories表记录数")
print("=" * 60)
total = conn.execute("SELECT COUNT(*) FROM memories").fetchone()[0]
print(f"  memories 记录数: {total}")

# 检查补录记录
print()
print("=" * 60)
print("补录记录检查")
print("=" * 60)
for mid in ["fb6e53897f9ace36", "749884cc6dbb59cd"]:
    row = conn.execute(
        "SELECT id, layer, substr(content, 1, 80) as preview FROM memories WHERE id=?",
        (mid,),
    ).fetchone()
    if row:
        print(f"  ID: {row[0]}")
        print(f"  Layer: {row[1]}")
        print(f"  Preview: {row[2]}")
    else:
        print(f"  ID: {mid} - 不存在")

conn.close()
