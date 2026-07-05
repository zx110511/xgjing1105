"""Meta层历史污染清理脚本 - 清理无效进化记录
[P2-CLEANUP] 清理4类历史污染:
1. [进化闭环] module=X action=Y effectiveness=Z 重复模板记录 (~52000条)
2. [Derived] [semantic->meta] [episodic->semantic] ... 派生链路记录 (~19569条)
3. [TVP推送记录] event_id=... 自动调度记录 (~2000条)
4. 保留: [策略归档]、[进化记录→Meta]、用户真实录入
"""
import sqlite3
import shutil
import os
from datetime import datetime

DB_PATH = r"D:\元初系统\天机v9.1\data\.memory\icme.db"
BACKUP_DIR = r"D:\元初系统\天机v9.1\data\backups"
META_TARGET = 40000  # 目标: 清理到40000条以下 (留足缓冲)

os.makedirs(BACKUP_DIR, exist_ok=True)

# Step 1: 备份数据库
ts = datetime.now().strftime("%Y%m%d_%H%M%S")
backup_db = os.path.join(BACKUP_DIR, f"icme_memory_backup_pollution_{ts}.db")
print(f"[BACKUP] 正在备份数据库...")
shutil.copy2(DB_PATH, backup_db)
print(f"[BACKUP] {backup_db} ({os.path.getsize(backup_db)/1024/1024:.1f} MB)")

conn = sqlite3.connect(DB_PATH)
conn.execute("PRAGMA journal_mode=WAL")
cur = conn.cursor()

# Step 2: 清理前统计
cur.execute("SELECT COUNT(*) FROM memories WHERE layer='meta'")
before_count = cur.fetchone()[0]
print(f"\n[BEFORE] Meta层: {before_count:,} 条")

# Step 3: 分类统计污染
print("\n[污染分类统计]")
pollution_patterns = [
    ("[进化闭环] module=hybrid_engine action=remember",
     "进化闭环-hybrid_engine-remember模板记录"),
    ("[进化闭环] module=quality_gate action=gate_check",
     "进化闭环-quality_gate-gate_check模板记录"),
    ("[进化闭环] module=%", "其他进化闭环模板记录"),
    ("[Derived] [semantic->meta]%", "派生链路semantic->meta记录"),
    ("[Derived] [episodic->semantic]%", "派生链路episodic->semantic记录"),
    ("[Derived] [short_term->episodic]%", "派生链路short_term->episodic记录"),
    ("[Derived] [working->short_term]%", "派生链路working->short_term记录"),
    ("[TVP推送记录]%", "TVP自动调度推送记录"),
]

total_pollution = 0
for pattern, desc in pollution_patterns:
    cur.execute(
        "SELECT COUNT(*) FROM memories WHERE layer='meta' AND content LIKE ?",
        (pattern,)
    )
    cnt = cur.fetchone()[0]
    if cnt > 0:
        print(f"  {desc}: {cnt:,} 条")
        total_pollution += cnt

print(f"\n  [总计待清理污染]: {total_pollution:,} 条")

# Step 4: 执行清理 (按优先级 — 先删大量重复模板)
print("\n[CLEANUP] 开始清理污染...")

cleanup_queries = [
    # 1. 最大量: hybrid_engine remember模板 (effectiveness=-0.50)
    ("[进化闭环] module=hybrid_engine action=remember%",
     "清理 hybrid_engine remember 模板"),
    # 2. 第二大量: quality_gate gate_check模板 (effectiveness=0.50)
    ("[进化闭环] module=quality_gate action=gate_check%",
     "清理 quality_gate gate_check 模板"),
    # 3. 其他进化闭环模板
    ("[进化闭环]%", "清理其他进化闭环模板"),
    # 4. 派生链路记录 (Derived)
    ("[Derived] [semantic->meta]%", "清理 semantic->meta 派生"),
    ("[Derived] [episodic->semantic]%", "清理 episodic->semantic 派生"),
    ("[Derived] [short_term->episodic]%", "清理 short_term->episodic 派生"),
    ("[Derived] [working->short_term]%", "清理 working->short_term 派生"),
    # 5. TVP自动调度推送
    ("[TVP推送记录]%", "清理 TVP推送记录"),
]

total_deleted = 0
for pattern, desc in cleanup_queries:
    cur.execute(
        "DELETE FROM memories WHERE layer='meta' AND content LIKE ?",
        (pattern,)
    )
    deleted = cur.rowcount
    conn.commit()
    if deleted > 0:
        print(f"  ✓ {desc}: 删除 {deleted:,} 条")
        total_deleted += deleted

# Step 5: 如果还超过目标，按时间清理最旧的低价值记录
cur.execute("SELECT COUNT(*) FROM memories WHERE layer='meta'")
after_cleanup = cur.fetchone()[0]
print(f"\n[AFTER_CLEANUP] Meta层: {after_cleanup:,} 条 (已删除 {total_deleted:,})")

if after_cleanup > META_TARGET:
    excess = after_cleanup - META_TARGET
    print(f"[EXCESS] 仍超出目标 {META_TARGET}: {excess} 条, 删除最旧低价值记录...")
    # 删除最旧的 value_score 较低的记录
    cur.execute("""
        DELETE FROM memories
        WHERE layer='meta'
        AND id IN (
            SELECT id FROM memories
            WHERE layer='meta'
            ORDER BY value_score ASC, access_count ASC, created_at ASC
            LIMIT ?
        )
    """, (excess,))
    extra_deleted = cur.rowcount
    conn.commit()
    print(f"  ✓ 额外删除低价值记录: {extra_deleted:,} 条")
    total_deleted += extra_deleted

# Step 6: VACUUM 释放空间
print("\n[VACUUM] 正在执行 VACUUM 释放磁盘空间...")
conn.execute("VACUUM")

# Step 7: 最终统计
cur.execute("SELECT COUNT(*) FROM memories WHERE layer='meta'")
final_count = cur.fetchone()[0]
conn.close()

print(f"\n[FINAL] Meta层最终: {final_count:,} 条")
print(f"[TOTAL_DELETED] 总删除: {total_deleted:,} 条")
print(f"[DB_SIZE] {os.path.getsize(DB_PATH)/1024/1024:.1f} MB")
print(f"\n✅ 历史污染清理完成 — Meta层从 {before_count:,} → {final_count:,}")
