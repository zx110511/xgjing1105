# -*- coding: utf-8-sig -*-
"""tianji_daemon_tianjiautopilot.py — 主类组合层 (SSS-PhaseB拆分后)

TianjiAutopilot通过多继承Mixin组合各方法组。
"""

import os
import sys
from typing import Any, Optional
from .tianji_daemon_tianjiautopilot_core import TianjiAutopilotCoreMixin
from .tianji_daemon_tianjiautopilot_tasks_main import TianjiAutopilotTasks_MainMixin
from .tianji_daemon_tianjiautopilot_tasks_ops import TianjiAutopilotTasks_OpsMixin
from .tianji_daemon_tianjiautopilot_checks import TianjiAutopilotChecksMixin


from typing import Optional

class TianjiAutopilot(TianjiAutopilotCoreMixin, TianjiAutopilotTasks_MainMixin, TianjiAutopilotTasks_OpsMixin, TianjiAutopilotChecksMixin):
    """TianjiAutopilot — 组合各方法组Mixin"""
    TASK_CONFIGS_BASE = {
        "capacity": {
            "base_interval": 120,
            "min_interval": 30,
            "max_interval": 600,
            "priority": 1,
        },
        "consolidate": {
            "base_interval": 600,
            "min_interval": 120,
            "max_interval": 3600,
            "priority": 2,
        },
        "evolution": {
            "base_interval": 300,
            "min_interval": 60,
            "max_interval": 1800,
            "priority": 2,
        },
        "deep_learn": {
            "base_interval": 900,
            "min_interval": 300,
            "max_interval": 3600,
            "priority": 3,
        },
        "kg_build": {
            "base_interval": 1800,
            "min_interval": 600,
            "max_interval": 7200,
            "priority": 4,
        },
        "agent_dispatch": {
            "base_interval": 0,
            "min_interval": 0,
            "max_interval": 0,
            "priority": 1,
        },
        "security": {
            "base_interval": 3600,
            "min_interval": 900,
            "max_interval": 14400,
            "priority": 5,
        },
        "compliance": {
            "base_interval": 21600,
            "min_interval": 3600,
            "max_interval": 86400,
            "priority": 5,
        },
        "extract": {
            "base_interval": 0,
            "min_interval": 0,
            "max_interval": 0,
            "priority": 1,
        },
        "anomaly": {
            "base_interval": 300,
            "min_interval": 60,
            "max_interval": 1800,
            "priority": 2,
        },
        "autoheal": {
            "base_interval": 0,
            "min_interval": 0,
            "max_interval": 0,
            "priority": 1,
        },
        "skill_learn": {
            "base_interval": 1800,
            "min_interval": 600,
            "max_interval": 7200,
            "priority": 4,
        },
        "preference": {
            "base_interval": 600,
            "min_interval": 300,
            "max_interval": 3600,
            "priority": 4,
        },
        "mem_health": {
            "base_interval": 600,
            "min_interval": 300,
            "max_interval": 3600,
            "priority": 3,
        },
        "predict": {
            "base_interval": 600,
            "min_interval": 120,
            "max_interval": 3600,
            "priority": 3,
        },
        "rca": {
            "base_interval": 0,
            "min_interval": 0,
            "max_interval": 0,
            "priority": 1,
        },
        "resilience": {
            "base_interval": 300,
            "min_interval": 60,
            "max_interval": 1800,
            "priority": 2,
        },
        "scheduler": {
            "base_interval": 0,
            "min_interval": 0,
            "max_interval": 0,
            "priority": 1,
        },
        "threshold": {
            "base_interval": 900,
            "min_interval": 300,
            "max_interval": 3600,
            "priority": 3,
        },
        "correlation": {
            "base_interval": 600,
            "min_interval": 180,
            "max_interval": 3600,
            "priority": 4,
        },
    }
    _UNCOVERED_MODULES = [
        "workflow_engine",
        "message_gateway",
        "monitor_bridge",
        "evolution_bus",
        "event_bus",
        "lingjing_bus",
        "service_registry",
        "async_bridge",
        "hybrid_engine",
        "llm_bridge",
        "dynamic_data_injector",
        "tvp_orchestrator",
        "realtime_monitor",
        "deepseek_proactive",
        "memory_router",
        "chinese_tokenizer",
        "encoding_safe",
        "namespace_manager",
        "conflict_resolver",
        "preference_drift_detector",
        "tvp_bridge",
        "backup_manager",
        "daemon_watchdog",
        "daemon_autobackup",
        "daemon_autorepair",
        "daemon_integrity",
        "agent_build",
        "agent_test",
        "agent_recovery",
        "agent_pipeline_logger",
        "agent_runtime_recovery",
        "chain_dashboard",
        "api_exposure",
        "search_indexer",
    ]
    _DAEMON_TASKS = [
        "daemon_main_loop",
        "rest_api_server",
        "websocket_server",
        "sse_monitor",
        "chat_pipeline",
        "frontend_dashboard",
    ]
    TASK_CONFIGS = {}  # Built dynamically in __init__


__all__ = ["TianjiAutopilot"]
