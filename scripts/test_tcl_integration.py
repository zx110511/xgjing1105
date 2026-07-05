"""TCL合体运行验证脚本 - 直接测试ICMEStorageEngine"""
import sys
sys.path.insert(0, r'd:\元初系统\天机v9.1')

from core.memory.hybrid_engine import ICMEStorageEngine
from core.shared.config import DEFAULT_CONFIG

print('Creating engine...')
engine = ICMEStorageEngine(config=DEFAULT_CONFIG, use_sqlite=True)
print('Engine created successfully')

# Test TCL integration
print('Testing TCL init...')
result = engine._init_tcl()
print(f'TCL init result: {result}')

if result:
    content = '天机记忆引擎的ICME六层记忆架构包含DeepSeek驾驶者'
    _, canonical_ids = engine._tcl_normalizer.normalize_content(content)
    print(f'canonical_ids: {canonical_ids}')

# Test remember with TCL
print('Testing remember with TCL...')
r = engine.remember(
    content='TCL合体运行验证：天机记忆引擎的ICME六层记忆架构',
    layer='working',
    tags=['TCL验证'],
    metadata={}
)
entry_id = r.get('id', 'NONE')
status = r.get('status', 'UNKNOWN')
print(f'Remember result: id={entry_id}, status={status}')

# Check if canonical_ids in metadata
if engine._use_sqlite and entry_id != 'NONE':
    entry = engine._store.get(entry_id)
    if entry:
        metadata = entry.get('metadata', {})
        tcl_ids = metadata.get('tcl_canonical_ids', 'MISSING')
        print(f'Metadata tcl_canonical_ids: {tcl_ids}')
        if tcl_ids != 'MISSING':
            print('SUCCESS: TCL canonical_ids written to memory metadata!')
        else:
            print('FAIL: tcl_canonical_ids not found in metadata')
    else:
        print('Entry not found in SQLite')
else:
    print('Not using SQLite or no entry_id')

# Test recall with TCL
print('Testing recall with TCL enhancement...')
results = engine.recall(query='六层记忆架构', layers=['working'], limit=5)
print(f'Recall results: {len(results)} entries found')
for r_item in results[:3]:
    content_preview = r_item.get('content', '')[:50]
    print(f'  - {content_preview}...')
