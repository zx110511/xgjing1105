"""
OrchestratorAgent - Master Pipeline Scheduler v1.1
===================================================
Priority-based task scheduling with state machine orchestration.
Uses weighted multi-factor priority algorithm for optimal resource allocation.

M34升级: EvolutionLoop闭环 + record_action喂入 + health() + 双注入
灵境道谱溯源: D9-2【Δ阈值配置煞】· 道九·进化体道 · 四地煞之变之术
  - 管道阶段阈值自适应+任务优先级权重动态调谐+编排策略演化
  - 源文件: agents/orchestrator.py → OrchestratorAgent

Priority Formula:
    P = (C × Wc) + (U × Wu) + (D × Wd) + (R × Wr)
    where:
      C = Criticality (1-10)
      U = Urgency (1-10)
      D = Dependency Depth (0-5)
      R = Retry Count (0-3, bonus for retries)
      W = Corresponding weights (mutable, Evolvable via EvolutionLoop)

State Machine:
    IDLE → ENV_CHECK → DEP_INSTALL → BACKEND_BUILD → FRONTEND_BUILD
    → DEP_FIX → PACKAGE_ASSEMBLY → SG0 → SG1 → SG2 → SG3 → SG4
    → REPORT → SUCCESS
    (Any state → RECOVERY → retry or → FAILURE)
"""

import os
import sys
import time
import heapq
import threading
from pathlib import Path
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Optional, List, Dict, Any, Callable

try:
    from core.processors.evolution_loop import EvolutionLoop
except ImportError:
    EvolutionLoop = None

from agents.pipeline_logger import PipelineLogger, LogLevel


class PipelineState(Enum):
    IDLE = auto()
    ENV_CHECK = auto()
    DEP_INSTALL = auto()
    BACKEND_BUILD = auto()
    FRONTEND_BUILD = auto()
    DEP_FIX = auto()
    PACKAGE_ASSEMBLY = auto()
    SG0_ENV_READY = auto()
    SG1_IMPORT_VERIFY = auto()
    SG2_FUNCTIONAL_VERIFY = auto()
    SG3_MCP_INTEGRATION = auto()
    SG4_REGRESSION = auto()
    REPORT = auto()
    RECOVERY = auto()
    SUCCESS = auto()
    FAILURE = auto()

    @property
    def label(self) -> str:
        labels = {
            PipelineState.IDLE: "Idle",
            PipelineState.ENV_CHECK: "Environment Check",
            PipelineState.DEP_INSTALL: "Dependency Install",
            PipelineState.BACKEND_BUILD: "Backend Build",
            PipelineState.FRONTEND_BUILD: "Frontend Build",
            PipelineState.DEP_FIX: "Dependency Fix",
            PipelineState.PACKAGE_ASSEMBLY: "Package Assembly",
            PipelineState.SG0_ENV_READY: "SG-0 Env Readiness",
            PipelineState.SG1_IMPORT_VERIFY: "SG-1 Import Verify",
            PipelineState.SG2_FUNCTIONAL_VERIFY: "SG-2 Functional Verify",
            PipelineState.SG3_MCP_INTEGRATION: "SG-3 MCP Integration",
            PipelineState.SG4_REGRESSION: "SG-4 Regression",
            PipelineState.REPORT: "Report Generation",
            PipelineState.RECOVERY: "Error Recovery",
            PipelineState.SUCCESS: "Success",
            PipelineState.FAILURE: "Failure",
        }
        return labels.get(self, self.name)


class TaskPriority(Enum):
    CRITICAL = 10
    HIGH = 7
    MEDIUM = 5
    LOW = 3
    OPTIONAL = 1


@dataclass(order=True)
class Task:
    """Priority-sortable task with multi-factor weighting."""
    sort_key: float = field(init=False)
    name: str = field(compare=False)
    state: PipelineState = field(compare=False)
    handler: Callable = field(compare=False, default=None)
    criticality: int = 5
    urgency: int = 5
    dependency_depth: int = 0
    retry_count: int = 0
    max_retries: int = 3
    timeout_seconds: float = 600.0

    def __post_init__(self):
        self.sort_key = self._compute_priority()

    def _compute_priority(self) -> float:
        W_C = 0.40
        W_U = 0.30
        W_D = 0.20
        W_R = 0.10

        C = self.criticality / 10.0
        U = self.urgency / 10.0
        D = self.dependency_depth / 5.0
        R = min(self.retry_count, 3) / 3.0

        priority = (C * W_C) + (U * W_U) + (D * W_D) + (R * W_R)
        return -priority


class OrchestratorAgent:
    """
    Master orchestrator implementing priority-based scheduling
    and state-machine-driven pipeline execution.
    """

    WEIGHT_CONFIG = {
        "criticality": 0.40,
        "urgency": 0.30,
        "dependency_depth": 0.20,
        "retry_bonus": 0.10,
    }

    STATE_TRANSITIONS = {
        PipelineState.IDLE: [PipelineState.ENV_CHECK, PipelineState.FAILURE],
        PipelineState.ENV_CHECK: [PipelineState.BACKEND_BUILD, PipelineState.RECOVERY, PipelineState.FAILURE],
        PipelineState.BACKEND_BUILD: [PipelineState.DEP_FIX, PipelineState.RECOVERY, PipelineState.FAILURE],
        PipelineState.DEP_FIX: [PipelineState.FRONTEND_BUILD, PipelineState.RECOVERY, PipelineState.FAILURE],
        PipelineState.FRONTEND_BUILD: [PipelineState.PACKAGE_ASSEMBLY, PipelineState.RECOVERY, PipelineState.FAILURE],
        PipelineState.PACKAGE_ASSEMBLY: [PipelineState.SG0_ENV_READY, PipelineState.RECOVERY, PipelineState.FAILURE],
        PipelineState.SG0_ENV_READY: [PipelineState.SG1_IMPORT_VERIFY, PipelineState.RECOVERY, PipelineState.FAILURE],
        PipelineState.SG1_IMPORT_VERIFY: [PipelineState.SG2_FUNCTIONAL_VERIFY, PipelineState.RECOVERY, PipelineState.FAILURE],
        PipelineState.SG2_FUNCTIONAL_VERIFY: [PipelineState.SG3_MCP_INTEGRATION, PipelineState.RECOVERY, PipelineState.FAILURE],
        PipelineState.SG3_MCP_INTEGRATION: [PipelineState.SG4_REGRESSION, PipelineState.RECOVERY, PipelineState.FAILURE],
        PipelineState.SG4_REGRESSION: [PipelineState.REPORT, PipelineState.RECOVERY, PipelineState.FAILURE],
        PipelineState.REPORT: [PipelineState.SUCCESS, PipelineState.FAILURE],
        PipelineState.RECOVERY: [PipelineState.ENV_CHECK, PipelineState.BACKEND_BUILD,
                                 PipelineState.FRONTEND_BUILD, PipelineState.PACKAGE_ASSEMBLY,
                                 PipelineState.SG0_ENV_READY, PipelineState.SG1_IMPORT_VERIFY,
                                 PipelineState.SG2_FUNCTIONAL_VERIFY, PipelineState.SG3_MCP_INTEGRATION,
                                 PipelineState.SG4_REGRESSION, PipelineState.FAILURE],
    }

    def __init__(self, logger: Optional[PipelineLogger] = None,
                 recorder: Optional[Any] = None,
                 learning_engine: Optional[Any] = None):
        self.logger = logger or PipelineLogger()
        self._recorder = recorder
        self._learning_engine = learning_engine
        self._errors = 0
        self.current_state = PipelineState.IDLE
        self.task_queue: List[Task] = []
        self.completed_tasks: List[Task] = []
        self.failed_tasks: List[Task] = []
        self.state_history: List[PipelineState] = []
        self.agent_registry: Dict[str, Any] = {}
        self.start_time = time.time()
        self._lock = threading.Lock()

        self._evo_loop = None
        if EvolutionLoop is not None:
            try:
                self._evo_loop = EvolutionLoop(
                    module_name="orchestrator",
                    effectiveness_fn=self._calc_orch_effectiveness,
                    learn_fn=self._learn_from_orch,
                    evolve_fn=self._evolve_orch_config,
                    mutable_config={
                        "weight_criticality": 0.40,
                        "weight_urgency": 0.30,
                        "weight_dependency": 0.20,
                        "weight_retry": 0.10,
                    },
                    recorder=recorder,
                    learning_engine=learning_engine,
                )
            except Exception:
                pass

    def register_agent(self, name: str, agent: Any) -> None:
        self.agent_registry[name] = agent
        self.logger.log(LogLevel.DEBUG, "Orchestrator", "Orchestrator",
                        f"Agent registered: {name}")

    def schedule_task(self, task: Task) -> None:
        with self._lock:
            heapq.heappush(self.task_queue, task)
        self.logger.log(LogLevel.DEBUG, "Orchestrator", "Orchestrator",
                        f"Task scheduled: {task.name} (priority: {-task.sort_key:.3f})")

        if self._evo_loop is not None:
            try:
                self._evo_loop.record_action(
                    action="schedule_task",
                    state_before={"queue_size": len(self.task_queue) - 1},
                    state_after={"task_name": task.name,
                                 "priority": -task.sort_key,
                                 "state": task.state.label if hasattr(task.state, 'label') else str(task.state),
                                 "queue_size": len(self.task_queue)},
                )
            except Exception:
                pass

    def schedule_tasks(self, tasks: List[Task]) -> None:
        for task in tasks:
            self.schedule_task(task)

    def get_next_task(self) -> Optional[Task]:
        with self._lock:
            if self.task_queue:
                return heapq.heappop(self.task_queue)
        return None

    def transition_to(self, state: PipelineState) -> bool:
        valid_transitions = self.STATE_TRANSITIONS.get(self.current_state, [])

        if state not in valid_transitions:
            self.logger.log(LogLevel.WARN, self.current_state.label, "Orchestrator",
                            f"Invalid transition: {self.current_state.label} -> {state.label}")
            if PipelineState.RECOVERY not in valid_transitions:
                return False

        old_state = self.current_state
        self.state_history.append(old_state)
        self.current_state = state

        self.logger.log(LogLevel.INFO, state.label, "Orchestrator",
                        f"State transition: {old_state.label} -> {state.label}")

        if self._evo_loop is not None:
            try:
                self._evo_loop.record_action(
                    action="transition_to",
                    state_before={"from_state": old_state.label},
                    state_after={"to_state": state.label,
                                 "valid": True,
                                 "history_len": len(self.state_history)},
                )
            except Exception:
                pass

        return True

    def execute_pipeline(self) -> bool:
        """
        Execute the full pipeline based on state machine.
        Returns True if pipeline succeeded, False otherwise.
        """
        self.current_state = PipelineState.IDLE
        self.start_time = time.time()
        self.logger.pipeline_start_time = self.start_time

        self.logger.log(LogLevel.INFO, "Pipeline", "Orchestrator",
                        "=" * 60)
        self.logger.log(LogLevel.INFO, "Pipeline", "Orchestrator",
                        "Intelligent Agent Scheduling Pipeline Started")

        pipeline_states = [
            PipelineState.ENV_CHECK,
            PipelineState.BACKEND_BUILD,
            PipelineState.DEP_FIX,
            PipelineState.FRONTEND_BUILD,
            PipelineState.PACKAGE_ASSEMBLY,
            PipelineState.SG0_ENV_READY,
            PipelineState.SG1_IMPORT_VERIFY,
            PipelineState.SG2_FUNCTIONAL_VERIFY,
            PipelineState.SG3_MCP_INTEGRATION,
            PipelineState.SG4_REGRESSION,
            PipelineState.REPORT,
        ]

        for state in pipeline_states:
            if not self.transition_to(state):
                self.transition_to(PipelineState.FAILURE)
                return False

            result = self._execute_state(state)
            if not result:
                recovery_agent = self.agent_registry.get("RecoveryAgent")
                if recovery_agent:
                    recovered = recovery_agent.attempt_recovery(
                        state, self.failed_tasks
                    )
                    if recovered:
                        self.logger.log(LogLevel.INFO, state.label, "Orchestrator",
                                        "Recovery successful, resuming pipeline")
                        continue

                self.transition_to(PipelineState.FAILURE)

                if self._evo_loop is not None:
                    try:
                        elapsed = time.time() - self.start_time
                        self._evo_loop.record_action(
                            action="execute_pipeline",
                            state_before={"pipeline_start": self.start_time},
                            state_after={"result": False,
                                         "failed_at": state.label,
                                         "elapsed": elapsed,
                                         "completed": len(self.completed_tasks),
                                         "failed": len(self.failed_tasks)},
                        )
                    except Exception:
                        pass

                return False

        self.transition_to(PipelineState.SUCCESS)

        if self._evo_loop is not None:
            try:
                elapsed = time.time() - self.start_time
                self._evo_loop.record_action(
                    action="execute_pipeline",
                    state_before={"pipeline_start": self.start_time},
                    state_after={"result": True,
                                 "elapsed": elapsed,
                                 "completed": len(self.completed_tasks),
                                 "failed": len(self.failed_tasks)},
                )
            except Exception:
                pass

        return True

    def _execute_state(self, state: PipelineState) -> bool:
        self.logger.stage_start(state.label)

        agent_name_map = {
            PipelineState.ENV_CHECK: "BuildAgent",
            PipelineState.BACKEND_BUILD: "BuildAgent",
            PipelineState.DEP_FIX: "BuildAgent",
            PipelineState.FRONTEND_BUILD: "BuildAgent",
            PipelineState.PACKAGE_ASSEMBLY: "BuildAgent",
            PipelineState.SG0_ENV_READY: "TestAgent",
            PipelineState.SG1_IMPORT_VERIFY: "TestAgent",
            PipelineState.SG2_FUNCTIONAL_VERIFY: "TestAgent",
            PipelineState.SG3_MCP_INTEGRATION: "TestAgent",
            PipelineState.SG4_REGRESSION: "TestAgent",
            PipelineState.REPORT: "Orchestrator",
        }

        agent_name = agent_name_map.get(state, "Unknown")
        agent = self.agent_registry.get(agent_name)

        if agent is None:
            self.logger.log(LogLevel.WARN, state.label, "Orchestrator",
                            f"No agent registered for state: {state.label}")
            self.logger.stage_end(state.label, "skipped")
            return True

        start = time.time()
        try:
            handler_method = {
                PipelineState.ENV_CHECK: lambda: agent.check_environment(),
                PipelineState.BACKEND_BUILD: lambda: agent.build_backend(),
                PipelineState.DEP_FIX: lambda: agent.fix_dependencies(),
                PipelineState.FRONTEND_BUILD: lambda: agent.build_frontend(),
                PipelineState.PACKAGE_ASSEMBLY: lambda: agent.assemble_package(),
                PipelineState.SG0_ENV_READY: lambda: agent.run_sg0(),
                PipelineState.SG1_IMPORT_VERIFY: lambda: agent.run_sg1(),
                PipelineState.SG2_FUNCTIONAL_VERIFY: lambda: agent.run_sg2(),
                PipelineState.SG3_MCP_INTEGRATION: lambda: agent.run_sg3(),
                PipelineState.SG4_REGRESSION: lambda: agent.run_sg4(),
                PipelineState.REPORT: lambda: self._generate_report(),
            }.get(state, lambda: True)

            result = handler_method()
            elapsed = time.time() - start

            self.logger.log(LogLevel.INFO, state.label, agent_name,
                            f"Completed in {elapsed:.1f}s" if result else "Failed",
                            duration_ms=elapsed * 1000)

            self.logger.stage_end(state.label, "completed" if result else "failed")
            return result

        except Exception as e:
            elapsed = time.time() - start
            self.logger.record_error(state.label, agent_name, str(e))
            self.logger.stage_end(state.label, "failed")
            self._errors += 1

            if self._evo_loop is not None:
                try:
                    self._evo_loop.record_action(
                        action="execute_state",
                        state_before={"state": state.label, "agent": agent_name},
                        state_after={"state": state.label,
                                     "agent": agent_name,
                                     "result": False,
                                     "error": str(e)[:100],
                                     "elapsed": elapsed},
                    )
                except Exception:
                    pass

            return False

    def _generate_report(self) -> bool:
        self.logger.print_summary()
        return True

    def get_pipeline_status(self) -> Dict[str, Any]:
        elapsed = time.time() - self.start_time
        return {
            "current_state": self.current_state.label,
            "elapsed_seconds": round(elapsed, 1),
            "tasks_total": len(self.completed_tasks) + len(self.failed_tasks) + len(self.task_queue),
            "tasks_completed": len(self.completed_tasks),
            "tasks_failed": len(self.failed_tasks),
            "tasks_pending": len(self.task_queue),
            "state_history": [s.label for s in self.state_history],
            "registered_agents": list(self.agent_registry.keys()),
            "weight_config": self.WEIGHT_CONFIG,
            "health": self.health(),
            "version": "1.1",
            "evo_loop": self._evo_loop.get_stats() if self._evo_loop else {},
        }

    def health(self) -> Dict[str, Any]:
        return {
            "status": "ready",
            "version": "1.1",
            "current_state": self.current_state.label,
            "tasks_pending": len(self.task_queue),
            "tasks_completed": len(self.completed_tasks),
            "tasks_failed": len(self.failed_tasks),
            "agents_registered": len(self.agent_registry),
            "errors": self._errors,
            "evo_loop_active": self._evo_loop is not None,
            "recorder_attached": self._recorder is not None,
        }

    def tick(self):
        if self._evo_loop is not None:
            try:
                self._evo_loop.tick()
            except Exception:
                pass

    def _calc_orch_effectiveness(self, action: str,
                                  state_before: Dict[str, Any],
                                  state_after: Dict[str, Any]) -> float:
        if action == "execute_pipeline":
            result = state_after.get("result", False)
            if result:
                failed = state_after.get("failed", 0)
                return 0.9 if failed == 0 else (0.6 if failed <= 2 else 0.3)
            return 0.1
        elif action == "schedule_task":
            return max(0.3, min(0.7, state_after.get("priority", 0.0) * 0.7))
        elif action == "transition_to":
            return 0.5
        elif action == "execute_state":
            return 0.0 if "error" in state_after else 0.6
        return 0.0

    def _learn_from_orch(self, causal_pairs: List[Any],
                          effectiveness_summary: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "patterns_found": len(causal_pairs),
            "avg_effectiveness": effectiveness_summary.get("avg_effectiveness", 0.0),
            "total_tasks_completed": len(self.completed_tasks),
            "total_tasks_failed": len(self.failed_tasks),
            "task_queue_depth": len(self.task_queue),
            "current_state": self.current_state.label,
            "weight_config": dict(self.WEIGHT_CONFIG),
        }

    def _evolve_orch_config(self, learn_result: Dict[str, Any],
                             mutable_config: Dict[str, Any]) -> Dict[str, Any]:
        changes = {}
        failed = learn_result.get("total_tasks_failed", 0)
        completed = learn_result.get("total_tasks_completed", 0)
        total = failed + completed
        if total > 0:
            fail_rate = failed / total
            if fail_rate > 0.3:
                changes["weight_criticality"] = min(0.60,
                    mutable_config.get("weight_criticality", 0.40) + 0.05)
                changes["weight_urgency"] = min(0.45,
                    mutable_config.get("weight_urgency", 0.30) + 0.05)
            elif fail_rate < 0.1:
                changes["weight_criticality"] = 0.40
                changes["weight_urgency"] = 0.30
        return {"rules_modified": changes, "skills_created": []}
