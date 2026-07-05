"""
L-Asset体系验证脚本
验证: asset_registry表、asset_snapshots表、三重绑定、版本链、TCL绑定
"""
import sqlite3
import json

db_path = r'D:\元初系统\天机v9.1\data\.memory\icme.db'
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row

print('=' * 60)
print('L-Asset体系验证')
print('=' * 60)

# 1. 检查asset_registry表
print('\n[1] asset_registry表检查')
try:
    rows = conn.execute('SELECT COUNT(*) as cnt FROM asset_registry').fetchone()
    print(f'  资产注册总数: {rows["cnt"]}')

    # 查看最近5条
    recent = conn.execute('''
        SELECT asset_id, memory_id, layer, content_hash, version, parent_version_id, status, created_at
        FROM asset_registry
        ORDER BY created_at DESC
        LIMIT 5
    ''').fetchall()
    print(f'  最近5条资产:')
    for r in recent:
        print(f'    {r["asset_id"]} | memory={r["memory_id"][:8]}... | v{r["version"]} | {r["status"]}')
except Exception as e:
    print(f'  [ERROR] {e}')

# 2. 检查asset_snapshots表
print('\n[2] asset_snapshots表检查')
try:
    rows = conn.execute('SELECT COUNT(*) as cnt FROM asset_snapshots').fetchone()
    print(f'  快照总数: {rows["cnt"]}')

    # 按类型统计
    by_type = conn.execute('''
        SELECT snapshot_type, COUNT(*) as cnt, SUM(size_bytes) as total_size
        FROM asset_snapshots
        GROUP BY snapshot_type
    ''').fetchall()
    print(f'  按类型统计:')
    for r in by_type:
        print(f'    {r["snapshot_type"]}: {r["cnt"]}条, {r["total_size"]}B')
except Exception as e:
    print(f'  [ERROR] {e}')

# 3. 检查三重绑定
print('\n[3] 三重绑定验证 (memory_id <-> asset_id <-> content_hash)')
try:
    # 随机检查3条
    samples = conn.execute('''
        SELECT ar.asset_id, ar.memory_id, ar.content_hash, m.id as mem_id
        FROM asset_registry ar
        LEFT JOIN memory_entries m ON ar.memory_id = m.id
        ORDER BY ar.created_at DESC
        LIMIT 5
    ''').fetchall()
    print(f'  绑定样本检查:')
    for r in samples:
        bind_ok = 'OK' if r['mem_id'] else 'MISSING'
        print(f'    [{bind_ok}] asset={r["asset_id"]} | memory={r["memory_id"][:8]}... | hash={r["content_hash"][:8]}...')
except Exception as e:
    print(f'  [ERROR] {e}')

# 4. 版本链检查
print('\n[4] 版本链完整性检查')
try:
    chains = conn.execute('''
        SELECT memory_id, COUNT(*) as versions, GROUP_CONCAT(version, '->') as chain
        FROM asset_registry
        GROUP BY memory_id
        HAVING versions > 1
        ORDER BY versions DESC
        LIMIT 5
    ''').fetchall()
    print(f'  多版本记忆数: {len(chains)}')
    for r in chains:
        print(f'    memory={r["memory_id"][:8]}... | versions={r["versions"]} | chain={r["chain"]}')
except Exception as e:
    print(f'  [ERROR] {e}')

# 5. TCL绑定检查
print('\n[5] TCL canonical_ids绑定检查')
try:
    tcl_bound = conn.execute('''
        SELECT asset_id, tcl_ids
        FROM asset_snapshots
        WHERE tcl_ids IS NOT NULL AND tcl_ids != '[]'
        ORDER BY created_at DESC
        LIMIT 5
    ''').fetchall()
    print(f'  TCL绑定样本:')
    for r in tcl_bound:
        tcl_list = json.loads(r['tcl_ids']) if r['tcl_ids'] else []
        print(f'    {r["asset_id"]} | TCL={len(tcl_list)}个')
except Exception as e:
    print(f'  [ERROR] {e}')

# 6. 表结构检查
print('\n[6] 表结构检查')
try:
    tables = conn.execute('''
        SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'asset%'
    ''').fetchall()
    print(f'  L-Asset相关表: {[t["name"] for t in tables]}')
except Exception as e:
    print(f'  [ERROR] {e}')

conn.close()
print('\n' + '=' * 60)
print('L-Asset体系验证完成')
print('=' * 60)
