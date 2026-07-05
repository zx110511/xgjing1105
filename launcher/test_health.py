# -*- coding: utf-8-sig -*-
import urllib.request
import json
import sys

print('Testing health endpoint...')
try:
    req = urllib.request.Request('http://127.0.0.1:8771/api/health', headers={'Accept': 'application/json'})
    resp = urllib.request.urlopen(req, timeout=10)
    data = json.loads(resp.read().decode('utf-8'))
    print('Status:', data.get('status'))
    print('Engine ready:', data.get('engine_ready'))
    print('Uptime:', data.get('uptime_seconds'), 's')
    layers = data.get('layers', {})
    total = sum(v.get('entry_count', 0) for v in layers.values() if isinstance(v, dict))
    print('Total memories:', total)
    print('RESULT: OK')
except Exception as e:
    print('Error:', e)
    import traceback
    traceback.print_exc()
    print('RESULT: FAIL')
