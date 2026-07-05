"""
C3修复: 重新生成law/engine.py，扩展范围包含完整模板
"""
from pathlib import Path

ROOT = Path(r"D:\元初系统\天机v9.1")
SRC = ROOT / "core" / "law_domain.py.pre_split"
LAW = ROOT / "core" / "law"

def main():
    source = SRC.read_text(encoding="utf-8-sig")
    lines = source.splitlines(keepends=True)
    print(f"源文件(backup): {SRC}, 行数: {len(lines)}")

    # engine.py: 行259-1837 (ExperienceMiner到LawEnforcer之前)
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
    # 行259-1837 (ExperienceMiner到LawEnforcer之前)
    engine_content += "".join(lines[258:1837])
    (LAW / "engine.py").write_text(engine_content, encoding="utf-8")
    print(f"  -> engine.py: {1837-258} lines from source")

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

    print("C3修复完成！")

if __name__ == "__main__":
    main()
