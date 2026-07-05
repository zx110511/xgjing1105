"""天机v9.1 存储结构清理脚本 — P0/P1/P2"""
import os, shutil

DATA = r"D:\元初系统\天机v9.1\data"
MEM = os.path.join(DATA, ".memory")

print("=" * 60)
print("P0: 删除 data/icme.db 旧版残留")
print("=" * 60)
old_db = os.path.join(DATA, "icme.db")
if os.path.exists(old_db):
    sz = os.path.getsize(old_db)
    os.remove(old_db)
    print(f"  [OK] 已删除 {old_db} ({sz / 1024 / 1024:.1f} MB)")
else:
    print(f"  [SKIP] {old_db} 不存在")

# 确认 .memory/icme.db 存在
active_db = os.path.join(MEM, "icme.db")
if os.path.exists(active_db):
    print(f"  [确认] 活跃主库存在: {active_db} ({os.path.getsize(active_db) / 1024 / 1024:.1f} MB)")
else:
    print(f"  [WARN] 活跃主库不存在: {active_db}")

print("\n" + "=" * 60)
print("P1: 迁移 test_*.db 到 data/tests/")
print("=" * 60)

test_dbs = [f for f in os.listdir(DATA) if f.startswith('test_') and f.endswith('.db')]
test_dir = os.path.join(DATA, 'tests')
if not os.path.exists(test_dir):
    os.makedirs(test_dir)
    print(f"  创建目录: {test_dir}")

for f in test_dbs:
    src = os.path.join(DATA, f)
    dst = os.path.join(test_dir, f)
    shutil.move(src, dst)
    print(f"  [OK] {f} -> tests/")

# 检查是否还有残留
remaining = [f for f in os.listdir(DATA) if f.startswith('test_') and f.endswith('.db')]
if remaining:
    print(f"  [WARN] 仍有残留: {remaining}")
else:
    print(f"  [OK] 所有test数据库已清理完毕")

print("\n" + "=" * 60)
print("P2: WAL 清理 — PRAGMA wal_checkpoint(TRUNCATE)")
print("=" * 60)
import sqlite3
wal_path = os.path.join(MEM, "icme.db-wal")
shm_path = os.path.join(MEM, "icme.db-shm")

wal_sz = os.path.getsize(wal_path) if os.path.exists(wal_path) else 0
shm_sz = os.path.getsize(shm_path) if os.path.exists(shm_path) else 0
print(f"  WAL前: wal={wal_sz / 1024 / 1024:.2f}MB, shm={shm_sz / 1024:.0f}KB")

try:
    conn = sqlite3.connect(active_db)
    result = conn.execute("PRAGMA wal_checkpoint(TRUNCATE)").fetchone()
    conn.close()
    wal_after = os.path.getsize(wal_path) if os.path.exists(wal_path) else 0
    shm_after = os.path.getsize(shm_path) if os.path.exists(shm_path) else 0
    print(f"  WAL后: wal={wal_after / 1024 / 1024:.2f}MB, shm={shm_after / 1024:.0f}KB")
    print(f"  checkpoint结果: busy={result[0]}, log={result[1]}, checkpointed={result[2]}")
except Exception as e:
    print(f"  [ERROR] {e}")

print("\n" + "=" * 60)
print("存储清理完成!")
print("=" * 60)
