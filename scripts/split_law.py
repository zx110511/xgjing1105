"""
C3: law_domain.py 拆分脚本
2223行 → law/子包(按域拆分) + 薄代理
"""
import shutil
from pathlib import Path

ROOT = Path(r"D:\元初系统\天机v9.1")
SRC = ROOT / "core" / "law_domain.py"
LAW = ROOT / "core" / "law"

def main():
    source = SRC.read_text(encoding="utf-8-sig")
    lines = source.splitlines(keepends=True)
    print(f"源文件: {SRC}, 行数: {len(lines)}")

    LAW.mkdir(parents=True, exist_ok=True)

    # === 1. core.py — 枚举 + 数据类 ===
    # 行52-258: LawDomain, LawType, LawPriority, LawStatus, EmpiricalLaw, ExperiencePattern
    core_content = '''"""法则核心枚举和数据类 — 从law_domain.py提取"""
from __future__ import annotations

import hashlib
import json
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

    # === 2. process_laws.py — PR-LAW进程法则 ===
    # 行1610-1689: check_hardcoded_paths + main(进程法则)
    # 行1690-1785: check_process_health + enforce_process_replacement
    # 行1786-1837: main(进程替换)
    process_content = '''"""PR-LAW 进程法则 — 从law_domain.py提取"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

'''
    # 行1610-1837
    process_content += "".join(lines[1609:1837])
    (LAW / "process_laws.py").write_text(process_content, encoding="utf-8")
    print("  -> process_laws.py")

    # === 3. path_laws.py — PATH-LAW路径法则 ===
    # 行1838-1918: LawEnforcer + 动态类生成
    path_content = '''"""PATH-LAW 路径法则 — 从law_domain.py提取"""
from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any, Dict, List

'''
    # 行1838-1918
    path_content += "".join(lines[1837:1918])
    (LAW / "path_laws.py").write_text(path_content, encoding="utf-8")
    print("  -> path_laws.py")

    # === 4. code_quality_laws.py — CODE-LAW代码质量法则 ===
    # 行1919-2029: main(代码质量)
    code_content = '''"""CODE-LAW 代码质量法则 — 从law_domain.py提取"""
from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any, Dict, List

'''
    # 行1919-2029
    code_content += "".join(lines[1918:2029])
    (LAW / "code_quality_laws.py").write_text(code_content, encoding="utf-8")
    print("  -> code_quality_laws.py")

    # === 5. deploy_laws.py — DEPLOY-LAW部署法则 ===
    # 行2030-2058: run_all_checks
    deploy_content = '''"""DEPLOY-LAW 部署法则 — 从law_domain.py提取"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List

'''
    # 行2030-2058
    deploy_content += "".join(lines[2029:2058])
    (LAW / "deploy_laws.py").write_text(deploy_content, encoding="utf-8")
    print("  -> deploy_laws.py")

    # === 6. engine.py — LawDomainEngine主引擎 ===
    # 行259-1609: ExperienceMiner, LawGenerator, RuleLifecycleManager,
    #             LearningBridge, EvolutionBridge, LawDomainEngine
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
    # 行259-1609
    engine_content += "".join(lines[258:1609])
    (LAW / "engine.py").write_text(engine_content, encoding="utf-8")
    print("  -> engine.py")

    # === 7. utils.py — 工具函数 ===
    # 行2059-2223: main + string等工具
    utils_content = '''"""法则工具函数 — 从law_domain.py提取"""
from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any, Dict, List

'''
    # 行2059-2223
    utils_content += "".join(lines[2058:])
    (LAW / "utils.py").write_text(utils_content, encoding="utf-8")
    print("  -> utils.py")

    # === 8. __init__.py ===
    init_content = '''"""Law包 — 从law_domain.py拆分后的模块集合"""
from .core import LawDomain, LawType, LawPriority, LawStatus, EmpiricalLaw, ExperiencePattern
from .engine import ExperienceMiner, LawGenerator, RuleLifecycleManager
from .engine import LearningBridge, EvolutionBridge, LawDomainEngine
from .process_laws import check_hardcoded_paths, check_process_health, enforce_process_replacement
from .path_laws import LawEnforcer
from .code_quality_laws import *
from .deploy_laws import run_all_checks
from .utils import *
'''
    (LAW / "__init__.py").write_text(init_content, encoding="utf-8")
    print("  -> __init__.py")

    # === 9. 更新law_domain.py为薄代理 ===
    backup = SRC.with_suffix(".py.pre_split")
    shutil.copy2(SRC, backup)
    print(f"  -> Backup: {backup}")

    thin_proxy = '''"""向后兼容入口 — 所有实现已迁移到 core/law/"""
from core.law import *  # noqa: F401,F403
'''
    SRC.write_text(thin_proxy, encoding="utf-8")
    print("  -> law_domain.py → thin proxy")

    # 验证
    print("\n验证import...")
    try:
        from core.law import LawDomain, LawDomainEngine, LawEnforcer
        print(f"  core.law: OK")
        print(f"  LawDomain members: {list(LawDomain)}")
    except Exception as e:
        print(f"  ERROR: {e}")

    try:
        from core.shared.law_domain import LawDomain as LD2
        print(f"  core.law_domain (thin proxy): OK")
    except Exception as e:
        print(f"  ERROR: {e}")

    print("\nC3拆分完成！")

if __name__ == "__main__":
    main()
