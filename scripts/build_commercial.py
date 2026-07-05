#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""天机v9.1 商业级发布包构建 v5 - 目录结构+标准.pyc方案
1. compileall编译所有.py为.pyc (optimize=2)
2. 将__pycache__中的.pyc重命名并移动到包目录
3. 删除所有.py源文件(保留__init__.py为空文件)
4. 清理__pycache__

效果: 用户只能看到.pyc字节码，源码完全不可见
"""
import compileall
import os
import shutil
import sys
from pathlib import Path

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="gbk", errors="replace")
        sys.stderr.reconfigure(encoding="gbk", errors="replace")
    except Exception:
        pass

SRC = Path(r"D:\元初系统\天机v9.1")
RELEASE = SRC / "release" / "天机v9.1-全量发布包"

CODE_DIRS = ["core", "server", "indexing", "active_memory", "agents", "adapters", "scripts"]


def compile_and_strip(directory: Path):
    """编译目录下所有.py为.pyc，重组文件结构，删除源码"""
    if not directory.exists():
        print(f"  跳过: {directory.name} (不存在)")
        return 0, 0

    print(f"  编译: {directory.name}...")
    compileall.compile_dir(str(directory), force=True, optimize=2, quiet=1)

    # Step 2: 将__pycache__中的.pyc移动到包目录，重命名为标准格式
    moved = 0
    for cache_dir in list(directory.rglob("__pycache__")):
        pkg_dir = cache_dir.parent
        # 跳过site-packages
        if "site-packages" in str(cache_dir):
            continue

        for pyc_file in list(cache_dir.glob("*.pyc")):
            # module.cpython-312.opt-2.pyc → module.pyc
            name = pyc_file.name
            parts = name.split(".")
            # 格式: module.cpython-312.opt-2.pyc
            if len(parts) >= 4 and "cpython" in parts[1]:
                new_name = parts[0] + ".pyc"
            else:
                new_name = name

            target = pkg_dir / new_name
            shutil.move(str(pyc_file), str(target))
            moved += 1

        # 删除空的__pycache__
        try:
            shutil.rmtree(str(cache_dir), ignore_errors=True)
        except Exception:
            pass

    # Step 3: 删除.py源文件，__init__.py替换为空文件
    removed = 0
    for py_file in list(directory.rglob("*.py")):
        if "site-packages" in str(py_file):
            continue

        if py_file.name == "__init__.py":
            # 保留__init__.py原始内容(包含重要的导入语句)
            # 只删除非__init__.py的源文件
            continue

        # 检查对应的.pyc是否存在
        pyc_file = py_file.with_suffix(".pyc")
        if pyc_file.exists():
            py_file.unlink()
            removed += 1
        else:
            print(f"    警告: 无.pyc, 保留 {py_file.relative_to(directory)}")

    return moved, removed


def main():
    print("=" * 60)
    print("  天机v9.1 商业级发布包构建 v5")
    print("  方案: compileall → 重命名.pyc → 删除源码")
    print("=" * 60)

    total_moved = 0
    total_removed = 0

    for d in CODE_DIRS:
        m, r = compile_and_strip(RELEASE / d)
        total_moved += m
        total_removed += r
        print(f"    {d}: 移动 {m} 个.pyc, 删除 {r} 个.py")

    # 编译顶层文件
    print("\n  编译顶层文件...")
    for f in ["functional_audit.py"]:
        src = RELEASE / f
        if src.exists():
            try:
                compileall.compile_file(str(src), force=True, optimize=2, quiet=1)
                # 查找生成的.pyc
                pyc_in_cache = src.parent / "__pycache__" / f"{src.stem}.cpython-312.opt-2.pyc"
                if pyc_in_cache.exists():
                    target = src.with_suffix(".pyc")
                    shutil.move(str(pyc_in_cache), str(target))
                    src.unlink()
                    total_moved += 1
                    total_removed += 1
                    print(f"    编译并删除: {f}")
                # 清理__pycache__
                cache_dir = RELEASE / "__pycache__"
                if cache_dir.exists():
                    shutil.rmtree(str(cache_dir), ignore_errors=True)
            except Exception as e:
                print(f"    编译失败: {f} - {e}")

    # 统计
    total_files = sum(1 for _ in RELEASE.rglob("*") if _.is_file())
    total_size = sum(f.stat().st_size for f in RELEASE.rglob("*") if f.is_file()) / (1024 * 1024)
    py_count = sum(1 for _ in RELEASE.rglob("*.py") if "site-packages" not in str(_))
    pyc_count = sum(1 for _ in RELEASE.rglob("*.pyc") if "site-packages" not in str(_))

    print(f"\n{'=' * 60}")
    print(f"  商业级构建完成!")
    print(f"  移动.pyc: {total_moved}")
    print(f"  删除源码: {total_removed}")
    print(f"  .py文件(空__init__+入口): {py_count}")
    print(f"  .pyc文件(字节码): {pyc_count}")
    print(f"  总文件数: {total_files}")
    print(f"  总大小: {total_size:.1f}MB")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
