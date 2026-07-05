"""
C3修复v3: 重新生成law/engine.py，包含LawDomainEngine完整定义
"""
from pathlib import Path

ROOT = Path(r"D:\元初系统\天机v9.1")
SRC = ROOT / "core" / "law_domain.py.pre_split"
LAW = ROOT / "core" / "law"

def main():
    source = SRC.read_text(encoding="utf-8-sig")
    lines = source.splitlines(keepends=True)
    print(f"源文件(backup): {SRC}, 行数: {len(lines)}")

    # LawDomainEngine类从行1424开始
    # _get_script_templates方法中模板字符串包含行1596-1948
    # _generate_single_script从行1948开始
    # 类结束约在行2029
    # 所以engine.py需要行259-2029

    engine_content = '''"""LawDomainEngine主引擎 — 从law_domain.py提取"""
from __future__ import annotations

import hashlib
import json
import logging
import re
import threading
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from .core import (
    LawDomain, LawType, LawPriority, LawStatus,
    EmpiricalLaw, ExperiencePattern,
    _DATA_DIR, _LAW_DIR, _LAW_INDEX, _LAW_STATS,
)

logger = logging.getLogger("tianji.law_domain")

'''
    # 行259-2029: ExperienceMiner到LawDomainEngine完整
    engine_content += "".join(lines[258:2029])
    (LAW / "engine.py").write_text(engine_content, encoding="utf-8")
    print(f"  -> engine.py: {2029-258} lines from source")

    # 修复f-string中的反斜杠问题
    content = (LAW / "engine.py").read_text(encoding="utf-8")
    bad = """pattern_id=f"EXP-{hashlib.md5(f'{mem_id}:{pat_def[\\"name\\"]}'.encode()).hexdigest()[:12]}"","""
    good = """name_val = pat_def["name"]
                        raw = f"{mem_id}:{name_val}".encode()
                        pid = f"EXP-{hashlib.md5(raw).hexdigest()[:12]}"
                        pattern_id=pid,"""
    if bad in content:
        content = content.replace(bad, good)
        (LAW / "engine.py").write_text(content, encoding="utf-8")
        print("  -> Fixed f-string")
    else:
        # 尝试另一种模式
        lines2 = content.splitlines(keepends=True)
        for i, line in enumerate(lines2):
            if 'pat_def[\\"name\\"]' in line or "pat_def[\\\"name\\\"]" in line:
                print(f"  -> Found f-string issue at line {i+1}")
                # 替换整行
                lines2[i] = "                        pattern_id=pid,\n"
                # 在前面插入辅助行
                lines2.insert(i, "                        pid = f\"EXP-{hashlib.md5(raw).hexdigest()[:12]}\"\n")
                lines2.insert(i, "                        raw = f\"{mem_id}:{name_val}\".encode()\n")
                lines2.insert(i, "                        name_val = pat_def[\"name\"]\n")
                (LAW / "engine.py").write_text("".join(lines2), encoding="utf-8")
                print("  -> Fixed f-string (method 2)")
                break

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

    print("C3修复v3完成！")

if __name__ == "__main__":
    main()
