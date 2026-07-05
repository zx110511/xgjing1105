"""Meta层备份+清理脚本 - 天机v9.1
[P0-FIX] 适配 .memory/icme.db 的 memories 表
目标: meta层 362,668 → <80,000 (保留最新80000条)
"""
import sqlite3
import shutil
import os
import json
import time
from datetime import datetime

# ── [P0-FIX] 适配 .memory DB ──
DB_PATH = r"D:\元初系统\天机v9.1\data\.memory\icme.db"
BACKUP_DIR = r"D:\元初系统\天机v9.1\data\backups"
KEEP_COUNT = 80000  # 保留最新80000条

os.makedirs(BACKUP_DIR, exist_ok=True)

# Step 1: 备份整个数据库
ts = datetime.now().strftime("%Y%m%d_%H%M%S")
backup_db = os.path.join(BACKUP_DIR, f"icme_memory_backup_{ts}.db")
print(f"[BACKUP] 正在备份数据库...")
shutil.copy2(DB_PATH, backup_db)
backup_size_mb = os.path.getsize(backup_db) / (1024 * 1024)
print(f"[BACKUP] {backup_db} ({backup_size_mb:.1f} MB)")

conn = sqlite3.connect(DB_PATH)
conn.execute("PRAGMA journal_mode=WAL")
conn.execute("PRAGMA synchronous=NORMAL")
cur = conn.cursor()

# Step 2: 查看表概况
cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
tables = [r[0] for r in cur.fetchall()]
print(f"\n[TABLES] {len(tables)} 个表")

for t in tables:
    try:
        cur.execute(f"SELECT COUNT(*) FROM [{t}]")
        cnt = cur.fetchone()[0]
        if cnt > 0:
            print(f"  {t}: {cnt:,} rows")
    except Exception as e:
        print(f"  {t}: ERROR {e}")

# Step 3: Meta层统计 (memories表, layer='meta')
print(f"\n[META LAYER]")
try:
    cur.execute("SELECT COUNT(*) FROM memories WHERE layer='meta'")
    meta_cnt = cur.fetchone()[0]
    print(f"  当前 meta 条目数: {meta_cnt:,}")

    # 按created_at查看分布
    cur.execute("""
        SELECT MIN(created_at), MAX(created_at), COUNT(*)
        FROM memories WHERE layer='meta'
    """)
    min_ts, max_ts, _ = cur.fetchone()
    if min_ts and max_ts:
        from datetime import datetime as dt
        print(f"  时间范围: {dt.fromtimestamp(min_ts)} ~ {dt.fromtimestamp(max_ts)}")

except Exception as e:
    print(f"  Error: {e}")
    meta_cnt = 0

# Step 4: 清理Meta层 — 保留最新 KEEP_COUNT 条
if meta_cnt > KEEP_COUNT:
    delete_cnt = meta_cnt - KEEP_COUNT
    print(f"\n[CLEANUP] 将删除 {delete_cnt:,} 条旧meta记录 (保留最新 {KEEP_COUNT:,})...")

    # 方案: 使用子查询删除 — 删除不在最新KEEP_COUNT条中的记录
    # 优化: 使用临时表避免子查询性能问题
    start_time = time.time()

    # 获取要保留的id列表 (用created_at排序)
    cur.execute("""
        CREATE TEMP TABLE _meta_keep AS
        SELECT id FROM memories
        WHERE layer='meta'
        ORDER BY created_at DESC
        LIMIT ?
    """, (KEEP_COUNT,))

    keep_rows = cur.fetchone()  # 先消费掉结果
    cur.execute("SELECT COUNT(*) FROM _meta_keep")
    kept_in_temp = cur.fetchone()[0]
    print(f"  临时表已创建: {kept_in_temp:,} 条待保留记录")

    # 删除不在保留列表中的记录
    cur.execute("""
        DELETE FROM memories
        WHERE layer='meta'
        AND id NOT IN (SELECT id FROM _meta_keep)
    """)
    deleted = cur.rowcount
    conn.commit()
    elapsed = time.time() - start_time
    print(f"  已删除: {deleted:,} 条 (耗时 {elapsed:.1f}s)")

    # 清理临时表
    cur.execute("DROP TABLE IF EXISTS _meta_keep")
    conn.commit()

    # 验证
    cur.execute("SELECT COUNT(*) FROM memories WHERE layer='meta'")
    remaining = cur.fetchone()[0]
    print(f"  剩余: {remaining:,} 条")

    # VACUUM释放空间
    print("  正在执行 VACUUM 释放磁盘空间...")
    vacuum_start = time.time()
    conn.execute("VACUUM")
    print(f"  VACUUM 完成 (耗时 {time.time() - vacuum_start:.1f}s)")

else:
    print(f"\n[CLEANUP] Meta层 ({meta_cnt:,}) 在阈值内, 无需清理.")

# Step 5: 最终统计
conn.close()

final_size_mb = os.path.getsize(DB_PATH) / (1024 * 1024)
print(f"\n[DONE] 最终 DB 大小: {final_size_mb:.1f} MB (清理前: {backup_size_mb:.1f} MB)")
print(f"备份文件: {backup_db}")
print(f"\n✅ Meta层清理完成 — 保留最新 {min(meta_cnt, KEEP_COUNT):,} 条")
