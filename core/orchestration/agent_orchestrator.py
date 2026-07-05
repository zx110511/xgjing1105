r"""
天机Agent调度引擎 (Tianji Agent Orchestrator) v2.0 — [v10-ready]
===================================================
编排中心 — 从62分的TVPBridge升级为SSS级(95+分)调度引擎。

【v10 重构】原1215行单文件已按职责拆分为 core/orchestration/ 子包:
  registry.py   — CapabilityRegistry  (能力矩阵管理/元数据解析/能力查询)
  tracker.py    — ToolTracker          (工具调用追踪/执行Agent标注/统计)
  pipeline.py   — PipelineOrchestrator (管道编排/阶段切换/结果聚合)
  dispatcher.py — AgentDispatcher      (Agent选择/并行调度/分配)

本文件保留为【编排中心】: AgentScheduler 组合调用各子模块。

兼容性保证:
  from core.orchestration.agent_orchestrator import AgentScheduler / AgentOrchestrator
  from core.orchestration.agent_orchestrator import AGENT_CAPABILITY_MATRIX, AgentPipeline ...
  以上全部继续可用 — 通过下方 re-export 从子包透传。

核心能力:
  1. ToolCallTracker   — 每次工具调用强制标注执行Agent
  2. AgentPipeline      — 长链任务多Agent阶段切换
  3. ParallelDispatcher  — 并行任务精准Agent分配
  4. StageSwitchProtocol — 阶段切换时TVP透明声明

位置: 天机/core/agent_orchestrator.py
"""

from __future__ import annotations

import logging
from collections.abc import Callable

# ═══════════════════════════════════════════════════════════════
# 兼容层 re-export — 所有原始符号从 core.orchestration 子包透传
# ═══════════════════════════════════════════════════════════════
from core.orchestration.dispatcher import AgentDispatcher, ParallelDispatcher
from core.orchestration.pipeline import (
    AgentPipeline,
    PipelineOrchestrator,
    StageResult,
)
from core.orchestration.registry import (
    AGENT_CAPABILITY_MATRIX,
    DEFAULT_REGISTRY,
    CapabilityRegistry,
    PipelineStage,
)
from core.orchestration.tracker import (
    AgentTask,
    ToolCallRecord,
    ToolCallTracker,
    ToolTracker,
)

logger = logging.getLogger("tianji.orchestrator")

__all__ = [
    # ---- 子包透传 (向后兼容) ----
    "AGENT_CAPABILITY_MATRIX",
    "PipelineStage",
    "AgentTask",
    "ToolCallRecord",
    "StageResult",
    "ToolCallTracker",
    "ToolTracker",
    "AgentPipeline",
    "PipelineOrchestrator",
    "ParallelDispatcher",
    "AgentDispatcher",
    "CapabilityRegistry",
    "DEFAULT_REGISTRY",
    # ---- 编排中心 ----
    "AgentScheduler",
    "AgentOrchestrator",
]


# ═══════════════════════════════════════════════════════════════
# AgentScheduler — 顶层编排中心 (替换62分TVPBridge) — [v10-ready]
# ═══════════════════════════════════════════════════════════════


class AgentScheduler:
    """
    SSS级Agent调度器 — 编排中心，组合调用 orchestration 子包

    三种调度模式:
      1. 长链流水线 (long_chain)  → AgentPipeline
      2. 并行分析   (parallel)    → ParallelDispatcher
      3. 单Agent执行 (single)     → 直接Tracker

    每次工具调用 → ToolCallTracker强制标注Agent
    """

    VERSION = "3.0.0-天枢-DAG"

    def __init__(self, event_bus=None, output_handler: Callable = None):
        self.tracker = ToolCallTracker(event_bus=event_bus)
        self.event_bus = event_bus
        self._output_handler = output_handler
        self.tracker.set_output_handler(output_handler)
        self._active_pipeline: AgentPipeline | None = None
        self._dispatcher = ParallelDispatcher(self.tracker, event_bus=event_bus)
        self._dispatcher.set_output_handler(output_handler)
        self._stats = {
            "pipelines_created": 0,
            "dispatches_run": 0,
            "tools_tracked": 0,
            "dag_pipelines_executed": 0,
            "dag_nodes_completed": 0,
        }

        # v10: DAG调度引擎 + LLM规划器 + 持久化执行
        self._dag_scheduler = None
        self._task_planner = None
        self._durable_runner = None

        self._evo_loop = None
        try:
            from ..processors.evolution_loop import EvolutionLoop

            self._evo_loop = EvolutionLoop(
                module_name="agent_orchestrator",
                effectiveness_fn=self._calc_orchestrator_effectiveness,
                learn_fn=self._learn_from_orchestration,
                evolve_fn=self._evolve_orchestration_config,
                mutable_config={
                    "max_pipeline_stages": 8,
                    "parallel_batch_size": 3,
                    "stage_timeout_ms": 60000,
                    "fallback_enabled": True,
                },
                health_metrics_fn=self._get_orchestrator_health,
            )
        except ImportError:
            pass

    def set_output_handler(self, handler: Callable[[str], None]):
        self._output_handler = handler
        self.tracker.set_output_handler(handler)
        self._dispatcher.set_output_handler(handler)

    def _calc_orchestrator_effectiveness(
        self, action: str, state_before: dict, state_after: dict
    ) -> float:
        if action == "pipeline_execute":
            if state_after.get("completed", False):
                return 0.4
            if state_after.get("partial", False):
                return -0.2
            return -0.5
        if action == "stage_switch":
            if state_after.get("success", False):
                return 0.2
            return -0.3
        if action == "parallel_dispatch":
            success_rate = state_after.get("success_rate", 0.0)
            return success_rate - 0.5
        return 0.0

    def _learn_from_orchestration(self, causal_pairs, effectiveness_summary) -> dict:
        failed_pipelines = sum(
            1
            for p in causal_pairs
            if p.action == "pipeline_execute" and p.effectiveness < 0
        )
        stage_failures = sum(
            1
            for p in causal_pairs
            if p.action == "stage_switch" and p.effectiveness < 0
        )
        avg_eff = effectiveness_summary.get("avg", 0.0)
        return {
            "failed_pipelines": failed_pipelines,
            "stage_failures": stage_failures,
            "avg_effectiveness": avg_eff,
        }

    def _evolve_orchestration_config(self, learn_result, mutable_config) -> dict:
        changes = []
        if learn_result.get("stage_failures", 0) > 5:
            old_timeout = mutable_config.get("stage_timeout_ms", 60000)
            new_timeout = min(int(old_timeout * 1.2), 300000)
            changes.append(
                {
                    "rule": "stage_timeout_ms",
                    "old_value": old_timeout,
                    "new_value": new_timeout,
                }
            )
        if learn_result.get("failed_pipelines", 0) > 3:
            if not mutable_config.get("fallback_enabled", True):
                changes.append(
                    {"rule": "fallback_enabled", "old_value": False, "new_value": True}
                )
        return {"changes": changes}

    def _get_orchestrator_health(self) -> dict[str, float]:
        total = max(self._stats.get("pipelines_created", 1), 1)
        return {
            "error_rate": self._stats.get("tools_tracked", 0) / max(total * 5, 1),
            "utilization": min(self._stats.get("pipelines_created", 0) / 10.0, 1.0),
        }

    @property
    def evolution_loop(self):
        return self._evo_loop

    def create_pipeline(self, pipeline_type: str = "development") -> AgentPipeline:
        """创建长链流水线"""
        pipeline = AgentPipeline(self.tracker, self.event_bus, pipeline_type)
        pipeline.set_output_handler(self._output_handler)
        self._active_pipeline = pipeline
        self._stats["pipelines_created"] += 1

        if self._output_handler:
            stage_names = " → ".join(
                f"@{AGENT_CAPABILITY_MATRIX.get(a, {}).get('name', a)}[{s.value}]"
                for s, a, _ in pipeline.stages
            )
            self._output_handler(
                f"[TVP] 🚀 长链流水线启动[{pipeline_type}]: {stage_names}"
            )

        return pipeline

    def get_pipeline(self) -> AgentPipeline | None:
        return self._active_pipeline

    def switch_pipeline_stage(
        self, stage_index: int, task_goal: str, task_context: str = ""
    ) -> dict:
        """切换流水线阶段 → Agent切换 + 工具标注上下文更新"""
        if not self._active_pipeline:
            return {"error": "No active pipeline"}

        result = self._active_pipeline.switch_to_stage(
            stage_index, task_goal, task_context
        )

        # 每次阶段切换时，track这个切换事件
        self.tracker.track(
            tool_name="pipeline_stage_switch",
            success=True,
            output_summary=f"切换到 {result.get('agent_name')} [{result.get('stage')}]",
        )

        return result

    def record_stage_done(
        self, status: str, summary: str, duration_s: float
    ) -> dict | None:
        if not self._active_pipeline:
            return None
        result = self._active_pipeline.record_stage_result(status, summary, duration_s)
        return result.to_tvp() if self._output_handler else None

    def dispatch_parallel(self, tasks: list[dict]) -> list[dict]:
        """并行调度多个Agent"""
        self._stats["dispatches_run"] += 1
        return self._dispatcher.dispatch(tasks)

    def track_tool(
        self,
        tool_name: str,
        success: bool = True,
        duration_ms: float = 0,
        output_summary: str = "",
    ) -> ToolCallRecord:
        """追踪一次工具调用 → 自动标注当前Agent"""
        self._stats["tools_tracked"] += 1
        return self.tracker.track(tool_name, success, duration_ms, output_summary)

    def get_pipeline_view(self) -> str:
        """获取当前TVP流水线全景"""
        return self.tracker.get_tvp_pipeline_view()

    def get_summary(self) -> dict:
        tracker_summary = self.tracker.get_summary()
        pipeline_summary = (
            self._active_pipeline.get_pipeline_summary()
            if self._active_pipeline
            else None
        )
        return {
            "version": self.VERSION,
            "stats": self._stats,
            "tracker": tracker_summary,
            "pipeline": pipeline_summary,
            "active_pipeline": {
                "type": self._active_pipeline.pipeline_type,
                "stage": (
                    self._active_pipeline.get_current_stage()[0].value
                    if self._active_pipeline.get_current_stage()
                    else "complete"
                ),
            }
            if self._active_pipeline
            else None,
        }

    def get_tvp_status(self) -> str:
        """生成状态报告中使用的TVP摘要"""
        parts = [self.get_pipeline_view()]
        if self._active_pipeline:
            ps = self._active_pipeline.get_pipeline_summary()
            parts.append(
                f"[TVP] 流水线: {ps['completed_stages']}/{ps['total_stages']}阶段完成, "
                f"{ps['total_tool_calls']}次工具调用"
            )
        return "\n".join(parts)

    # ═══════════════════════════════════════════════════════════
    # v10 天枢级: DAG调度 + LLM规划 + 持久化执行
    # ═══════════════════════════════════════════════════════════

    @property
    def dag_scheduler(self):
        """懒加载DAG调度器"""
        if self._dag_scheduler is None:
            from core.orchestration.dag_scheduler import DAGScheduler

            self._dag_scheduler = DAGScheduler(
                event_bus=self.event_bus,
                tracker=self.tracker,
            )
        return self._dag_scheduler

    @property
    def task_planner(self):
        """懒加载LLM任务规划器"""
        if self._task_planner is None:
            from core.orchestration.task_planner import TaskPlanner

            self._task_planner = TaskPlanner(
                event_bus=self.event_bus,
            )
        return self._task_planner

    @property
    def durable_runner(self):
        """懒加载持久化执行器"""
        if self._durable_runner is None:
            from core.shared.durable_executor import get_workflow_runner

            self._durable_runner = get_workflow_runner()
        return self._durable_runner

    def plan_task(
        self, task_description: str, context: str = "", prefer_llm: bool = True
    ) -> dict:
        """v10: LLM驱动的任务规划 → 返回Plan + DAG"""
        plan = self.task_planner.plan(task_description, context, prefer_llm=prefer_llm)
        dag = self.task_planner.plan_to_dag(plan, event_bus=self.event_bus)
        return {
            "plan": plan.to_dict(),
            "dag": dag.to_dict(),
        }

    def execute_dag(
        self,
        dag_pipeline=None,
        plan=None,
        node_executor: Callable = None,
        parallel: bool = True,
    ) -> dict:
        """v10: 执行DAG流水线

        Args:
            dag_pipeline: DAGPipeline对象 (可选)
            plan: TaskPlan对象 (可选, 自动转为DAG)
            node_executor: 节点执行函数
            parallel: 是否并行

        Returns:
            {"success": bool, "pipeline_id": str, "result": dict}
        """

        if plan is not None and dag_pipeline is None:
            dag_pipeline = self.task_planner.plan_to_dag(plan, event_bus=self.event_bus)

        if dag_pipeline is None:
            return {"success": False, "error": "No DAG pipeline or plan provided"}

        result = self.dag_scheduler.execute(
            dag_pipeline,
            node_executor=node_executor,
            parallel=parallel,
        )
        self._stats["dag_pipelines_executed"] += 1
        nodes_done = result.get("nodes_completed", 0)
        self._stats["dag_nodes_completed"] += nodes_done

        return {
            "success": result.get("success", False),
            "pipeline_id": dag_pipeline.pipeline_id,
            "result": result,
            "dag": dag_pipeline.to_dict(),
        }

    def plan_and_execute(
        self,
        task_description: str,
        context: str = "",
        prefer_llm: bool = True,
        parallel: bool = True,
    ) -> dict:
        """v10: 一站式: 规划+执行 — 自然语言→DAG→执行→结果"""
        plan = self.task_planner.plan(task_description, context, prefer_llm=prefer_llm)
        return self.execute_dag(plan=plan, parallel=parallel)

    def get_v10_stats(self) -> dict:
        """获取v10调度统计"""
        stats = {
            **self._stats,
            "dag_scheduler": self.dag_scheduler.get_stats()
            if self._dag_scheduler
            else {},
            "planner": self.task_planner.get_stats() if self._task_planner else {},
        }
        try:
            from core.shared.durable_executor import get_checkpoint_manager

            mgr = get_checkpoint_manager()
            stats["durable_executor"] = mgr.get_stats()
        except Exception:
            stats["durable_executor"] = {"status": "not_initialized"}
        return stats


# ═══════════════════════════════════════════════════════════════
# 向后兼容别名: AgentOrchestrator = AgentScheduler
# (历史文档与 from core.orchestration.agent_orchestrator import AgentOrchestrator 兼容)
# ═══════════════════════════════════════════════════════════════
AgentOrchestrator = AgentScheduler
