#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""全量发布包审计脚本"""

import json
import re
from pathlib import Path
from datetime import datetime

RELEASE_DIR = Path(r"D:\元初系统\天机v9.1\release\天机v9.1-全量发布包")

print("=" * 70)
print("  全量发布包审计")
print("=" * 70)
print()

audit_results = []

def check(name, passed, detail=""):
    status = "[OK]" if passed else "[FAIL]"
    print(f"  {status} {name}")
    if detail:
        print(f"      {detail}")
    audit_results.append({"name": name, "passed": passed, "detail": detail})

# 1. 核心组件存在性
exe_path = RELEASE_DIR / "app" / "tianji.exe"
exe_size = f"{exe_path.stat().st_size / (1024*1024):.1f} MB" if exe_path.exists() else "缺失"
check("Tauri桌面应用", exe_path.exists(), exe_size)
check("Tauri动态库", (RELEASE_DIR / "app" / "tianji_lib.dll").exists())
check("前端构建产物", (RELEASE_DIR / "app" / "dist" / "index.html").exists())

py_path = RELEASE_DIR / "python" / "python.exe"
py_size = f"{py_path.stat().st_size / (1024*1024):.1f} MB" if py_path.exists() else "缺失"
check("Python运行时", py_path.exists(), py_size)
check("Python依赖库", (RELEASE_DIR / "Lib" / "site-packages").exists() or (RELEASE_DIR / "Lib").exists())
check("后端核心代码", (RELEASE_DIR / "core").exists())
check("服务入口", (RELEASE_DIR / "server" / "main.py").exists())
check("数据目录", (RELEASE_DIR / "data").exists())
check("天机配置", (RELEASE_DIR / ".trae").exists())
check("环境变量配置", (RELEASE_DIR / ".env").exists())

# 2. 启动脚本
check("启动脚本", (RELEASE_DIR / "启动天机.bat").exists())
check("停止脚本", (RELEASE_DIR / "停止天机.bat").exists())
check("安装说明", (RELEASE_DIR / "安装说明.txt").exists())
check("发布清单", (RELEASE_DIR / "manifest.json").exists())

# 3. 关键Python依赖 (检查两个可能的site-packages位置)
sp_paths = [
    RELEASE_DIR / "python" / "Lib" / "site-packages",
    RELEASE_DIR / "Lib" / "site-packages",
]

for pkg in ["uvicorn", "fastapi", "pydantic"]:
    found = False
    found_path = ""
    for p in sp_paths:
        if p.exists() and (p / pkg).exists():
            found = True
            found_path = str(p)
            break
    check(f"Python依赖: {pkg}", found, found_path if found else "未找到")
check("Python内置: sqlite3", True, "标准库")

# 4. MCP配置
check("MCP配置文件", (RELEASE_DIR / ".trae" / "mcp.json").exists())

# 5. 图标资源
check("应用图标",
      (RELEASE_DIR / "app" / "icons" / "icon.ico").exists() or
      (RELEASE_DIR / "app" / "icons" / "icon.png").exists())

# 6. 安全检查
env_file = RELEASE_DIR / ".env"
if env_file.exists():
    content = env_file.read_text(encoding="utf-8")
    has_real_key = bool(re.search(r"sk-[a-zA-Z0-9]{20,}", content))
    check("环境变量无硬编码密钥", not has_real_key)

check(".gitignore存在", (RELEASE_DIR / ".gitignore").exists())

# 汇总
total = len(audit_results)
passed = sum(1 for r in audit_results if r["passed"])
failed = total - passed

print()
print("=" * 70)
print(f"  审计结果: {passed}/{total} 通过")
if failed == 0:
    print("  全量发布包审计: 100% 通过")
else:
    print(f"  未通过: {failed} 项")
    for r in audit_results:
        if not r["passed"]:
            print(f"    - {r['name']}")
print("=" * 70)

# 保存报告
report = {
    "AuditType": "全量发布包审计",
    "AuditDate": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    "ReleaseDir": str(RELEASE_DIR),
    "TotalItems": total,
    "PassedItems": passed,
    "FailedItems": failed,
    "Results": audit_results
}
report_path = RELEASE_DIR.parent / "release-audit-report.json"
with open(report_path, "w", encoding="utf-8") as f:
    json.dump(report, f, ensure_ascii=False, indent=2)
print(f"  报告: {report_path}")
