"""
C2: tianji_container.py 简化拆分
只提取独立的数据类和辅助模块，主类保留在core.py
"""
import shutil
from pathlib import Path

ROOT = Path(r"D:\元初系统\天机v9.1")
SRC = ROOT / "core" / "tianji_container.py"
CONT = ROOT / "core" / "container"

def main():
    source_backup = SRC.with_suffix(".py.pre_split")
    original_source = source_backup.read_text(encoding="utf-8-sig")
    lines = original_source.splitlines(keepends=True)
    print(f"源文件(backup): {source_backup}, 行数: {len(lines)}")

    # === 1. module_lifecycle.py — 独立数据类 ===
    lifecycle_content = '''"""模块生命周期数据类 — 从tianji_container.py提取"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


'''
    lifecycle_content += "".join(lines[49:83])
    (CONT / "module_lifecycle.py").write_text(lifecycle_content, encoding="utf-8")
    print(f"  -> module_lifecycle.py")

    # === 2. core.py — 主类 + 工厂函数 + 全部内部类 ===
    # 包含TianjiContainer(84-1087) + build_container(1088-3085) + get/set(3086-3093)
    core_content = '''"""TianjiContainer主类 + 工厂函数 — 从tianji_container.py提取"""
from __future__ import annotations

import hashlib
import json
import os
import platform
import subprocess
import sys
import threading
import time
import traceback
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

from .module_lifecycle import ModuleState, ModuleDescriptor, ModuleInstance


'''
    # 行46-48: _log函数
    core_content += "".join(lines[45:49])
    core_content += "\n\n"
    # 行84-1087: TianjiContainer类
    core_content += "".join(lines[83:1087])
    core_content += "\n\n"
    # 行1088-3085: build_container + 内部类
    core_content += "".join(lines[1087:3085])
    core_content += "\n\n"
    # 行3086-3093: get_container/set_container
    core_content += "".join(lines[3085:])

    (CONT / "core.py").write_text(core_content, encoding="utf-8")
    print(f"  -> core.py")

    # === 3. __init__.py ===
    init_content = '''"""Container包 — 从tianji_container.py拆分"""
from .core import TianjiContainer, build_container, get_container, set_container
from .module_lifecycle import ModuleState, ModuleDescriptor, ModuleInstance
'''
    (CONT / "__init__.py").write_text(init_content, encoding="utf-8")
    print("  -> __init__.py")

    # 删除不需要的子模块
    for f in ["signal_router.py", "capacity_planner.py", "benchmark.py"]:
        p = CONT / f
        if p.exists():
            p.unlink()
            print(f"  -> Removed: {f}")

    # 验证import
    print("\n验证import...")
    import importlib
    try:
        mod = importlib.import_module("core.container")
        print(f"  core.container: OK")
        print(f"  TianjiContainer.VERSION: {mod.TianjiContainer.VERSION}")
    except Exception as e:
        print(f"  ERROR: {e}")

    # 验证向后兼容
    try:
        mod2 = importlib.import_module("core.tianji_container")
        print(f"  core.tianji_container: OK (thin proxy)")
    except Exception as e:
        print(f"  ERROR: {e}")

    print("\nC2拆分完成！")

if __name__ == "__main__":
    main()
