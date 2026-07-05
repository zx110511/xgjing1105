"""修复后审计验证脚本"""
import sqlite3
import py_compile
import os

DB_PATH = r"D:\元初系统\天机v9.1\data\.memory\icme.db"

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

# 1. Meta层当前状态
cur.execute("SELECT COUNT(*) FROM memories WHERE layer='meta'")
print(f"[Meta层当前] {cur.fetchone()[0]:,} 条")

# 2. 验证污染已清理
patterns = [
    ("[进化闭环]%", "进化闭环模板"),
    ("[Derived] [semantic->meta]%", "semantic->meta派生"),
    ("[Derived] [episodic->semantic]%", "episodic->semantic派生"),
    ("[TVP推送记录]%", "TVP推送记录"),
]
print("\n[污染清理验证]")
for pat, desc in patterns:
    cur.execute(
        "SELECT COUNT(*) FROM memories WHERE layer='meta' AND content LIKE ?",
        (pat,)
    )
    cnt = cur.fetchone()[0]
    status = "OK 已清理" if cnt == 0 else f"FAIL 仍有 {cnt} 条"
    print(f"  {desc}: {status}")

# 3. 保留的有价值内容
print("\n[保留内容验证]")
for pat, desc in [
    ("[策略归档]%", "策略归档"),
    ("[进化记录→Meta]%", "进化记录→Meta"),
    ("[Derived] 天机%", "天机相关Derived"),
    ("[Derived] 元初%", "元初相关Derived"),
]:
    cur.execute(
        "SELECT COUNT(*) FROM memories WHERE layer='meta' AND content LIKE ?",
        (pat,)
    )
    cnt = cur.fetchone()[0]
    print(f"  {desc}: {cnt} 条")

conn.close()

# 4. 验证修复代码语法
print("\n[修复代码语法验证]")
files = [
    r"core\processors\evolution_loop.py",
    r"core\memory\hybrid_engine_consolidate.py",
]
os.chdir(r"D:\元初系统\天机v9.1")
for f in files:
    try:
        py_compile.compile(f, doraise=True)
        print(f"  OK {f} 语法正确")
    except py_compile.PyCompileError as e:
        print(f"  FAIL {f} 语法错误: {e}")

print("\n=== 审计完成 ===")
