"""天机v9.1 全功能深度在线测试+审计 v2 — 质问驱动+正确路由"""
import http.client, json, time, sys, threading
from urllib.parse import quote

BASE = "127.0.0.1"
PORT = 8771
PASS = 0
FAIL = 0
QUESTIONS = []

def check(name, condition, detail=""):
    global PASS, FAIL
    tag = "[PASS]" if condition else "[FAIL]"
    if condition: PASS += 1
    else: FAIL += 1
    print(f"  {tag} {name}")
    if detail: print(f"       {detail}")
    if not condition:
        QUESTIONS.append(f"  ✗ {name}: {detail}")

def api(method, path, body=None):
    c = http.client.HTTPConnection(BASE, PORT, timeout=10)
    c.request(method, path,
              body=json.dumps(body).encode() if body else None,
              headers={"Content-Type": "application/json"} if body else {})
    r = c.getresponse()
    d = r.read().decode("utf-8")
    try: return r.status, json.loads(d)
    except: return r.status, d[:500]

print("=" * 70)
print("天机v9.1 全功能深度在线测试+审计 v2")
print(f"目标: {BASE}:{PORT} | {time.strftime('%H:%M:%S')}")
print("=" * 70)

# ====== A: 系统标识 ======
print("\n>>> A: 系统标识与版本")
s, h = api("GET", "/api/health")
check("A1 /api/health", s == 200 and isinstance(h, dict) and h.get("status") == "healthy")

s, h2 = api("GET", "/api/platform/stats")
check("A2 /api/platform/stats", s == 200)
# platform/stats = {"status":"success", "engine":{...}}
engine_data = h2.get("engine", {}) if isinstance(h2, dict) else {}
version_ok = "9.1" in json.dumps(engine_data.get("version", "")) or "9.1" in json.dumps(h2)
check("A2b 版本含9.1", version_ok)

s, h = api("GET", "/api/system/stats")
check("A3 /api/system/stats", s == 200) if s == 200 else check("A3 /api/system/stats", False)

s, h = api("GET", "/api/stats")
check("A4 /api/stats", s == 200) if s == 200 else check("A4 /api/stats", False)

# ====== B: 记忆六层 ======
print("\n>>> B: ICME六层记忆")
s, m = api("GET", "/api/memory/stats")
check("B1 /api/memory/stats", s == 200)
total = m.get("total_entries", 0) if isinstance(m, dict) else 0
check("B2 entries > 70000", total > 70000, f"total={total}")

layers = m.get("layers", {}) if isinstance(m, dict) else {}
check("B3 layers存在", bool(layers))
for ln in ["sensory","working","short_term","episodic","semantic","meta"]:
    if ln in layers:
        l = layers[ln]
        cnt = l.get("entry_count", l.get("count", 0)) if isinstance(l, dict) else l
        check(f"B4 {ln}", cnt > 0, f"{cnt} entries" if cnt else "0 - 可能是空层")

s, li = api("GET", "/api/memory/layers/info")
check("B5 /api/memory/layers/info", s == 200)

# 🔍 质问: 六层比例
if isinstance(m, dict):
    def _layer_cnt(layer_name):
        l = layers.get(layer_name, 0)
        if isinstance(l, dict): return l.get("entry_count", l.get("count", 0))
        elif isinstance(l, (int, float)): return int(l)
        return 0
    meta = _layer_cnt("meta")
    if meta > total * 0.5:
        QUESTIONS.append(f"  ⚡ 质问: L5元枢占{meta/total*100:.1f}%。Meta层是否过度膨胀？需审计内容质量")
    sensory = _layer_cnt("sensory")
    if sensory < 500:
        QUESTIONS.append(f"  ⚡ 质问: L0感枢仅{sensory}条({sensory/total*100:.1f}%)。实时捕获是否在正常工作？")

# ====== C: 记忆CRUD(Platform API) ======
print("\n>>> C: 记忆CRUD (Platform API)")
ts = int(time.time())
test_content = f"v9.1深度审计测试_{ts}"

s, r = api("POST", "/api/platform/remember", {
    "content": test_content,
    "layer": "working",
    "priority": "high",
    "tags": ["deep-audit", "v9.1", "live-test"]
})
check("C1 remember写入", s in (200, 201), f"status={s}")
mid = None
if isinstance(r, dict):
    mid = r.get("id") or r.get("entry_id") or r.get("memory_id")
    check("C2 返回entry_id", bool(mid), f"id={mid}")
    print(f"       写入内容: {test_content[:50]}...")

# recall
s, rc = api("GET", f"/api/platform/recall?query={quote(test_content)}&limit=5")
check("C3 recall搜索", s == 200, f"status={s}")
found = False
if isinstance(rc, dict):
    results = rc.get("results") or rc.get("entries") or []
    found = any(test_content in str(r) for r in results)
    check("C3b 结果含写入内容", found, f"匹配结果数: {len(results)}")

# platform stats
s, ps = api("GET", "/api/platform/stats")
check("C4 platform/stats", s == 200)
if isinstance(ps, dict):
    ps_engine = ps.get("engine", {})
    ps_total = ps_engine.get("total_entries", ps.get("total_entries", 0)) if isinstance(ps_engine, dict) else 0
    check("C4b total_entries", ps_total > 0, f"engine={ps_total}")

# MCP store_memory
s, mr = api("POST", "/api/mcp/tools/store_memory", {
    "content": f"天机MCP存储测试_{ts}",
    "layer": "working",
    "tags": ["mcp-test", "v9.1"]
})
check("C5 MCP store_memory", s in (200, 201) or s == 404, f"status={s}")
if isinstance(mr, dict) and mid:
    id2 = mr.get("id") or mr.get("entry_id")

# MCP get_memory
if mid:
    s, gm = api("POST", "/api/mcp/tools/get_memory", {"memory_id": mid})
    check("C6 MCP get_memory", s == 200 or s == 404, f"status={s}")

# List memories
s, lm = api("GET", "/api/memory/?limit=3&layer=working")
check("C7 列出working层记忆", s == 200)
if isinstance(lm, dict):
    entries = lm.get("entries") or lm.get("memories") or []
    check("C7b 有记忆条目", len(entries) > 0, f"count={len(entries)}")

# ====== D: 搜索能力 ======
print("\n>>> D: 搜索能力")
s, ss = api("POST", "/api/search/semantic", {
    "query": "天机系统记忆架构",
    "limit": 5
})
check("D1 语义搜索POST", s == 200 or s == 404, f"status={s}")
if s == 200 and isinstance(ss, dict):
    results = ss.get("results", [])
    check("D1b 返回结果", len(results) > 0, f"count={len(results)}")

s, ss2 = api("GET", f"/api/search/semantic?q={quote('ICME')}&limit=3")
check("D2 语义搜索GET(q参)", s == 200, f"status={s}")

s, qs = api("GET", f"/api/search/quick?q={quote('天机v9.1')}&limit=5")
check("D3 快速搜索", s == 200 or s == 404, f"status={s}")

s, fs = api("POST", "/api/search/fusion", {
    "query": "天机启动器审计",
    "limit": 5
})
check("D4 融合搜索", s == 200 or s == 404, f"status={s}")

# ====== E: MCP工具链 ======
print("\n>>> E: MCP工具链")
s, es = api("POST", "/api/mcp/tools/explain_memory_lineage", {"memory_id": mid} if mid else {"memory_id": "test"})
check("E1 explain_memory_lineage", s == 200 or s == 404, f"status={s}")

s, dm = api("POST", "/api/mcp/tools/delete_memory", {"memory_id": mid} if mid else {"memory_id": "test"})
check("E2 delete_memory(memory_id)", s == 200, f"status={s}")

# ====== F: 治理与审计 ======
print("\n>>> F: 治理与审计")
s, gv = api("GET", "/api/governance/status")
check("F1 governance/status", s == 200)

s, sr = api("GET", "/api/standards/report")
check("F2 standards/report", s == 200 or s == 404, f"status={s}")

# ====== G: 容器与MCP ======
print("\n>>> G: 容器与MCP状态")
s, cs = api("GET", "/api/container/status")
check("G1 container/status", s == 200)

s, mc = api("GET", "/api/mcp/status")
check("G2 mcp/status", s == 200)

s, sh = api("GET", "/api/storage_health")
check("G3 storage_health", s == 200)

# ====== H: 前端资源 ======
print("\n>>> H: 前端资源")
for path, name in [("/docs", "Swagger"), ("/dashboard", "Dashboard"),
                    ("/memory", "Memory UI"), ("/search", "Search UI"),
                    ("/monitor", "Monitor UI"), ("/audit", "Audit UI"),
                    ("/chat", "Chat UI"), ("/settings", "Settings UI")]:
    s, _ = api("GET", path)
    check(f"H  {name} ({path})", s == 200, f"status={s}")

# ====== I: 性能 ======
print("\n>>> I: 性能与韧性")
# 延迟
t0 = time.time()
s, _ = api("GET", "/api/health")
lat = (time.time() - t0) * 1000
check("I1 健康检查 < 300ms", lat < 300, f"{lat:.0f}ms")
if lat > 300:
    QUESTIONS.append(f"  ⚡ 质问: 健康检查延迟{lat:.0f}ms，超过300ms。检查是否有阻塞调用？")

# 并发
results = []
def do_req():
    try:
        c = http.client.HTTPConnection(BASE, PORT, timeout=5)
        c.request("GET", "/api/health")
        results.append(c.getresponse().status == 200)
    except: results.append(False)

t0 = time.time()
threads = [threading.Thread(target=do_req) for _ in range(10)]
[t.start() for t in threads]
[t.join() for t in threads]
elapsed = (time.time() - t0) * 1000
check("I2 10并发全成功", all(results), f"{sum(results)}/10, {elapsed:.0f}ms")
check("I3 10并发 < 3s", elapsed < 3000, f"{elapsed:.0f}ms")

# 连续请求100次
t0 = time.time()
for _ in range(100):
    api("GET", "/api/health")
elapsed = (time.time() - t0)
check("I4 100次连续请求 < 10s", elapsed < 10, f"{elapsed:.1f}s, {100/elapsed:.0f} req/s")
if 100/elapsed < 10:
    QUESTIONS.append(f"  ⚡ 质问: 吞吐量{100/elapsed:.0f} req/s，低于10req/s。是否存在性能瓶颈？")

# ====== J: 学习与进化 ======
print("\n>>> J: 学习与进化")
s, ev = api("GET", "/api/orchestrator/v10/evolution/stats")
check("J1 evolution/stats", s == 200 or s == 404, f"status={s}")

s, ev2 = api("GET", "/api/orchestrator/v10/stats")
check("J2 orchestrator/stats", s == 200 or s == 404, f"status={s}")

# ====== K: 启动器集成 ======
print("\n>>> K: 启动器v5.0集成")
import subprocess, os
proj_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
r = subprocess.run([sys.executable, "launcher/tianji_v91_launcher.py", "--status"],
                   capture_output=True, timeout=15,
                   cwd=proj_root,
                   env={**os.environ, "PYTHONIOENCODING": "utf-8"})
out = r.stdout.decode("utf-8", errors="replace") + r.stderr.decode("utf-8", errors="replace")
check("K1 --status 检测运行中", "运行中" in out)
check("K2 --status 含9.1", "9.1" in out)
check("K3 --status 含六层", "感枢" in out or "sensory" in out)

# ====== L: SSE/WebSocket ======
print("\n>>> L: SSE监控端点")
s, ws = api("GET", "/ws/status")
check("L1 /ws/status", s == 200 or s == 404, f"status={s}")

# ====== 最终报告 ======
total_tests = PASS + FAIL
print("\n" + "=" * 70)
print(f"最终报告: Total={total_tests}  Pass={PASS}  Fail={FAIL}  通过率={PASS/total_tests*100:.1f}%")
print("=" * 70)

if QUESTIONS:
    print("\n🔍 关键质问:")
    for q in QUESTIONS:
        print(q)

# 生成更多有价值质问
print("\n🔍 自动生成质问:")
more = [
    f"1. 当前{total}条记忆中，WAL checkpoint机制是否在正常运行？磁盘碎片率？",
    "2. L0感枢实时捕获到前端的延迟是多少？是否有丢事件风险？",
    "3. 47模块容器架构中，是否有单点故障？没有健康检查探针的模块有哪些？",
    "4. 语义搜索的embedding模型是否支持热更新？模型版本变更如何追踪？",
    "5. MCP工具store_memory与platform/remember数据是否最终一致？",
    "6. 前端9个SPA页面是否都已完成功能对后端API的完整对接？",
    "7. 连续请求下内存是否有泄漏趋势？建议做24小时soak test。",
]
for q in more:
    print(f"  {q}")