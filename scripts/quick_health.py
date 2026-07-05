import urllib.request, json
resp = urllib.request.urlopen('http://127.0.0.1:8771/api/health', timeout=5)
d = json.loads(resp.read().decode())
print(f"status={d['status']} engine_ready={d['engine_ready']}")
