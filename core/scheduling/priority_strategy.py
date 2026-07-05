# -*- coding: utf-8-sig -*-
"""优先级调度策略 PriorityBasedScheduler  [v10-ready]

ISchedulerStrategy 的本地实现，基于任务优先级与 Agent 实时负载完成
"任务 → Agent" 的分配决策，并维护进程内调度队列。

调度逻辑:
  - decide()            : 综合任务优先级权重与各 Agent 剩余容量打分，
                          选择得分最高 (最空闲且优先级匹配) 的 Agent。
  - schedule()          : 生成 task_id，登记任务到调度队列与触发器映射。
  - evaluate_capacity() : 依据 Agent 当前队列长度 / 历史负载估算剩余容量
                          (0.0=满载, 1.0=空闲)。

本地实现 core.shared.protocols.ISchedulerStrategy，携带 PLUGIN_INFO
(category="scheduler")。全部状态操作经 threading.Lock 保护，线程安全。

架构定位: core/scheduling/ 调度策略插件层 (本地实现)
版本: 1.0.0
"""
from __future__ import annotations

import hashlib
import logging
import threading
import time
from typing import Any

from core.shared.plugin_interface import PluginInfo

logger = logging.getLogger("tianji.scheduling.priority")

#: 兜底 Agent (无可用 Agent 时返回)
DEFAULT_AGENT = "tianshu"

#: 单个 Agent 满载时的并发队列长度基准 (用于容量归一化)
DEFAULT_CAPACITY_BASELINE = 10

#: 任务优先级 → 权重 (越高越优先调度)
PRIORITY_WEIGHTS: dict[str, float] = {
    "critical": 5.0,
    "high": 4.0,
    "medium": 3.0,
    "low": 2.0,
    "background": 1.0,
}


class PriorityBasedScheduler:
    """优先级调度策略  [v10-ready]

    本地实现: 基于任务优先级 + Agent 负载的单进程调度器。
    实现协议: core.shared.protocols.ISchedulerStrategy
              (decide / schedule / evaluate_capacity)。
    线程安全: 所有共享状态读写经 threading.Lock 保护。
    """

    STRATEGY_NAME = "priority_based"

    def __init__(self, capacity_baseline: int = DEFAULT_CAPACITY_BASELINE) -> None:
        """初始化优先级调度策略。  [v10-ready]

        Args:
            capacity_baseline: Agent 满载基准队列长度，用于容量归一化。
        """
        self._capacity_baseline = max(1, capacity_baseline)
        self._lock = threading.Lock()
        # Agent → 当前在途任务数 (负载计数)
        self._agent_load: dict[str, int] = {}
        # task_id → 任务记录 (含 trigger/agent/优先级/状态)
        self._task_queue: dict[str, dict[str, Any]] = {}

    # ---- ISchedulerStrategy 协议实现 ----

    def decide(self, task: dict[str, Any], agents: list[str]) -> str:
        """决定任务分配给哪个 Agent。  [v10-ready]

        基于任务优先级权重与各 Agent 剩余容量综合打分，返回最优 Agent。
        得分 = 剩余容量 * 优先级权重；容量相同则优先级越高越优先。

        Args:
            task: 任务描述字典，支持字段:
                  - agent_id: 显式指定 Agent (若在候选内则直接采用)
                  - priority: 任务优先级 (critical/high/medium/low/background)
            agents: 候选 Agent 标识列表。

        Returns:
            选中的 Agent 标识；候选为空时返回 DEFAULT_AGENT。
        """
        if not agents:
            return DEFAULT_AGENT

        # 显式指定且合法 → 直接采用
        explicit = task.get("agent_id")
        if explicit and explicit in agents:
            return explicit

        weight = self._priority_weight(task.get("priority"))

        with self._lock:
            best_agent = agents[0]
            best_score = -1.0
            for agent in agents:
                capacity = self._capacity_locked(agent)
                score = capacity * weight
                if score > best_score:
                    best_score = score
                    best_agent = agent
        return best_agent

    def schedule(self, task: dict[str, Any], trigger: str) -> str:
        """调度任务，注册到调度队列并返回任务 ID。  [v10-ready]

        生成稳定的 task_id (优先取任务自带 task_id，否则按内容哈希)，
        登记任务记录与触发器，并对目标 Agent 负载计数 +1。

        Args:
            task: 任务描述字典 (可含 task_id/agent_id/priority/goal 等)。
            trigger: 触发方式标识 (如 immediate/cron/event)。

        Returns:
            登记后的 task_id。
        """
        task_id = task.get("task_id") or self._gen_task_id(task)
        agent = task.get("agent_id") or DEFAULT_AGENT
        priority = task.get("priority", "medium")

        with self._lock:
            self._task_queue[task_id] = {
                "task_id": task_id,
                "agent": agent,
                "priority": priority,
                "trigger": trigger,
                "status": "queued",
                "created_at": time.time(),
            }
            self._agent_load[agent] = self._agent_load.get(agent, 0) + 1

        logger.debug(
            "scheduled task %s -> agent=%s trigger=%s priority=%s",
            task_id, agent, trigger, priority,
        )
        return task_id

    def evaluate_capacity(self, agent: str) -> float:
        """评估 Agent 当前负载容量 (0.0~1.0)。  [v10-ready]

        基于 Agent 当前在途任务数与满载基准估算剩余容量:
        capacity = 1.0 - min(load / baseline, 1.0)。
        返回 0.0 表示满载，1.0 表示完全空闲。

        Args:
            agent: Agent 标识。

        Returns:
            剩余容量比例 (0.0 ~ 1.0)。
        """
        with self._lock:
            return self._capacity_locked(agent)

    # ---- 辅助查询 ----

    def get_scheduling_strategy(self) -> str:
        """获取当前调度策略名称。  [v10-ready]"""
        return self.STRATEGY_NAME

    def get_task(self, task_id: str) -> dict[str, Any] | None:
        """查询某任务的调度记录。  [v10-ready]"""
        with self._lock:
            record = self._task_queue.get(task_id)
            return dict(record) if record is not None else None

    def complete_task(self, task_id: str) -> bool:
        """标记任务完成并释放对应 Agent 负载。  [v10-ready]

        Args:
            task_id: 任务标识。

        Returns:
            是否成功标记 (任务不存在时返回 False)。
        """
        with self._lock:
            record = self._task_queue.get(task_id)
            if record is None:
                return False
            record["status"] = "completed"
            agent = record.get("agent", DEFAULT_AGENT)
            if self._agent_load.get(agent, 0) > 0:
                self._agent_load[agent] -= 1
            return True

    def queue_size(self) -> int:
        """获取当前调度队列规模。  [v10-ready]"""
        with self._lock:
            return len(self._task_queue)

    # ---- 内部实现 ----

    def _capacity_locked(self, agent: str) -> float:
        """在持锁状态下计算 Agent 剩余容量。  [v10-ready]"""
        load = self._agent_load.get(agent, 0)
        used = min(load / self._capacity_baseline, 1.0)
        return round(1.0 - used, 4)

    @staticmethod
    def _priority_weight(priority: Any) -> float:
        """将优先级映射为调度权重。  [v10-ready]"""
        key = str(priority).lower() if priority is not None else "medium"
        return PRIORITY_WEIGHTS.get(key, PRIORITY_WEIGHTS["medium"])

    @staticmethod
    def _gen_task_id(task: dict[str, Any]) -> str:
        """按任务内容生成稳定的 task_id。  [v10-ready]"""
        seed = f"{task.get('goal', '')}:{task.get('agent_id', '')}:{time.time()}"
        return hashlib.md5(seed.encode("utf-8")).hexdigest()[:12]


PLUGIN_INFO = PluginInfo(
    name="priority_scheduler",
    version="1.0.0",
    description="优先级调度策略",
    category="scheduler",
    protocols=["ISchedulerStrategy"],
)
