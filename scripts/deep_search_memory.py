# -*- coding: utf-8-sig -*-
"""深度搜索记忆中的MCP工具和修复经验"""

import sqlite3

db_path = r"d:\元初系统\天机v9.1\data\.memory\icme.db"
conn = sqlite3.connect(db_path)
c = conn.cursor()

keywords = [
    "73个",
    "73个MCP",
    "MCP全部技能测试",
    "全量测试通过",
    "托盘启动成功",
    "mcp_tools",
    "MCP工具清单",
    "tool_schema",
    "MCP测试报告",
]

print("=" * 72)
print("深度搜索记忆中的修复经验")
print("=" * 72)

for kw in keywords:
    try:
        c.execute(
            "SELECT id, layer, content FROM memories WHERE content LIKE ? ORDER BY created_at DESC LIMIT 3",
            (f"%{kw}%",),
        )
        rows = c.fetchall()
        if rows:
            print(f"\n📌 关键词: {kw} | 找到 {len(rows)} 条")
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
