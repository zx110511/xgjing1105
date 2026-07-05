r"""
天机调度 - 自然语言定时调度引擎 (Cron Parser) [v10-ready]
===========================================================
借鉴 Hermes 的自然语言定时调度: "每周一早上9点运行三个并行分析"。

核心能力:
  - parse_natural_language — DeepSeek/规则双链路将自然语言解析为 cron 表达式
  - add_task / remove_task / list_tasks — 定时任务 CRUD
  - start / stop — 后台 60s tick 主循环 (如同 Hermes cron 模块)

从 core/intelligent_scheduler.py 拆分而来 (原 NaturalLanguageCronEngine)。
"""

import time
import json
import hashlib
import logging
import threading
from typing import Any, Dict, List
from datetime import datetime

from core.scheduling import CronTask, SubAgentTask, SubAgentResult, SubAgentStatus
from core.scheduling.executor import BatchExecutor

logger = logging.getLogger("tianji.scheduler")


class CronParser:
    """借鉴Hermes的自然语言定时调度: "每周一早上9点运行三个并行分析"

    Hermes cron架构:
      - cron/ 独立模块
      - 每60秒tick
      - 处理调度任务
      - 结果发布到gateway
    """

    def __init__(self, delegation_engine: BatchExecutor,
                 decision_engine=None, memory_api_url: str = "http://127.0.0.1:8771"):
        self.delegation_engine = delegation_engine
        self.decision_engine = decision_engine
        self.memory_api_url = memory_api_url
        self._tasks: Dict[str, CronTask] = {}
        self._running = False
        self._thread = None
        self._lock = threading.Lock()

    def parse_natural_language(self, nl_schedule: str) -> Dict[str, Any]:
        """DeepSeek解析自然语言为cron表达式

        示例:
          "每周一早上9点" → {"cron": "0 9 * * 1", "interval_s": 604800}
          "每小时" → {"cron": "0 * * * *", "interval_s": 3600}
          "每天凌晨3点" → {"cron": "0 3 * * *", "interval_s": 86400}
        """
        if self.decision_engine and self.decision_engine.is_ready:
            prompt = f"""将以下自然语言时间表达式解析为cron格式:

表达式: {nl_schedule}

返回JSON:
{{"cron": "cron表达式(5字段)", "interval_s": 秒数, "readable": "人类可读描述", "confidence": 0.9}}"""
            try:
                result = self.decision_engine.client.chat_sync(prompt, expect_json=True)
                if "cron" in result:
                    return result
            except Exception:
                pass

        schedule_lower = nl_schedule.lower()
        if "每分钟" in schedule_lower or "per minute" in schedule_lower:
            return {"cron": "* * * * *", "interval_s": 60, "readable": "每分钟", "confidence": 0.9}
        if "每小时" in schedule_lower or "hourly" in schedule_lower:
            return {"cron": "0 * * * *", "interval_s": 3600, "readable": "每小时", "confidence": 0.9}
        if "每天" in schedule_lower or "daily" in schedule_lower:
            return {"cron": "0 0 * * *", "interval_s": 86400, "readable": "每天午夜", "confidence": 0.8}
        if "每周" in schedule_lower or "weekly" in schedule_lower:
            return {"cron": "0 0 * * 0", "interval_s": 604800, "readable": "每周日午夜", "confidence": 0.8}

        return {"cron": "0 0 * * *", "interval_s": 86400, "readable": "每天(默认)", "confidence": 0.3}

    def add_task(self, nl_schedule: str, goal: str, context: str = "",
                 toolsets: List[str] = None, platform: str = "auto") -> str:
        """添加定时任务 — 如Hermes的"每天早上9点发送报告" """
        parsed = self.parse_natural_language(nl_schedule)
        now = time.time()
        cron_id = hashlib.md5(f"{nl_schedule}:{goal}:{now}".encode()).hexdigest()[:12]

        task = CronTask(
            cron_id=cron_id,
            natural_language_schedule=nl_schedule,
            parsed_schedule=parsed,
            goal=goal,
            context=context,
            toolsets=toolsets or [],
            platform=platform,
            next_run=now + parsed.get("interval_s", 3600),
        )

        with self._lock:
            self._tasks[cron_id] = task

        logger.info(f"[Cron] Added task: {cron_id} - '{nl_schedule}' → {goal[:60]}")
        return cron_id

    def remove_task(self, cron_id: str) -> bool:
        with self._lock:
            if cron_id in self._tasks:
                del self._tasks[cron_id]
                return True
            return False

    def list_tasks(self) -> List[Dict]:
        with self._lock:
            return [
                {
                    "cron_id": t.cron_id,
                    "schedule": t.natural_language_schedule,
                    "goal": t.goal[:100],
                    "enabled": t.enabled,
                    "next_run": datetime.fromtimestamp(t.next_run).isoformat() if t.next_run else None,
                    "run_count": t.run_count,
                }
                for t in self._tasks.values()
            ]

    def start(self):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._cron_loop, daemon=True)
        self._thread.start()
        logger.info("[Cron] Natural language scheduler started")

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
        logger.info("[Cron] Scheduler stopped")

    def _cron_loop(self):
        """定时器主循环 — 每60秒tick (如同Hermes的cron模块)"""
        while self._running:
            try:
                now = time.time()
                with self._lock:
                    for task in list(self._tasks.values()):
                        if not task.enabled or task.next_run is None:
                            continue
                        if now >= task.next_run:
                            self._execute_cron_task(task)
                            task.next_run = now + task.parsed_schedule.get("interval_s", 3600)
                            task.last_run = now
                            task.run_count += 1
            except Exception as e:
                logger.error(f"[Cron] Loop error: {e}")
            time.sleep(60)

    def _execute_cron_task(self, task: CronTask):
        logger.info(f"[Cron] Executing: {task.cron_id} - {task.goal[:60]}")
        sub_task = SubAgentTask(
            task_id=task.cron_id,
            goal=task.goal,
            context=task.context,
            toolsets=task.toolsets,
            timeout_s=300,
        )
        try:
            result = self.delegation_engine.delegate_single(sub_task)
            if result.status == SubAgentStatus.FAILED:
                task.error_count += 1
            self._store_cron_result(task, result)
        except Exception as e:
            task.error_count += 1
            logger.error(f"[Cron] Task {task.cron_id} failed: {e}")

    def _store_cron_result(self, task: CronTask, result: SubAgentResult):
        try:
            import urllib.request
            content = json.dumps({
                "type": "cron_execution",
                "cron_id": task.cron_id,
                "schedule": task.natural_language_schedule,
                "goal": task.goal[:200],
                "result": result.summary[:500],
                "run_count": task.run_count,
            }, ensure_ascii=False)
            data = json.dumps({
                "content": content,
                "layer": "episodic",
                "tags": ["cron", "scheduled", result.status.value],
                "priority": "low",
            }, ensure_ascii=False).encode("utf-8")
            req = urllib.request.Request(
                f"{self.memory_api_url}/api/memory/",
                data=data,
                headers={"Content-Type": "application/json; charset=utf-8"},
                method="POST",
            )
            urllib.request.urlopen(req, timeout=5)
        except Exception:
            pass


# 兼容别名: 原 Hermes 命名
NaturalLanguageCronEngine = CronParser
