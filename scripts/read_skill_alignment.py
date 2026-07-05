# -*- coding: utf-8-sig -*-
"""读取MCP工具与技能对齐的完整记忆+查看技能文件结构"""

import sqlite3

db_path = r"d:\元初系统\天机v9.1\data\.memory\icme.db"
conn = sqlite3.connect(db_path)
c = conn.cursor()

# 读取关键记忆
c.execute("SELECT content FROM memories WHERE id = 'd2153d1b2b43538e'")
row = c.fetchone()
if row:
    print("=" * 72)
    print("MCP工具与技能对齐记忆")
    print("=" * 72)
    print(row[0])
    print()

# 搜索更多关于技能注册中心的记忆
c.execute(
    "SELECT id, content FROM memories WHERE content LIKE '%技能注册中心%' AND content LIKE '%设计%' ORDER BY created_at DESC LIMIT 3"
)
rows = c.fetchall()
if rows:
    print("=" * 72)
    print("技能注册中心设计记忆")
    print("=" * 72)
    for r in rows:
        content = r[1]
        if len(content) > 500:
            content = content[:500] + "..."
        print(f"[{r[0]}]")
        print(content)
        print()

conn.close()
