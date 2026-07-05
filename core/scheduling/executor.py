r"""
天机调度 - 并行批量子代理执行器 (Batch Executor) [v10-ready]
==============================================================
借鉴 Hermes 的 delegate_task: 隔离上下文 + 受限工具集 + 独立会话。
负责子代理的单个/批量并行执行、中断传播、结果回写记忆。

核心能力:
  - delegate_single  — 委派单个子代理 (隔离HTTP执行)
  - delegate_batch   — ThreadPoolExecutor 并行批量执行 + 超时控制
  - interrupt_all    — 中断传播 (取消所有未完成 future)

从 core/intelligent_scheduler.py 拆分而来 (原 SubAgentDelegationEngine)。
"""

import time
import json
import logging
import threading
from typing import Any, Dict, List
from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError

from core.scheduling import SubAgentTask, SubAgentResult, SubAgentStatus

logger = logging.getLogger("tianji.scheduler")


class BatchExecutor:
    """借鉴Hermes的delegate_task: 隔离上下文 + 受限工具集 + 独立会话"""

    def __init__(self, memory_api_url: str = "http://127.0.0.1:8771",
                 event_bus=None, max_concurrency: int = 8):
        self.memory_api_url = memory_api_url
        self.event_bus = event_bus
        self.max_concurrency = max_concurrency
        self._executor = None
        self._results: Dict[str, SubAgentResult] = {}
        self._lock = threading.Lock()
        self._interrupted = False

    def delegate_single(self, task: SubAgentTask) -> SubAgentResult:
        """委派单个子代理 — 如同Hermes的delegate_task(goal=..., context=..., toolsets=[...])"""
        task_id = task.task_id
        logger.info(f"[Delegate] Starting sub-agent: {task_id} - {task.goal[:60]}")

        start_time = time.time()
        try:
            result_data = self._execute_in_isolation(task)
            duration = time.time() - start_time

            result = SubAgentResult(
                task_id=task_id,
                status=SubAgentStatus.COMPLETED if result_data.get("success") else SubAgentStatus.FAILED,
                summary=result_data.get("summary", ""),
                findings=result_data.get("findings", []),
                files_modified=result_data.get("files_modified", []),
                errors=result_data.get("errors", []),
                tool_calls_count=result_data.get("tool_calls", 0),
                duration_s=duration,
                model_used=task.model,
            )
        except Exception as e:
            duration = time.time() - start_time
            result = SubAgentResult(
                task_id=task_id,
                status=SubAgentStatus.FAILED,
                summary=f"子代理执行失败: {e}",
                errors=[str(e)],
                duration_s=duration,
                model_used=task.model,
            )

        with self._lock:
            self._results[task_id] = result

        self._store_result_to_memory(result, task)

        if self.event_bus:
            try:
                from core.shared.deepseek_driver import TianjiEvent, EventType
                self.event_bus.publish(TianjiEvent(
                    event_type=EventType.MCP_TOOL_CALL,
                    source="subagent_delegation",
                    payload={
                        "task_id": task_id,
                        "status": result.status.value,
                        "summary": result.summary[:200],
                    },
                ))
            except Exception:
                pass

        return result

    def delegate_batch(self, tasks: List[SubAgentTask]) -> List[SubAgentResult]:
        """并行批量委派 — 如同Hermes的delegate_task(tasks=[{...}, {...}])"""
        logger.info(f"[Delegate] Starting parallel batch: {len(tasks)} tasks, "
                     f"max_concurrency={self.max_concurrency}")

        self._interrupted = False
        self._executor = ThreadPoolExecutor(max_workers=self.max_concurrency)
        futures = {}
        for task in tasks:
            future = self._executor.submit(self.delegate_single, task)
            futures[future] = task.task_id

        results = []
        try:
            for future in as_completed(futures, timeout=max(t.timeout_s for t in tasks) + 10):
                if self._interrupted:
                    for f in futures:
                        f.cancel()
                    break
                try:
                    result = future.result(timeout=30)
                    results.append(result)
                except TimeoutError:
                    task_id = futures[future]
                    results.append(SubAgentResult(
                        task_id=task_id,
                        status=SubAgentStatus.TIMEOUT,
                        summary="子代理超时",
                        errors=["执行超时"],
                    ))
        except TimeoutError:
            for f in futures:
                f.cancel()
            logger.warning("Batch execution timeout, cancelling remaining tasks")

        results.sort(key=lambda r: r.task_id)
        logger.info(f"[Delegate] Batch complete: {len(results)} results")
        return results

    def interrupt_all(self):
        """中断所有子代理 — 如同Hermes的中断传播"""
        self._interrupted = True
        if self._executor:
            self._executor.shutdown(wait=False, cancel_futures=True)
        logger.info("[Delegate] All sub-agents interrupted")

    def _execute_in_isolation(self, task: SubAgentTask) -> Dict[str, Any]:
        """在隔离上下文中执行子代理"""
        try:
            import urllib.request
            payload = json.dumps({
                "goal": task.goal,
                "context": task.context,
                "toolsets": task.toolsets,
                "model": task.model,
                "timeout_s": task.timeout_s,
                "session_id": task.parent_session_id,
            }, ensure_ascii=False).encode("utf-8")

            req = urllib.request.Request(
                f"{self.memory_api_url}/api/active/subagent_execute",
                data=payload,
                headers={"Content-Type": "application/json; charset=utf-8"},
                method="POST",
            )
            r = urllib.request.urlopen(req, timeout=task.timeout_s + 10)
            return json.loads(r.read().decode("utf-8"))
        except Exception as e:
            logger.error(f"Sub-agent {task.task_id} execution failed: {e}")
            return {
                "success": False,
                "summary": f"执行失败: {e}",
                "errors": [str(e)],
                "tool_calls": 0,
            }

    def _store_result_to_memory(self, result: SubAgentResult, task: SubAgentTask):
        try:
            import urllib.request
            content = json.dumps({
                "type": "subagent_result",
                "task_id": result.task_id,
                "goal": task.goal[:200],
                "status": result.status.value,
                "summary": result.summary[:500],
                "findings": result.findings[:10],
                "duration_s": result.duration_s,
                "model_used": result.model_used,
            }, ensure_ascii=False)
            data = json.dumps({
                "content": content,
                "layer": "episodic",
                "tags": ["subagent", "delegation", result.status.value],
                "priority": "medium" if result.status == SubAgentStatus.COMPLETED else "high",
            }, ensure_ascii=False).encode("utf-8")
            req = urllib.request.Request(
                f"{self.memory_api_url}/api/memory/",
                data=data,
                headers={"Content-Type": "application/json; charset=utf-8"},
                method="POST",
            )
            r = urllib.request.urlopen(req, timeout=5)
            if r.status in (200, 201):
                mem_result = json.loads(r.read().decode("utf-8"))
                result.memory_ids = [mem_result.get("memory_id", "")]
        except Exception:
            pass

    def get_results(self) -> Dict[str, SubAgentResult]:
        with self._lock:
            return dict(self._results)

    def shutdown(self):
        if self._executor:
            self._executor.shutdown(wait=True, cancel_futures=True)


# 兼容别名: 原 Hermes 命名
SubAgentDelegationEngine = BatchExecutor
