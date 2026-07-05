r"""
天机持久化执行引擎 (Tianji Durable Executor) v1.0
==================================================
借鉴 Temporal.io 的 Workflow/Activity 模型 + Durable Execution，
为天机v9.1提供检查点持久化、故障恢复、Saga补偿事务能力。

核心能力:
  1. WorkflowContext — 工作流上下文，自动持久化状态
  2. CheckpointManager — SQLite检查点存储，每步自动快照
  3. SagaCoordinator — 多步事务补偿回滚
  4. WorkflowRunner — Python函数→持久化工作流自动包装
  5. 故障恢复 — 从最近检查点恢复，不重跑已完成步骤

参考架构:
  - Temporal.io: Workflow/Activity + Serverless Workers (2026 Replay)
  - Restate: 轻量级持久化执行 + 事件驱动
  - Celery: 分布式任务队列 + 重试 + 结果存储

位置: 天机/core/durable_executor.py
"""

from __future__ import annotations

import functools
import json
import logging
import os
import sqlite3
import threading
import time
import uuid
from collections.abc import Callable
from contextlib import contextmanager
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

logger = logging.getLogger("tianji.durable_executor")


# ═══════════════════════════════════════════════════════════════
# 数据模型
# ═══════════════════════════════════════════════════════════════


class WorkflowStatus(str, Enum):
    CREATED = "created"
    RUNNING = "running"
    SUSPENDED = "suspended"  # 暂停等待
    COMPLETED = "completed"
    FAILED = "failed"
    COMPENSATING = "compensating"  # 正在回滚
    COMPENSATED = "compensated"  # 已回滚


class StepStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    COMPENSATED = "compensated"


@dataclass
class WorkflowStep:
    """工作流步骤 — 一个原子操作单元"""

    step_id: str
    step_name: str
    status: StepStatus = StepStatus.PENDING
    started_at: float | None = None
    completed_at: float | None = None
    duration_s: float = 0.0
    input_data: dict[str, Any] = field(default_factory=dict)
    output_data: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    retry_count: int = 0
    # Saga补偿
    compensation_fn: str | None = None  # 补偿函数名
    compensation_args: dict[str, Any] = field(default_factory=dict)
    compensated_at: float | None = None

    def to_dict(self) -> dict:
        return {
            "step_id": self.step_id,
            "step_name": self.step_name,
            "status": self.status.value,
            "duration_s": self.duration_s,
            "error": self.error,
            "retry_count": self.retry_count,
        }


@dataclass
class WorkflowContext:
    """工作流上下文 — 自动持久化的执行状态"""

    workflow_id: str
    workflow_name: str = ""
    status: WorkflowStatus = WorkflowStatus.CREATED
    steps: list[WorkflowStep] = field(default_factory=list)
    current_step_index: int = 0
    variables: dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    started_at: float | None = None
    completed_at: float | None = None
    last_checkpoint_at: float | None = None
    checkpoint_version: int = 0
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def add_step(
        self, name: str, compensation_fn: str = None, compensation_args: dict = None
    ) -> WorkflowStep:
        step = WorkflowStep(
            step_id=f"step-{uuid.uuid4().hex[:8]}",
            step_name=name,
            compensation_fn=compensation_fn,
            compensation_args=compensation_args or {},
        )
        self.steps.append(step)
        return step

    def get_current_step(self) -> WorkflowStep | None:
        if 0 <= self.current_step_index < len(self.steps):
            return self.steps[self.current_step_index]
        return None

    def to_dict(self) -> dict:
        return {
            "workflow_id": self.workflow_id,
            "workflow_name": self.workflow_name,
            "status": self.status.value,
            "steps": [s.to_dict() for s in self.steps],
            "current_step_index": self.current_step_index,
            "checkpoint_version": self.checkpoint_version,
            "error": self.error,
            "duration_s": (self.completed_at or time.time())
            - (self.started_at or time.time()),
        }


# ═══════════════════════════════════════════════════════════════
# 检查点管理器 (SQLite)
# ═══════════════════════════════════════════════════════════════


class CheckpointManager:
    """
    检查点管理器 — SQLite持久化工作流状态

    借鉴Temporal的Checkpoint机制:
      - 每步执行后自动保存快照
      - 故障恢复时从最近检查点恢复
      - WAL模式支持高并发读写
    """

    def __init__(self, db_path: str = None):
        if db_path is None:
            db_path = os.path.join(
                os.environ.get("AI_MEMORY_ROOT", os.getcwd()),
                "data",
                "workflow_checkpoints.db",
            )
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._init_db()

    def _init_db(self):
        """初始化数据库表"""
        with self._get_conn() as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
            conn.execute("""
                CREATE TABLE IF NOT EXISTS workflow_checkpoints (
                    workflow_id TEXT NOT NULL,
                    checkpoint_version INTEGER NOT NULL,
                    workflow_name TEXT,
                    status TEXT,
                    current_step_index INTEGER,
                    variables_json TEXT,
                    steps_json TEXT,
                    error TEXT,
                    created_at REAL,
                    updated_at REAL,
                    metadata_json TEXT,
                    PRIMARY KEY (workflow_id, checkpoint_version)
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS workflow_events (
                    event_id TEXT PRIMARY KEY,
                    workflow_id TEXT NOT NULL,
                    event_type TEXT,
                    step_id TEXT,
                    event_data_json TEXT,
                    timestamp REAL
                )
            """)
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_wf_events ON workflow_events(workflow_id, timestamp)"
            )

    @contextmanager
    def _get_conn(self):
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def save_checkpoint(self, ctx: WorkflowContext) -> int:
        """保存工作流检查点"""
        ctx.checkpoint_version += 1
        ctx.last_checkpoint_at = time.time()
        with self._lock:
            with self._get_conn() as conn:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO workflow_checkpoints
                    (workflow_id, checkpoint_version, workflow_name, status,
                     current_step_index, variables_json, steps_json, error,
                     created_at, updated_at, metadata_json)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        ctx.workflow_id,
                        ctx.checkpoint_version,
                        ctx.workflow_name,
                        ctx.status.value,
                        ctx.current_step_index,
                        json.dumps(ctx.variables, ensure_ascii=False),
                        json.dumps(
                            [s.__dict__ for s in ctx.steps],
                            ensure_ascii=False,
                            default=str,
                        ),
                        ctx.error,
                        ctx.created_at,
                        time.time(),
                        json.dumps(ctx.metadata, ensure_ascii=False),
                    ),
                )
        logger.debug(
            f"[Checkpoint] 💾 {ctx.workflow_id} v{ctx.checkpoint_version} saved"
        )
        return ctx.checkpoint_version

    def load_latest(self, workflow_id: str) -> WorkflowContext | None:
        """加载最近检查点"""
        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT * FROM workflow_checkpoints WHERE workflow_id=? "
                "ORDER BY checkpoint_version DESC LIMIT 1",
                (workflow_id,),
            ).fetchone()
            if not row:
                return None
            return self._row_to_context(row)

    def load_checkpoint(self, workflow_id: str, version: int) -> WorkflowContext | None:
        """加载指定版本检查点"""
        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT * FROM workflow_checkpoints WHERE workflow_id=? AND checkpoint_version=?",
                (workflow_id, version),
            ).fetchone()
            if not row:
                return None
            return self._row_to_context(row)

    def _row_to_context(self, row) -> WorkflowContext:
        """数据库行→WorkflowContext"""
        steps_data = json.loads(row["steps_json"]) if row["steps_json"] else []
        steps = []
        for sd in steps_data:
            step = WorkflowStep(
                step_id=sd.get("step_id", ""),
                step_name=sd.get("step_name", ""),
                status=StepStatus(sd.get("status", "pending")),
                started_at=sd.get("started_at"),
                completed_at=sd.get("completed_at"),
                duration_s=sd.get("duration_s", 0.0),
                input_data=sd.get("input_data", {}),
                output_data=sd.get("output_data", {}),
                error=sd.get("error"),
                retry_count=sd.get("retry_count", 0),
                compensation_fn=sd.get("compensation_fn"),
                compensation_args=sd.get("compensation_args", {}),
                compensated_at=sd.get("compensated_at"),
            )
            steps.append(step)

        ctx = WorkflowContext(
            workflow_id=row["workflow_id"],
            workflow_name=row["workflow_name"] or "",
            status=WorkflowStatus(row["status"]),
            steps=steps,
            current_step_index=row["current_step_index"],
            variables=json.loads(row["variables_json"])
            if row["variables_json"]
            else {},
            created_at=row["created_at"],
            last_checkpoint_at=row["updated_at"],
            checkpoint_version=row["checkpoint_version"],
            error=row["error"],
            metadata=json.loads(row["metadata_json"]) if row["metadata_json"] else {},
        )
        return ctx

    def list_workflows(self, status: str = None, limit: int = 50) -> list[dict]:
        """列出工作流"""
        with self._get_conn() as conn:
            if status:
                rows = conn.execute(
                    "SELECT DISTINCT workflow_id, workflow_name, status, updated_at "
                    "FROM workflow_checkpoints WHERE status=? "
                    "GROUP BY workflow_id ORDER BY updated_at DESC LIMIT ?",
                    (status, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT DISTINCT workflow_id, workflow_name, status, updated_at "
                    "FROM workflow_checkpoints "
                    "GROUP BY workflow_id ORDER BY updated_at DESC LIMIT ?",
                    (limit,),
                ).fetchall()
            return [dict(r) for r in rows]

    def log_event(
        self, workflow_id: str, event_type: str, step_id: str = "", data: dict = None
    ):
        """记录工作流事件 (用于审计/回放)"""
        with self._get_conn() as conn:
            conn.execute(
                "INSERT INTO workflow_events (event_id, workflow_id, event_type, step_id, event_data_json, timestamp) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (
                    f"evt-{uuid.uuid4().hex[:8]}",
                    workflow_id,
                    event_type,
                    step_id,
                    json.dumps(data or {}, ensure_ascii=False),
                    time.time(),
                ),
            )

    def get_events(self, workflow_id: str, limit: int = 100) -> list[dict]:
        """获取工作流事件历史"""
        with self._get_conn() as conn:
            rows = conn.execute(
                "SELECT * FROM workflow_events WHERE workflow_id=? ORDER BY timestamp ASC LIMIT ?",
                (workflow_id, limit),
            ).fetchall()
            return [dict(r) for r in rows]

    def delete_workflow(self, workflow_id: str):
        """删除工作流及所有检查点"""
        with self._get_conn() as conn:
            conn.execute(
                "DELETE FROM workflow_checkpoints WHERE workflow_id=?", (workflow_id,)
            )
            conn.execute(
                "DELETE FROM workflow_events WHERE workflow_id=?", (workflow_id,)
            )

    def get_stats(self) -> dict:
        """统计信息"""
        with self._get_conn() as conn:
            total = conn.execute(
                "SELECT COUNT(DISTINCT workflow_id) FROM workflow_checkpoints"
            ).fetchone()[0]
            completed = conn.execute(
                "SELECT COUNT(DISTINCT workflow_id) FROM workflow_checkpoints WHERE status='completed'"
            ).fetchone()[0]
            failed = conn.execute(
                "SELECT COUNT(DISTINCT workflow_id) FROM workflow_checkpoints WHERE status='failed'"
            ).fetchone()[0]
            running = conn.execute(
                "SELECT COUNT(DISTINCT workflow_id) FROM workflow_checkpoints WHERE status='running'"
            ).fetchone()[0]
            return {
                "total_workflows": total,
                "completed": completed,
                "failed": failed,
                "running": running,
                "db_path": str(self.db_path),
                "db_size_mb": round(self.db_path.stat().st_size / 1024 / 1024, 2)
                if self.db_path.exists()
                else 0,
            }


# ═══════════════════════════════════════════════════════════════
# Saga协调器
# ═══════════════════════════════════════════════════════════════


class SagaCoordinator:
    """
    Saga协调器 — 多步事务的补偿回滚

    借鉴Temporal的Saga模式:
      - 每步注册补偿函数
      - 任一步失败 → 逆序执行已成功步骤的补偿
      - 支持部分补偿 (跳过已补偿步骤)
    """

    def __init__(self, checkpoint_mgr: CheckpointManager):
        self.checkpoint_mgr = checkpoint_mgr

    def compensate(
        self, ctx: WorkflowContext, compensation_fns: dict[str, Callable] = None
    ) -> tuple[bool, str]:
        """
        执行Saga补偿 — 逆序回滚已完成步骤

        Args:
            ctx: 工作流上下文
            compensation_fns: {step_name: 补偿函数}

        Returns:
            (success, message)
        """
        ctx.status = WorkflowStatus.COMPENSATING
        self.checkpoint_mgr.save_checkpoint(ctx)
        self.checkpoint_mgr.log_event(ctx.workflow_id, "compensation_started")

        compensated_count = 0
        failed_compensations = []

        # 逆序遍历已完成的步骤
        for step in reversed(ctx.steps):
            if step.status != StepStatus.COMPLETED:
                continue
            if step.status == StepStatus.COMPENSATED:
                continue
            if not step.compensation_fn:
                continue

            try:
                logger.info(f"[Saga] ↩️ Compensating step: {step.step_name}")
                fn = (
                    compensation_fns.get(step.compensation_fn)
                    if compensation_fns
                    else None
                )
                if fn:
                    fn(**step.compensation_args, step_output=step.output_data)
                else:
                    logger.warning(
                        f"[Saga] No compensation function for: {step.compensation_fn}"
                    )

                step.status = StepStatus.COMPENSATED
                step.compensated_at = time.time()
                compensated_count += 1
                self.checkpoint_mgr.log_event(
                    ctx.workflow_id,
                    "step_compensated",
                    step.step_id,
                    {"step_name": step.step_name},
                )
            except Exception as e:
                logger.error(f"[Saga] ❌ Compensation failed for {step.step_name}: {e}")
                failed_compensations.append({"step": step.step_name, "error": str(e)})
                # 继续尝试补偿其他步骤 (best-effort)

        if failed_compensations:
            ctx.status = WorkflowStatus.FAILED
            ctx.error = f"Compensation partially failed: {failed_compensations}"
            self.checkpoint_mgr.save_checkpoint(ctx)
            return (
                False,
                f"{compensated_count} steps compensated, {len(failed_compensations)} failed",
            )

        ctx.status = WorkflowStatus.COMPENSATED
        self.checkpoint_mgr.save_checkpoint(ctx)
        self.checkpoint_mgr.log_event(ctx.workflow_id, "compensation_completed")
        return True, f"All {compensated_count} steps compensated successfully"


# ═══════════════════════════════════════════════════════════════
# 工作流运行器
# ═══════════════════════════════════════════════════════════════


class WorkflowRunner:
    """
    工作流运行器 — 持久化执行工作流

    使用方式:
      runner = WorkflowRunner(checkpoint_mgr)
      ctx = WorkflowContext(workflow_id="wf-001", workflow_name="deploy")

      # 注册步骤
      ctx.add_step("env_check", compensation_fn="rollback_env")
      ctx.add_step("deploy_code", compensation_fn="rollback_deploy")
      ctx.add_step("health_check")

      # 执行
      result = runner.run(ctx, step_fns={
          "env_check": check_environment,
          "deploy_code": deploy_to_server,
          "health_check": verify_health,
      })
    """

    def __init__(
        self,
        checkpoint_mgr: CheckpointManager,
        saga_coordinator: SagaCoordinator = None,
        max_step_retries: int = 3,
        retry_backoff_base: float = 2.0,
    ):
        self.checkpoint_mgr = checkpoint_mgr
        self.saga_coordinator = saga_coordinator or SagaCoordinator(checkpoint_mgr)
        self.max_step_retries = max_step_retries
        self.retry_backoff_base = retry_backoff_base
        self._running_workflows: dict[str, WorkflowContext] = {}
        self._lock = threading.Lock()

    def run(
        self,
        ctx: WorkflowContext,
        step_fns: dict[str, Callable],
        compensation_fns: dict[str, Callable] = None,
        resume_from_checkpoint: bool = True,
    ) -> tuple[bool, WorkflowContext]:
        """
        执行工作流

        Args:
            ctx: 工作流上下文
            step_fns: {step_name: 执行函数}
            compensation_fns: {compensation_fn_name: 补偿函数}
            resume_from_checkpoint: 是否从检查点恢复

        Returns:
            (success, updated_context)
        """
        # 尝试从检查点恢复
        if resume_from_checkpoint:
            saved = self.checkpoint_mgr.load_latest(ctx.workflow_id)
            if saved and saved.status == WorkflowStatus.RUNNING:
                logger.info(
                    f"[Workflow] 🔄 从检查点恢复: {ctx.workflow_id} v{saved.checkpoint_version}"
                )
                ctx = saved
            elif saved and saved.status == WorkflowStatus.SUSPENDED:
                logger.info(f"[Workflow] ▶️ 恢复暂停的工作流: {ctx.workflow_id}")
                ctx = saved

        ctx.status = WorkflowStatus.RUNNING
        ctx.started_at = ctx.started_at or time.time()
        self.checkpoint_mgr.save_checkpoint(ctx)
        self.checkpoint_mgr.log_event(ctx.workflow_id, "workflow_started")

        with self._lock:
            self._running_workflows[ctx.workflow_id] = ctx

        try:
            # 从当前步骤开始执行
            for i in range(ctx.current_step_index, len(ctx.steps)):
                step = ctx.steps[i]
                ctx.current_step_index = i

                # 跳过已完成步骤
                if step.status == StepStatus.COMPLETED:
                    logger.info(f"[Workflow] ⏭️ Skip completed: {step.step_name}")
                    continue
                if step.status == StepStatus.COMPENSATED:
                    logger.info(f"[Workflow] ⏭️ Skip compensated: {step.step_name}")
                    continue

                # 执行步骤
                success, output, error = self._execute_step(ctx, step, step_fns)

                if not success:
                    logger.error(
                        f"[Workflow] ❌ Step failed: {step.step_name} — {error}"
                    )
                    # 触发Saga补偿
                    if any(
                        s.status == StepStatus.COMPLETED and s.compensation_fn
                        for s in ctx.steps[:i]
                    ):
                        logger.info("[Workflow] ⚠️ Triggering Saga compensation...")
                        success, msg = self.saga_coordinator.compensate(
                            ctx, compensation_fns
                        )
                        ctx.error = f"Step '{step.step_name}' failed: {error}. Compensation: {msg}"
                    else:
                        ctx.error = f"Step '{step.step_name}' failed: {error}"

                    ctx.status = WorkflowStatus.FAILED
                    self.checkpoint_mgr.save_checkpoint(ctx)
                    self.checkpoint_mgr.log_event(ctx.workflow_id, "workflow_failed")
                    return False, ctx

                # 保存检查点
                self.checkpoint_mgr.save_checkpoint(ctx)
                self.checkpoint_mgr.log_event(
                    ctx.workflow_id,
                    "step_completed",
                    step.step_id,
                    {"step_name": step.step_name, "duration_s": step.duration_s},
                )

            # 全部完成
            ctx.status = WorkflowStatus.COMPLETED
            ctx.completed_at = time.time()
            self.checkpoint_mgr.save_checkpoint(ctx)
            self.checkpoint_mgr.log_event(ctx.workflow_id, "workflow_completed")

            logger.info(
                f"[Workflow] ✅ {ctx.workflow_name} completed: "
                f"{len(ctx.steps)} steps, {ctx.completed_at - ctx.started_at:.1f}s"
            )
            return True, ctx

        finally:
            with self._lock:
                self._running_workflows.pop(ctx.workflow_id, None)

    def _execute_step(
        self, ctx: WorkflowContext, step: WorkflowStep, step_fns: dict[str, Callable]
    ) -> tuple[bool, dict | None, str | None]:
        """执行单步 — 带重试"""
        fn = step_fns.get(step.step_name)
        if fn is None:
            return False, None, f"No function registered for step: {step.step_name}"

        step.status = StepStatus.RUNNING
        step.started_at = time.time()

        for attempt in range(self.max_step_retries + 1):
            try:
                step.retry_count = attempt
                result = fn(ctx)
                step.completed_at = time.time()
                step.duration_s = step.completed_at - step.started_at
                step.status = StepStatus.COMPLETED
                step.output_data = (
                    result if isinstance(result, dict) else {"result": str(result)}
                )
                return True, step.output_data, None

            except Exception as e:
                error_str = f"{type(e).__name__}: {str(e)}"
                logger.error(
                    f"[Workflow] Step {step.step_name} attempt {attempt + 1}/{self.max_step_retries + 1}: {error_str}"
                )
                if attempt < self.max_step_retries:
                    backoff = self.retry_backoff_base**attempt
                    time.sleep(backoff)
                    continue
                step.status = StepStatus.FAILED
                step.error = error_str
                step.completed_at = time.time()
                step.duration_s = step.completed_at - step.started_at
                return False, None, error_str

        return False, None, "Max retries exceeded"


# ═══════════════════════════════════════════════════════════════
# 装饰器 — 将普通函数变为持久化工作流
# ═══════════════════════════════════════════════════════════════


def durable_workflow(name: str = None, max_retries: int = 3):
    """
    装饰器: 将Python函数包装为持久化工作流

    使用:
      @durable_workflow("deploy_service")
      def deploy(env: str, version: str):
          yield "env_check", check_env, "rollback_env"
          yield "deploy", do_deploy, "rollback_deploy"
          yield "verify", verify, None
    """

    def decorator(func: Callable):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            workflow_name = name or func.__name__
            checkpoint_mgr = CheckpointManager()
            runner = WorkflowRunner(checkpoint_mgr)
            ctx = WorkflowContext(
                workflow_id=f"wf-{uuid.uuid4().hex[:8]}",
                workflow_name=workflow_name,
            )

            step_fns = {}
            compensation_fns = {}
            generator = func(*args, **kwargs)
            for item in generator:
                step_name, step_fn, comp_fn_name = item
                ctx.add_step(step_name, compensation_fn=comp_fn_name)
                step_fns[step_name] = step_fn
                if comp_fn_name:
                    # 补偿函数由调用者注册
                    pass

            success, ctx = runner.run(ctx, step_fns, compensation_fns)
            return success, ctx

        return wrapper

    return decorator


# ═══════════════════════════════════════════════════════════════
# 全局单例
# ═══════════════════════════════════════════════════════════════

_checkpoint_manager: CheckpointManager | None = None
_workflow_runner: WorkflowRunner | None = None
_durable_lock = threading.Lock()


def get_checkpoint_manager(db_path: str = None) -> CheckpointManager:
    """获取全局检查点管理器单例"""
    global _checkpoint_manager
    with _durable_lock:
        if _checkpoint_manager is None:
            _checkpoint_manager = CheckpointManager(db_path)
        return _checkpoint_manager


def get_workflow_runner(max_step_retries: int = 3) -> WorkflowRunner:
    """获取全局工作流运行器单例"""
    global _workflow_runner
    with _durable_lock:
        if _workflow_runner is None:
            mgr = get_checkpoint_manager()
            _workflow_runner = WorkflowRunner(mgr, max_step_retries=max_step_retries)
        return _workflow_runner
