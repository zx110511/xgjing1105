#!/usr/bin/env python
"""
天机v9.1 路径引用审计脚本 (PATH-LAW-001)
用法: python scripts/path_audit.py [--strict] [--fix]
--strict: 商用模式，零容忍（任何非法路径=FAIL）
--fix:    自动修复可修复的引用（仅相对安全操作）
"""
import os
import sys
import re
import json
import argparse
from pathlib import Path
from datetime import datetime

PROJECT_ROOT = Path(__file__).resolve().parent.parent
BANNED_PATTERNS = [
    (r"C:\\\\Users\\\\Administrator\\\\python-sdk", "python-sdk外部路径"),
    (r"C:/Users/Administrator/python-sdk", "python-sdk外部路径(正斜杠)"),
    (r"WindowsApps.*python\.exe", "WindowsApps Python路径"),
    (r"AI记忆系统", "旧系统命名(应为天机v9.1)"),
    (r"python\\\\Scripts\\\\python", "Scripts子目录Python(应使用python/python.exe)"),
    (r"python/Scripts/python", "Scripts子目录Python(应使用python/python.exe)"),
    (r"8770", "旧端口8770(应为8771)"),
]
ALLOWED_FILES = {
    "core/config.py",
    "python/pyvenv.cfg",
}
EXCLUDE_DIRS = {".venv", "__pycache__", "node_modules", ".git", "dist", "output"}
EXCLUDE_EXTENSIONS = {".pyc", ".pyo", ".pyd", ".exe", ".dll", ".png", ".ico"}

VIOLATIONS = []
FIXED = 0


def scan_file(filepath: Path, strict: bool) -> list:
    global FIXED
    violations = []
    try:
        content = filepath.read_text(encoding="utf-8", errors="ignore")
        rel_path = str(filepath.relative_to(PROJECT_ROOT))
        for pattern, reason in BANNED_PATTERNS:
            matches = list(re.finditer(pattern, content))
            if matches:
                for m in matches:
                    line_num = content[:m.start()].count("\n") + 1
                    line_content = content.split("\n")[line_num - 1].strip()
                    violations.append({
                        "file": rel_path,
                        "line": line_num,
                        "pattern": pattern,
                        "reason": reason,
                        "snippet": line_content[:120],
                    })
    except Exception as e:
        print(f"[WARN] 无法读取 {filepath}: {e}")
    return violations


def scan_directory(root: Path, strict: bool):
    global VIOLATIONS
    for filepath in root.rglob("*"):
        if not filepath.is_file():
            continue
        rel = str(filepath.relative_to(PROJECT_ROOT))
        skip = False
        for ex_dir in EXCLUDE_DIRS:
            if f"{ex_dir}/" in rel or rel.startswith(ex_dir + "/"):
                skip = True
                break
        if skip:
            continue
        ext = filepath.suffix.lower()
        if ext in EXCLUDE_EXTENSIONS:
            continue
        basename = filepath.name
        if any(basename == af for af in ALLOWED_FILES):
            continue
        v = scan_file(filepath, strict)
        VIOLATIONS.extend(v)


def main():
    parser = argparse.ArgumentParser(description="天机路径引用审计")
    parser.add_argument("--strict", action="store_true", help="商用零容忍模式")
    parser.add_argument("--fix", action="store_true", help="尝试自动修复")
    args = parser.parse_args()

    mode = "商用零容忍(STRICT)" if args.strict else "开发宽松模式"
    print(f"\n{'='*60}")
    print(f" 天机v9.1 路径引用审计 — PATH-LAW-001")
    print(f" 模式: {mode}")
    print(f" 时间: {datetime.now().isoformat()}")
    print(f"{'='*60}\n")

    scan_directory(PROJECT_ROOT, args.strict)

    total = len(VIOLATIONS)
    by_reason = {}
    for v in VIOLATIONS:
        r = v["reason"]
        by_reason[r] = by_reason.get(r, 0) + 1

    print(f" 扫描结果: {'PASS ✅' if total == 0 else f'FAIL ❌ ({total}处违规)'}\n")

    if by_reason:
        print(" 违规分类:")
        for reason, count in sorted(by_reason.items(), key=lambda x: -x[1]):
            print(f"   - {reason}: {count}处")
        print()

    if VIOLATIONS and len(VIOLATIONS) <= 30:
        print(" 详细列表:")
        for i, v in enumerate(VIOLATIONS, 1):
            print(f"   [{i}] {v['file']}:{v['line']}")
            print(f"       原因: {v['reason']}")
            print(f"       内容: {v['snippet']}")
            print()
    elif VIOLATIONS:
        print(f"   (共{total}处，仅显示前30处，其余见完整报告)")

    report = {
        "audit_version": "PATH-LAW-001-v1.0",
        "timestamp": datetime.now().isoformat(),
        "mode": mode,
        "project_root": str(PROJECT_ROOT),
        "total_violations": total,
        "by_category": by_reason,
        "violations": VIOLATIONS[:50],
        "status": "PASS" if total == 0 else "FAIL",
    }
    report_path = PROJECT_ROOT / ".daemon" / "path_audit_report.json"
    report_path.parent.mkdir(exist_ok=True=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f" 完整报告: {report_path}")

    if args.strict and total > 0:
        print(f"\n❌ STRICT模式下{total}处违规 → Gate不通过！必须修复后重新提交。")
        return 2
    elif total == 0:
        print(f"\n✅ 审计通过 — 零非法路径引用。")
        return 0
    else:
        print(f"\n⚠ 发现{total}处违规建议修复。")
        return 1


if __name__ == "__main__":
    sys.exit(main())
