"""天机v9.1 API路由探查"""
import http.client, json

def probe(method, path):
    c = http.client.HTTPConnection("127.0.0.1", 8771, timeout=5)
    try:
        c.request(method, path)
        r = c.getresponse()
        body = r.read().decode()[:500]
        return r.status, body
    except Exception as e:
        return 0, str(e)

print("=== API路由探查 ===")
endpoints = [
    ("GET", "/api/memory/remember"),
    ("POST", "/api/memory/remember"),
    ("GET", "/api/memory/recall"),
    ("POST", "/api/memory/recall"),
    ("GET", "/api/memory/search"),
    ("POST", "/api/memory/search"),
    ("GET", "/api/memory/semantic"),
    ("POST", "/api/memory/semantic"),
    ("GET", "/api/memory/normalize"),
    ("POST", "/api/memory/normalize"),
    ("GET", "/api/memory/forget"),
    ("POST", "/api/memory/forget"),
    ("DELETE", "/api/memory/forget"),
    ("GET", "/api/agent"),
    ("POST", "/api/agent"),
    ("GET", "/api/container"),
    ("POST", "/api/container"),
    ("GET", "/openapi.json"),
]

for method, path in endpoints:
    s, body = probe(method, path)
    short = body[:120].replace("\n"," ")
    print(f"  {method:6} {path:35} → {s} {short}")

# Also check: does the server list all routes?
print("\n=== 根路由 ===")
s, body = probe("GET", "/")
print(f"  GET / → {s} {body[:200]}")

# FastAPI openapi schema
print("\n=== OpenAPI Schema(前2000字符) ===")
s, body = probe("GET", "/openapi.json")
if s == 200:
    import json as j
    try:
        schema = j.loads(body[:20000])
        paths = schema.get("paths", {})
        print(f"  端点总数: {len(paths)}")
        for p in sorted(paths.keys())[:50]:
            methods = list(paths[p].keys())
            print(f"  {', '.join(methods):10} {p}")
    except:
        print(f"  解析失败: {body[:500]}")