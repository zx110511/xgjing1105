"""
C3修复v4: 简化策略 — 只提取枚举+数据类到law/core.py，
其余保留在law/engine.py中(完整复制原始文件内容)
"""
from pathlib import Path

ROOT = Path(r"D:\元初系统\天机v9.1")
SRC = ROOT / "core" / "law_domain.py.pre_split"
LAW = ROOT / "core" / "law"

def main():
    source = SRC.read_text(encoding="utf-8-sig")
    lines = source.splitlines(keepends=True)
    print(f"源文件(backup): {SRC}, 行数: {len(lines)}")

    # === 1. core.py — 枚举 + 数据类 (行52-258) ===
    core_content = '''"""法则核心枚举和数据类 — 从law_domain.py提取"""
from __future__ import annotations

import hashlib
import re
import time
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

_DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"
_LAW_DIR = _DATA_DIR / ".law_domain"
_LAW_INDEX = _LAW_DIR / "law_index.json"
_LAW_STATS = _LAW_DIR / "law_stats.json"


'''
    core_content += "".join(lines[51:258])
    (LAW / "core.py").write_text(core_content, encoding="utf-8")
    print("  -> core.py")

    # === 2. engine.py — 完整复制原始文件，替换枚举import ===
    # 使用原始文件全部内容，只修改import部分
    engine_lines = list(lines)  # 完整复制

    # 找到import块结束位置，插入from .core import
    new_imports = """from .core import (
    LawDomain, LawType, LawPriority, LawStatus,
    EmpiricalLaw, ExperiencePattern,
    _DATA_DIR, _LAW_DIR, _LAW_INDEX, _LAW_STATS,
)
"""
    # 替换原始枚举/数据类定义(行52-258)为import
    # 保留行1-51(模块docstring + imports)
    # 替换行52-258为 from .core import
    # 保留行259-end

    header = "".join(lines[:51])  # 行1-51
    body = "".join(lines[258:])   # 行259-end

    engine_content = header + "\n" + new_imports + "\n" + body
    (LAW / "engine.py").write_text(engine_content, encoding="utf-8")
    print("  -> engine.py (full copy with import redirect)")

    # 修复f-string中的反斜杠
    content = (LAW / "engine.py").read_text(encoding="utf-8")
    # 查找并替换有问题的f-string
    bad_pattern = 'pattern_id=f"EXP-{hashlib.md5(f\'{mem_id}:{pat_def[\\"name\\"]}\'.encode()).hexdigest()[:12]}"'
    if bad_pattern in content:
        content = content.replace(
            bad_pattern,
            'pattern_id=pid  # fixed: see name_val/raw/pid above'
        )
        # 在if matches:行后插入辅助变量
        content = content.replace(
            '                if matches:\n                    ep = ExperiencePattern(\n                        pattern_id=pid  # fixed',
            '                if matches:\n                    name_val = pat_def["name"]\n                    raw = f"{mem_id}:{name_val}".encode()\n                    pid = f"EXP-{hashlib.md5(raw).hexdigest()[:12]}"\n                    ep = ExperiencePattern(\n                        pattern_id=pid,'
        )
        (LAW / "engine.py").write_text(content, encoding="utf-8")
        print("  -> Fixed f-string")

    # === 3. __init__.py ===
    init_content = '''"""Law包 — 从law_domain.py拆分"""
from .core import LawDomain, LawType, LawPriority, LawStatus, EmpiricalLaw, ExperiencePattern
from .engine import ExperienceMiner, LawGenerator, RuleLifecycleManager
from .engine import LearningBridge, EvolutionBridge, LawDomainEngine
from .engine import LawEnforcer, check_hardcoded_paths, check_process_health
from .engine import enforce_process_replacement, run_all_checks
'''
    (LAW / "__init__.py").write_text(init_content, encoding="utf-8")
    print("  -> __init__.py")

    # 删除不需要的子模块
    for f in ["process_laws.py", "path_laws.py", "code_quality_laws.py", "deploy_laws.py", "utils.py"]:
        p = LAW / f
        if p.exists():
            p.unlink()
            print(f"  -> Removed: {f}")

    # 验证
    try:
        from core.law import LawDomain, LawDomainEngine
        print(f"  core.law: OK")
        print(f"  LawDomain members: {list(LawDomain)}")
    except Exception as e:
        print(f"  ERROR: {e}")

    try:
        from core.shared.law_domain import LawDomain as LD2
        print(f"  core.law_domain (thin proxy): OK")
    except Exception as e:
        print(f"  ERROR: {e}")

    print("C3修复v4完成！")

if __name__ == "__main__":
    main()
