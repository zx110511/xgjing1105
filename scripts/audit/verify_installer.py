#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""验证一键安装包的完整性"""
import base64, re, zipfile, os, sys, tempfile, shutil
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.resolve()
PS1_PATH = PROJECT_ROOT / "release" / "天机v9.1_一键安装.ps1"
VBS_PATH = PROJECT_ROOT / "release" / "天机v9.1_一键安装.vbs"

def main():
    print("=" * 60)
    print("  天机v9.1 一键安装包 功能审计")
    print("=" * 60)

    results = []

    # 1. PS1文件存在性
    print("\n[1] 文件存在性检查")
    if PS1_PATH.exists():
        size = PS1_PATH.stat().st_size / (1024 * 1024)
        print(f"    [OK] PS1安装程序: {size:.1f} MB")
        results.append(("文件", "PS1安装程序存在", True))
    else:
        print(f"    [FAIL] PS1安装程序不存在")
        results.append(("文件", "PS1安装程序存在", False))

    if VBS_PATH.exists():
        print(f"    [OK] VBS启动器")
        results.append(("文件", "VBS启动器存在", True))
    else:
        print(f"    [FAIL] VBS启动器不存在")
        results.append(("文件", "VBS启动器存在", False))

    if not PS1_PATH.exists():
        print("\n  审计终止: PS1文件缺失")
        return

    # 2. Base64数据提取与验证
    print("\n[2] 内嵌数据验证")
    content = PS1_PATH.read_text(encoding='utf-8')

    match = re.search(r"@'([\s\S]+?)'@", content)
    if match:
        b64 = match.group(1).strip()
        print(f"    [OK] Base64数据块: {len(b64)} 字符")
        results.append(("数据", "Base64数据块存在", True))

        try:
            zip_bytes = base64.b64decode(b64)
            decoded_size = len(zip_bytes) / (1024 * 1024)
            print(f"    [OK] 解码后大小: {decoded_size:.1f} MB")
            results.append(("数据", "Base64解码成功", True))
        except Exception as e:
            print(f"    [FAIL] Base64解码失败: {e}")
            results.append(("数据", "Base64解码成功", False))
            return
    else:
        print("    [FAIL] 未找到Base64数据块")
        results.append(("数据", "Base64数据块存在", False))
        return

    # 3. ZIP签名验证
    print("\n[3] ZIP结构验证")
    if zip_bytes[:2] == b'PK':
        print(f"    [OK] ZIP签名: PK (有效)")
        results.append(("ZIP", "ZIP签名有效", True))
    else:
        print(f"    [FAIL] ZIP签名无效: {zip_bytes[:2].hex()}")
        results.append(("ZIP", "ZIP签名有效", False))
        return

    # 4. ZIP内容验证
    import io
    try:
        zf = zipfile.ZipFile(io.BytesIO(zip_bytes))
        names = zf.namelist()
        file_count = sum(1 for n in names if not n.endswith('/'))
        dir_count = sum(1 for n in names if n.endswith('/'))
        print(f"    [OK] ZIP内容: {file_count} 个文件, {dir_count} 个目录")
        results.append(("ZIP", "ZIP内容可读取", True))

        # 关键文件检查
        key_files = {
            '启动天机.vbs': '无窗口启动器',
            '停止天机.vbs': '停止脚本',
            'python/python.exe': 'Python运行时',
            'app/tianji.exe': 'Tauri桌面应用',
            '.env': '环境变量配置',
            '.trae/mcp.json': 'MCP配置',
            'server/main.py': '服务入口',
            'core/': '核心代码目录',
            'data/': '数据目录',
            'manifest.json': '发布清单',
            '安装说明.txt': '安装说明',
        }

        print(f"\n[4] 关键组件检查")
        missing = []
        for pattern, desc in key_files.items():
            found = any(
                pattern in n or pattern.replace('/', '\\') in n or n.startswith(pattern.rstrip('/'))
                for n in names
            )
            if found:
                print(f"    [OK] {desc} ({pattern})")
                results.append(("组件", f"{desc}存在", True))
            else:
                print(f"    [WARN] 缺失: {desc} ({pattern})")
                missing.append(pattern)
                results.append(("组件", f"{desc}存在", False))

        zf.close()
    except Exception as e:
        print(f"    [FAIL] ZIP解析失败: {e}")
        results.append(("ZIP", "ZIP内容可读取", False))
        return

    # 5. 模拟解压测试
    print(f"\n[5] 模拟解压测试")
    test_dir = Path(tempfile.mkdtemp(prefix="tianji_test_"))
    try:
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            zf.extractall(test_dir)

        extracted = list(test_dir.rglob("*"))
        extracted_files = [f for f in extracted if f.is_file()]
        print(f"    [OK] 解压成功: {len(extracted_files)} 个文件")

        # 验证关键文件确实存在
        critical_ok = 0
        critical_total = 0
        for pattern, _ in key_files.items():
            target = test_dir / pattern.replace('/', os.sep)
            if not target.exists() and not pattern.endswith('/'):
                target_alt = test_dir / pattern.split('/')[-1]
                if target_alt.exists():
                    critical_ok += 1
            elif target.exists() or (pattern.endswith('/') and target.parent.exists()):
                critical_ok += 1
            critical_total += 1

        print(f"    [OK] 关键文件可用性: {critical_ok}/{critical_total}")
        results.append(("功能", "模拟解压成功", True))

        shutil.rmtree(test_dir, ignore_errors=True)
    except Exception as e:
        print(f"    [FAIL] 解压测试失败: {e}")
        results.append(("功能", "模拟解压成功", False))
        shutil.rmtree(test_dir, ignore_errors=True)

    # 6. VBS启动器验证
    print(f"\n[6] VBS启动器验证")
    if VBS_PATH.exists():
        vbs_content = VBS_PATH.read_text(encoding='utf-8')
        checks = [
            ("WindowStyle Hidden", "无窗口模式"),
            ("powershell.exe", "调用PowerShell"),
            ("ExecutionPolicy Bypass", "执行策略绕过"),
            ("天机v9.1_一键安装.ps1", "引用PS1"),
        ]
        all_ok = True
        for check_str, desc in checks:
            if check_str in vbs_content:
                print(f"    [OK] {desc}")
            else:
                print(f"    [WARN] 缺失: {desc}")
                all_ok = False
        results.append(("VBS", "VBS启动器完整", all_ok))

    # 7. 无Python依赖确认
    print(f"\n[7] 架构依赖检查")
    has_python_dep = "python" in content.lower() and "_install.py" in content
    if not has_python_dep:
        print(f"    [OK] 安装过程无需Python运行时")
        results.append(("架构", "零外部依赖", True))
    else:
        print(f"    [WARN] 可能仍有Python依赖")
        results.append(("架构", "零外部依赖", False))

    # 结果汇总
    print("\n" + "=" * 60)
    total = len(results)
    passed = sum(1 for _, _, ok in results if ok)
    failed = total - passed
    rate = passed / total * 100 if total > 0 else 0

    print(f"  总项: {total} | 通过: {passed} | 失败: {failed} | 通过率: {rate:.1f}%")
    print("=" * 60)

    if rate >= 95:
        print("  结论: 一键安装包通过功能审计")
    elif rate >= 80:
        print("  结论: 基本通过，有少量警告")
    else:
        print("  结论: 未通过，需要修复")


if __name__ == "__main__":
    main()
