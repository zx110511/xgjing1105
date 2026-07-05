# -*- coding: utf-8-sig -*-
"""快速检索记忆数据库中的托盘启动和MCP修复经验"""

import sqlite3

db_path = r"d:\元初系统\天机v9.1\data\.memory\tianji_memory.db"

try:
    conn = sqlite3.connect(db_path)
    c = conn.cursor()

    # 先查看表结构
    c.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = c.fetchall()
    print(f"数据库表: {[t[0] for t in tables]}")
    print()

    # 查看记忆表结构
    c.execute("PRAGMA table_info(memories)")
    cols = c.fetchall()
    print(f"memories表字段: {[c[1] for c in cols]}")
    print()

    # 搜索关键词
    keywords = [
        "托盘",
        "启动",
        "MCP",
        "修复",
        "tray",
        "71",
        "73",
        "全部技能",
        "桌面快捷方式",
    ]
    found_total = 0

    for kw in keywords:
        try:
            c.execute(
                "SELECT id, layer, content, created_at FROM memories WHERE content LIKE ? ORDER BY created_at DESC LIMIT 3",
                (f"%{kw}%",),
            )
            rows = c.fetchall()
            if rows:
                print(f'=== 关键词 "{kw}" 找到 {len(rows)} 条 ===')
                for r in rows:
                    content_preview = r[2][:120].replace("\n", " ")
                    print(f"  [{r[1]}] {content_preview}...")
                    print(f"    id: {r[0]}, time: {r[3]}")
                print()
                found_total += len(rows)
        except Exception:
            pass

    print(f"共找到 {found_total} 条相关记忆")

    conn.close()
except Exception as e:
    print(f"错误: {e}")
    import traceback

    traceback.print_exc()
