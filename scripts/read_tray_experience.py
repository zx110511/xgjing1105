# -*- coding: utf-8-sig -*-
"""读取托盘启动经验的完整内容"""

import sqlite3

db_path = r"d:\元初系统\天机v9.1\data\.memory\icme.db"
conn = sqlite3.connect(db_path)
c = conn.cursor()

# 读取托盘启动经验
c.execute(
    "SELECT content FROM memories WHERE layer = 'short_term' AND content LIKE '%托盘启动%' ORDER BY created_at DESC LIMIT 1"
)
row = c.fetchone()
if row:
    print("=" * 72)
    print("托盘启动经验")
    print("=" * 72)
    print(row[0])

# 读取鉴衡审计经验
print("\n" + "=" * 72)
print("鉴衡-七律审计v3.0经验")
print("=" * 72)
c.execute(
    "SELECT content FROM memories WHERE content LIKE '%鉴衡-七律审计%' ORDER BY created_at DESC LIMIT 1"
)
row = c.fetchone()
if row:
    print(row[0])

# 读取v9.0全自动化测试经验
print("\n" + "=" * 72)
print("天机v9.0全自动化测试")
print("=" * 72)
c.execute(
    "SELECT content FROM memories WHERE content LIKE '%全自动化测试通过率100%%%' ORDER BY created_at DESC LIMIT 1"
)
row = c.fetchone()
if row:
    print(row[0][:1000])

conn.close()
