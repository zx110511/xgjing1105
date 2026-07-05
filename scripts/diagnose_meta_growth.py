"""Meta层增长诊断脚本 - 找出异常写入源头"""
import sqlite3
import os
from datetime import datetime
from collections import Counter

DB_PATH = r"D:\元初系统\天机v9.1\data\.memory\icme.db"

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

# 1. Meta层当前总数
cur.execute("SELECT COUNT(*) FROM memories WHERE layer='meta'")
total = cur.fetchone()[0]
print(f"[Meta层总数] {total:,}")

# 2. 按时间分布 - 最近24小时每小时统计
print("\n[最近24小时每小时写入量]")
cur.execute("""
    SELECT strftime('%Y-%m-%d %H:00', datetime(created_at, 'unixepoch', 'localtime')) AS hour,
           COUNT(*) AS cnt
    FROM memories
    WHERE layer='meta'
      AND created_at >= strftime('%s', 'now', '-1 day')
    GROUP BY hour
    ORDER BY hour DESC
    LIMIT 30
""")
for hour, cnt in cur.fetchall():
    print(f"  {hour}: {cnt}")

# 3. 按agent字段分布 - 看是谁在写入
print("\n[按agent字段分布 (Top 20)]")
try:
    cur.execute("""
        SELECT COALESCE(agent, '(空)'), COUNT(*) AS cnt
        FROM memories WHERE layer='meta'
        GROUP BY agent
        ORDER BY cnt DESC
        LIMIT 20
    """)
    for agent, cnt in cur.fetchall():
        print(f"  {agent}: {cnt:,}")
except Exception as e:
    print(f"  agent列不存在: {e}")

# 4. 按tags分布 - 看是哪类记忆
print("\n[按tags字段分布 (Top 20)]")
try:
    cur.execute("""
        SELECT COALESCE(tags, '(空)'), COUNT(*) AS cnt
        FROM memories WHERE layer='meta'
        GROUP BY tags
        ORDER BY cnt DESC
        LIMIT 20
    """)
    for tags, cnt in cur.fetchall():
        print(f"  {tags[:80]}: {cnt:,}")
except Exception as e:
    print(f"  tags列错误: {e}")

# 5. 按内容前50字符分布 - 看是哪类内容
print("\n[按content前80字符分组 (Top 30)]")
try:
    cur.execute("""
        SELECT SUBSTR(content, 1, 80) AS prefix, COUNT(*) AS cnt
        FROM memories WHERE layer='meta'
        GROUP BY prefix
        ORDER BY cnt DESC
        LIMIT 30
    """)
    for prefix, cnt in cur.fetchall():
        print(f"  [{cnt:,}] {prefix}")
except Exception as e:
    print(f"  content列错误: {e}")

# 6. 最近100条样本查看
print("\n[最近100条Meta记录样本]")
cur.execute("""
    SELECT id, created_at, agent, SUBSTR(content, 1, 100), tags
    FROM memories WHERE layer='meta'
    ORDER BY created_at DESC
    LIMIT 100
""")
rows = cur.fetchall()
for rid, ts, agent, content, tags in rows[:30]:
    try:
        dt = datetime.fromtimestamp(ts).strftime('%m-%d %H:%M:%S')
    except:
        dt = str(ts)
    print(f"  [{dt}] agent={agent} | {(content or '')[:80]}")

# 7. 80000条阈值之后新增的记录分析
print("\n[清理后新增的4276条记录分析]")
cur.execute("""
    SELECT id, created_at, agent, SUBSTR(content, 1, 80), tags
    FROM memories WHERE layer='meta'
    ORDER BY created_at DESC
    LIMIT 4276
""")
new_rows = cur.fetchall()
agent_counter = Counter()
content_counter = Counter()
for rid, ts, agent, content, tags in new_rows:
    agent_counter[agent or '(空)'] += 1
    content_counter[(content or '')[:60]] += 1

print(f"\n  [新增记录按agent分布 Top 15]:")
for agent, cnt in agent_counter.most_common(15):
    print(f"    {agent}: {cnt}")

print(f"\n  [新增记录按content前缀分布 Top 20]:")
for prefix, cnt in content_counter.most_common(20):
    print(f"    [{cnt}] {prefix}")

# 8. 表结构
print("\n[memories表结构]")
cur.execute("PRAGMA table_info(memories)")
for col in cur.fetchall():
    print(f"  {col}")

conn.close()
print("\n✅ 诊断完成")
