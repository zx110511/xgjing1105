"""Law包 — 从law_domain.py拆分"""
from .core import LawDomain, LawType, LawPriority, LawStatus, EmpiricalLaw, ExperiencePattern
from .engine import ExperienceMiner, LawGenerator, RuleLifecycleManager
from .engine import LearningBridge, EvolutionBridge, LawDomainEngine
