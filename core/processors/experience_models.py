# -*- coding: utf-8-sig -*-
"""经验自动沉淀 - 数据模型层

定义经验条目、操作轨迹、评估结果等核心数据结构。

架构位置: D4悟道域 - 进化处理器
版本: v1.0.0 (Phase 1 MVP)
"""

from __future__ import annotations

import hashlib
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class ExperienceDomain(str, Enum):
    """经验领域分类"""
    MEMORY = "memory"
    AGENT_DISPATCH = "agent_dispatch"
    CODE_REVIEW = "code_review"
    NOVEL_CREATION = "novel_creation"
    MCP_TOOL = "mcp_tool"
    SYSTEM_OPERATION = "system_operation"
    SECURITY = "security"
    PERFORMANCE = "performance"
    OTHER = "other"


class PatternType(str, Enum):
    """经验模式类型"""
    SUCCESS_PATTERN = "success_pattern"
    FAILURE_LESSON = "failure_lesson"
    BEST_PRACTICE = "best_practice"
    OPTIMIZATION = "optimization"
    TRACE = "trace"


class ExperienceGrade(str, Enum):
    """经验质量分级"""
    S = "S"
    A = "A"
    B = "B"
    C = "C"
    D = "D"


@dataclass
class OperationTrace:
    """操作轨迹 - 单次工具调用/Agent操作的完整记录

    Phase 1 MVP: 基础采集单元
    """
    trace_id: str = field(default_factory=lambda: f"trace_{int(time.time() * 1000)}_{uuid.uuid4().hex[:8]}")
    session_id: str = ""
    agent_id: str = ""
    task_type: str = ""
    tool_name: str = ""
    tool_params: Dict[str, Any] = field(default_factory=dict)
    result_summary: str = ""
    success: bool = False
    duration_ms: float = 0.0
    error_type: str = ""
    error_message: str = ""
    context_tags: List[str] = field(default_factory=list)
    timestamp: float = field(default_factory=time.time)
    parent_trace_id: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "trace_id": self.trace_id,
            "session_id": self.session_id,
            "agent_id": self.agent_id,
            "task_type": self.task_type,
            "tool_name": self.tool_name,
            "tool_params": self.tool_params,
            "result_summary": self.result_summary,
            "success": self.success,
            "duration_ms": self.duration_ms,
            "error_type": self.error_type,
            "error_message": self.error_message,
            "context_tags": self.context_tags,
            "timestamp": self.timestamp,
            "parent_trace_id": self.parent_trace_id,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "OperationTrace":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})

    def content_hash(self) -> str:
        """生成内容哈希，用于去重"""
        content = f"{self.tool_name}|{self.task_type}|{str(sorted(self.tool_params.items())) if self.tool_params else ''}"
        return hashlib.md5(content.encode("utf-8")).hexdigest()


@dataclass
class ExperienceEntry:
    """经验条目 - 沉淀后的可复用经验

    Phase 1: 基础结构定义（主要存储trace，评估/沉淀在Phase 2实现）
    """
    experience_id: str = field(default_factory=lambda: f"exp_{int(time.time() * 1000)}_{uuid.uuid4().hex[:8]}")
    version: str = "1.0"
    domain: ExperienceDomain = ExperienceDomain.OTHER
    pattern_type: PatternType = PatternType.TRACE
    grade: ExperienceGrade = ExperienceGrade.D

    trigger_context: Dict[str, Any] = field(default_factory=dict)
    solution: Dict[str, Any] = field(default_factory=dict)
    outcome: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    source_trace_ids: List[str] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "experience_id": self.experience_id,
            "version": self.version,
            "domain": self.domain.value if isinstance(self.domain, Enum) else self.domain,
            "pattern_type": self.pattern_type.value if isinstance(self.pattern_type, Enum) else self.pattern_type,
            "grade": self.grade.value if isinstance(self.grade, Enum) else self.grade,
            "trigger_context": self.trigger_context,
            "solution": self.solution,
            "outcome": self.outcome,
            "metadata": self.metadata,
            "source_trace_ids": self.source_trace_ids,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_trace(cls, trace: OperationTrace) -> "ExperienceEntry":
        """从操作轨迹生成基础经验条目"""
        domain = cls._infer_domain(trace.tool_name)
        pattern_type = PatternType.SUCCESS_PATTERN if trace.success else PatternType.FAILURE_LESSON

        return cls(
            domain=domain,
            pattern_type=pattern_type,
            trigger_context={
                "task_type": trace.task_type,
                "agent": trace.agent_id,
                "tool": trace.tool_name,
                "tool_params": trace.tool_params,
                "context_tags": trace.context_tags,
            },
            solution={
                "tool_chain": [trace.tool_name],
                "parameters": trace.tool_params,
            },
            outcome={
                "success": trace.success,
                "quality_score": 1.0 if trace.success else 0.0,
                "duration_ms": trace.duration_ms,
                "error_type": trace.error_type,
            },
            metadata={
                "source": "auto_extracted",
                "confidence": 0.3,
                "reuse_count": 0,
                "success_rate": 1.0 if trace.success else 0.0,
                "first_seen": trace.timestamp,
                "last_used": trace.timestamp,
                "tags": trace.context_tags,
            },
            source_trace_ids=[trace.trace_id],
        )

    @staticmethod
    def _infer_domain(tool_name: str) -> ExperienceDomain:
        """从工具名推断领域"""
        tool_lower = tool_name.lower()
        if any(k in tool_lower for k in ["memory", "remember", "recall", "forget", "consolidate"]):
            return ExperienceDomain.MEMORY
        if any(k in tool_lower for k in ["agent", "dispatch", "pipeline"]):
            return ExperienceDomain.AGENT_DISPATCH
        if any(k in tool_lower for k in ["security", "scan", "compliance", "vulnerab"]):
            return ExperienceDomain.SECURITY
        if any(k in tool_lower for k in ["performance", "profile", "bottleneck", "cpu", "memory_profile"]):
            return ExperienceDomain.PERFORMANCE
        if any(k in tool_lower for k in ["command", "execute", "script", "process", "deploy", "service"]):
            return ExperienceDomain.SYSTEM_OPERATION
        if tool_lower:
            return ExperienceDomain.MCP_TOOL
        return ExperienceDomain.OTHER


@dataclass
class CollectionStats:
    """采集统计信息"""
    total_traces: int = 0
    success_count: int = 0
    failure_count: int = 0
    total_experiences: int = 0
    by_domain: Dict[str, int] = field(default_factory=dict)
    by_tool: Dict[str, int] = field(default_factory=dict)
    by_agent: Dict[str, int] = field(default_factory=dict)
    avg_duration_ms: float = 0.0
    last_collection_time: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_traces": self.total_traces,
            "success_count": self.success_count,
            "failure_count": self.failure_count,
            "total_experiences": self.total_experiences,
            "by_domain": self.by_domain,
            "by_tool": self.by_tool,
            "by_agent": self.by_agent,
            "avg_duration_ms": self.avg_duration_ms,
            "last_collection_time": self.last_collection_time,
        }


__all__ = [
    "ExperienceDomain",
    "PatternType",
    "ExperienceGrade",
    "OperationTrace",
    "ExperienceEntry",
    "CollectionStats",
]
