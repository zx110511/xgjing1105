"""
C2: tianji_container.py 拆分脚本
3093行 → container/子包(5个模块) + 薄代理
"""
import shutil
from pathlib import Path

ROOT = Path(r"D:\元初系统\天机v9.1")
SRC = ROOT / "core" / "tianji_container.py"
CONT = ROOT / "core" / "container"

def main():
    source = SRC.read_text(encoding="utf-8-sig")
    lines = source.splitlines(keepends=True)
    print(f"源文件: {SRC}, 行数: {len(lines)}")

    # 创建container目录
    CONT.mkdir(parents=True, exist_ok=True)

    # === 1. module_lifecycle.py ===
    # 行50-83: ModuleState, ModuleDescriptor, ModuleInstance
    lifecycle_content = '''"""模块生命周期管理 — 从tianji_container.py提取"""
from __future__ import annotations

import threading
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

'''
    lifecycle_content += "".join(lines[49:83])
    (CONT / "module_lifecycle.py").write_text(lifecycle_content, encoding="utf-8")
    print(f"  -> module_lifecycle.py: {83-49} lines")

    # === 2. signal_router.py ===
    # TianjiContainer中的信号路由/事件总线方法
    # 从TianjiContainer中提取: _emit_event, add_event_listener, set_event_bus_ref,
    # register_subscription, _compute_parallel_layers, _init_single_module
    # 行177-224 (事件/信号相关方法)
    signal_content = '''"""信号路由 + 事件总线 — 从tianji_container.py提取"""
from __future__ import annotations

import threading
from typing import Any, Callable, Dict, List, Optional

'''
    # 提取事件相关方法(行177-224)
    signal_content += "".join(lines[176:224])
    (CONT / "signal_router.py").write_text(signal_content, encoding="utf-8")
    print(f"  -> signal_router.py: {224-176} lines")

    # === 3. capacity_planner.py ===
    # TianjiContainer中的容量规划方法
    # 行范围: 容量相关方法
    capacity_content = '''"""容量规划 + 预警 — 从tianji_container.py提取"""
from __future__ import annotations

from typing import Any, Dict, Optional

'''
    # 提取容量规划方法(行950-1087)
    capacity_content += "".join(lines[949:1087])
    (CONT / "capacity_planner.py").write_text(capacity_content, encoding="utf-8")
    print(f"  -> capacity_planner.py: {1087-949} lines")

    # === 4. benchmark.py ===
    # benchmark方法
    benchmark_content = '''"""性能基准测试 — 从tianji_container.py提取"""
from __future__ import annotations

import time
from typing import Any, Dict, List

'''
    # 提取benchmark方法(行880-949)
    benchmark_content += "".join(lines[879:949])
    (CONT / "benchmark.py").write_text(benchmark_content, encoding="utf-8")
    print(f"  -> benchmark.py: {949-879} lines")

    # === 5. core.py ===
    # TianjiContainer主类(行84-1087) + build_container工厂(行1088-3085) +
    # get_container/set_container(行3086-3093)
    # 这是最核心的部分，包含主类和所有内部类
    core_content = '''"""TianjiContainer主类 — 从tianji_container.py提取"""
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
    # TianjiContainer主类(行84-1087)
    core_content += "".join(lines[83:1087])
    core_content += "\n\n"
    # build_container工厂 + 内部类(行1088-3085)
    core_content += "".join(lines[1087:3085])
    core_content += "\n\n"
    # get_container/set_container(行3086-3093)
    core_content += "".join(lines[3085:])

    (CONT / "core.py").write_text(core_content, encoding="utf-8")
    print(f"  -> core.py: extracted")

    # === 6. __init__.py ===
    init_content = '''"""Container包 — 从tianji_container.py拆分后的模块集合"""
from .core import TianjiContainer, build_container, get_container, set_container
from .module_lifecycle import ModuleState, ModuleDescriptor, ModuleInstance
from .signal_router import *
from .capacity_planner import *
from .benchmark import *
'''
    (CONT / "__init__.py").write_text(init_content, encoding="utf-8")
    print("  -> __init__.py")

    # === 7. 更新tianji_container.py为薄代理 ===
    backup = SRC.with_suffix(".py.pre_split")
    shutil.copy2(SRC, backup)
    print(f"  -> Backup: {backup}")

    thin_proxy = '''"""向后兼容入口 — 所有实现已迁移到 core/container/"""
from core.container import *  # noqa: F401,F403
'''
    SRC.write_text(thin_proxy, encoding="utf-8")
    print("  -> tianji_container.py → thin proxy")

    print("\nC2拆分完成！")

if __name__ == "__main__":
    main()
