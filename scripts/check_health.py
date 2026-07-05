import urllib.request, json, time

for i in range(20):
    time.sleep(5)
    try:
        resp = urllib.request.urlopen('http://127.0.0.1:8771/api/health', timeout=5)
        r = json.loads(resp.read().decode('utf-8'))
        status = r.get('status', '?')
        version = r.get('version', '?')
        engine_ready = r.get('engine_ready', False)
        print(f'[{i+1}] status={status} version={version} engine_ready={engine_ready}')
        break
    except Exception as e:
        print(f'[{i+1}] waiting... {str(e)[:60]}')
else:
    print('TIMEOUT: 100s')
