# -*- coding: utf-8-sig -*-
"""读取MCP工具和启动修复的完整记忆"""

import sqlite3

db_path = r"d:\元初系统\天机v9.1\data\.memory\icme.db"
conn = sqlite3.connect(db_path)
c = conn.cursor()

# 搜索更多关键词
keywords = [
    "MCP协议工具",
    "39个MCP",
    "桌面快捷方式",
    "托盘启动修复",
    "start_tianji.bat",
    "2026-06-30 天机v9.1启动修复",
    "全量测试",
    "MCP全部技能测试",
]

for kw in keywords:
    try:
        c.execute(
            "SELECT id, layer, content FROM memories WHERE content LIKE ? ORDER BY created_at DESC LIMIT 2",
            (f"%{kw}%",),
        )
        rows = c.fetchall()
        if rows:
            print("=" * 72)
            print(f"关键词: {kw} | 找到 {len(rows)} 条")
            print("=" * 72)
            for r in rows[:1]:
                print(f"ID: {r[0]} | Layer: {r[1]}")
                # 打印前500字
                content = r[2]
                if len(content) > 800:
                    content = content[:800] + "..."
                print(content)
            print()
    except Exception:
        pass

conn.close()
