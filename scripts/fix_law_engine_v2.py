"""
C3修复v2: 重新生成law/engine.py，扩展到包含完整模板字符串
"""
from pathlib import Path

ROOT = Path(r"D:\元初系统\天机v9.1")
SRC = ROOT / "core" / "law_domain.py.pre_split"
LAW = ROOT / "core" / "law"

def main():
    source = SRC.read_text(encoding="utf-8-sig")
    lines = source.splitlines(keepends=True)
    print(f"源文件(backup): {SRC}, 行数: {len(lines)}")

    # engine.py: 行259-1609 (ExperienceMiner到LawDomainEngine结尾)
    # + 行1592-1948 (_get_script_templates完整)
    # 实际上LawDomainEngine从1424到1609, _get_script_templates从1592到1948
    # 所以需要259-1948
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
    # 行259-1948 (ExperienceMiner到_get_script_templates结束)
    engine_content += "".join(lines[258:1948])
    (LAW / "engine.py").write_text(engine_content, encoding="utf-8")
    print(f"  -> engine.py: {1948-258} lines from source")

    # 修复f-string中的反斜杠
    content = (LAW / "engine.py").read_text(encoding="utf-8")
    # 替换 f"...{pat_def[\"name\"]}..." 模式
    import re as regex
    old = r'''pattern_id=f"EXP-{hashlib.md5(f\'{mem_id}:{pat_def[\"name\"]}\'.encode()).hexdigest()[:12]}"'''
    new = '''name_val = pat_def["name"]
                        raw = f"{mem_id}:{name_val}".encode()
                        pid = f"EXP-{hashlib.md5(raw).hexdigest()[:12]}"
                        pattern_id=pid,'''
    # 简单字符串替换
    old_str = 'pattern_id=f"EXP-{hashlib.md5(f\'{mem_id}:{pat_def[\\"name\\"]}\'.encode()).hexdigest()[:12]}"'
    if old_str in content:
        content = content.replace(old_str, new)
        print("  -> Fixed f-string in engine.py")

    (LAW / "engine.py").write_text(content, encoding="utf-8")

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

    print("C3修复v2完成！")

if __name__ == "__main__":
    main()
