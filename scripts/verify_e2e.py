"""
天机v9.1 端到端验证 — 策略D+TCL全链路合体运行
测试：资产注册、TCL归一化、版本链、快照统计、TCL检索增强
"""
import urllib.request, urllib.parse, json, sys, os

BASE = "http://127.0.0.1:8771"
PASS = 0
FAIL = 0

def check(name, condition, detail=""):
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  [PASS] {name}{' — ' + detail if detail else ''}")
    else:
        FAIL += 1
        print(f"  [FAIL] {name}{' — ' + detail if detail else ''}")

def api(method, path, data=None):
    url = BASE + path
    body = json.dumps(data, ensure_ascii=False).encode() if data else None
    req = urllib.request.Request(url, data=body, headers={'Content-Type': 'application/json'}, method=method)
    r = urllib.request.urlopen(req)
    return json.loads(r.read())

print("=" * 60)
print("天机v9.1 策略D+TCL全链路合体验证")
print("=" * 60)

# ── 1. 健康检查 ──
print("\n[1/6] 服务健康检查")
h = api("GET", "/api/health")
check("服务运行中", h.get("status") == "healthy", f"version={h.get('version')}")

# ── 2. 记忆写入 ── (策略D: asset_id + TCL: canonical_ids)
print("\n[2/6] 记忆写入 (策略D+TCL合体)")
r = api("POST", "/api/platform/remember", {
    "content": "天机系统的ICME六层记忆架构中，感枢层(L0)负责原始输入捕获，运枢层(L1)管理会话上下文，近枢层(L2)保持跨会话短期信息，忆枢层(L3)记录决策经验",
    "layer": "working",
    "tags": ["端到端验证", "策略D", "TCL"],
})
check("记忆写入成功", bool(r.get("id")), f"id={r.get('id','')[:12]}...")
check("asset_id返回", bool(r.get("asset_id")), r.get("asset_id"))
check("TCL canonical_ids存在", bool(r.get("metadata", {}).get("tcl_canonical_ids")),
      str(r.get("metadata", {}).get("tcl_canonical_ids")))
tcl_count = len(r.get("metadata", {}).get("tcl_canonical_ids", []))
check("识别≥2个TCL术语", tcl_count >= 2, f"识别{tcl_count}个")

asset_id = r.get("asset_id", "")
entry_id = r.get("id", "")

# ── 3. 版本链 ── (同一记忆再写一次)
print("\n[3/6] 版本链生成")
r2 = api("POST", "/api/platform/remember", {
    "content": "天机系统的ICME六层记忆架构中，感枢层(L0)负责原始输入捕获，运枢层(L1)管理会话上下文 — 补充说明",
    "layer": "working",
    "tags": ["端到端验证", "策略D", "TCL"],
})
aid2 = r2.get("asset_id", "")
check("第二次写入生成新asset_id", bool(aid2) and aid2 != asset_id,
      f"首次={asset_id}, 第二次={aid2}")

# 查询版本链
try:
    versions = api("GET", f"/api/asset/versions/{entry_id}")
    has_chain = len(versions) >= 1
    check("版本链>=1", has_chain, f"版本数={len(versions)}")
except Exception as e:
    check(f"版本链查询可用", False, str(e))

# ── 4. 快照统计 ──
print("\n[4/6] 策略D快照统计")
try:
    stats = api("GET", "/api/asset/stats")
    check("快照统计返回", bool(stats), str(stats)[:120])
except Exception as e:
    check("快照统计可用", False, str(e))

# ── 5. TCL增强检索 ──
print("\n[5/6] TCL增强检索")
try:
    sr = api("GET", f"/api/search/semantic?q={urllib.parse.quote('ICME六层记忆架构')}&limit=5")
    check("语义搜索成功", bool(sr), f"返回{len(sr)}条" if isinstance(sr, list) else str(type(sr)))
except Exception as e:
    check("语义搜索可用", False, str(e)[:80])

try:
    qr = api("GET", f"/api/platform/recall?query={urllib.parse.quote('感枢层+L0')}&limit=5")
    check("记忆召回成功", bool(qr), f"返回{len(qr)}条" if isinstance(qr, list) else str(type(qr)))
except Exception as e:
    check("记忆召回可用", False, str(e)[:80])

# ── 6. 综合统计 ──
print(f"\n[6/6] 验证结果汇总: {PASS} PASS, {FAIL} FAIL ({PASS+FAIL} total)")
print("=" * 60)
if FAIL == 0:
    print("策略D+TCL全链路合体: 全部通过!")
else:
    print(f"策略D+TCL全链路合体: {FAIL}项失败")
print("=" * 60)