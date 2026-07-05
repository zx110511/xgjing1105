import sqlite3
import json

db_path = r"d:\元初系统\天机v9.1\data\icme.db"

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# 查询最近录入的记录
ids = ['06c852ba8b345207', '8c9fd930de8857bb', '64f2088ca2033dd2']

for id in ids:
    cursor.execute("SELECT id, layer, content, tags FROM memories WHERE id = ?", (id,))
    row = cursor.fetchone()
    if row:
        print(f"\n✅ 找到记录: {row[0]}")
        print(f"   Layer: {row[1]}")
        print(f"   Content (前100字): {row[2][:100]}...")
        print(f"   Tags: {row[3]}")
    else:
        print(f"\n❌ 未找到记录: {id}")

# 查询最近的记录
print("\n\n=== 最近录入的5条记录 ===")
cursor.execute("SELECT id, layer, substr(content, 1, 50) as content_preview, created_at FROM memories ORDER BY created_at DESC LIMIT 5")
rows = cursor.fetchall()
for row in rows:
    print(f"{row[0]} | {row[1]} | {row[2]}... | {row[3]}")

conn.close()
