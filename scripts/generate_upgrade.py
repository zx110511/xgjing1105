#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
天机v9.1 升级包生成器
====================
开发端使用: 对比当前版本与发布版本, 生成增量升级包
只包含变更的文件, 体积远小于全量包

用法:
  python generate_upgrade.py --from 9.1.0 --to 9.2.0
  python generate_upgrade.py --to 9.2.0  (自动检测当前版本)
"""

import os
import sys
import json
import hashlib
import shutil
import argparse
from pathlib import Path
from datetime import datetime

# 强制GBK输出
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="gbk", errors="replace")
        sys.stderr.reconfigure(encoding="gbk", errors="replace")
    except Exception:
        pass

PROJECT_ROOT = Path(__file__).parent.parent
RELEASE_DIR = PROJECT_ROOT / "release" / "天机v9.1-全量发布包"
UPGRADE_OUTPUT = PROJECT_ROOT / "天机v9.1-发布仓库" / "升级包"

# 升级时需要保留的用户数据目录(不覆盖)
PRESERVE_DIRS = {
    "data",           # 用户记忆数据
    "indexing/data",  # 索引数据
    "active_memory/data",  # 主动记忆数据
    "logs",           # 日志
}

# 升级时需要排除的文件
EXCLUDE_PATTERNS = {
    "__pycache__",
    ".git",
    "*.log",
    "*.tmp",
    "data",
    "logs",
}


def file_md5(filepath: Path) -> str:
    """计算文件MD5"""
    h = hashlib.md5()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def should_include(rel_path: str) -> bool:
    """判断文件是否应包含在升级包中"""
    parts = Path(rel_path).parts
    # 排除用户数据目录
    for preserve in PRESERVE_DIRS:
        if rel_path.startswith(preserve.replace("/", "\\")):
            return False
    # 排除缓存和临时文件
    for part in parts:
        if part in ("__pycache__", ".git", "logs", "data"):
            return False
    # 排除日志和临时文件
    if rel_path.endswith((".log", ".tmp")):
        return False
    return True


def scan_directory(directory: Path) -> dict:
    """扫描目录, 返回 {相对路径: md5} 字典"""
    files = {}
    if not directory.exists():
        return files
    for f in directory.rglob("*"):
        if not f.is_file():
            continue
        rel = str(f.relative_to(directory))
        if not should_include(rel):
            continue
        try:
            files[rel] = file_md5(f)
        except (PermissionError, OSError):
            continue
    return files


def generate_upgrade(from_version: str, to_version: str):
    """生成增量升级包"""
    print(f"========================================")
    print(f"  天机v9.1 升级包生成器")
    print(f"  {from_version} -> {to_version}")
    print(f"========================================")

    source_dir = RELEASE_DIR
    if not source_dir.exists():
        print(f"[ERROR] 发布目录不存在: {source_dir}")
        sys.exit(1)

    # 1. 读取当前版本信息
    version_file = source_dir / "version.json"
    if version_file.exists():
        with open(version_file, "r", encoding="utf-8") as f:
            current_version = json.load(f)
        print(f"[INFO] 当前发布版本: {current_version.get('version', 'unknown')}")
    else:
        current_version = {"version": from_version}

    # 2. 扫描当前发布目录
    print(f"[INFO] 扫描发布目录...")
    current_files = scan_directory(source_dir)
    print(f"[INFO] 发现 {len(current_files)} 个文件")

    # 3. 创建升级包目录
    upgrade_name = f"天机v9.1_升级包_{from_version}_to_{to_version}"
    upgrade_dir = UPGRADE_OUTPUT / upgrade_name
    if upgrade_dir.exists():
        shutil.rmtree(upgrade_dir)
    upgrade_dir.mkdir(parents=True, exist_ok=True)

    # 4. 复制所有变更文件到升级包
    print(f"[INFO] 打包升级文件...")
    copied = 0
    total_size = 0
    manifest = {
        "upgrade_from": from_version,
        "upgrade_to": to_version,
        "build_time": datetime.now().isoformat(),
        "files": {},
        "preserve_dirs": list(PRESERVE_DIRS),
    }

    for rel_path, md5 in current_files.items():
        src_file = source_dir / rel_path
        dst_file = upgrade_dir / rel_path
        dst_file.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(str(src_file), str(dst_file))
        file_size = src_file.stat().st_size
        total_size += file_size
        manifest["files"][rel_path] = {
            "md5": md5,
            "size": file_size,
        }
        copied += 1

    # 5. 写入升级清单
    manifest_file = upgrade_dir / "upgrade_manifest.json"
    with open(manifest_file, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)

    # 6. 写入新版本信息
    new_version = {
        "product": "天机",
        "version": to_version,
        "build": int(datetime.now().strftime("%Y%m%d")) * 100 + 1,
        "release_date": datetime.now().strftime("%Y-%m-%d"),
        "channel": "stable",
        "min_upgrade_from": from_version,
    }
    version_out = upgrade_dir / "version.json"
    with open(version_out, "w", encoding="utf-8") as f:
        json.dump(new_version, f, ensure_ascii=False, indent=2)

    # 7. 复制升级脚本
    upgrade_script = Path(__file__).parent / "upgrade_apply.vbs"
    if upgrade_script.exists():
        shutil.copy2(str(upgrade_script), str(upgrade_dir / "一键升级.vbs"))

    size_mb = total_size / (1024 * 1024)
    print(f"")
    print(f"========================================")
    print(f"  升级包生成完成!")
    print(f"========================================")
    print(f"  版本: {from_version} -> {to_version}")
    print(f"  文件数: {copied}")
    print(f"  大小: {size_mb:.1f} MB")
    print(f"  位置: {upgrade_dir}")
    print(f"========================================")
    print(f"")
    print(f"  发送方式: 将整个文件夹打包为ZIP发送给用户")
    print(f"  用户操作: 解压后双击'一键升级.vbs'")
    print(f"========================================")

    return upgrade_dir


def generate_diff_upgrade(old_dir: Path, new_dir: Path, to_version: str):
    """对比两个目录, 只打包差异文件(增量升级包)"""
    print(f"========================================")
    print(f"  天机v9.1 增量升级包生成器")
    print(f"========================================")

    # 扫描旧版本和新版本
    print(f"[INFO] 扫描旧版本: {old_dir}")
    old_files = scan_directory(old_dir)
    print(f"[INFO] 扫描新版本: {new_dir}")
    new_files = scan_directory(new_dir)

    # 找出差异: 新增 + 修改
    added = set(new_files.keys()) - set(old_files.keys())
    modified = {k for k in set(new_files.keys()) & set(old_files.keys())
                if new_files[k] != old_files[k]}
    removed = set(old_files.keys()) - set(new_files.keys())

    changed = added | modified
    print(f"[INFO] 新增: {len(added)}, 修改: {len(modified)}, 删除: {len(removed)}")
    print(f"[INFO] 需要更新: {len(changed)} 个文件")

    # 读取旧版本号
    old_version_file = old_dir / "version.json"
    from_version = "9.0.0"
    if old_version_file.exists():
        with open(old_version_file, "r", encoding="utf-8") as f:
            old_ver = json.load(f)
            from_version = old_ver.get("version", from_version)

    # 创建升级包
    upgrade_name = f"天机v9.1_增量升级_{from_version}_to_{to_version}"
    upgrade_dir = UPGRADE_OUTPUT / upgrade_name
    if upgrade_dir.exists():
        shutil.rmtree(upgrade_dir)
    upgrade_dir.mkdir(parents=True, exist_ok=True)

    # 复制变更文件
    total_size = 0
    manifest = {
        "upgrade_from": from_version,
        "upgrade_to": to_version,
        "build_time": datetime.now().isoformat(),
        "type": "incremental",
        "files": {},
        "removed_files": list(removed),
        "preserve_dirs": list(PRESERVE_DIRS),
    }

    for rel_path in changed:
        src_file = new_dir / rel_path
        if not src_file.exists():
            continue
        dst_file = upgrade_dir / rel_path
        dst_file.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(str(src_file), str(dst_file))
        file_size = src_file.stat().st_size
        total_size += file_size
        manifest["files"][rel_path] = {
            "md5": new_files[rel_path],
            "size": file_size,
            "action": "add" if rel_path in added else "modify",
        }

    # 写入清单
    with open(upgrade_dir / "upgrade_manifest.json", "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)

    # 写入新版本
    new_version = {
        "product": "天机",
        "version": to_version,
        "build": int(datetime.now().strftime("%Y%m%d")) * 100 + 1,
        "release_date": datetime.now().strftime("%Y-%m-%d"),
        "channel": "stable",
        "min_upgrade_from": from_version,
    }
    with open(upgrade_dir / "version.json", "w", encoding="utf-8") as f:
        json.dump(new_version, f, ensure_ascii=False, indent=2)

    # 复制升级脚本
    upgrade_script = Path(__file__).parent / "upgrade_apply.vbs"
    if upgrade_script.exists():
        shutil.copy2(str(upgrade_script), str(upgrade_dir / "一键升级.vbs"))

    size_mb = total_size / (1024 * 1024)
    print(f"")
    print(f"========================================")
    print(f"  增量升级包生成完成!")
    print(f"========================================")
    print(f"  版本: {from_version} -> {to_version}")
    print(f"  更新文件: {len(changed)}")
    print(f"  删除文件: {len(removed)}")
    print(f"  包大小: {size_mb:.1f} MB")
    print(f"  位置: {upgrade_dir}")
    print(f"========================================")

    return upgrade_dir


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="天机v9.1 升级包生成器")
    parser.add_argument("--from", dest="from_ver", default=None, help="源版本号")
    parser.add_argument("--to", dest="to_ver", required=True, help="目标版本号")
    parser.add_argument("--diff", dest="diff_dir", default=None, help="旧版本目录(增量模式)")
    args = parser.parse_args()

    if args.diff_dir:
        generate_diff_upgrade(Path(args.diff_dir), RELEASE_DIR, args.to_ver)
    else:
        from_ver = args.from_ver or "9.1.0"
        generate_upgrade(from_ver, args.to_ver)
