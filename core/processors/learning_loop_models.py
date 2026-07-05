# -*- coding: utf-8-sig -*-
"""学习闭环 — 数据模型

从 learning_loop.py 拆分 (SSS-PhaseB)
"""

import json
import time
import hashlib
import threading
import logging
from pathlib import Path
from typing import Any, Optional, Dict, List, Set, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
try:
    from core.shared.deepseek_driver import TianjiEvent, EventType
except ImportError:
    TianjiEvent = None
    EventType = None
import urllib.request
try:
    from ..shared.skill_registry import SkillSchema, SkillCategory, SkillStatus
except ImportError:
    SkillSchema = None
    SkillCategory = None
    SkillStatus = None


from typing import Dict

class TaskComplexity(str, Enum):
    SIMPLE = "simple"
    MODERATE = "moderate"
    COMPLEX = "complex"
    CRITICAL = "critical"


class LearningPhase(str, Enum):
    EXECUTE = "execute"
    EVALUATE = "evaluate"
    EXTRACT = "extract"
    CONSOLIDATE = "consolidate"
    REFLECT = "reflect"


class KnowledgeType(str, Enum):
    PATTERN = "pattern"
    SOLUTION = "solution"
    DECISION = "decision"
    ERROR_PATTERN = "error_pattern"
    WORKFLOW = "workflow"
    BEST_PRACTICE = "best_practice"


@dataclass
class LearningRecord:
    session_id: str
    task_description: str
    agent_id: str
    complexity: TaskComplexity
    phase: LearningPhase
    mcp_calls: List[str] = field(default_factory=list)
    duration_ms: float = 0.0
    success: bool = True
    error_info: str = ""
    tags: List[str] = field(default_factory=list)
    knowledge_extracted: bool = False
    skill_created: bool = False
    memory_ids: List[str] = field(default_factory=list)
    timestamp: float = field(default_factory=time.time)

    @property
    def content_hash(self) -> str:
        raw = f"{self.session_id}:{self.agent_id}:{self.task_description[:100]}"
        return hashlib.md5(raw.encode()).hexdigest()[:12]

    def to_dict(self) -> dict:
        return {
            "session_id": self.session_id,
            "task_description": self.task_description[:500],
            "agent_id": self.agent_id,
            "complexity": self.complexity.value,
            "phase": self.phase.value,
            "mcp_calls": self.mcp_calls,
            "duration_ms": self.duration_ms,
            "success": self.success,
            "tags": self.tags,
            "knowledge_extracted": self.knowledge_extracted,
            "skill_created": self.skill_created,
            "memory_ids": self.memory_ids,
            "timestamp": self.timestamp,
        }


@dataclass
class ExtractedKnowledge:
    knowledge_type: KnowledgeType
    title: str
    body: str
    source_session: str
    source_agent: str
    confidence: float = 0.5
    tags: List[str] = field(default_factory=list)
    target_layer: str = "semantic"
    reusable: bool = True
    memory_id: str = ""

    def to_dict(self) -> dict:
        return {
            "knowledge_type": self.knowledge_type.value,
            "title": self.title,
            "body": self.body,
            "source_session": self.source_session,
            "source_agent": self.source_agent,
            "confidence": self.confidence,
            "tags": self.tags,
            "target_layer": self.target_layer,
            "reusable": self.reusable,
        }


@dataclass
class ReflectionResult:
    skills_reviewed: int = 0
    skills_optimized: int = 0
    skills_deprecated: int = 0
    knowledge_updated: int = 0
    patterns_discovered: int = 0
    insights: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "skills_reviewed": self.skills_reviewed,
            "skills_optimized": self.skills_optimized,
            "skills_deprecated": self.skills_deprecated,
            "knowledge_updated": self.knowledge_updated,
            "patterns_discovered": self.patterns_discovered,
            "insights": self.insights[:10],
        }


COMPLEXITY_RULES = {
    TaskComplexity.SIMPLE: {
        "min_mcp_calls": 0,
        "max_mcp_calls": 2,
        "min_duration_ms": 0,
        "max_duration_ms": 5000,
        "target_layers": ["sensory"],
        "extract_knowledge": False,
        "create_skill": False,
    },
    TaskComplexity.MODERATE: {
        "min_mcp_calls": 2,
        "max_mcp_calls": 5,
        "min_duration_ms": 5000,
        "max_duration_ms": 30000,
        "target_layers": ["episodic"],
        "extract_knowledge": True,
        "create_skill": False,
    },
    TaskComplexity.COMPLEX: {
        "min_mcp_calls": 5,
        "max_mcp_calls": 15,
        "min_duration_ms": 30000,
        "max_duration_ms": 120000,
        "target_layers": ["episodic", "semantic"],
        "extract_knowledge": True,
        "create_skill": True,
    },
    TaskComplexity.CRITICAL: {
        "min_mcp_calls": 0,
        "max_mcp_calls": 999,
        "min_duration_ms": 0,
        "max_duration_ms": float("inf"),
        "target_layers": ["episodic", "semantic", "meta"],
        "extract_knowledge": True,
        "create_skill": True,
    },
}

CRITICAL_KEYWORDS = [
    "架构", "设计", "重构", "安全", "部署", "生产",
    "critical", "紧急", "崩溃", "数据丢失", "密钥泄露",
    "性能退化", "回滚", "故障",
]

MODERATE_KEYWORDS = [
    "优化", "改进", "修复", "bug", "配置", "迁移",
    "集成", "测试", "审校", "创作",
]




__all__ = ["TaskComplexity", "LearningPhase", "KnowledgeType", "LearningRecord", "ExtractedKnowledge", "ReflectionResult"]
