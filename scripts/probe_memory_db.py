# -*- coding: utf-8-sig -*-
"""探查 .memory/icme.db 数据库结构"""
import sqlite3, os

db_path = r"D:\元初系统\天机v9.1\data\.memory\icme.db"
# 使用URI方式打开（只读模式，避免锁冲突）
uri = f"file://{db_path}?mode=ro"
try:
    conn = sqlite3.connect(uri, uri=True)
except:
    conn = sqlite3.connect(db_path)

cur = conn.cursor()

# 列出所有表
cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
tables = [r[0] for r in cur.fetchall()]
print(f"[TABLES] ({len(tables)}): {tables}")

# 检查每个表的行数和结构
for t in tables:
    try:
        cur.execute(f"SELECT COUNT(*) FROM [{t}]")
        cnt = cur.fetchone()[0]
        if cnt > 0:
            print(f"  [{t}]: {cnt:,} rows")
            # 检查是否有 layer 字段
            cur.execute(f"PRAGMA table_info([{t}])")
            cols = [(r[1], r[2]) for r in cur.fetchall()]
            col_names = [c[0] for c in cols]
            if 'layer' in col_names:
                # 按layer统计
                cur.execute(f"SELECT layer, COUNT(*) FROM [{t}] GROUP BY layer ORDER BY COUNT(*) DESC")
                for layer, lcnt in cur.fetchall():
                    print(f"      layer='{layer}': {lcnt:,}")
    except Exception as e:
        print(f"  [{t}]: ERROR {e}")

conn.close()

# 也检查其他DB
for db_name in ['tcl_terminology.db', 'turn_log.db', 'tianji_memory.db']:
    db2 = rf"D:\元初系统\天机v9.1\data\.memory\{db_name}"
    if os.path.exists(db2):
        try:
            c2 = sqlite3.connect(f"file://{db2}?mode=ro", uri=True)
        except:
            c2 = sqlite3.connect(db2)
        cur2 = c2.cursor()
        cur2.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        tabs = [r[0] for r in cur2.fetchall()]
        print(f"\n[{db_name}] tables: {tabs}")
        for t in tabs:
            try:
                cur2.execute(f"SELECT COUNT(*) FROM [{t}]")
                print(f"  [{t}]: {cur2.fetchone()[0]:,} rows")
            except:
                pass
        c2.close()
