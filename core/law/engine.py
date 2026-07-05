# -*- coding: utf-8 -*-
"""
天机经验法则领域引擎 (Tianji Empirical Law Domain Engine) v2.0
=============================================================
[SSS-PhaseB] 已瘦身: 2180行 → ~50行 (re-export兼容层)

原始文件已拆分为:
- miner.py           → ExperienceMiner (经验挖掘器)
- generator.py       → LawGenerator + RuleLifecycleManager (法则生成+生命周期)
- bridges.py         → LearningBridge + EvolutionBridge (学习/进化桥接)
- engine_core.py     → LawDomainEngine + LawEnforcer (主引擎+执行器基类)
- enforcer_templates.py → DynamicLawEnforcer (动态执行器+Gate门禁)

架构定位:
  天机ICME六层记忆之上 → 元规则层(Meta-Rule Layer)
  输入: L3故障记录 / L4知识概念 / L5策略决策
  输出: 结构化经验法则 → 代码检测脚本 → Gate门禁强制执行

Usage (向后兼容):
    from core.law.engine import LawDomainEngine, ExperienceMiner, ...
    engine = LawDomainEngine()
    laws = engine.quick_mine("进程替换失败...")
"""

# === 核心导入 (从拆分后的模块) ===
from .miner import ExperienceMiner
from .generator import LawGenerator, RuleLifecycleManager
from .bridges import LearningBridge, EvolutionBridge
from .engine_core import LawDomainEngine, LawEnforcer
from .enforcer_templates import DynamicLawEnforcer

# === 基础类型导出 ===
from .core import (
    EmpiricalLaw,
    ExperiencePattern,
    LawDomain,
    LawPriority,
    LawStatus,
    LawType,
)

__all__ = [
    # 主引擎
    "LawDomainEngine",
    "LawEnforcer",
    "DynamicLawEnforcer",
    # 子系统
    "ExperienceMiner",
    "LawGenerator",
    "RuleLifecycleManager",
    "LearningBridge",
    "EvolutionBridge",
    # 数据模型
    "EmpiricalLaw",
    "ExperiencePattern",
    "LawDomain",
    "LawPriority",
    "LawStatus",
    "LawType",
]
