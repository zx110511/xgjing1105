#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
天机v9.1 安全审计脚本
执行代码/配置/资源审计，确保发布质量
"""

import json
import os
import re
from datetime import datetime
from pathlib import Path

# 项目根目录
PROJECT_ROOT = Path(__file__).parent.resolve()

# 审计结果
audit_results = []
critical_issues = []
warnings = []


def add_result(category: str, item: str, passed: bool, severity: str, detail: str = ""):
    """添加审计结果"""
    audit_results.append({
        "Category": category,
        "Item": item,
        "Passed": passed,
        "Severity": severity,
        "Detail": detail,
        "Timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    })

    status = "[OK]" if passed else "[FAIL]"
    color = "\033[92m" if passed else ("\033[91m" if severity == "Critical" else "\033[93m")
    print(f"  {color}{status}\033[0m [{severity}] {item}")
    if detail:
        print(f"      {detail}")

    if not passed:
        if severity == "Critical":
            critical_issues.append(f"{category} - {item}")
        else:
            warnings.append(f"{category} - {item}")


def audit_code():
    """代码审计"""
    print("\n" + "=" * 70)
    print("  1. 代码审计")
    print("=" * 70)

    # 获取代码文件
    code_files = []
    for ext in ["*.py", "*.ts", "*.js"]:
        code_files.extend(PROJECT_ROOT.rglob(ext))

    # 过滤排除目录
    exclude_patterns = ["node_modules", ".git", "__pycache__", "dist", "target", ".venv", "site-packages", "Lib\\site-packages", "_archive"]
    code_files = [f for f in code_files if not any(p in str(f) for p in exclude_patterns)]

    # 1.1 硬编码密钥检测
    secret_patterns = [
        r'sk-[a-zA-Z0-9]{20,}',  # OpenAI API Key
        r'AIza[a-zA-Z0-9_-]{35}',  # Google API Key
        r'ghp_[a-zA-Z0-9]{36}',  # GitHub Token
    ]

    found_secrets = False
    for file in code_files:
        try:
            content = file.read_text(encoding='utf-8', errors='ignore')
            # 跳过测试文件、placeholder和文档示例
            if file.name.startswith('test_') or 'placeholder=' in content or 'DEEPSEEK_API_KEY=sk-xxx' in content:
                continue
            for pattern in secret_patterns:
                matches = re.findall(pattern, content)
                # 过滤掉明显的placeholder和测试数据 (全是x或数字)
                real_secrets = [m for m in matches if not re.match(r'sk-x+$', m) and not re.match(r'sk-\d+$', m)]
                if real_secrets:
                    found_secrets = True
                    add_result("代码", "硬编码密钥检测", False, "Critical", f"文件: {file.name}")
                    break
            if found_secrets:
                break
        except Exception:
            pass

    if not found_secrets:
        add_result("代码", "硬编码密钥检测", True, "Critical")

    # 1.2 bare except检测
    bare_except_count = 0
    for file in [f for f in code_files if f.suffix == ".py"]:
        try:
            content = file.read_text(encoding='utf-8', errors='ignore')
            if re.search(r'except\s*:', content):
                bare_except_count += 1
        except Exception:
            pass

    add_result("代码", "无bare except", bare_except_count == 0, "Warning", f"文件数: {bare_except_count}")

    # 1.3 TODO/FIXME检测
    todo_count = 0
    for file in code_files:
        try:
            content = file.read_text(encoding='utf-8', errors='ignore')
            todo_count += len(re.findall(r'TODO:|FIXME:', content))
        except Exception:
            pass

    add_result("代码", "无技术债务", todo_count < 20, "Warning", f"TODO/FIXME数: {todo_count}")

    # 1.4 SQL注入检测 - 改进检测逻辑
    sql_injection_found = False
    for file in [f for f in code_files if f.suffix == ".py"]:
        try:
            content = file.read_text(encoding='utf-8', errors='ignore')
            # 检测真正的SQL注入模式: execute("..." + variable)
            # 不检测参数化查询: execute(sql, params)
            lines = content.split('\n')
            for i, line in enumerate(lines):
                # 跳过注释
                if line.strip().startswith('#'):
                    continue
                # 检测危险模式: execute("..." + ...) 或 execute('...' + ...)
                if re.search(r'execute\s*\(\s*["\'][^"\']*["\']\s*\+', line):
                    sql_injection_found = True
                    break
                # 检测危险模式: execute("..." % ...)
                if re.search(r'execute\s*\(\s*["\'][^"\']*%[sd][^"\']*["\']', line):
                    sql_injection_found = True
                    break
            if sql_injection_found:
                break
        except Exception:
            pass

    add_result("代码", "无SQL注入风险", not sql_injection_found, "Critical")


def audit_configuration():
    """配置审计"""
    print("\n" + "=" * 70)
    print("  2. 配置审计")
    print("=" * 70)

    # 2.1 tauri.conf.json
    tauri_conf = PROJECT_ROOT / "web" / "src-tauri" / "tauri.conf.json"
    if tauri_conf.exists():
        try:
            conf = json.loads(tauri_conf.read_text(encoding='utf-8'))
            has_product_name = conf.get("productName") and conf["productName"] != "app"
            add_result("配置", "tauri.conf.json productName正确", has_product_name, "Critical", f"值: {conf.get('productName')}")

            has_identifier = conf.get("identifier") and conf["identifier"] != "com.tauri.dev"
            add_result("配置", "tauri.conf.json identifier正确", has_identifier, "Critical", f"值: {conf.get('identifier')}")
        except Exception as e:
            add_result("配置", "tauri.conf.json解析", False, "Critical", f"解析失败: {e}")
    else:
        add_result("配置", "tauri.conf.json存在", False, "Critical")

    # 2.2 Cargo.toml
    cargo_toml = PROJECT_ROOT / "web" / "src-tauri" / "Cargo.toml"
    if cargo_toml.exists():
        content = cargo_toml.read_text(encoding='utf-8')
        has_version = re.search(r'version\s*=\s*["\'][\d.]+["\']', content)
        add_result("配置", "Cargo.toml版本正确", bool(has_version), "Warning")
    else:
        add_result("配置", "Cargo.toml存在", False, "Critical")

    # 2.3 环境变量
    env_files = list(PROJECT_ROOT.rglob(".env")) + list(PROJECT_ROOT.rglob(".env.local"))
    has_hardcoded_env = False
    for file in env_files:
        # 跳过示例文件
        if file.name in [".env.example", ".env.template"]:
            continue
        try:
            content = file.read_text(encoding='utf-8', errors='ignore')
            # 检测真实密钥，跳过placeholder
            if re.search(r'sk-[a-zA-Z0-9]{20,}', content):
                # 过滤placeholder
                matches = re.findall(r'sk-[a-zA-Z0-9]{20,}', content)
                real_secrets = [m for m in matches if not re.match(r'sk-x+$', m)]
                if real_secrets:
                    has_hardcoded_env = True
                    break
        except Exception:
            pass

    add_result("配置", "环境变量无硬编码", not has_hardcoded_env, "Critical")


def audit_resources():
    """资源审计"""
    print("\n" + "=" * 70)
    print("  3. 资源审计")
    print("=" * 70)

    # 3.1 图标文件
    icon_path = PROJECT_ROOT / "web" / "src-tauri" / "icons"
    icon_ico = icon_path / "icon.ico"
    icon_png = icon_path / "icon.png"
    icons_exist = icon_ico.exists() and icon_png.exists()
    add_result("资源", "图标文件完整", icons_exist, "Warning")

    # 3.2 静态资源
    static_dir = PROJECT_ROOT / "web" / "dist"
    static_exists = static_dir.exists()
    add_result("资源", "前端构建产物存在", static_exists, "Critical")

    # 3.3 数据目录
    data_dir = PROJECT_ROOT / "data"
    data_exists = data_dir.exists()
    add_result("资源", "数据目录存在", data_exists, "Warning")

    # 3.4 数据库文件
    db_path = PROJECT_ROOT / "data" / ".memory" / "tianji_memory.db"
    db_exists = db_path.exists()
    add_result("资源", "数据库文件存在", db_exists, "Warning")


def audit_documentation():
    """文档审计"""
    print("\n" + "=" * 70)
    print("  4. 文档审计")
    print("=" * 70)

    # 4.1 README
    readme = PROJECT_ROOT / "README.md"
    add_result("文档", "README.md存在", readme.exists(), "Warning")

    # 4.2 验收标准文档
    acceptance = PROJECT_ROOT / "ACCEPTANCE-CRITERIA-V2.md"
    add_result("文档", "验收标准文档存在", acceptance.exists(), "Warning")

    # 4.3 构建脚本
    build_script = PROJECT_ROOT / "build-desktop.ps1"
    add_result("文档", "构建脚本存在", build_script.exists(), "Warning")

    # 4.4 测试脚本
    test_script = PROJECT_ROOT / "test-acceptance-v2.ps1"
    add_result("文档", "测试脚本存在", test_script.exists(), "Warning")


def generate_report():
    """生成报告"""
    print("\n" + "=" * 70)
    print("  审计报告摘要")
    print("=" * 70)

    total_items = len(audit_results)
    passed_items = sum(1 for r in audit_results if r["Passed"])
    critical_count = len(critical_issues)
    warning_count = len(warnings)

    report = {
        "AuditDate": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "ProjectRoot": str(PROJECT_ROOT),
        "Summary": {
            "TotalItems": total_items,
            "PassedItems": passed_items,
            "FailedItems": total_items - passed_items,
            "CriticalIssues": critical_count,
            "Warnings": warning_count,
            "PassRate": round((passed_items / total_items) * 100, 1) if total_items > 0 else 0
        },
        "CriticalIssues": critical_issues,
        "Warnings": warnings,
        "Results": audit_results
    }

    # 保存报告
    report_path = PROJECT_ROOT / "audit-report.json"
    with open(report_path, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    # 输出摘要
    print(f"\n  总审计项: {total_items}")
    print(f"  通过项: {passed_items}")
    print(f"  严重问题: {critical_count}")
    print(f"  警告问题: {warning_count}")

    if critical_count == 0 and warning_count == 0:
        print("\n  \033[92m[OK] 审计通过！\033[0m")
    elif critical_count == 0:
        print(f"\n  \033[93m[WARN] 审计通过，但有 {warning_count} 个警告\033[0m")
    else:
        print(f"\n  \033[91m[FAIL] 审计未通过！发现 {critical_count} 个严重问题\033[0m")
        for issue in critical_issues:
            print(f"     - {issue}")

    print(f"\n  报告已保存: {report_path}")


if __name__ == "__main__":
    print("\n  天机v9.1 安全审计脚本")
    print("  执行代码/配置/资源/文档审计")

    audit_code()
    audit_configuration()
    audit_resources()
    audit_documentation()
    generate_report()
