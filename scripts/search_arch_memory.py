# -*- coding: utf-8-sig -*-
"""搜索记忆中关于MCP工具与技能文件关系的架构决策"""

import sqlite3

db_path = r"d:\元初系统\天机v9.1\data\.memory\icme.db"
conn = sqlite3.connect(db_path)
c = conn.cursor()

searches = [
    "MCP工具%技能%关系",
    "技能文件%MCP%规划",
    "三套工具系统%架构",
    "技能注册中心%设计",
    "CapabilityRegistry%SkillRegistry",
    "工具%技能%一体化",
    "统一能力%架构",
    "技能%MCP%对齐",
]

print("=" * 72)
print("搜索架构决策相关记忆")
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
                if len(content) > 400:
                    content = content[:400] + "..."
                print(f"  [{r[1]}] {r[0]}")
                print(f"  {content}")
                print()
    except Exception:
        pass

conn.close()
