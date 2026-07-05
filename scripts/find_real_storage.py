"""查找真实存储位置"""

import glob
import io
import os
import sqlite3
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

print("=" * 60)
print("扫描所有icme.db文件")
print("=" * 60)
db_files = []
for root in [
    r"d:\元初系统\天机v9.1",
    r"d:\元初系统\天机v9.1\data",
    r"d:\元初系统\天机v9.1\data\.memory",
]:
    for f in glob.glob(os.path.join(root, "*.db")):
        size = os.path.getsize(f)
        db_files.append((f, size))

for f, size in db_files:
    print(f"  {f} ({size} bytes)")
    try:
        conn = sqlite3.connect(f)
        # 检查memories表
        try:
            count = conn.execute("SELECT COUNT(*) FROM memories").fetchone()[0]
            print(f"    memories记录: {count}")
        except:
            print("    memories表不存在")
        # 检查memories_fts表
        try:
            fts_count = conn.execute("SELECT COUNT(*) FROM memories_fts").fetchone()[0]
            print(f"    memories_fts记录: {fts_count}")
        except:
            print("    memories_fts表不存在")
        # 检查补录记录
        try:
            for mid in ["fb6e53897f9ace36", "749884cc6dbb59cd"]:
                row = conn.execute(
                    "SELECT id, layer FROM memories WHERE id=?", (mid,)
                ).fetchone()
                if row:
                    print(f"    找到补录记录: {mid} (layer={row[1]})")
        except:
            pass
        conn.close()
    except Exception as e:
        print(f"    错误: {e}")
    print()

print()
print("=" * 60)
print("扫描.json记忆文件")
print("=" * 60)
for root in [r"d:\元初系统\天机v9.1\data", r"d:\元初系统\天机v9.1\data\.memory"]:
    if os.path.exists(root):
        for f in glob.glob(os.path.join(root, "*.json"))[:5]:
            size = os.path.getsize(f)
            print(f"  {f} ({size} bytes)")

print()
print("=" * 60)
print("扫描.jsonl记忆文件")
print("=" * 60)
for root in [r"d:\元初系统\天机v9.1\data", r"d:\元初系统\天机v9.1\data\.memory"]:
    if os.path.exists(root):
        for f in glob.glob(os.path.join(root, "*.jsonl"))[:5]:
            size = os.path.getsize(f)
            print(f"  {f} ({size} bytes)")
