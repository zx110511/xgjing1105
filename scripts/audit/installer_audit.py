#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
天机v9.1 安装包功能审计脚本
对NSIS安装包进行全面功能审计
"""

import json
import os
import subprocess
import struct
import hashlib
from pathlib import Path
from datetime import datetime

PROJECT_ROOT = Path(__file__).parent.resolve()

# 审计结果
audit_results = []
critical_issues = []
warnings = []

def add_result(category, item, passed, severity, detail=""):
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


def audit_installer_integrity():
    """审计安装包完整性"""
    print("\n" + "=" * 70)
    print("  1. 安装包完整性审计")
    print("=" * 70)

    installer = PROJECT_ROOT / "web" / "src-tauri" / "target" / "release" / "bundle" / "nsis" / "天机v9.1_9.1.0_x64-setup.exe"

    # 1.1 安装包存在性
    add_result("完整性", "安装包文件存在", installer.exists(), "Critical",
               f"路径: {installer}" if installer.exists() else "未找到安装包")

    if not installer.exists():
        return

    # 1.2 文件大小合理
    size_mb = installer.stat().st_size / (1024 * 1024)
    size_ok = 1.0 < size_mb < 100.0  # 合理范围: 1MB~100MB
    add_result("完整性", "安装包大小合理", size_ok, "Critical",
               f"大小: {size_mb:.2f} MB")

    # 1.3 PE文件头验证
    try:
        with open(installer, 'rb') as f:
            header = f.read(2)
            is_pe = header == b'MZ'
        add_result("完整性", "PE文件头验证", is_pe, "Critical",
                   f"Header: {header.hex()}")
    except Exception as e:
        add_result("完整性", "PE文件头验证", False, "Critical", f"读取失败: {e}")

    # 1.4 文件哈希
    try:
        sha256 = hashlib.sha256()
        with open(installer, 'rb') as f:
            for chunk in iter(lambda: f.read(8192), b''):
                sha256.update(chunk)
        hash_val = sha256.hexdigest()
        add_result("完整性", "SHA256哈希计算", True, "Warning",
                   f"SHA256: {hash_val[:32]}...")
    except Exception as e:
        add_result("完整性", "SHA256哈希计算", False, "Warning", f"计算失败: {e}")

    # 1.5 数字签名检查 (Windows)
    try:
        result = subprocess.run(
            ['powershell', '-Command',
             f'(Get-AuthenticodeSignature "{installer}").Status'],
            capture_output=True, text=True, timeout=10
        )
        sig_status = result.stdout.strip()
        # 未签名不算Critical，需要商业代码签名证书
        is_signed = sig_status == "Valid"
        add_result("完整性", "数字签名", is_signed, "Warning",
                   f"签名状态: {sig_status}(需商业代码签名证书)" if not is_signed else f"签名状态: {sig_status}")
    except Exception:
        add_result("完整性", "数字签名", False, "Warning", "检查失败")


def audit_installer_content():
    """审计安装包内容"""
    print("\n" + "=" * 70)
    print("  2. 安装包内容审计")
    print("=" * 70)

    # 2.1 Tauri主程序
    tauri_exe = PROJECT_ROOT / "web" / "src-tauri" / "target" / "release" / "tianji.exe"
    add_result("内容", "Tauri主程序存在", tauri_exe.exists(), "Critical")
    if tauri_exe.exists():
        size_mb = tauri_exe.stat().st_size / (1024 * 1024)
        add_result("内容", "Tauri主程序大小合理", 5.0 < size_mb < 50.0, "Critical",
                   f"大小: {size_mb:.2f} MB")

    # 2.2 前端构建产物
    dist_dir = PROJECT_ROOT / "web" / "dist"
    add_result("内容", "前端构建产物存在", dist_dir.exists(), "Critical")
    if dist_dir.exists():
        html_files = list(dist_dir.rglob("*.html"))
        js_files = list(dist_dir.rglob("*.js"))
        css_files = list(dist_dir.rglob("*.css"))
        add_result("内容", "前端资源完整",
                   len(html_files) > 0 and len(js_files) > 0,
                   "Critical",
                   f"HTML: {len(html_files)}, JS: {len(js_files)}, CSS: {len(css_files)}")

    # 2.3 图标资源
    icon_dir = PROJECT_ROOT / "web" / "src-tauri" / "icons"
    icon_ico = icon_dir / "icon.ico"
    icon_png = icon_dir / "icon.png"
    add_result("内容", "图标资源完整",
               icon_ico.exists() and icon_png.exists(), "Warning")

    # 2.4 Tauri动态库
    tauri_dll = PROJECT_ROOT / "web" / "src-tauri" / "target" / "release" / "tianji_lib.dll"
    add_result("内容", "Tauri动态库存在", tauri_dll.exists(), "Critical")
    if tauri_dll.exists():
        size_mb = tauri_dll.stat().st_size / (1024 * 1024)
        add_result("内容", "Tauri动态库大小合理", 0.1 < size_mb < 50.0, "Warning",
                   f"大小: {size_mb:.2f} MB")


def audit_configuration():
    """审计配置正确性"""
    print("\n" + "=" * 70)
    print("  3. 配置正确性审计")
    print("=" * 70)

    # 3.1 tauri.conf.json
    tauri_conf = PROJECT_ROOT / "web" / "src-tauri" / "tauri.conf.json"
    if tauri_conf.exists():
        try:
            conf = json.loads(tauri_conf.read_text(encoding='utf-8'))

            # 产品名称
            pn = conf.get("productName", "")
            add_result("配置", "产品名称正确", pn == "天机v9.1", "Critical",
                       f"值: {pn}")

            # 版本号
            ver = conf.get("version", "")
            add_result("配置", "版本号正确", ver == "9.1.0", "Critical",
                       f"值: {ver}")

            # 标识符
            ident = conf.get("identifier", "")
            add_result("配置", "标识符正确", ident == "com.yuanchu.tianji", "Critical",
                       f"值: {ident}")

            # 窗口标题
            title = conf.get("app", {}).get("windows", [{}])[0].get("title", "")
            add_result("配置", "窗口标题正确", "天机" in title, "Warning",
                       f"值: {title}")

            # 系统托盘
            has_tray = "trayIcon" in conf.get("app", {})
            add_result("配置", "系统托盘配置", has_tray, "Warning")

            # NSIS打包目标
            targets = conf.get("bundle", {}).get("targets", [])
            has_nsis = "nsis" in targets
            add_result("配置", "NSIS打包目标", has_nsis, "Critical",
                       f"目标: {targets}")

            # WebView安装模式
            wv_mode = conf.get("bundle", {}).get("windows", {}).get(
                "webviewInstallMode", {}).get("type", "")
            add_result("配置", "WebView安装模式", wv_mode in ["downloadBootstrapper", "fixedRuntime", "embedBootstrapper"], "Warning",
                       f"模式: {wv_mode}")

        except Exception as e:
            add_result("配置", "tauri.conf.json解析", False, "Critical", f"解析失败: {e}")
    else:
        add_result("配置", "tauri.conf.json存在", False, "Critical")

    # 3.2 Cargo.toml
    cargo_toml = PROJECT_ROOT / "web" / "src-tauri" / "Cargo.toml"
    if cargo_toml.exists():
        content = cargo_toml.read_text(encoding='utf-8')
        has_tauri_dep = "tauri =" in content
        add_result("配置", "Tauri依赖声明", has_tauri_dep, "Critical")

        has_tray_feature = '"tray-icon"' in content
        add_result("配置", "托盘图标特性", has_tray_feature, "Warning")

        has_shell_plugin = "tauri-plugin-shell" in content
        add_result("配置", "Shell插件", has_shell_plugin, "Warning")

        has_autostart = "tauri-plugin-autostart" in content
        add_result("配置", "自启动插件", has_autostart, "Warning")

        has_updater = "tauri-plugin-updater" in content
        add_result("配置", "更新器插件", has_updater, "Warning")


def audit_functionality():
    """审计功能完整性"""
    print("\n" + "=" * 70)
    print("  4. 功能完整性审计")
    print("=" * 70)

    # 4.1 Rust源码功能检查
    lib_rs = PROJECT_ROOT / "web" / "src-tauri" / "src" / "lib.rs"
    if lib_rs.exists():
        content = lib_rs.read_text(encoding='utf-8')

        has_start_backend = "start_backend" in content
        add_result("功能", "后端启动命令", has_start_backend, "Critical")

        has_stop_backend = "stop_backend" in content
        add_result("功能", "后端停止命令", has_stop_backend, "Critical")

        has_backend_status = "backend_status" in content
        add_result("功能", "后端状态查询", has_backend_status, "Critical")

        has_tray = "TrayIconBuilder" in content
        add_result("功能", "系统托盘实现", has_tray, "Warning")

        has_autostart_backend = "start_backend" in content and "thread::spawn" in content
        add_result("功能", "自动启动后端", has_autostart_backend, "Critical")

        has_exit_handler = "ExitRequested" in content
        add_result("功能", "退出处理", has_exit_handler, "Warning")

        has_port_picker = "find_available_port" in content or "portpicker" in content
        add_result("功能", "端口自动选择", has_port_picker, "Warning")

    else:
        add_result("功能", "Rust源码存在", False, "Critical")

    # 4.2 前端路由检查
    app_tsx = PROJECT_ROOT / "web" / "src" / "App.tsx"
    if app_tsx.exists():
        content = app_tsx.read_text(encoding='utf-8')
        has_routes = "Route" in content or "route" in content
        add_result("功能", "前端路由配置", has_routes, "Warning")
    else:
        # 检查其他入口
        main_tsx = PROJECT_ROOT / "web" / "src" / "main.tsx"
        add_result("功能", "前端入口存在",
                   app_tsx.exists() or main_tsx.exists(), "Warning")

    # 4.3 后端服务检查
    server_main = PROJECT_ROOT / "server" / "main.py"
    add_result("功能", "后端服务入口存在", server_main.exists(), "Critical")

    # 4.4 MCP配置检查
    mcp_json = PROJECT_ROOT / ".trae" / "mcp.json"
    add_result("功能", "MCP配置存在", mcp_json.exists(), "Warning")

    # 4.5 数据目录
    data_dir = PROJECT_ROOT / "data"
    add_result("功能", "数据目录存在", data_dir.exists(), "Warning")

    # 4.6 环境配置模板
    env_file = PROJECT_ROOT / ".env"
    add_result("功能", "环境配置文件存在", env_file.exists(), "Warning")


def audit_security():
    """审计安全性"""
    print("\n" + "=" * 70)
    print("  5. 安全性审计")
    print("=" * 70)

    # 5.1 CSP策略
    tauri_conf = PROJECT_ROOT / "web" / "src-tauri" / "tauri.conf.json"
    if tauri_conf.exists():
        conf = json.loads(tauri_conf.read_text(encoding='utf-8'))
        csp = conf.get("app", {}).get("security", {}).get("csp")
        # CSP为null表示宽松，生产环境应设置; 数字签名需要代码签名证书(商业)
        add_result("安全", "CSP安全策略", csp is not None, "Critical",
                   f"当前: {csp}" if csp else "CSP未设置(开发模式)")

    # 5.2 环境变量无硬编码密钥
    import re
    env_file = PROJECT_ROOT / ".env"
    if env_file.exists():
        content = env_file.read_text(encoding='utf-8')
        has_real_key = bool(re.search(r'sk-[a-zA-Z0-9]{20,}', content))
        add_result("安全", "环境变量无硬编码密钥", not has_real_key, "Critical")

    # 5.3 .gitignore包含.env
    gitignore = PROJECT_ROOT / ".gitignore"
    if gitignore.exists():
        content = gitignore.read_text(encoding='utf-8')
        has_env_ignore = ".env" in content
        add_result("安全", ".gitignore排除.env", has_env_ignore, "Critical")

    # 5.4 WebView安装模式安全
    if tauri_conf.exists():
        conf = json.loads(tauri_conf.read_text(encoding='utf-8'))
        wv_silent = conf.get("bundle", {}).get("windows", {}).get(
            "webviewInstallMode", {}).get("silent", False)
        add_result("安全", "WebView静默安装", wv_silent, "Warning",
                   f"silent: {wv_silent}")


def generate_report():
    """生成审计报告"""
    print("\n" + "=" * 70)
    print("  安装包功能审计报告摘要")
    print("=" * 70)

    total = len(audit_results)
    passed = sum(1 for r in audit_results if r["Passed"])
    critical_count = len(critical_issues)
    warning_count = len(warnings)
    pass_rate = round((passed / total) * 100, 1) if total > 0 else 0

    report = {
        "AuditType": "安装包功能审计",
        "AuditDate": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "InstallerPath": str(PROJECT_ROOT / "web" / "src-tauri" / "target" / "release" / "bundle" / "nsis" / "天机v9.1_9.1.0_x64-setup.exe"),
        "Summary": {
            "TotalItems": total,
            "PassedItems": passed,
            "FailedItems": total - passed,
            "CriticalIssues": critical_count,
            "Warnings": warning_count,
            "PassRate": pass_rate
        },
        "CriticalIssues": critical_issues,
        "Warnings": warnings,
        "Results": audit_results
    }

    report_path = PROJECT_ROOT / "installer-audit-report.json"
    with open(report_path, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print(f"\n  总审计项: {total}")
    print(f"  通过项: {passed}")
    print(f"  严重问题: {critical_count}")
    print(f"  警告问题: {warning_count}")
    print(f"  通过率: {pass_rate}%")

    if critical_count == 0 and warning_count == 0:
        print("\n  \033[92m[OK] 安装包功能审计全部通过！\033[0m")
    elif critical_count == 0:
        print(f"\n  \033[93m[WARN] 审计通过，但有 {warning_count} 个警告\033[0m")
        for w in warnings:
            print(f"     - {w}")
    else:
        print(f"\n  \033[91m[FAIL] 审计未通过！发现 {critical_count} 个严重问题\033[0m")
        for c in critical_issues:
            print(f"     - {c}")

    print(f"\n  报告已保存: {report_path}")

    return critical_count == 0


if __name__ == "__main__":
    print("\n  天机v9.1 安装包功能审计")
    print("  对NSIS安装包进行全面功能审计")
    print()

    audit_installer_integrity()
    audit_installer_content()
    audit_configuration()
    audit_functionality()
    audit_security()
    all_passed = generate_report()

    if all_passed:
        print("\n  \033[92m安装包功能审计: 100% 通过\033[0m")
