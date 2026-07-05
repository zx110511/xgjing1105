# -*- coding: utf-8-sig -*-
"""读取关键记忆的完整内容"""

import sqlite3

db_path = r"d:\元初系统\天机v9.1\data\.memory\icme.db"
conn = sqlite3.connect(db_path)
c = conn.cursor()

# 关键记忆关键词
queries = [
    "启动文件最强修复对齐规则",
    "启动体系灵魂拷问",
    "71个API端点",
    "三套工具系统澄清",
]

for q in queries:
    try:
        c.execute(
            "SELECT id, layer, content FROM memories WHERE content LIKE ? ORDER BY created_at DESC LIMIT 1",
            (f"%{q}%",),
        )
        row = c.fetchone()
        if row:
            print("=" * 72)
            print(f"ID: {row[0]} | Layer: {row[1]}")
            print(f"关键词: {q}")
            print("=" * 72)
            print(row[2])
            print()
    except Exception as e:
        print(f"搜索 {q} 出错: {e}")

conn.close()
