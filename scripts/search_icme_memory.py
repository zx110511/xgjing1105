# -*- coding: utf-8-sig -*-
"""快速检索ICME记忆数据库中的托盘启动和MCP修复经验"""

import sqlite3

db_paths = [
    r"d:\元初系统\天机v9.1\data\icme.db",
    r"d:\元初系统\天机v9.1\data\.memory\icme.db",
]

for db_path in db_paths:
    print(f"检查数据库: {db_path}")
    try:
        conn = sqlite3.connect(db_path)
        c = conn.cursor()

        # 查看表结构
        c.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = c.fetchall()
        print(f"  表: {[t[0] for t in tables]}")

        # 查找记忆相关的表
        mem_tables = [
            t[0] for t in tables if "memor" in t[0].lower() or "entry" in t[0].lower()
        ]

        for tbl in mem_tables[:3]:
            try:
                c.execute(f"SELECT COUNT(*) FROM {tbl}")
                count = c.fetchone()[0]
                print(f"  {tbl}: {count} 条记录")
            except:
                pass

        # 搜索关键词
        keywords = ["托盘", "启动", "MCP", "修复", "tray", "71", "73", "技能"]

        for tbl in mem_tables[:2]:
            for kw in keywords:
                try:
                    c.execute(
                        f"SELECT * FROM {tbl} WHERE content LIKE ? ORDER BY created_at DESC LIMIT 2",
                        (f"%{kw}%",),
                    )
                    rows = c.fetchall()
                    if rows:
                        print(f'  === {tbl} 关键词"{kw}" 找到 {len(rows)} 条 ===')
                        for r in rows[:2]:
                            # 找content字段
                            content = ""
                            for val in r:
                                if isinstance(val, str) and len(val) > 20:
                                    content = val[:100].replace("\n", " ")
                                    break
                            print(f"    {content}...")
                except:
                    pass

        conn.close()
    except Exception as e:
        print(f"  错误: {e}")
    print()
