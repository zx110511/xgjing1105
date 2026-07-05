"""Orchestrator页面崩溃诊断 + 存储结构审计"""
import http.client, json, os

BASE = "127.0.0.1"
PORT = 8771

def api(method, path):
    c = http.client.HTTPConnection(BASE, PORT, timeout=8)
    c.request(method, path)
    r = c.getresponse()
    d = r.read().decode()
    try: return r.status, json.loads(d)
    except: return r.status, d[:500]

print("=" * 70)
print("1. Orchestrator API 响应结构深度检查")
print("=" * 70)

# 1.1 Root info
status, root = api("GET", "/api/orchestrator/v10/")
print(f"\n[ROOT] {status} keys={list(root.keys()) if isinstance(root, dict) else type(root)}")
if isinstance(root, dict):
    print(f"  version={root.get('version')}")
    print(f"  modules type={type(root.get('modules')).__name__}")

# 1.2 Stats
status, stats = api("GET", "/api/orchestrator/v10/stats")
print(f"\n[STATS] {status} keys={list(stats.keys()) if isinstance(stats, dict) else type(stats)}")
if isinstance(stats, dict):
    for k, v in stats.items():
        if isinstance(v, dict):
            print(f"  {k}: dict keys={list(v.keys())[:10]}")
        elif isinstance(v, list):
            print(f"  {k}: list len={len(v)}")
        else:
            print(f"  {k}: {v} ({type(v).__name__})")

# 1.3 Agent cards - 检查每个card的skills/capabilities结构
status, ac = api("GET", "/api/orchestrator/v10/a2a/agent-cards")
print(f"\n[AGENT_CARDS] {status}")
if isinstance(ac, dict):
    cards = ac.get("agent_cards", [])
    print(f"  total_cards={len(cards)}")
    for i, card in enumerate(cards[:3]):
        print(f"\n  Card[{i}] name={card.get('name')}")
        caps = card.get("capabilities")
        skills = card.get("skills")
        print(f"    capabilities: type={type(caps).__name__}", f"len={len(caps) if hasattr(caps, '__len__') else 'N/A'}")
        print(f"    skills:       type={type(skills).__name__}", f"len={len(skills) if hasattr(skills, '__len__') else 'N/A'}")
        if skills and len(skills) > 0:
            s0 = skills[0]
            print(f"    skills[0]:   type={type(s0).__name__}", f"keys={list(s0.keys()) if isinstance(s0, dict) else 'N/A'}")
            if isinstance(s0, dict) and 'name' in s0:
                print(f"    skills[0].name={s0['name']}")

# 1.4 Workflows
status, wf = api("GET", "/api/orchestrator/v10/workflows?limit=5")
print(f"\n[WORKFLOWS] {status}")
if isinstance(wf, dict):
    wfs = wf.get("workflows", [])
    print(f"  count={wf.get('count')}, actual_len={len(wfs)}")
    if wfs:
        w0 = wfs[0]
        print(f"  wf[0] keys={list(w0.keys())}")
        steps = w0.get("steps")
        print(f"  wf[0].steps: type={type(steps).__name__} len={len(steps) if hasattr(steps,'__len__') else 'N/A'}")

# 1.5 Agent stats
status, ast = api("GET", "/api/orchestrator/agent-stats")
print(f"\n[AGENT_STATS] {status}")
if isinstance(ast, dict):
    agents = ast.get("agents", {})
    print(f"  total_calls={ast.get('total_calls')}, agents_count={len(agents)}")
    if agents:
        first_key = list(agents.keys())[0]
        print(f"  agent_example[{first_key}]: {agents[first_key]}")

print("\n" + "=" * 70)
print("2. 存储结构科学性审计")
print("=" * 70)

data_dir = r"D:\元初系统\天机v9.1\data"
mem_dir = os.path.join(data_dir, ".memory")

# 2.1 data/ 根目录分析
print("\n[data/ 根目录组成]")
root_items = os.listdir(data_dir)
db_files = [f for f in root_items if f.endswith(('.db', '.db-shm', '.db-wal'))]
json_files = [f for f in root_items if f.endswith('.json')]
dirs = [f for f in root_items if os.path.isdir(os.path.join(data_dir, f))]
other = [f for f in root_items if f not in db_files + json_files + dirs]

print(f"  数据库文件({len(db_files)}): {db_files}")
print(f"  JSON配置({len(json_files)}): {json_files}")
print(f"  子目录({len(dirs)}): {dirs}")
print(f"  其他({len(other)}): {other}")

# 2.2 icme.db 重复检测
print("\n[icme.db 重复检测]")
db_root = os.path.join(data_dir, "icme.db")
db_mem = os.path.join(mem_dir, "icme.db")
print(f"  data/icme.db:          {'EXISTS' if os.path.exists(db_root) else 'MISSING'} ({os.path.getsize(db_root) / 1024 / 1024:.1f} MB)")
print(f"  data/.memory/icme.db:  {'EXISTS' if os.path.exists(db_mem) else 'MISSING'} ({os.path.getsize(db_mem) / 1024 / 1024:.1f} MB)" if os.path.exists(db_mem) else "  data/.memory/icme.db:  MISSING")

# 2.3 .memory/ 六层统计
print("\n[data/.memory/ ICME六层统计]")
layers = ['sensory', 'working', 'short_term', 'episodic', 'semantic', 'meta']
total = 0
for layer in layers:
    lp = os.path.join(mem_dir, layer)
    if os.path.exists(lp):
        count = len([f for f in os.listdir(lp) if f.endswith('.json')])
        total += count
        size_mb = sum(os.path.getsize(os.path.join(lp, f)) for f in os.listdir(lp) if f.endswith('.json')) / 1024 / 1024
        print(f"  {layer:12s}: {count:5d} 条  ({size_mb:.2f} MB)")
    else:
        print(f"  {layer:12s}: [不存在!]")
print(f"  {'合计':12s}: {total:5d} 条")

# 2.4 .memory/ 非层文件
print("\n[data/.memory/ 非层文件]")
non_layer = [f for f in os.listdir(mem_dir) if f not in layers and not f.startswith('.')]
for f in non_layer:
    fp = os.path.join(mem_dir, f)
    sz = os.path.getsize(fp) if os.path.isfile(fp) else '<dir>'
    print(f"  {f:40s} {sz:>12}")

# 2.5 data/ vs data/.memory/ 职责划分建议
print("\n[存储架构评估]")
print("""
  当前状态:
  ┌─ data/                    ← 系统级数据(混杂)
  │   ├─ icme.db              ← ?? (12MB, 可能是旧版残留)
  │   ├─ evolution_bus.db     ← 进化总线
  │   ├─ evolving_topology.db ← 进化拓扑
  │   ├─ service_registry.db  ← 服务注册
  │   ├─ turn_log.db          ← 对话日志
  │   ├─ workflow_checkpoints.db ← 工作流检查点
  │   ├─ tcl_terminology.db   ← TCL术语
  │   └─ ...
  │
  └─ data/.memory/            ← ICME记忆引擎(六层JSON + SQLite)
      ├─ sensory/             ← L0 感枢 (103条)
      ├─ working/             ← L1 运枢 (56条)
      ├─ short_term/          ← L2 近枢 (953条)
      ├─ episodic/            ← L3 忆枢 (100条)
      ├─ semantic/            ← L4 知枢 (18条)
      ├─ meta/                ← L5 元枢 (34条)
      ├─ icme.db              ← SQLite FTS5索引 (192MB!) ← 活跃主库
      ├─ procedural_memory/   ← 程序记忆
      └─ .law_domain/          ← 法律领域
""")

print("=" * 70)
print("3. 问题汇总与修复建议")
print("=" * 70)
issues = [
    ("P0-致命", "data/icme.db(12MB) 与 data/.memory/icme.db(192MB) 重复"),
    ("P0-致命", "Orchestrator API路径使用 /v10/ 但产品版本为 v9.1 — 版本号矛盾"),
    ("P1-高",   "data/ 根目录职责不清: 应只含系统级DB，不含icme.db"),
    ("P1-高",   ".memory/icme.db 达192MB需WAL清理或VACUUM"),
    ("P2-中",   "test_*.db 测试数据库混在生产目录(6个)"),
    ("P2-中",   "evolution_bus.db 与 evolving_topology.db 职责边界模糊"),
    ("P3-低",   "autopilot_v*.json 审计报告放在data/而非专用审计目录"),
]
for level, desc in issues:
    print(f"  [{level}] {desc}")
