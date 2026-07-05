# -*- coding: utf-8-sig -*-
"""搜索记忆中关于激进精简、技能系统重构的经验"""

import sqlite3

db_path = r"d:\元初系统\天机v9.1\data\.memory\icme.db"
conn = sqlite3.connect(db_path)
c = conn.cursor()

searches = [
    "激进精简",
    "技能系统重构",
    "技能文件%删除",
    "统一能力层",
    "去中心化技能",
    "技能%记忆%融合",
    "极简架构",
    "能力驱动设计",
]

print("=" * 72)
print("搜索激进精简相关记忆")
print("=" * 72)

for kw in searches:
    try:
        c.execute(
            "SELECT id, layer, content FROM memories WHERE content LIKE ? ORDER BY created_at DESC LIMIT 2",
            (f"%{kw}%",),
        )
        rows = c.fetchall()
        if rows:
            print(f"\n📌 {kw} | {len(rows)} 条")
            for r in rows:
                content = r[2]
                if len(content) > 300:
                    content = content[:300] + "..."
                print(f"  [{r[1]}] {r[0]}")
                print(f"  {content}")
                print()
    except Exception:
        pass

conn.close()
