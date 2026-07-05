"""
深度检查数据库初始化和存储问题
"""

import sqlite3
import json
import time
import os
from pathlib import Path

print("=" * 80)
print("数据库初始化深度检查")
print("=" * 80)

# 1. 检查所有可能的数据库文件
print("\n[1] 查找所有数据库文件")
print("-" * 80)

db_files = []
for root, dirs, files in os.walk(r"d:\元初系统\天机v9.1"):
    for file in files:
        if file.endswith(".db"):
            db_path = Path(root) / file
            size = db_path.stat().st_size
            mtime = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(db_path.stat().st_mtime))
            db_files.append((db_path, size, mtime))
            print(f"  {db_path}")
            print(f"    大小: {size / 1024:.2f} KB")
            print(f"    修改: {mtime}")

print(f"\n找到 {len(db_files)} 个数据库文件")

# 2. 检查每个数据库的表结构
print("\n[2] 检查每个数据库的表结构")
print("-" * 80)

for db_path, size, mtime in db_files:
    print(f"\n{'='*80}")
    print(f"数据库: {db_path}")
    print("=" * 80)

    try:
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()

        # 列出所有表
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = cursor.fetchall()
        print(f"\n表数量: {len(tables)}")

        for table in tables:
            table_name = table[0]
            cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
            count = cursor.fetchone()[0]
            print(f"  - {table_name}: {count} 条记录")

        # 检查是否有memories表
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='memories'")
        if cursor.fetchone():
            print("\n✅ memories表存在")

            # 检查表结构
            cursor.execute("PRAGMA table_info(memories)")
            columns = cursor.fetchall()
            print("\nmemories表字段:")
            for col in columns:
                print(f"  {col[1]:20s} {col[2]:15s}")

            # 检查最近的记录
            cursor.execute("""
                SELECT id, layer, substr(content, 1, 80), created_at, metadata
                FROM memories
                ORDER BY created_at DESC
                LIMIT 5
            """)
            recent = cursor.fetchall()
            if recent:
                print("\n最近的5条记录:")
                for i, row in enumerate(recent, 1):
                    print(f"\n  [{i}] {row[0]} | {row[1]}")
                    print(f"      {row[2]}...")
                    created = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(row[3]))
                    print(f"      时间: {created}")
        else:
            print("\n❌ memories表不存在")

        conn.close()

    except Exception as e:
        print(f"\n❌ 检查失败: {e}")

# 3. 测试SQLiteMemoryStore初始化
print("\n\n[3] 测试SQLiteMemoryStore初始化")
print("-" * 80)

try:
    import sys
    sys.path.insert(0, r"d:\元初系统\天机v9.1")

    from core.memory.sqlite_store import SQLiteMemoryStore

    # 测试初始化
    test_db_path = Path(r"d:\元初系统\天机v9.1\data\icme.db")
    print(f"\n初始化SQLiteMemoryStore: {test_db_path}")

    store = SQLiteMemoryStore(test_db_path, cache_size=100)

    # 验证表创建
    conn = sqlite3.connect(str(test_db_path))
    cursor = conn.cursor()

    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='memories'")
    if cursor.fetchone():
        print("✅ memories表已创建")

        # 检查表结构
        cursor.execute("PRAGMA table_info(memories)")
        columns = cursor.fetchall()
        print(f"   字段数: {len(columns)}")

        # 尝试插入测试数据
        test_entry = {
            "id": "test-" + str(int(time.time())),
            "content": "测试内容 - 验证写入功能",
            "layer": "sensory",
            "tags": ["test"],
            "priority": "medium",
            "value_score": 0.5,
            "access_count": 0,
            "created_at": time.time(),
            "last_accessed": time.time(),
            "metadata": {"test": True},
            "related_ids": [],
            "changelog": [],
        }

        success = store.insert(test_entry)
        if success:
            print("✅ 测试数据插入成功")

            # 验证读取
            cursor.execute("SELECT * FROM memories WHERE id = ?", (test_entry["id"],))
            row = cursor.fetchone()
            if row:
                print("✅ 测试数据读取成功")
            else:
                print("❌ 测试数据读取失败")
        else:
            print("❌ 测试数据插入失败")
    else:
        print("❌ memories表未创建")

    conn.close()

except Exception as e:
    print(f"\n❌ 初始化失败: {e}")
    import traceback
    traceback.print_exc()

# 4. 检查hybrid_engine初始化
print("\n\n[4] 检查hybrid_engine初始化")
print("-" * 80)

try:
    from core.memory.hybrid_engine import ICMEStorageEngine
    from core.shared.config import ICMEConfig

    config = ICMEConfig()
    print(f"\n数据路径: {config.data_path}")
    print(f"使用SQLite: True")

    engine = ICMEStorageEngine(config, use_sqlite=True)

    # 检查存储后端
    if hasattr(engine, '_store'):
        print(f"✅ 存储后端: {type(engine._store).__name__}")

        # 检查数据库路径
        if hasattr(engine._store, 'db_path'):
            print(f"   数据库路径: {engine._store.db_path}")
    else:
        print("❌ 存储后端未初始化")

    # 测试remember
    print("\n测试remember()...")
    result = engine.remember(
        content="测试对话录入 - hybrid_engine",
        layer="sensory",
        tags=["test", "hybrid_engine"],
        metadata={"source": "test_script"}
    )

    print(f"结果: {result}")

    if result.get("id"):
        print(f"✅ remember成功: id={result['id']}")

        # 验证存储
        if hasattr(engine, '_store') and hasattr(engine._store, 'db_path'):
            conn = sqlite3.connect(str(engine._store.db_path))
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM memories WHERE id = ?", (result["id"],))
            row = cursor.fetchone()
            if row:
                print("✅ 数据已存储到SQLite")
            else:
                print("❌ 数据未存储到SQLite")
            conn.close()
    else:
        print(f"❌ remember失败: {result.get('status')}")

except Exception as e:
    print(f"\n❌ hybrid_engine初始化失败: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 80)
print("检查完成")
print("=" * 80)
