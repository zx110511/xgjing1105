"""E2E验证：3新字段 + 管道 + 序列化"""
import sys, json, time
sys.path.insert(0, '.')

from core.enforcement.enforcement_hook import TianjiEnforcementHook, ConversationRecord, ConversationRegistry

registry = ConversationRegistry()
hook = TianjiEnforcementHook(registry=registry, memory_api_url='http://127.0.0.1:8771')

r = ConversationRecord(
    session_id='test-e2e-001',
    user_input='请修复enforcement_hook.py中的bug，包含password=secret和192.168.1.1',
    ai_response='已修复3个字段+管道激活+OWASP检测',
    agent_id='tianshu',
    timestamp=time.time(),
    turn_number=1,
)

hook.register_file_operation('test-e2e-001', 'edit', 'core/enforcement_hook.py',
    lines_changed={'added': 15, 'removed': 2},
    reason='auto_fix',
    content_before='old code line 1\nold code line 2\nold code line 3',
    content_after='new code line 1\nnew code line 2\nnew code line 3 with fix',
    file_size=12345,
)

hook._flush_pending_to_record(r, 'test-e2e-001')

print('=== file_snap ===')
fs = json.dumps(r.file_snap, ensure_ascii=False, indent=2)
print(fs[:600])
assert r.file_snap.get('status') == 'captured', "file_snap status wrong"
assert r.file_snap.get('count') == 1, f"file_snap count wrong: {r.file_snap.get('count')}"

print('\n=== trigger_frequency ===')
print(r.trigger_frequency)
assert r.trigger_frequency == 1, f"trigger_frequency wrong: {r.trigger_frequency}"

print('\n=== standards_check summary ===')
sc = r.standards_check.get('summary', {})
print(json.dumps(sc, ensure_ascii=False))
assert sc.get('total_checks') == 4, f"standards_check total wrong: {sc}"

owasp = r.standards_check.get('owasp_aos', {})
print(f'\n=== owasp_aos: {owasp.get("rules_triggered")} rules triggered ===')
assert owasp.get('rules_checked') == 14, f"OWASP rules checked wrong: {owasp}"
# Should detect hardcoded credential and internal IP
assert owasp.get('rules_triggered', 0) >= 2, f"OWASP should detect at least 2: {owasp}"

print('\n=== SERIALIZATION CHECK ===')
payload = json.dumps({
    'type': 'conversation_record',
    'session_id': r.session_id,
    'file_snap': r.file_snap,
    'trigger_frequency': r.trigger_frequency,
    'standards_check': r.standards_check,
}, ensure_ascii=False)
checks = [
    ('file_snap', 'file_snap' in payload),
    ('trigger_frequency', 'trigger_frequency' in payload),
    ('standards_check', 'standards_check' in payload),
    ('owasp_aos', 'owasp_aos' in payload),
    ('hardcoded_credential', 'hardcoded_credential' in payload),
    ('internal_ip', 'internal_ip_exposure' in payload),
]
all_pass = True
for name, ok in checks:
    status = 'OK' if ok else 'FAIL'
    print(f'  [{status}] {name}')
    if not ok:
        all_pass = False

print(f'\nPayload size: {len(payload)} bytes')

if all_pass:
    print('\nALL E2E VALIDATIONS PASSED')
else:
    print('\nSOME VALIDATIONS FAILED')
    sys.exit(1)
