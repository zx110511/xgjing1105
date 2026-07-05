# -*- coding: utf-8-sig -*-
"""搜索托盘启动和全量测试相关记忆"""

import sqlite3

db_path = r"d:\元初系统\天机v9.1\data\.memory\icme.db"
conn = sqlite3.connect(db_path)
c = conn.cursor()

searches = [
    ("托盘启动成功", "托盘.*启动.*成功|启动.*托盘.*成功"),
    ("全量测试通过", "全量.*测试.*通过|测试.*全量.*通过"),
    ("桌面快捷方式修复", "桌面快捷方式.*修复|快捷方式.*启动"),
    ("71个工具测试", "71.*工具.*测试|工具.*71.*测试"),
    ("MCP全部技能", "MCP全部技能|全部技能测试"),
    ("启动修复经验", "启动.*修复.*经验|修复.*启动.*经验"),
]

for name, pattern in searches:
    try:
        c.execute(
            "SELECT id, layer, content FROM memories WHERE content REGEXP ? ORDER BY created_at DESC LIMIT 2",
            (pattern,),
        )
        rows = c.fetchall()
        if rows:
            print(f"\n📌 {name} | 找到 {len(rows)} 条")
            for r in rows:
                print(f"  [{r[1]}] {r[0]}")
                content = r[2]
                if len(content) > 300:
                    content = content[:300] + "..."
                print(f"  {content}")
                print()
    except Exception as e:
        print(f"  搜索 {name} 出错: {e}")

# 用LIKE搜索更简单的关键词
simple_kw = [
    "托盘启动",
    "快捷方式启动",
    "测试通过率",
    "MCP测试",
]
print("\n" + "=" * 72)
print("简单关键词搜索")
print("=" * 72)
for kw in simple_kw:
    try:
        c.execute(
            "SELECT id, layer, content FROM memories WHERE content LIKE ? ORDER BY created_at DESC LIMIT 2",
            (f"%{kw}%",),
        )
        rows = c.fetchall()
        if rows:
            print(f"\n{kw} | {len(rows)} 条")
            for r in rows:
                content = r[2][:200].replace("\n", " ")
                print(f"  [{r[1]}] {content}...")
    except Exception:
        pass

conn.close()
