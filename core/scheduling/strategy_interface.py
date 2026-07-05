# -*- coding: utf-8-sig -*-
"""调度策略接口层 (Scheduler Strategy Interface)  [v10-ready]

为 core/scheduling/ 子包提供统一的策略接口入口，将 ISchedulerStrategy
协议、本地实现 PriorityBasedScheduler 与远程实现 RemoteSchedulerStrategy
集中导出，供调度工厂/上层编排按运行模式装配。

策略接口说明:
    ISchedulerStrategy 定义三个核心能力 (均见 core.shared.protocols):
      - decide(task, agents)     → 基于优先级+负载选择最优 Agent
      - schedule(task, trigger)  → 注册任务到调度队列, 返回 task_id
      - evaluate_capacity(agent) → 评估 Agent 当前负载容量 (0.0~1.0)

    本地实现: PriorityBasedScheduler (优先级调度, 单进程默认, 线程安全)
    远程实现: RemoteSchedulerStrategy (灵境分布式任务调度, gRPC stub 预留)

    切换方式: 统一调度接口，单进程模式使用 PriorityBasedScheduler；
    分布式模式由调度工厂返回 RemoteSchedulerStrategy，将调度决策下推
    至灵境中心调度服务。上层仅依赖 ISchedulerStrategy，无需感知切换。

架构定位: core/scheduling/ 调度策略插件层 (接口入口)
版本: 1.0.0
"""
from __future__ import annotations

from core.shared.protocols import ISchedulerStrategy
from core.scheduling.priority_strategy import (
    PriorityBasedScheduler,
    PLUGIN_INFO as PRIORITY_PLUGIN_INFO,
)
from core.scheduling.remote_stub import (
    RemoteSchedulerStrategy,
    PLUGIN_INFO as REMOTE_PLUGIN_INFO,
)

__all__ = [
    # 协议
    "ISchedulerStrategy",
    # 本地实现
    "PriorityBasedScheduler",
    # 远程实现 (stub)
    "RemoteSchedulerStrategy",
    # 插件元信息
    "PRIORITY_PLUGIN_INFO",
    "REMOTE_PLUGIN_INFO",
]
