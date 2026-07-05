"""等待天机服务就绪并报告状态"""
import urllib.request
import json
import time

url = "http://127.0.0.1:8771/api/health"

for i in range(20):
    try:
        resp = urllib.request.urlopen(url, timeout=5)
        data = json.loads(resp.read().decode("utf-8-sig"))
        if data.get("engine_ready"):
            meta_cnt = data.get("layers", {}).get("meta", {}).get("entry_count", "?")
            print(f"[OK] 服务就绪! uptime={data.get('uptime_seconds',0):.1f}s meta_entries={meta_cnt}")
            break
    except Exception:
        pass
    time.sleep(3)
else:
    print("[FAIL] 服务60s内未就绪")
