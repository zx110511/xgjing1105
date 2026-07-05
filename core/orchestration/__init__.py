r"""
天机Agent编排子包 (core.orchestration) — [v10-ready]
=====================================================
将原 core/agent_orchestrator.py (1215行) 按职责拆分的子包入口。

子模块:
  registry.py   — CapabilityRegistry  (能力矩阵管理/元数据解析/能力查询)
  tracker.py    — ToolTracker          (工具调用追踪/执行Agent标注/统计)
  pipeline.py   — PipelineOrchestrator (管道编排/阶段切换/结果聚合)
  dispatcher.py — AgentDispatcher      (Agent选择/并行调度/分配)

兼容性: 所有原始符号通过 core.agent_orchestrator 继续可用。
位置: 天机/core/orchestration/__init__.py
"""

from __future__ import annotations

from .dispatcher import AgentDispatcher, ParallelDispatcher
from .pipeline import AgentPipeline, PipelineOrchestrator, StageResult
from .registry import (
    AGENT_CAPABILITY_MATRIX,
    DEFAULT_REGISTRY,
    CapabilityRegistry,
    PipelineStage,
)
from .tracker import AgentTask, ToolCallRecord, ToolCallTracker, ToolTracker

__all__ = [
    # registry
    "AGENT_CAPABILITY_MATRIX",
    "PipelineStage",
    "CapabilityRegistry",
    "DEFAULT_REGISTRY",
    # tracker
    "AgentTask",
    "ToolCallRecord",
    "ToolCallTracker",
    "ToolTracker",
    # pipeline
    "StageResult",
    "AgentPipeline",
    "PipelineOrchestrator",
    # dispatcher
    "ParallelDispatcher",
    "AgentDispatcher",
]
