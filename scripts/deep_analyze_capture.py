"""
深度解析天机对话录入的具体操作细节
"""

import sqlite3
import json
import time
from pathlib import Path

db_path = Path(r"d:\元初系统\天机v9.1\data\icme.db")
memory_path = Path(r"d:\元初系统\天机v9.1\data\.memory")

print("=" * 80)
print("天机对话录入深度解析")
print("=" * 80)

# 1. 数据库结构检查
print("\n[1] 数据库结构检查")
print("-" * 80)

conn = sqlite3.connect(str(db_path))
cursor = conn.cursor()

# 列出所有表
cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = cursor.fetchall()
print(f"数据库表数量: {len(tables)}")
for table in tables:
    print(f"  - {table[0]}")

# 检查memories表结构
print("\nmemories表结构:")
cursor.execute("PRAGMA table_info(memories)")
columns = cursor.fetchall()
for col in columns:
    print(f"  {col[1]:20s} {col[2]:15s} {'NOT NULL' if col[3] else ''}")

# 2. 数据统计
print("\n[2] 数据统计")
print("-" * 80)

# 总记录数
cursor.execute("SELECT COUNT(*) FROM memories")
total_count = cursor.fetchone()[0]
print(f"总记录数: {total_count}")

# 按层级统计
cursor.execute("SELECT layer, COUNT(*) FROM memories GROUP BY layer")
layer_stats = cursor.fetchall()
print("\n按层级统计:")
for layer, count in layer_stats:
    print(f"  {layer:15s}: {count:5d} 条")

# 3. 最近录入的记录
print("\n[3] 最近录入的记录 (最新10条)")
print("-" * 80)

cursor.execute("""
    SELECT id, layer, substr(content, 1, 80) as content_preview,
           created_at, tags, metadata
    FROM memories
    ORDER BY created_at DESC
    LIMIT 10
""")
recent_records = cursor.fetchall()

for i, record in enumerate(recent_records, 1):
    entry_id, layer, content, created_at, tags, metadata = record
    created_time = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(created_at))
    print(f"\n[{i}] ID: {entry_id}")
    print(f"    Layer: {layer}")
    print(f"    Content: {content}...")
    print(f"    Created: {created_time}")
    try:
        tags_list = json.loads(tags)
        if tags_list:
            print(f"    Tags: {tags_list[:5]}")
    except Exception:
        pass
    try:
        meta_dict = json.loads(metadata)
        if meta_dict.get("source"):
            print(f"    Source: {meta_dict['source']}")
        if meta_dict.get("turn_id"):
            print(f"    Turn ID: {meta_dict['turn_id']}")
    except Exception:
        pass

# 4. 对话捕获记录检查
print("\n[4] 对话捕获记录检查")
print("-" * 80)

cursor.execute("""
    SELECT COUNT(*) FROM memories
    WHERE metadata LIKE '%capture_conversation%'
""")
capture_count = cursor.fetchone()[0]
print(f"对话捕获记录数: {capture_count}")

if capture_count > 0:
    cursor.execute("""
        SELECT id, layer, substr(content, 1, 100), created_at, metadata
        FROM memories
        WHERE metadata LIKE '%capture_conversation%'
        ORDER BY created_at DESC
        LIMIT 5
    """)
    capture_records = cursor.fetchall()
    print("\n最近的对话捕获记录:")
    for i, record in enumerate(capture_records, 1):
        entry_id, layer, content, created_at, metadata = record
        created_time = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(created_at))
        print(f"\n  [{i}] {entry_id} | {layer} | {created_time}")
        print(f"      {content}...")

# 5. JSON文件检查
print("\n[5] JSON文件存储检查")
print("-" * 80)

for layer_name in ["sensory", "working", "episodic", "semantic", "meta"]:
    layer_dir = memory_path / layer_name
    if layer_dir.exists():
        json_files = list(layer_dir.glob("*.json"))
        print(f"{layer_name:15s}: {len(json_files):5d} 个JSON文件")

        # 检查最新的文件
        if json_files:
            latest_file = max(json_files, key=lambda f: f.stat().st_mtime)
            mtime = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(latest_file.stat().st_mtime))
            print(f"              最新文件: {latest_file.name} ({mtime})")
    else:
        print(f"{layer_name:15s}: 目录不存在")

conn.close()

print("\n" + "=" * 80)
print("深度解析完成")
print("=" * 80)
