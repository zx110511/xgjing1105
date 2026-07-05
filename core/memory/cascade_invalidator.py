# core/memory/cascade_invalidator.py [v10-ready]
"""级联失效器 — 记忆失效时自动传播到依赖项

核心机制：
1. 接收失效请求（record_id + reason）
2. 通过 IGraph 协议查找所有依赖此记录的下游记录
3. BFS 遍历依赖图，对每个下游记录执行失效
4. 发布失效事件到 EventBus
5. 返回所有受影响的 record_id 列表

设计约束：
- 依赖 IGraph 协议（不导入具体 graph 实现）
- 依赖 TemporalRecord 模型（设置 valid_to 和 invalidation_reason）
- 所有操作可选 DeepSeek 参与决策
- 失效深度可配置（防止无限级联）

设计原则映射：
- 主动: 失效触发后主动级联传播（非被动等待查询时发现）
- DeepSeek 驱动: _should_cascade 支持可选 LLM 智能失效决策
- 自动化: 与 EventBus 集成，失效操作自动发布 memory.invalidated 事件
- 自进化: InvalidationReport 提供失效统计供 evolution_loop 学习优化

[v10-ready] 本模块为 v9.1 时序记忆能力的级联失效核心组件。
"""

from __future__ import annotations

import asyncio
import inspect
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Protocol, runtime_checkable

from core.memory.temporal_record import TemporalRecord, invalidate_record

__all__ = [
    "IInvalidator",
    "IGraph",
    "InvalidationReport",
    "CascadeInvalidator",
]


@runtime_checkable
class IInvalidator(Protocol):
    """失效器协议

    [v10-ready] 定义失效器的最小行为契约，供依赖注入与替换实现。
    """

    async def invalidate(self, record_id: str, reason: str) -> list[str]:
        """失效一条记录并级联传播，返回所有受影响的 record_id。"""
        ...

    def find_dependents(self, record_id: str) -> list[str]:
        """查找直接依赖此记录的下游记录 ID。"""
        ...

    async def bulk_invalidate(
        self, record_ids: list[str], reason: str
    ) -> dict[str, list[str]]:
        """批量失效，返回 {source_id: [affected_ids]}。"""
        ...


@runtime_checkable
class IGraph(Protocol):
    """图查询协议 — 用于查找记忆依赖关系

    [v10-ready] 仅定义查询契约，不绑定任何具体图实现。
    """

    def get_dependents(self, node_id: str) -> list[str]:
        """获取依赖 node_id 的所有下游节点。"""
        ...

    def get_dependencies(self, node_id: str) -> list[str]:
        """获取 node_id 依赖的所有上游节点。"""
        ...

    def has_edge(self, from_id: str, to_id: str) -> bool:
        """检查是否存在依赖边。"""
        ...


@dataclass
class InvalidationReport:
    """失效操作报告

    [v10-ready] 汇总单次级联失效的范围、深度、截断与 LLM 决策信息，
    供日志审计与 evolution_loop 学习失效策略使用。
    """

    source_id: str
    reason: str
    affected_ids: list[str]
    depth_reached: int
    truncated: bool  # 是否因 max_depth / max_affected 截断
    timestamp: datetime
    llm_decisions: dict[str, bool] = field(default_factory=dict)


@dataclass
class _CascadeState:
    """BFS 级联遍历的可变状态容器（内部使用）。"""

    affected: list[str]
    visited: set[str]
    queue: deque[tuple[str, int]]
    llm_decisions: dict[str, bool]
    depth_reached: int = 0
    truncated: bool = False


class CascadeInvalidator:
    """级联失效器实现

    [v10-ready] 核心算法: BFS 遍历依赖图
    1. 将起始 record_id 加入队列并失效
    2. 对队列中每个 id，查找其 dependents
    3. 对每个 dependent 执行失效（设置 valid_to=now, invalidation_reason）
    4. 将新失效的 dependent 加入队列（如果未访问过）
    5. 重复直到队列为空或达到 max_depth / max_affected
    """

    def __init__(
        self,
        graph: IGraph | None = None,
        event_bus: Any = None,
        llm_driver: Any = None,
        max_depth: int = 10,
        max_affected: int = 100,
    ) -> None:
        """初始化级联失效器。

        Args:
            graph: 依赖图（可选，None 时仅失效单条，不级联）。
            event_bus: IEventBus 实例（可选，用于发布失效事件）。
            llm_driver: DeepSeek 驾驶者（可选，用于智能级联决策）。
            max_depth: 最大级联深度，防止无限级联。
            max_affected: 最大受影响记录数（安全阀）。
        """
        self.graph = graph
        self.event_bus = event_bus
        self.llm_driver = llm_driver
        self.max_depth = max_depth
        self.max_affected = max_affected
        self._last_report: InvalidationReport | None = None

    async def invalidate(self, record_id: str, reason: str) -> list[str]:
        """主入口：失效一条记录并级联传播。

        Args:
            record_id: 起始失效记录 ID。
            reason: 失效原因。

        Returns:
            list[str]: 所有受影响的 record_id（含起始记录）。
        """
        report = await self._cascade_from(record_id, reason)
        self._last_report = report
        return report.affected_ids

    def find_dependents(self, record_id: str) -> list[str]:
        """查找直接依赖此记录的下游记录 ID。

        Args:
            record_id: 目标记录 ID。

        Returns:
            list[str]: 直接下游记录 ID 列表；graph 不可用时返回空列表。
        """
        if self.graph is None:
            return []
        try:
            return list(self.graph.get_dependents(record_id))
        except Exception:
            return []

    async def bulk_invalidate(
        self, record_ids: list[str], reason: str
    ) -> dict[str, list[str]]:
        """批量失效多条记录，各自独立级联传播。

        Args:
            record_ids: 待失效的起始记录 ID 列表。
            reason: 统一失效原因。

        Returns:
            dict[str, list[str]]: {source_id: [affected_ids]} 映射。
        """
        result: dict[str, list[str]] = {}
        for source_id in record_ids:
            report = await self._cascade_from(source_id, reason)
            result[source_id] = report.affected_ids
            self._last_report = report
        return result

    @property
    def last_report(self) -> InvalidationReport | None:
        """返回最近一次失效操作的报告（供审计与自进化学习）。"""
        return self._last_report

    async def _cascade_from(self, record_id: str, reason: str) -> InvalidationReport:
        """从单个起始记录执行 BFS 级联失效。

        Args:
            record_id: 起始记录 ID。
            reason: 失效原因。

        Returns:
            InvalidationReport: 本次级联的完整报告。
        """
        state = _CascadeState(
            affected=[record_id],
            visited={record_id},
            queue=deque([(record_id, 0)]),
            llm_decisions={},
        )
        self._apply_invalidation(record_id, reason)

        while state.queue:
            current, depth = state.queue.popleft()
            if depth >= self.max_depth:
                state.truncated = True
                continue
            await self._expand_node(current, depth, reason, state)
            if state.truncated and len(state.affected) >= self.max_affected:
                break

        report = InvalidationReport(
            source_id=record_id,
            reason=reason,
            affected_ids=state.affected,
            depth_reached=state.depth_reached,
            truncated=state.truncated,
            timestamp=datetime.now(),
            llm_decisions=state.llm_decisions,
        )
        self._publish_event(
            "memory.invalidated",
            {
                "source_id": record_id,
                "reason": reason,
                "affected_ids": state.affected,
                "depth_reached": state.depth_reached,
                "truncated": state.truncated,
            },
        )
        return report

    async def _expand_node(
        self, current: str, depth: int, reason: str, state: _CascadeState
    ) -> None:
        """展开单个节点的下游依赖并执行失效（BFS 单步）。

        Args:
            current: 当前节点 ID。
            depth: 当前节点深度。
            reason: 失效原因。
            state: 共享的级联遍历状态。
        """
        for dep in self.find_dependents(current):
            if dep in state.visited:
                continue
            if len(state.affected) >= self.max_affected:
                state.truncated = True
                break
            state.visited.add(dep)
            should = await self._should_cascade(current, dep, reason)
            state.llm_decisions[dep] = should
            if not should:
                continue
            self._apply_invalidation(dep, reason)
            state.affected.append(dep)
            state.depth_reached = max(state.depth_reached, depth + 1)
            state.queue.append((dep, depth + 1))

    async def _should_cascade(self, parent_id: str, child_id: str, reason: str) -> bool:
        """智能决策：是否应级联失效此子节点（DeepSeek 可参与）。

        Args:
            parent_id: 上游（已失效）节点 ID。
            child_id: 待评估的下游节点 ID。
            reason: 失效原因。

        Returns:
            bool: 是否级联失效；默认 True，LLM 异常时静默回退 True。
        """
        if self.llm_driver is None:
            return True
        decider = getattr(self.llm_driver, "should_cascade", None)
        if decider is None:
            return True
        try:
            outcome = decider(parent_id, child_id, reason)
            if inspect.isawaitable(outcome):
                outcome = await outcome
            return bool(outcome)
        except Exception:
            return True

    def _apply_invalidation(self, record_id: str, reason: str) -> None:
        """对指定记录应用失效（设置 valid_to 与 invalidation_reason）。

        通过 graph 可选暴露的 get_record / put_record 接口定位并回写记录；
        无记录存储时仅记录失效意图，静默降级。

        Args:
            record_id: 待失效记录 ID。
            reason: 失效原因。
        """
        record = self._resolve_record(record_id)
        if record is None:
            return
        try:
            updated = invalidate_record(record, reason)
            writer = getattr(self.graph, "put_record", None)
            if writer is not None:
                writer(updated)
        except Exception:
            return

    def _resolve_record(self, record_id: str) -> TemporalRecord | None:
        """尝试从 graph 暴露的 get_record 接口解析时序记录（可选）。

        Args:
            record_id: 记录 ID。

        Returns:
            TemporalRecord | None: 解析到的记录；不可用时返回 None。
        """
        if self.graph is None:
            return None
        getter = getattr(self.graph, "get_record", None)
        if getter is None:
            return None
        try:
            record = getter(record_id)
        except Exception:
            return None
        return record if isinstance(record, TemporalRecord) else None

    def _publish_event(self, event_type: str, payload: dict[str, Any]) -> None:
        """发布事件到 EventBus（静默降级）。

        兼容同步与异步 publish 接口；EventBus 不可用或异常时静默忽略。

        Args:
            event_type: 事件类型，如 "memory.invalidated"。
            payload: 事件载荷。
        """
        if self.event_bus is None:
            return
        publisher = getattr(self.event_bus, "publish", None)
        if publisher is None:
            return
        try:
            result = publisher(event_type, payload)
            if inspect.isawaitable(result):
                self._schedule_coroutine(result)
        except Exception:
            return

    @staticmethod
    def _schedule_coroutine(coro: Any) -> None:
        """调度异步发布结果，兼容有/无运行中事件循环两种场景。

        Args:
            coro: 待调度的可等待对象。
        """
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(coro)
        except RuntimeError:
            try:
                asyncio.run(coro)
            except Exception:
                return
