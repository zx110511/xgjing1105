r"""
天机调度子包 (Tianji Scheduling Subpackage) [v10-ready]
=======================================================
将原 core/intelligent_scheduler.py (1115行) 按职责拆分而成的子包。

模块划分:
  - delegation.py  → DelegationDecider   (DeepSeek驱动的委派决策)
  - cron.py        → CronParser          (自然语言定时调度)
  - sandbox.py     → ExecutionSandbox    (隔离执行上下文工厂)
  - executor.py    → BatchExecutor       (并行批量子代理执行)

本 __init__ 集中定义跨模块共享的核心数据结构 (枚举 + dataclass)，
并 re-export 四个子模块的主类，保证:
    from core.scheduling import DelegationDecider, CronParser, ...
始终可用。

兼容性: core/intelligent_scheduler.py 作为协调层从本包导入并 re-export，
原有 `from core.orchestration.intelligent_scheduler import ...` 全部继续可用。
"""

import time
import hashlib
from typing import Any, Optional, Dict, List
from dataclasses import dataclass, field
from enum import Enum


# ═══════════════════════════════════════════════════════════════
# 核心数据结构 (跨模块共享)
# ═══════════════════════════════════════════════════════════════

class DelegationStrategy(str, Enum):
    DIRECT = "direct"
    SINGLE_SUBAGENT = "single_subagent"
    PARALLEL_BATCH = "parallel_batch"
    HIERARCHICAL = "hierarchical"


class TaskPriority(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    BACKGROUND = "background"


class SubAgentStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"
    INTERRUPTED = "interrupted"


@dataclass
class SubAgentTask:
    task_id: str
    goal: str
    context: str
    toolsets: List[str]
    model: str = "default"
    priority: TaskPriority = TaskPriority.MEDIUM
    timeout_s: int = 300
    max_retries: int = 1
    parent_session_id: str = ""
    created_at: float = field(default_factory=time.time)

    def __post_init__(self):
        if not self.task_id:
            self.task_id = hashlib.md5(
                f"{self.goal}:{time.time()}".encode()
            ).hexdigest()[:12]


@dataclass
class SubAgentResult:
    task_id: str
    status: SubAgentStatus
    summary: str
    findings: List[str] = field(default_factory=list)
    files_modified: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    tool_calls_count: int = 0
    duration_s: float = 0.0
    model_used: str = ""
    memory_ids: List[str] = field(default_factory=list)


@dataclass
class CronTask:
    cron_id: str
    natural_language_schedule: str
    parsed_schedule: Dict[str, Any]
    goal: str
    context: str
    toolsets: List[str]
    platform: str = "auto"
    enabled: bool = True
    last_run: Optional[float] = None
    next_run: Optional[float] = None
    run_count: int = 0
    error_count: int = 0
    created_at: float = field(default_factory=time.time)


@dataclass
class DelegationDecision:
    strategy: DelegationStrategy
    sub_tasks: List[SubAgentTask]
    max_concurrency: int
    use_cheaper_model: bool
    reason: str
    confidence: float

    def to_dict(self) -> dict:
        return {
            "strategy": self.strategy.value,
            "sub_tasks_count": len(self.sub_tasks),
            "max_concurrency": self.max_concurrency,
            "use_cheaper_model": self.use_cheaper_model,
            "reason": self.reason,
            "confidence": self.confidence,
        }


# ═══════════════════════════════════════════════════════════════
# 子模块主类 re-export
# (数据结构必须在此行之前全部定义完毕，子模块通过
#  `from core.scheduling import SubAgentTask` 反向引用，依赖此顺序)
# ═══════════════════════════════════════════════════════════════

from core.scheduling.sandbox import ExecutionSandbox, IsolatedContextFactory
from core.scheduling.delegation import DelegationDecider, DeepSeekDelegationDecider
from core.scheduling.executor import BatchExecutor, SubAgentDelegationEngine
from core.scheduling.cron import CronParser, NaturalLanguageCronEngine

# 调度策略接口层 (P2-5 新增) [v10-ready]
from core.shared.protocols import ISchedulerStrategy
from core.scheduling.priority_strategy import PriorityBasedScheduler
from core.scheduling.remote_stub import RemoteSchedulerStrategy


__all__ = [
    # 枚举
    "DelegationStrategy", "TaskPriority", "SubAgentStatus",
    # dataclass
    "SubAgentTask", "SubAgentResult", "CronTask", "DelegationDecision",
    # 子模块主类 (v10 命名)
    "ExecutionSandbox", "DelegationDecider", "BatchExecutor", "CronParser",
    # 兼容别名 (原 Hermes 命名)
    "IsolatedContextFactory", "DeepSeekDelegationDecider",
    "SubAgentDelegationEngine", "NaturalLanguageCronEngine",
    # 调度策略接口层 (P2-5 新增)
    "ISchedulerStrategy", "PriorityBasedScheduler", "RemoteSchedulerStrategy",
]
