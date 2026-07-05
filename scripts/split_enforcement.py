"""
C1: enforcement_hook.py 拆分脚本
将3593行单体拆分为5个子模块，保持向后兼容
"""
import re
import shutil
from pathlib import Path

ROOT = Path(r"D:\元初系统\天机v9.1")
SRC = ROOT / "core" / "enforcement_hook.py"
ENF = ROOT / "core" / "enforcement"

def read_source():
    return SRC.read_text(encoding="utf-8-sig")

def extract_imports(source: str) -> str:
    """提取文件顶部的import语句"""
    lines = source.splitlines(keepends=True)
    imports = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("import ") or stripped.startswith("from "):
            imports.append(line)
        elif stripped.startswith("#") or stripped.startswith('"""') or stripped == "":
            imports.append(line)
        else:
            break
    # 找到第一个非import/注释/docstring行
    result = []
    in_docstring = False
    for line in lines:
        stripped = line.strip()
        if not in_docstring and stripped.startswith('"""'):
            in_docstring = True
            result.append(line)
            if stripped.count('"""') >= 2 and not stripped.endswith('"""'):
                pass
            elif stripped.endswith('"""') and stripped.count('"""') == 2:
                in_docstring = False
            continue
        if in_docstring:
            result.append(line)
            if '"""' in stripped and not stripped.startswith('"""'):
                in_docstring = False
            continue
        if stripped.startswith("import ") or stripped.startswith("from "):
            result.append(line)
        elif stripped.startswith("#") or stripped == "":
            result.append(line)
        else:
            break
    return "".join(result)

def extract_class_range(source: str, class_name: str, all_classes: list) -> tuple:
    """提取指定class的行范围"""
    lines = source.splitlines()
    start = None
    for i, line in enumerate(lines):
        if re.match(rf'^class {re.escape(class_name)}\b', line):
            start = i
            break
    if start is None:
        return None, None

    # 找到下一个同级class或文件末尾
    end = len(lines)
    for i in range(start + 1, len(lines)):
        if re.match(r'^class \w+', lines[i]) and not lines[i].startswith(' '):
            end = i
            break
        if re.match(r'^(def |[A-Z_]+\s*=|if __name__)', lines[i]) and not lines[i].startswith(' '):
            end = i
            break
    return start, end

def main():
    source = read_source()
    lines = source.splitlines(keepends=True)

    print(f"源文件: {SRC}")
    print(f"总行数: {len(lines)}")

    # === 1. otel_attributes.py ===
    # OtelGenAISpanKind(55), GenAIAgentAttributes(64), OtelGenAISpan(86)
    # 行55-151
    otel_content = '''"""OTel GenAI 属性定义 — 从enforcement_hook.py提取"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

'''
    # 提取OtelGenAISpanKind + GenAIAgentAttributes + OtelGenAISpan
    otel_lines = lines[54:151]  # 0-based: line 55-151
    otel_content += "".join(otel_lines)

    otel_path = ENF / "otel_attributes.py"
    otel_path.write_text(otel_content, encoding="utf-8")
    print(f"  -> {otel_path}: {len(otel_lines)} lines")

    # === 2. standards/owasp_inspect.py ===
    # OWASPInspectionColumn(943), OWASPAgBOMEntry(954), OWASPAOSObservation(978),
    # OWASPAosBridge(999), OWASPInspectRule(1069), OWASPInspectEngine(1162)
    # 行943-1246
    owasp_content = '''"""OWASP AOS Inspect规则库 — 从enforcement_hook.py提取"""
from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

'''
    owasp_lines = lines[942:1246]
    owasp_content += "".join(owasp_lines)

    owasp_path = ENF / "standards" / "owasp_inspect.py"
    owasp_path.write_text(owasp_content, encoding="utf-8")
    print(f"  -> {owasp_path}: {len(owasp_lines)} lines")

    # === 3. standards/iso_diaml.py ===
    # ISODimension(687), ISOAnnotation(701), DiAMLSerializer(758), PROVTrace(836)
    # 行687-861
    iso_content = '''"""ISO DiAML CF映射 — 从enforcement_hook.py提取"""
from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

'''
    iso_lines = lines[686:861]
    iso_content += "".join(iso_lines)

    iso_path = ENF / "standards" / "iso_diaml.py"
    iso_path.write_text(iso_content, encoding="utf-8")
    print(f"  -> {iso_path}: {len(iso_lines)} lines")

    # === 4. standards/ms_agent_span.py ===
    # MsAgentTaskSpanKind(152), MsAgentTaskSpan(164), MsAgentTaskSpanManager(279)
    # 行152-384
    ms_content = '''"""Microsoft Agent Task Span — 从enforcement_hook.py提取"""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

'''
    ms_lines = lines[151:384]
    ms_content += "".join(ms_lines)

    ms_path = ENF / "standards" / "ms_agent_span.py"
    ms_path.write_text(ms_content, encoding="utf-8")
    print(f"  -> {ms_path}: {len(ms_lines)} lines")

    # === 5. standards/otel_eval.py ===
    # OTelEvaluationSpanKind(1247), OTelEvaluationSpan(1254), OTelEvaluationBridge(1299),
    # EvalDimension(3351), EvalScoringMatrix(3361), EvalResult(3425), OTelEvalEngine(3445)
    # 行1247-1345 + 行3351-3593
    eval_content = '''"""OTel GenAI Evaluation 6维评分 — 从enforcement_hook.py提取"""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

'''
    eval_lines_1 = lines[1246:1345]  # OTelEvaluationSpanKind/Span/Bridge
    eval_lines_2 = lines[3350:]       # EvalDimension/Matrix/Result/OTelEvalEngine
    eval_content += "".join(eval_lines_1)
    eval_content += "\n\n"
    eval_content += "".join(eval_lines_2)

    eval_path = ENF / "standards" / "otel_eval.py"
    eval_path.write_text(eval_content, encoding="utf-8")
    print(f"  -> {eval_path}: {len(eval_lines_1)+len(eval_lines_2)} lines")

    # === 6. hook_core.py ===
    # EnforcementLevel(49) + 剩余核心类(385-686, 862-942, 1346-3350)
    # 排除已提取的类
    hook_content = '''"""EnforcementHook核心 — 从enforcement_hook.py提取"""
from __future__ import annotations

import hashlib
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set

from .otel_attributes import OtelGenAISpanKind, GenAIAgentAttributes, OtelGenAISpan
from .standards.ms_agent_span import MsAgentTaskSpanKind, MsAgentTaskSpan, MsAgentTaskSpanManager

'''
    # EnforcementLevel(49-54) + OtelSpanContext(385-397) + OtelMCPInterceptor(398-515)
    # + vCon*(516-637) + FileOperation(612-637) + MCPCallDetail(638-655) + ErrorLog(656-674)
    # + ConversationClass(675-686) + TokenEconomy(862-882) + SevenDimensionalLogModel(883-894)
    # + LoongSuite*(895-942) + LoongSuiteAlignment(1346-1405) + ReasoningLog(1406-1435)
    # + StateLog(1436-1459) + DecisionLog(1460-1505) + ActionLog(1506-1527)
    # + ObservationLog(1528-1551) + ReflectionLog(1552-1574) + FeedbackRecord(1575-1638)
    # + FeedbackAwareLoop(1639-1660) + FAIRMetadata(1661-1703) + ConversationRecord(1704-1725)
    # + EnforcementDecision(1726-1791) + ConversationRegistry(1792-3289)
    # + TianjiEnforcementHook(1792-3289) + SkillExtractionPipeline(3290-3350)

    # 行49-54 (EnforcementLevel)
    hook_content += "".join(lines[48:54])
    # 行385-686 (OtelSpanContext到ConversationClass)
    hook_content += "\n\n"
    hook_content += "".join(lines[384:686])
    # 行862-942 (TokenEconomy到LoongSuiteMetadata)
    hook_content += "\n\n"
    hook_content += "".join(lines[861:942])
    # 行1346-3350 (LoongSuiteAlignment到SkillExtractionPipeline)
    hook_content += "\n\n"
    hook_content += "".join(lines[1345:3350])

    hook_path = ENF / "hook_core.py"
    hook_path.write_text(hook_content, encoding="utf-8")
    print(f"  -> {hook_path}: extracted")

    # === 7. standards/__init__.py ===
    standards_init = '''"""Standards子包"""
from .owasp_inspect import OWASPInspectionColumn, OWASPAgBOMEntry, OWASPAOSObservation
from .owasp_inspect import OWASPAosBridge, OWASPInspectRule, OWASPInspectEngine
from .iso_diaml import ISODimension, ISOAnnotation, DiAMLSerializer, PROVTrace
from .ms_agent_span import MsAgentTaskSpanKind, MsAgentTaskSpan, MsAgentTaskSpanManager
from .otel_eval import OTelEvaluationSpanKind, OTelEvaluationSpan, OTelEvaluationBridge
from .otel_eval import EvalDimension, EvalScoringMatrix, EvalResult, OTelEvalEngine
'''
    (ENF / "standards" / "__init__.py").write_text(standards_init, encoding="utf-8")
    print("  -> standards/__init__.py")

    # === 8. 更新 enforcement/__init__.py ===
    enf_init = '''"""Enforcement包 — 从enforcement_hook.py拆分后的模块集合"""
from .hook_core import (
    EnforcementLevel,
    OtelSpanContext,
    OtelMCPInterceptor,
    vConConsentStatus,
    vConLifecycleState,
    vConParty,
    vConConsent,
    vConLifecycle,
    FileOperation,
    MCPCallDetail,
    ErrorLog,
    ConversationClass,
    TokenEconomy,
    SevenDimensionalLogModel,
    LoongSuiteAgentCategory,
    LoongSuiteMetadata,
    LoongSuiteAlignment,
    ReasoningLog,
    StateLog,
    DecisionLog,
    ActionLog,
    ObservationLog,
    ReflectionLog,
    FeedbackRecord,
    FeedbackAwareLoop,
    FAIRMetadata,
    ConversationRecord,
    EnforcementDecision,
    ConversationRegistry,
    TianjiEnforcementHook,
    SkillExtractionPipeline,
)
from .otel_attributes import OtelGenAISpanKind, GenAIAgentAttributes, OtelGenAISpan
from .standards import (
    OWASPInspectionColumn, OWASPAgBOMEntry, OWASPAOSObservation,
    OWASPAosBridge, OWASPInspectRule, OWASPInspectEngine,
    ISODimension, ISOAnnotation, DiAMLSerializer, PROVTrace,
    MsAgentTaskSpanKind, MsAgentTaskSpan, MsAgentTaskSpanManager,
    OTelEvaluationSpanKind, OTelEvaluationSpan, OTelEvaluationBridge,
    EvalDimension, EvalScoringMatrix, EvalResult, OTelEvalEngine,
)
'''
    (ENF / "__init__.py").write_text(enf_init, encoding="utf-8")
    print("  -> enforcement/__init__.py (updated)")

    # === 9. 更新 enforcement_hook.py 为薄代理 ===
    thin_proxy = '''"""向后兼容入口 — 所有实现已迁移到 core/enforcement/"""
from core.enforcement import *  # noqa: F401,F403
'''
    # 备份原文件
    backup = SRC.with_suffix(".py.pre_split")
    shutil.copy2(SRC, backup)
    print(f"  -> Backup: {backup}")

    SRC.write_text(thin_proxy, encoding="utf-8")
    print(f"  -> enforcement_hook.py → thin proxy")

    print("\n拆分完成！")

if __name__ == "__main__":
    main()
