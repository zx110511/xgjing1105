# -*- coding: utf-8-sig -*-
"""读取MCP Server故障排查经验的完整内容"""

import sqlite3

db_path = r"d:\元初系统\天机v9.1\data\.memory\icme.db"
conn = sqlite3.connect(db_path)
c = conn.cursor()

# 读取MCP故障排查经验
c.execute("SELECT content FROM memories WHERE id = 'b8bc4ebf7db994a2'")
row = c.fetchone()
if row:
    print(row[0])

# 再搜索更多相关经验
print("\n" + "=" * 72)
print("搜索更多MCP测试经验")
print("=" * 72)

c.execute(
    "SELECT id, layer, content FROM memories WHERE content LIKE '%MCP%测试%' ORDER BY created_at DESC LIMIT 5"
)
rows = c.fetchall()
for r in rows:
    print(f"\n[{r[1]}] {r[0]}")
    content = r[2]
    if len(content) > 500:
        content = content[:500] + "..."
    print(content)

conn.close()
