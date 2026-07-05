r"""
天机DAG调度引擎 (Tianji DAG Scheduler) v1.0
===========================================
借鉴 Apache Airflow DAG + LangGraph StateGraph 的拓扑调度核心，
为天机v9.1提供动态DAG构建、拓扑排序并行执行、条件分支能力。

核心能力:
  1. DAGNode/DAGEdge — 有向无环图数据模型
  2. topological_execute — 拓扑排序 + 并行无依赖节点
  3. conditional_branch — 运行时动态决定下一节点
  4. 实时状态追踪 — 每节点 pending→running→completed/failed
  5. WebSocket事件推送 — 实时通知前端画布更新
  6. 与AgentScheduler无缝集成 — 复用ToolCallTracker+TVP

参考架构:
  - Apache Airflow: DAG定义 + 调度器 + 拓扑执行
  - LangGraph: StateGraph + 条件边 + 检查点
  - networkx: 图算法 (拓扑排序, 连通分量)

位置: 天机/core/dag_scheduler.py
"""

from __future__ import annotations

import logging
import threading
import time
import uuid
from collections import defaultdict, deque
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger("tianji.dag_scheduler")


# ═══════════════════════════════════════════════════════════════
# 核心数据结构
# ═══════════════════════════════════════════════════════════════


class NodeStatus(str, Enum):
    PENDING = "pending"  # 等待依赖完成
    READY = "ready"  # 依赖已满足，等待执行
    RUNNING = "running"  # 正在执行
    COMPLETED = "completed"  # 执行成功
    FAILED = "failed"  # 执行失败
    SKIPPED = "skipped"  # 条件分支跳过
    CANCELLED = "cancelled"  # 被取消


class EdgeType(str, Enum):
    DEPENDENCY = "dependency"  # 标准依赖: A完成→B开始
    CONDITIONAL = "conditional"  # 条件分支: A完成后根据结果选择B或C
    TRIGGER = "trigger"  # 触发边: A事件→触发B
    DATA_FLOW = "data_flow"  # 数据流: A输出→B输入


@dataclass
class DAGNode:
    """DAG节点 — 代表一个可被Agent执行的任务单元"""

    node_id: str
    agent_id: str  # 分配的Agent ID
    agent_name: str = ""  # Agent名称
    agent_emoji: str = "🤖"  # Agent图标
    goal: str = ""  # 任务目标
    context: str = ""  # 上下文
    tools_allowed: list[str] = field(default_factory=list)
    priority: str = "medium"  # critical/high/medium/low
    timeout_s: int = 300
    max_retries: int = 1
    status: NodeStatus = NodeStatus.PENDING
    result: dict[str, Any] | None = None
    error: str | None = None
    started_at: float | None = None
    completed_at: float | None = None
    duration_s: float = 0.0
    retry_count: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "node_id": self.node_id,
            "agent_id": self.agent_id,
            "agent_name": self.agent_name,
            "agent_emoji": self.agent_emoji,
            "goal": self.goal,
            "status": self.status.value,
            "priority": self.priority,
            "duration_s": self.duration_s,
            "error": self.error,
        }

    def to_tvp(self) -> str:
        icon = (
            "✅"
            if self.status == NodeStatus.COMPLETED
            else (
                "❌"
                if self.status == NodeStatus.FAILED
                else ("⏳" if self.status == NodeStatus.RUNNING else "⬜")
            )
        )
        return (
            f"[TVP-DAG] {icon} {self.agent_emoji}@{self.agent_name} "
            f"[{self.status.value}] {self.goal[:50]}"
        )


@dataclass
class DAGEdge:
    """DAG边 — 节点间的依赖/条件关系"""

    edge_id: str
    source_id: str  # 源节点ID
    target_id: str  # 目标节点ID
    edge_type: EdgeType = EdgeType.DEPENDENCY
    condition: Callable[[dict[str, Any]], bool] | None = None  # 条件函数
    condition_desc: str = ""  # 条件描述
    data_mapping: dict[str, str] = field(default_factory=dict)  # 数据映射

    def to_dict(self) -> dict:
        return {
            "edge_id": self.edge_id,
            "source": self.source_id,
            "target": self.target_id,
            "type": self.edge_type.value,
            "condition": self.condition_desc,
        }


@dataclass
class DAGPipeline:
    """DAG流水线 — 完整的任务图"""

    pipeline_id: str
    pipeline_name: str = ""
    nodes: dict[str, DAGNode] = field(default_factory=dict)
    edges: list[DAGEdge] = field(default_factory=list)
    status: str = "created"  # created/running/completed/failed/cancelled
    created_at: float = field(default_factory=time.time)
    started_at: float | None = None
    completed_at: float | None = None
    stats: dict[str, int] = field(
        default_factory=lambda: {
            "total": 0,
            "pending": 0,
            "ready": 0,
            "running": 0,
            "completed": 0,
            "failed": 0,
            "skipped": 0,
        }
    )
    event_bus: Any = None
    _executor: ThreadPoolExecutor | None = None
    _lock: threading.Lock = field(default_factory=threading.Lock)
    _status_callbacks: list[Callable] = field(default_factory=list)
    _cancelled: bool = False

    def add_node(self, node: DAGNode):
        """添加节点到DAG"""
        self.nodes[node.node_id] = node
        self.stats["total"] = len(self.nodes)
        self.stats["pending"] = len(self.nodes)

    def add_edge(
        self,
        source_id: str,
        target_id: str,
        edge_type: EdgeType = EdgeType.DEPENDENCY,
        condition: Callable = None,
        condition_desc: str = "",
        data_mapping: dict = None,
    ):
        """添加边到DAG"""
        if source_id not in self.nodes or target_id not in self.nodes:
            raise ValueError(f"边端点不存在: {source_id}→{target_id}")
        edge = DAGEdge(
            edge_id=f"edge-{uuid.uuid4().hex[:8]}",
            source_id=source_id,
            target_id=target_id,
            edge_type=edge_type,
            condition=condition,
            condition_desc=condition_desc,
            data_mapping=data_mapping or {},
        )
        self.edges.append(edge)

    def get_dependencies(self, node_id: str) -> list[str]:
        """获取节点的所有前驱依赖"""
        return [
            e.source_id
            for e in self.edges
            if e.target_id == node_id and e.edge_type == EdgeType.DEPENDENCY
        ]

    def get_dependents(self, node_id: str) -> list[str]:
        """获取节点的所有后继"""
        return [e.target_id for e in self.edges if e.source_id == node_id]

    def get_ready_nodes(self) -> list[DAGNode]:
        """获取所有依赖已满足的节点 (READY状态)"""
        ready = []
        for node_id, node in self.nodes.items():
            if node.status != NodeStatus.PENDING:
                continue
            deps = self.get_dependencies(node_id)
            all_deps_met = all(
                self.nodes[d].status == NodeStatus.COMPLETED for d in deps
            )
            if all_deps_met:
                node.status = NodeStatus.READY
                ready.append(node)
        return ready

    def topological_levels(self) -> list[list[str]]:
        """拓扑分层 — 返回每层可并行执行的节点列表"""
        # 计算入度
        in_degree: dict[str, int] = defaultdict(int)
        out_edges: dict[str, list[str]] = defaultdict(list)
        for edge in self.edges:
            if edge.edge_type == EdgeType.DEPENDENCY:
                in_degree[edge.target_id] += 1
                out_edges[edge.source_id].append(edge.target_id)

        # 初始化: 入度为0的节点作为第一层
        for node_id in self.nodes:
            if node_id not in in_degree:
                in_degree[node_id] = 0

        queue = deque([nid for nid, deg in in_degree.items() if deg == 0])
        levels: list[list[str]] = []
        visited: set[str] = set()

        while queue:
            level_size = len(queue)
            current_level: list[str] = []
            for _ in range(level_size):
                node_id = queue.popleft()
                if node_id in visited:
                    continue
                visited.add(node_id)
                current_level.append(node_id)
                for target in out_edges.get(node_id, []):
                    in_degree[target] -= 1
                    if in_degree[target] == 0:
                        queue.append(target)
            if current_level:
                levels.append(current_level)

        # 处理剩余节点 (可能有环)
        remaining = [nid for nid in self.nodes if nid not in visited]
        if remaining:
            logger.warning(
                f"[DAG] {len(remaining)} nodes not reachable (possible cycle): {remaining}"
            )
            levels.append(remaining)

        return levels

    def has_cycle(self) -> bool:
        """检测DAG是否有环"""
        try:
            import networkx as nx

            g = nx.DiGraph()
            for nid in self.nodes:
                g.add_node(nid)
            for edge in self.edges:
                if edge.edge_type == EdgeType.DEPENDENCY:
                    g.add_edge(edge.source_id, edge.target_id)
            return not nx.is_directed_acyclic_graph(g)
        except Exception:
            # 降级: 使用拓扑排序检测
            visited = set()
            rec_stack = set()

            def _dfs(node_id: str) -> bool:
                visited.add(node_id)
                rec_stack.add(node_id)
                for target in self.get_dependents(node_id):
                    if target not in visited:
                        if _dfs(target):
                            return True
                    elif target in rec_stack:
                        return True
                rec_stack.discard(node_id)
                return False

            for nid in self.nodes:
                if nid not in visited:
                    if _dfs(nid):
                        return True
            return False

    def on_status_change(self, callback: Callable):
        """注册状态变更回调"""
        self._status_callbacks.append(callback)

    def _notify_status_change(self, node: DAGNode):
        """通知所有回调"""
        for cb in self._status_callbacks:
            try:
                cb(node)
            except Exception:
                pass

    def _emit_event(self, event_type: str, payload: dict):
        """通过EventBus发送事件"""
        if self.event_bus:
            try:
                from core.shared.deepseek_driver import EventType, TianjiEvent

                event_type_map = {
                    "node_started": EventType.MCP_TOOL_CALL,
                    "node_completed": EventType.MCP_TOOL_CALL,
                    "node_failed": EventType.MCP_TOOL_CALL,
                    "pipeline_completed": EventType.AGENT_SWITCH,
                }
                et = event_type_map.get(event_type, EventType.MCP_TOOL_CALL)
                self.event_bus.publish(
                    TianjiEvent(
                        event_type=et,
                        source="dag_scheduler",
                        payload={**payload, "pipeline_id": self.pipeline_id},
                    )
                )
            except Exception:
                pass

    def to_dict(self) -> dict:
        """导出DAG为字典 — 供前端React Flow渲染"""
        return {
            "pipeline_id": self.pipeline_id,
            "pipeline_name": self.pipeline_name,
            "status": self.status,
            "stats": self.stats,
            "nodes": [
                {
                    "id": n.node_id,
                    "type": "agentNode",
                    "data": {
                        "label": n.goal[:40],
                        "agent_id": n.agent_id,
                        "agent_name": n.agent_name,
                        "agent_emoji": n.agent_emoji,
                        "status": n.status.value,
                        "duration_s": n.duration_s,
                        "error": n.error,
                    },
                    "position": n.metadata.get("position", {"x": 0, "y": 0}),
                }
                for n in self.nodes.values()
            ],
            "edges": [
                {
                    "id": e.edge_id,
                    "source": e.source_id,
                    "target": e.target_id,
                    "type": "smoothstep",
                    "animated": e.edge_type == EdgeType.DATA_FLOW,
                    "data": {"type": e.edge_type.value, "condition": e.condition_desc},
                }
                for e in self.edges
            ],
            "levels": self.topological_levels(),
        }

    def cancel(self):
        """取消流水线"""
        self._cancelled = True
        self.status = "cancelled"
        if self._executor:
            self._executor.shutdown(wait=False, cancel_futures=True)

    def is_cancelled(self) -> bool:
        return self._cancelled


# ═══════════════════════════════════════════════════════════════
# DAG调度执行引擎
# ═══════════════════════════════════════════════════════════════


class DAGScheduler:
    """
    DAG调度器 — 将DAGPipeline按拓扑顺序调度执行

    执行流程:
      1. 拓扑分层 → 识别每层可并行的节点
      2. 逐层执行 → 每层内并行执行所有节点
      3. 条件评估 → 条件边根据源节点结果决定是否激活
      4. 状态追踪 → 实时更新节点状态+推送事件
      5. 错误处理 → 失败节点根据策略决定继续/停止/重试
    """

    VERSION = "1.0.0-DAG"

    FatalErrorStrategy = Enum(
        "FatalErrorStrategy",
        [
            "STOP_ALL",  # 任何失败立即停止全部
            "CONTINUE",  # 失败不影响其他分支
            "STOP_DEPENDENTS",  # 只停止依赖失败节点的后继
        ],
    )

    def __init__(
        self,
        max_workers: int = 8,
        error_strategy=FatalErrorStrategy.CONTINUE,
        event_bus=None,
        tracker=None,
    ):
        self.max_workers = max_workers
        self.error_strategy = error_strategy
        self.event_bus = event_bus
        self.tracker = tracker  # ToolCallTracker引用
        self._active_pipelines: dict[str, DAGPipeline] = {}
        self._lock = threading.Lock()
        self._stats: dict[str, int] = {
            "pipelines_executed": 0,
            "nodes_executed": 0,
            "nodes_failed": 0,
            "total_duration_s": 0,
        }

    def execute(
        self,
        pipeline: DAGPipeline,
        node_executor: Callable[[DAGNode], dict[str, Any]] = None,
        parallel: bool = True,
    ) -> dict[str, Any]:
        """
        执行DAG流水线

        Args:
            pipeline: DAG流水线
            node_executor: 节点执行函数 (node → result dict)
            parallel: 是否并行执行同级节点

        Returns:
            {"success": bool, "nodes_completed": int, "nodes_failed": int, ...}
        """
        pipeline_id = pipeline.pipeline_id
        with self._lock:
            self._active_pipelines[pipeline_id] = pipeline

        pipeline.status = "running"
        pipeline.started_at = time.time()

        logger.info(
            f"[DAG] 🚀 流水线启动: {pipeline_id} "
            f"(nodes={len(pipeline.nodes)}, edges={len(pipeline.edges)})"
        )

        # 检测环
        if pipeline.has_cycle():
            logger.error(f"[DAG] ❌ 流水线{pipeline_id}存在环，无法执行")
            pipeline.status = "failed"
            return {"success": False, "error": "DAG contains cycle"}

        start_time = time.time()

        try:
            if parallel:
                result = self._execute_parallel(pipeline, node_executor)
            else:
                result = self._execute_serial(pipeline, node_executor)
        finally:
            pipeline.completed_at = time.time()
            pipeline.status = "completed" if result.get("success", False) else "failed"
            self._stats["pipelines_executed"] += 1
            self._stats["total_duration_s"] += int(time.time() - start_time)

        return result

    def _execute_parallel(
        self, pipeline: DAGPipeline, node_executor: Callable = None
    ) -> dict[str, Any]:
        """并行拓扑执行 — 每层内并行，层间串行"""
        levels = pipeline.topological_levels()
        logger.info(
            f"[DAG] 拓扑分层: {len(levels)}层 → "
            f"{' → '.join(f'L{i}({len(lv)})' for i, lv in enumerate(levels))}"
        )

        nodes_completed = 0
        nodes_failed = 0

        for level_idx, level_nodes in enumerate(levels):
            if pipeline.is_cancelled():
                return {"success": False, "cancelled": True}

            # 评估条件边: 检查哪些目标节点应该被激活
            active_nodes = self._evaluate_conditions(pipeline, level_nodes)

            if not active_nodes:
                continue

            logger.info(f"[DAG] Level {level_idx}: 并行执行{len(active_nodes)}个节点")

            # 并行执行当前层
            with ThreadPoolExecutor(
                max_workers=min(self.max_workers, len(active_nodes))
            ) as executor:
                futures = {}
                for node in active_nodes:
                    node.status = NodeStatus.RUNNING
                    node.started_at = time.time()
                    pipeline.stats["running"] += 1
                    pipeline.stats["ready"] -= 1
                    pipeline._notify_status_change(node)
                    pipeline._emit_event("node_started", node.to_dict())
                    futures[
                        executor.submit(
                            self._execute_node, pipeline, node, node_executor
                        )
                    ] = node.node_id

                for future in as_completed(futures):
                    node_id = futures[future]
                    try:
                        success, result_data, error = future.result(timeout=600)
                        node = pipeline.nodes[node_id]
                        node.completed_at = time.time()
                        node.duration_s = node.completed_at - (
                            node.started_at or node.completed_at
                        )
                        pipeline.stats["running"] -= 1

                        if success:
                            node.status = NodeStatus.COMPLETED
                            node.result = result_data
                            pipeline.stats["completed"] += 1
                            nodes_completed += 1
                            self._stats["nodes_executed"] += 1
                        else:
                            node.status = NodeStatus.FAILED
                            node.error = error
                            pipeline.stats["failed"] += 1
                            nodes_failed += 1
                            self._stats["nodes_failed"] += 1

                        pipeline._notify_status_change(node)
                        pipeline._emit_event(
                            "node_completed" if success else "node_failed",
                            node.to_dict(),
                        )

                        # 错误策略
                        if (
                            not success
                            and self.error_strategy == self.FatalErrorStrategy.STOP_ALL
                        ):
                            pipeline.cancel()
                            return {
                                "success": False,
                                "nodes_completed": nodes_completed,
                                "nodes_failed": nodes_failed,
                            }

                    except Exception as e:
                        logger.error(f"[DAG] Node {node_id} execution error: {e}")
                        node = pipeline.nodes[node_id]
                        node.status = NodeStatus.FAILED
                        node.error = str(e)
                        pipeline.stats["failed"] += 1
                        nodes_failed += 1

        pipeline._emit_event("pipeline_completed", pipeline.to_dict())
        return {
            "success": nodes_failed == 0,
            "nodes_completed": nodes_completed,
            "nodes_failed": nodes_failed,
            "pipeline_id": pipeline.pipeline_id,
            "duration_s": time.time() - (pipeline.started_at or time.time()),
        }

    def _execute_serial(
        self, pipeline: DAGPipeline, node_executor: Callable = None
    ) -> dict[str, Any]:
        """串行拓扑执行"""
        levels = pipeline.topological_levels()
        nodes_completed = 0
        nodes_failed = 0

        for level_idx, level_nodes in enumerate(levels):
            active_nodes = self._evaluate_conditions(pipeline, level_nodes)
            for node in active_nodes:
                if pipeline.is_cancelled():
                    return {"success": False, "cancelled": True}

                node.status = NodeStatus.RUNNING
                node.started_at = time.time()
                pipeline._notify_status_change(node)

                success, result_data, error = self._execute_node(
                    pipeline, node, node_executor
                )
                node.completed_at = time.time()
                node.duration_s = node.completed_at - (
                    node.started_at or node.completed_at
                )

                if success:
                    node.status = NodeStatus.COMPLETED
                    node.result = result_data
                    nodes_completed += 1
                    self._stats["nodes_executed"] += 1
                else:
                    node.status = NodeStatus.FAILED
                    node.error = error
                    nodes_failed += 1
                    self._stats["nodes_failed"] += 1

                pipeline._notify_status_change(node)

        return {
            "success": nodes_failed == 0,
            "nodes_completed": nodes_completed,
            "nodes_failed": nodes_failed,
            "pipeline_id": pipeline.pipeline_id,
        }

    def _evaluate_conditions(
        self, pipeline: DAGPipeline, level_nodes: list[str]
    ) -> list[DAGNode]:
        """评估条件边 — 返回应该在本层激活的节点"""
        active = []
        for node_id in level_nodes:
            node = pipeline.nodes[node_id]
            # 查找指向此节点的条件边
            cond_edges = [
                e
                for e in pipeline.edges
                if e.target_id == node_id and e.edge_type == EdgeType.CONDITIONAL
            ]
            if cond_edges:
                # 条件边: 检查源节点结果是否满足条件
                should_activate = True
                for ce in cond_edges:
                    source_node = pipeline.nodes.get(ce.source_id)
                    if source_node and source_node.status == NodeStatus.COMPLETED:
                        if ce.condition and not ce.condition(source_node.result or {}):
                            should_activate = False
                            node.status = NodeStatus.SKIPPED
                            pipeline.stats["skipped"] += 1
                            break
                    elif source_node and source_node.status == NodeStatus.FAILED:
                        should_activate = False
                        node.status = NodeStatus.SKIPPED
                        pipeline.stats["skipped"] += 1
                if should_activate:
                    active.append(node)
            else:
                # 标准依赖边: 检查所有前驱是否完成
                deps = pipeline.get_dependencies(node_id)
                all_deps_met = all(
                    pipeline.nodes[d].status == NodeStatus.COMPLETED for d in deps
                )
                if all_deps_met:
                    active.append(node)
                else:
                    # 如果前驱有失败的，根据策略决定
                    failed_deps = [
                        d for d in deps if pipeline.nodes[d].status == NodeStatus.FAILED
                    ]
                    if (
                        failed_deps
                        and self.error_strategy
                        == self.FatalErrorStrategy.STOP_DEPENDENTS
                    ):
                        node.status = NodeStatus.SKIPPED
                        pipeline.stats["skipped"] += 1
                    elif (
                        failed_deps
                        and self.error_strategy == self.FatalErrorStrategy.STOP_ALL
                    ):
                        node.status = NodeStatus.CANCELLED
        return active

    def _execute_node(
        self, pipeline: DAGPipeline, node: DAGNode, node_executor: Callable = None
    ) -> tuple[bool, dict | None, str | None]:
        """执行单个节点 — 带重试"""
        last_error = None
        for attempt in range(node.max_retries + 1):
            try:
                node.retry_count = attempt

                # 使用注入的Tracker追踪
                if self.tracker:
                    self.tracker.track(
                        tool_name=f"dag:{node.agent_id}",
                        success=True,
                        duration_ms=0,
                        output_summary=f"DAG节点: {node.goal[:80]}",
                    )

                if node_executor:
                    result = node_executor(node)
                    if isinstance(result, dict) and not result.get("success", True):
                        last_error = result.get("error", "Unknown error")
                        if attempt < node.max_retries:
                            logger.warning(
                                f"[DAG] Node {node.node_id} retry {attempt + 1}/{node.max_retries}"
                            )
                            time.sleep(2**attempt)
                            continue
                        return False, result, last_error
                    return True, result, None
                else:
                    # 降级: 模拟执行
                    time.sleep(0.1)
                    return True, {"simulated": True, "node_id": node.node_id}, None

            except Exception as e:
                last_error = str(e)
                logger.error(
                    f"[DAG] Node {node.node_id} attempt {attempt + 1} failed: {e}"
                )
                if attempt < node.max_retries:
                    time.sleep(2**attempt)
                    continue

        return False, None, last_error

    def get_pipeline(self, pipeline_id: str) -> DAGPipeline | None:
        with self._lock:
            return self._active_pipelines.get(pipeline_id)

    def get_stats(self) -> dict:
        return {
            "version": self.VERSION,
            **self._stats,
            "active_pipelines": len(self._active_pipelines),
        }

    def cancel_pipeline(self, pipeline_id: str) -> bool:
        pipeline = self.get_pipeline(pipeline_id)
        if pipeline:
            pipeline.cancel()
            return True
        return False


# ═══════════════════════════════════════════════════════════════
# DAG构建器 — 便捷API
# ═══════════════════════════════════════════════════════════════


class DAGBuilder:
    """DAG构建器 — 提供流式API构建DAG流水线"""

    def __init__(self, pipeline_name: str = ""):
        self.pipeline = DAGPipeline(
            pipeline_id=f"dag-{uuid.uuid4().hex[:8]}",
            pipeline_name=pipeline_name,
        )

    def node(
        self,
        agent_id: str,
        goal: str,
        context: str = "",
        tools: list[str] = None,
        priority: str = "medium",
        timeout_s: int = 300,
    ) -> DAGBuilder:
        """添加节点 (自动生成node_id)"""
        from core.orchestration.agent_orchestrator import AGENT_CAPABILITY_MATRIX

        info = AGENT_CAPABILITY_MATRIX.get(agent_id, {})
        node = DAGNode(
            node_id=f"node-{uuid.uuid4().hex[:6]}",
            agent_id=agent_id,
            agent_name=info.get("name", agent_id),
            agent_emoji=info.get("emoji", "🤖"),
            goal=goal,
            context=context,
            tools_allowed=tools or info.get("tools", []),
            priority=priority,
            timeout_s=timeout_s,
        )
        self.pipeline.add_node(node)
        self._last_node_id = node.node_id
        return self

    def then(
        self,
        agent_id: str,
        goal: str,
        context: str = "",
        tools: list[str] = None,
        condition: Callable = None,
        condition_desc: str = "",
    ) -> DAGBuilder:
        """添加后继节点 (从上一个节点连边)"""
        prev_id = getattr(self, "_last_node_id", None)
        builder = self.node(agent_id, goal, context, tools)
        if prev_id:
            edge_type = EdgeType.CONDITIONAL if condition else EdgeType.DEPENDENCY
            self.pipeline.add_edge(
                prev_id,
                self._last_node_id,
                edge_type=edge_type,
                condition=condition,
                condition_desc=condition_desc,
            )
        return builder

    def depends_on(self, source_node_id: str) -> DAGBuilder:
        """从指定源节点添加依赖边"""
        if hasattr(self, "_last_node_id"):
            self.pipeline.add_edge(source_node_id, self._last_node_id)
        return self

    def parallel(self, *node_specs: tuple[str, str]) -> DAGBuilder:
        """添加多个并行节点 (从上一个节点分叉)"""
        prev_id = getattr(self, "_last_node_id", None)
        last_ids = []
        for agent_id, goal in node_specs:
            self.node(agent_id, goal)
            if prev_id:
                self.pipeline.add_edge(prev_id, self._last_node_id)
            last_ids.append(self._last_node_id)
        if last_ids:
            self._last_branch_ids = last_ids
        return self

    def merge(self, agent_id: str, goal: str) -> DAGBuilder:
        """合并多个分支到一个节点"""
        branch_ids = getattr(self, "_last_branch_ids", [])
        self.node(agent_id, goal)
        for bid in branch_ids:
            self.pipeline.add_edge(bid, self._last_node_id)
        return self

    def build(self, event_bus=None) -> DAGPipeline:
        """构建并返回DAGPipeline"""
        self.pipeline.event_bus = event_bus
        if self.pipeline.has_cycle():
            logger.warning("[DAGBuilder] ⚠️ 构建的DAG存在环!")
        return self.pipeline


# ═══════════════════════════════════════════════════════════════
# 工厂函数 — 快速创建常见流水线
# ═══════════════════════════════════════════════════════════════


def create_development_dag(task_goal: str, event_bus=None) -> DAGPipeline:
    """创建标准开发流水线DAG"""
    builder = DAGBuilder(f"开发: {task_goal[:30]}")
    builder.node("dongcha", f"分析需求: {task_goal}").then(
        "jingwei", f"架构设计: {task_goal}"
    ).then("miaobi", f"编码实现: {task_goal}").then(
        "mingjing", f"代码审校: {task_goal}"
    ).then("tiewei", f"测试验证: {task_goal}").then("gongzao", f"部署上线: {task_goal}")
    return builder.build(event_bus)


def create_analysis_dag(topics: list[str], event_bus=None) -> DAGPipeline:
    """创建并行分析流水线DAG"""
    builder = DAGBuilder("并行分析")
    # 起始节点: 任务分发
    builder.node("tianshu", f"分发分析任务: {len(topics)}个主题")
    # 并行分支: 每个主题分配不同Agent
    agent_map = ["tiansuan", "jingwei", "dongcha", "zhuiguang", "zhenshan"]
    for i, topic in enumerate(topics):
        agent = agent_map[i % len(agent_map)]
        builder.node(agent, f"分析: {topic}").depends_on(
            builder.pipeline.nodes[list(builder.pipeline.nodes.keys())[0]].node_id
        )
    # 合并节点
    builder.node("mingjing", f"汇总{len(topics)}个分析结果")
    for nid in list(builder.pipeline.nodes.keys())[1:-1]:
        builder.pipeline.add_edge(nid, builder._last_node_id)
    return builder.build(event_bus)


def create_security_audit_dag(target: str, event_bus=None) -> DAGPipeline:
    """创建安全审计流水线DAG — 并行扫描+合并"""
    builder = DAGBuilder(f"安全审计: {target[:30]}")
    builder.node("tianshu", f"启动安全审计: {target}").parallel(
        ("zhenshan", f"漏洞扫描: {target}"),
        ("luling", f"合规检查: {target}"),
        ("zhuiguang", f"性能基线: {target}"),
    ).merge("jingwei", f"综合风险报告: {target}")
    return builder.build(event_bus)


# ═══════════════════════════════════════════════════════════════
# 全局单例
# ═══════════════════════════════════════════════════════════════

_dag_scheduler: DAGScheduler | None = None
_dag_lock = threading.Lock()


def get_dag_scheduler(
    max_workers: int = 8, event_bus=None, tracker=None
) -> DAGScheduler:
    """获取全局DAG调度器单例"""
    global _dag_scheduler
    with _dag_lock:
        if _dag_scheduler is None:
            _dag_scheduler = DAGScheduler(
                max_workers=max_workers,
                event_bus=event_bus,
                tracker=tracker,
            )
        return _dag_scheduler
