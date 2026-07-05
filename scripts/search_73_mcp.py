# -*- coding: utf-8-sig -*-
"""搜索记忆中关于73个MCP工具的记录"""

import sqlite3

db_path = r"d:\元初系统\天机v9.1\data\.memory\icme.db"
conn = sqlite3.connect(db_path)
c = conn.cursor()

# 搜索包含73且与MCP/工具/技能相关的记忆
searches = [
    "%73%MCP%",
    "%MCP%73%",
    "%73个%技能%",
    "%73个%工具%",
    "%工具总数%73%",
    "%MCP工具总数%",
    "%技能总数%",
    "%71个%MCP%",
    "%39个%MCP%",
]

for s in searches:
    try:
        c.execute(
            "SELECT id, layer, content FROM memories WHERE content LIKE ? ORDER BY created_at DESC LIMIT 2",
            (s,),
        )
        rows = c.fetchall()
        if rows:
            print(f"\n📌 模式: {s} | 找到 {len(rows)} 条")
            for r in rows:
                content = r[2]
                if len(content) > 300:
                    content = content[:300] + "..."
                print(f"  [{r[1]}] {r[0]}")
                print(f"  {content}")
                print()
    except Exception as e:
        print(f"  搜索 {s} 出错: {e}")

# 搜索MCP相关的所有L5 Meta记忆
print("\n" + "=" * 72)
print("所有L5 Meta层MCP相关记忆")
print("=" * 72)
try:
    c.execute(
        "SELECT id, created_at, content FROM memories WHERE layer = 'meta' AND content LIKE '%MCP%' ORDER BY created_at DESC LIMIT 10"
    )
    rows = c.fetchall()
    for r in rows:
        content = r[2]
        if len(content) > 200:
            content = content[:200] + "..."
        print(f"\n[{r[1]}] {r[0]}")
        print(f"  {content}")
except Exception as e:
    print(f"出错: {e}")

conn.close()
