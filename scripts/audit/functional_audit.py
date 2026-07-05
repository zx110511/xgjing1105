#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""天机v9.1 SSS级全功能实现度审计 v3

修复清单:
- 修复KeyError: 'total' bug (分类统计字典键名不一致)
- 修复Python运行时检测误报 (run_py参数错误)
- 修复后端模式匹配逻辑 (FastAPI实例/路由/跨域检测)
- 修复记忆引擎核心文件检测 (实际路径: core/engine.py, core/hybrid_engine.py等)
- 修复数据库检测 (实际使用icme.db, 非memory.db/tianji.db)
- 修复API端点路径 (/api/health, 非/health)
- 修复端口配置 (使用8778, 与项目配置一致)
- 增加等待时间让后端充分启动
- 修复Windows控制台中文乱码
"""

import os
import sys
import json
import time
import subprocess
import socket
import urllib.request
from pathlib import Path
from datetime import datetime

# Windows控制台编码修复: 强制使用GBK输出，匹配终端编码
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="gbk", errors="replace")
        sys.stderr.reconfigure(encoding="gbk", errors="replace")
    except Exception:
        pass

PROJECT_ROOT = Path(__file__).parent.resolve()
PYTHON_EXE = PROJECT_ROOT / "python" / "python.exe"
SERVER_MAIN = PROJECT_ROOT / "server" / "main.py"
MCP_CONFIG = PROJECT_ROOT / ".trae" / "mcp.json"
DATA_DIR = PROJECT_ROOT / "data"
CORE_DIR = PROJECT_ROOT / "core"
MEMORY_DIR = DATA_DIR / ".memory"
BACKEND_PORT = 8778

R = []
BP = None


def ok(cat, name, status=True, lvl="Normal", detail=""):
    R.append({"c": cat, "n": name, "ok": status, "l": lvl, "d": detail})
    tag = "[OK]" if status else f"[{lvl}]"
    extra = f" - {detail}" if detail else ""
    print(f"  {tag} {name}{extra}")


def free_port(p):
    with socket.socket() as s:
        return s.connect_ex(("127.0.0.1", p)) != 0


def http_get(url, t=8):
    try:
        req = urllib.request.Request(url)
        r = urllib.request.urlopen(req, timeout=t)
        return r.status, r.read().decode("utf-8", errors="ignore")
    except Exception as e:
        return None, str(e)


def run_py(code, t=15):
    try:
        p = subprocess.run(
            [str(PYTHON_EXE), "-c", code],
            capture_output=True, text=True, timeout=t,
            encoding="gbk", errors="replace",
        )
        return p.returncode == 0, (p.stdout + p.stderr).strip()
    except Exception as e:
        return False, str(e)


# ============================================================
print("=" * 65)
print("  天机v9.1 SSS级全功能实现度审计 v3")
print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print("=" * 65)

# [1] 运行时环境
print("\n[1/7] 运行时环境")
print("-" * 45)

if PYTHON_EXE.exists():
    rc, out = run_py("import sys; print(sys.version)")
    ok("环境", "Python运行时", rc, "Critical", out.split("\n")[0] if out else "")
else:
    ok("环境", "Python运行时", False, "Critical", "文件不存在")

for pkg, desc in [
    ("fastapi", "FastAPI框架"),
    ("uvicorn", "Uvicorn服务器"),
    ("pydantic", "Pydantic校验"),
    ("aiofiles", "异步文件IO"),
    ("sklearn", "scikit-learn嵌入"),
    ("sqlite3", "SQLite3数据库"),
]:
    rc, out = run_py(f"import {pkg}; print('OK')")
    detail = ""
    if rc and pkg == "sqlite3":
        import sqlite3 as _sq
        detail = f"v{_sq.sqlite_version}"
    ok("依赖", desc, rc, "Warning" if pkg in ("aiofiles", "sklearn") else "Critical", detail)

# [2] 后端服务能力
print("\n[2/7] 后端服务能力")
print("-" * 45)

if not SERVER_MAIN.exists():
    ok("后端", "服务入口", False, "Critical", "server/main.py不存在")
else:
    ok("后端", "服务入口", True, "Critical")
    mc = SERVER_MAIN.read_text(encoding="utf-8", errors="ignore")
    # 修复: 使用实际存在的模式匹配
    for pat, nm in [
        ("FastAPI(", "FastAPI实例"),
        ("uvicorn", "Uvicorn配置"),
        ("@app.get", "路由定义(GET)"),
        ("@app.post", "路由定义(POST)"),
        ("CORSMiddleware", "跨域配置"),
        ("startup_event", "启动事件"),
    ]:
        ok("后端", nm, pat in mc, "Normal")

    # 实际启动测试
    print("\n  >> 实际启动后端...")
    if free_port(BACKEND_PORT):
        env = dict(os.environ)
        env["AI_MEMORY_ROOT"] = str(PROJECT_ROOT)
        env["AI_MEMORY_PORT"] = str(BACKEND_PORT)
        env["PYTHONIOENCODING"] = "utf-8"
        try:
            BP = subprocess.Popen(
                [str(PYTHON_EXE), "-X", "utf8", "-m", "uvicorn", "server.main:app",
                 "--host", "127.0.0.1", "--port", str(BACKEND_PORT)],
                cwd=str(PROJECT_ROOT), env=env,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            )
            # 轮询等待端口就绪 (最长60秒)
            port_ready = False
            for wait_i in range(30):
                time.sleep(2)
                if BP.poll() is not None:
                    break
                if not free_port(BACKEND_PORT):
                    port_ready = True
                    break
            if port_ready and BP.poll() is None:
                ok("后端", "服务启动成功", True, "Critical", f"PID={BP.pid}, port={BACKEND_PORT}")
            elif BP.poll() is not None:
                err = BP.stderr.read().decode("utf-8", errors="ignore")[:300]
                ok("后端", "服务启动失败", False, "Critical", err[:150])
                BP = None
            else:
                ok("后端", "服务启动-端口未监听", False, "Critical",
                   f"PID={BP.pid} alive but port {BACKEND_PORT} not listening after 60s")
                BP = None
        except Exception as e:
            ok("后端", "启动异常", False, "Critical", str(e))
            BP = None
    else:
        ok("后端", "端口已占用(服务已在运行)", True, "Normal", f":{BACKEND_PORT}")

# [3] API端点可用性
print("\n[3/7] API端点可用性")
print("-" * 45)

base = f"http://127.0.0.1:{BACKEND_PORT}"
if not free_port(BACKEND_PORT):
    for path, label in [
        ("/api/health", "健康检查"),
        ("/", "根路径"),
        ("/api/stats", "系统统计"),
        ("/api/config", "系统配置"),
        ("/openapi.json", "OpenAPI规范"),
    ]:
        st, bd = http_get(f"{base}{path}", 5)
        if st:
            ok("API", label, True, "Normal", f"HTTP {st}")
        else:
            ok("API", label, False, "Warning", str(bd)[:80])
else:
    ok("API", "全部API测试", False, "Critical", "后端未运行")

# [4] 记忆引擎核心
print("\n[4/7] 记忆引擎核心")
print("-" * 45)

# 修复: 检测实际存在的核心文件
core_files = [
    ("engine.py", "ICME引擎(核心)"),
    ("hybrid_engine.py", "混合存储引擎"),
    ("models.py", "Pydantic数据模型"),
    ("config.py", "配置管理"),
    ("sqlite_store.py", "SQLite存储"),
    ("router.py", "智能路由"),
    ("memory/writer.py", "记忆写入器"),
    ("memory/promoter.py", "层级晋升器"),
    ("memory/archiver.py", "归档管理器"),
    ("memory/indexer.py", "检索索引器"),
    ("memory_core/base.py", "记忆核心基类"),
    ("memory_core/core_working.py", "工作记忆层"),
    ("memory_core/core_sensory.py", "感知记忆层"),
    ("memory_core/core_episodic.py", "情景记忆层"),
    ("memory_core/core_semantic.py", "语义记忆层"),
    ("memory_core/core_meta.py", "元认知层"),
    ("search/fts5_strategy.py", "FTS5搜索策略"),
    ("search/semantic_strategy.py", "语义搜索策略"),
    ("search/fusion_strategy.py", "融合搜索策略"),
]

for mf, md in core_files:
    mp = CORE_DIR / mf
    if mp.exists():
        c = mp.read_text(encoding="utf-8", errors="ignore")
        has_code = "class " in c or "def " in c
        ok("核心", md, has_code, "Critical" if "engine" in mf else "Normal")
    else:
        ok("核心", md, False, "Critical" if "engine" in mf else "Warning", "文件缺失")

# 数据库检测 (修复: 实际使用icme.db)
print("\n  >> 数据层检测")
db_files = [
    (MEMORY_DIR / "icme.db", "ICME主数据库"),
    (MEMORY_DIR / "icme.db-shm", "ICME共享内存"),
    (DATA_DIR / "turn_log.db-shm", "对话日志DB"),
]
for dp, dn in db_files:
    if dp.exists():
        sz = dp.stat().st_size / 1024
        ok("数据", dn, True, "Normal", f"{sz:.0f}KB")
    else:
        ok("数据", dn, False, "Warning", "文件缺失")

# 记忆数据检测
if MEMORY_DIR.exists():
    layer_counts = {}
    for layer_dir in MEMORY_DIR.iterdir():
        if layer_dir.is_dir() and not layer_dir.name.startswith("."):
            jsons = list(layer_dir.glob("*.json"))
            layer_counts[layer_dir.name] = len(jsons)
    total = sum(layer_counts.values())
    ok("数据", "记忆数据文件", total > 0, "Critical", f"{total}条, {len(layer_counts)}层")
    # 核心层0条才算失败；辅助层(backups/metrics/test_engine等)0条正常
    _AUX_LAYERS = {"backups", "metrics", "test_engine", "evolution_history", "procedural_memory"}
    for ln, lc in sorted(layer_counts.items()):
        is_aux = ln in _AUX_LAYERS
        ok("数据", f"  {ln}层", lc > 0 or is_aux, "Normal", f"{lc}条{'(辅助层)' if is_aux and lc == 0 else ''}")
else:
    ok("数据", "记忆数据目录", False, "Critical", ".memory目录缺失")

# [5] MCP工具链
print("\n[5/7] MCP工具链")
print("-" * 45)

if MCP_CONFIG.exists():
    try:
        cfg = json.loads(MCP_CONFIG.read_text(encoding="utf-8"))
        srvs = cfg.get("mcpServers", {})
        ok("MCP", "配置有效", True, "Critical", f"{len(srvs)}个服务器")
        for sn, sc in srvs.items():
            cmd_ok = "command" in sc and "args" in sc
            ok("MCP", sn, cmd_ok, "Normal",
               sc.get("command", "?") if cmd_ok else "缺少cmd/args")
    except Exception as e:
        ok("MCP", "JSON解析失败", False, "Critical", str(e))
else:
    ok("MCP", "配置文件不存在", False, "Critical")

# AI平台适配
adapter_file = PROJECT_ROOT / "adapters" / "ai_platform_adapters.py"
ok("适配", "AI平台适配器", adapter_file.exists(), "Normal",
   "多平台适配" if adapter_file.exists() else "文件缺失")

# [6] 前端与桌面应用
print("\n[6/7] 前端与桌面应用")
print("-" * 45)

tauri_exe = PROJECT_ROOT / "web" / "src-tauri" / "target" / "release" / "tianji.exe"
dist = PROJECT_ROOT / "web" / "dist"

if tauri_exe.exists():
    ok("前端", "Tauri桌面应用", True, "Normal",
       f"{tauri_exe.stat().st_size/(1024*1024):.1f}MB")
else:
    ok("前端", "Tauri应用未构建", False, "Warning")

if dist.exists():
    htmls = list(dist.glob("*.html"))
    jss = list(dist.rglob("*.js"))
    csss = list(dist.rglob("*.css"))
    ok("前端", "HTML构建产物", len(htmls) > 0, "Critical", f"{len(htmls)}页")
    ok("前端", "JS资源", len(jss) > 0, "Normal", f"{len(jss)}个")
    ok("前端", "CSS资源", len(csss) > 0, "Normal", f"{len(csss)}个")
else:
    ok("前端", "dist目录不存在", False, "Warning")

# 启动脚本
for sf, sd in [("启动天机.vbs", "无窗口启动器"), ("安装说明.txt", "安装说明")]:
    locs = [PROJECT_ROOT / sf, PROJECT_ROOT / "release" / "天机v9.1-全量发布包" / sf]
    ok("部署", sd, any(l.exists() for l in locs))

# [7] 安装包
print("\n[7/7] 安装包完整性")
print("-" * 45)

release_dir = PROJECT_ROOT / "天机v9.1-发布仓库"
if release_dir.exists():
    ok("安装包", "发布仓库目录", True, "Normal")
    oneclick = release_dir / "一键安装包" / "天机v9.1_一键安装.ps1"
    ok("安装包", "一键安装包", oneclick.exists(), "Critical",
       f"{oneclick.stat().st_size/(1024*1024):.1f}MB" if oneclick.exists() else "缺失")
    nsis = PROJECT_ROOT / "web" / "src-tauri" / "target" / "release" / "bundle" / "nsis"
    nsis_exe = None
    if nsis.exists():
        nsis_exes = list(nsis.glob("*setup.exe"))
        if nsis_exes:
            nsis_exe = nsis_exes[0]
    ok("安装包", "NSIS安装程序", nsis_exe is not None, "Normal",
       nsis_exe.name if nsis_exe else "未构建")
else:
    ok("安装包", "发布仓库目录", False, "Warning", "目录缺失")

# 清理
if BP and BP.poll() is None:
    BP.terminate()
    try:
        BP.wait(timeout=5)
    except Exception:
        BP.kill()

# ============================================================
# 汇总
# ============================================================
print("\n" + "=" * 65)
T = len(R)
P = sum(1 for r in R if r["ok"])
F = T - P
CF = sum(1 for r in R if not r["ok"] and r["l"] == "Critical")
WF = sum(1 for r in R if not r["ok"] and r["l"] == "Warning")
rate = P / T * 100 if T else 0

print(f"\n  总计: {T} | 通过: {P} | 失败: {F}")
print(f"       严重:{CF} 警告:{WF} | 通过率: {rate:.1f}%\n")

cats = {}
for r in R:
    c = r["c"]
    cats.setdefault(c, {"t": 0, "p": 0})
    cats[c]["t"] += 1
    if r["ok"]:
        cats[c]["p"] += 1

print("  分类:")
for c, s in sorted(cats.items()):
    pct = s["p"] / s["t"] * 100
    bar = "#" * int(pct / 5) + "-" * (20 - int(pct / 5))
    lv = "PASS" if pct >= 90 else "WARN" if pct >= 70 else "FAIL"
    print(f"    {c:6s} [{bar}] {s['p']}/{s['t']} ({pct:.0f}%) [{lv}]")

if F > 0:
    print("\n  失败项:")
    for r in R:
        if not r["ok"]:
            m = "!!!" if r["l"] == "Critical" else "!"
            print(f"    [{m}] [{r['l']:8s}] {r['c']}/{r['n']}: {r['d']}")

print("\n" + "=" * 65)
if CF == 0 and rate >= 95:
    g, v = "A+", "产品级就绪"
elif CF == 0 and rate >= 85:
    g, v = "A ", "基本就绪"
elif CF <= 2 and rate >= 75:
    g, v = "B+", "核心可用"
elif rate >= 60:
    g, v = "B ", "部分可用"
else:
    g, v = "C ", "原型阶段"

print(f"  评级: {g}  结论: {v}")
print("=" * 65)

# 保存报告 (修复KeyError: 使用正确的字典键名)
report = {
    "time": datetime.now().isoformat(),
    "grade": g, "verdict": v,
    "summary": {"total": T, "passed": P, "failed": F,
                "critical": CF, "warnings": WF, "passRate": round(rate, 1)},
    "categories": {k: {"total": v_["t"], "passed": v_["p"],
                       "rate": round(v_["p"] / v_["t"] * 100, 1)}
                   for k, v_ in cats.items()},
    "details": R,
}
rp = PROJECT_ROOT / "functional-audit-report.json"
with open(rp, "w", encoding="utf-8") as f:
    json.dump(report, f, ensure_ascii=False, indent=2)
print(f"\n  报告: {rp}")
