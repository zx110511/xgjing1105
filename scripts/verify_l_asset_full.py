"""
L-Asset体系完整验证
"""
import sqlite3
import json

db_path = r'D:\元初系统\天机v9.1\data\.memory\icme.db'
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row

print('=' * 60)
print('L-Asset体系完整验证')
print('=' * 60)

PASS = 0
FAIL = 0

def check(name, condition, detail=""):
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f'  [PASS] {name}{" - " + detail if detail else ""}')
    else:
        FAIL += 1
        print(f'  [FAIL] {name}{" - " + detail if detail else ""}')

# 1. asset_registry表
print('\n[1] asset_registry表')
try:
    total = conn.execute('SELECT COUNT(*) as cnt FROM asset_registry').fetchone()['cnt']
    check('资产注册表存在', total > 0, f'{total}条记录')

    # 按层级统计
    by_layer = conn.execute('''
        SELECT layer, COUNT(*) as cnt FROM asset_registry GROUP BY layer
    ''').fetchall()
    for r in by_layer:
        print(f'       {r["layer"]}: {r["cnt"]}条')
except Exception as e:
    check('资产注册表', False, str(e))

# 2. asset_snapshots表
print('\n[2] asset_snapshots表')
try:
    total = conn.execute('SELECT COUNT(*) as cnt FROM asset_snapshots').fetchone()['cnt']
    check('快照表存在', total > 0, f'{total}条记录')

    # 按类型统计
    by_type = conn.execute('''
        SELECT snapshot_type, COUNT(*) as cnt, SUM(size) as total_size
        FROM asset_snapshots GROUP BY snapshot_type
    ''').fetchall()
    for r in by_type:
        print(f'       {r["snapshot_type"]}: {r["cnt"]}条, {r["total_size"]}B')
except Exception as e:
    check('快照表', False, str(e))

# 3. 三重绑定验证
print('\n[3] 三重绑定 (memory_id <-> asset_id <-> content_hash)')
try:
    # 检查asset_registry与memories表的绑定
    bound = conn.execute('''
        SELECT COUNT(*) as cnt FROM asset_registry ar
        INNER JOIN memories m ON ar.memory_id = m.id
    ''').fetchone()['cnt']
    check('记忆-资产绑定', bound > 0, f'{bound}条有效绑定')

    # 检查content_hash非空
    hashed = conn.execute('''
        SELECT COUNT(*) as cnt FROM asset_registry
        WHERE content_hash IS NOT NULL AND content_hash != ''
    ''').fetchone()['cnt']
    check('内容哈希绑定', hashed > 0, f'{hashed}条有哈希')
except Exception as e:
    check('三重绑定', False, str(e))

# 4. 版本链验证
print('\n[4] 版本链')
try:
    chains = conn.execute('''
        SELECT memory_id, COUNT(*) as versions,
               MIN(version) as min_v, MAX(version) as max_v
        FROM asset_registry
        GROUP BY memory_id
        HAVING versions > 1
        ORDER BY versions DESC
        LIMIT 5
    ''').fetchall()
    check('版本链存在', len(chains) > 0, f'{len(chains)}个多版本记忆')
    for r in chains:
        print(f'       {r["memory_id"][:8]}...: v{r["min_v"]}->v{r["max_v"]} ({r["versions"]}版本)')
except Exception as e:
    check('版本链', False, str(e))

# 5. TCL绑定验证
print('\n[5] TCL canonical_ids绑定')
try:
    tcl_bound = conn.execute('''
        SELECT COUNT(*) as cnt FROM asset_snapshots
        WHERE tcl_canonical_ids IS NOT NULL AND tcl_canonical_ids != '[]'
    ''').fetchone()['cnt']
    check('TCL绑定存在', tcl_bound > 0, f'{tcl_bound}条有TCL')

    # 查看样本
    samples = conn.execute('''
        SELECT asset_id, tcl_canonical_ids FROM asset_snapshots
        WHERE tcl_canonical_ids IS NOT NULL AND tcl_canonical_ids != '[]'
        ORDER BY created_at DESC LIMIT 3
    ''').fetchall()
    for r in samples:
        tcl_list = json.loads(r['tcl_canonical_ids']) if r['tcl_canonical_ids'] else []
        print(f'       {r["asset_id"]}: {len(tcl_list)}个TCL术语')
except Exception as e:
    check('TCL绑定', False, str(e))

# 6. 父子版本链验证
print('\n[6] 父子版本链')
try:
    parent_child = conn.execute('''
        SELECT COUNT(*) as cnt FROM asset_registry
        WHERE parent_version_id IS NOT NULL AND parent_version_id != ''
    ''').fetchone()['cnt']
    check('父子链存在', parent_child > 0, f'{parent_child}条有父版本')
except Exception as e:
    check('父子版本链', False, str(e))

# 7. 状态分布
print('\n[7] 资产状态分布')
try:
    by_status = conn.execute('''
        SELECT status, COUNT(*) as cnt FROM asset_registry GROUP BY status
    ''').fetchall()
    for r in by_status:
        print(f'       {r["status"]}: {r["cnt"]}条')
    check('状态字段正常', len(by_status) > 0)
except Exception as e:
    check('状态分布', False, str(e))

# 8. TDAF兼容性
print('\n[8] TDAF兼容性')
try:
    tdaf = conn.execute('''
        SELECT COUNT(*) as cnt FROM asset_registry WHERE tdaf_compatible = 1
    ''').fetchone()['cnt']
    check('TDAF兼容', tdaf > 0, f'{tdaf}条兼容')
except Exception as e:
    check('TDAF兼容', False, str(e))

conn.close()

print('\n' + '=' * 60)
print(f'验证结果: {PASS} PASS, {FAIL} FAIL')
if FAIL == 0:
    print('L-Asset体系: 完整建立!')
else:
    print(f'L-Asset体系: {FAIL}项异常')
print('=' * 60)
