# -*- coding: utf-8-sig -*-
"""status_routes_persist.py — 从 status_routes.py 拆分 (SSS-PhaseB)

persist功能组
源文件: status_routes.py
"""

import json
import os
import sys
import threading
import time
from typing import Any, Dict, List
from fastapi import APIRouter

# [FIX-AUDIT] 补充缺失的路径常量定义 (SSS拆分时遗漏)
_PERSIST_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "data", ".memory", "status_persist")
_CUMULATIVE_FILE = os.path.join(_PERSIST_DIR, "cumulative_counters.json")
_HISTORY_FILE = os.path.join(_PERSIST_DIR, "history_snapshots.json")

# [FIX-AUDIT] 补充global变量的初始定义 (否则import失败)
_cumulative_counters: Dict[str, Dict[str, float]] = {}
_history_snapshots: List[Dict[str, Any]] = []
_last_snapshot_ts: float = 0.0
_MODULE_ICONS: Dict[str, str] = {}

# [FIX-DASHBOARD-CUMULATIVE] 补充缺失的锁和常量定义 (SSS拆分时遗漏)
# 根因: _persist_data() 和 get_system_stats() 使用了这些变量但未定义
# 影响: dashboard累计数据tab显示异常 (0 + "-" + "+1 更多字段")
_cumulative_lock = threading.Lock()
_history_lock = threading.Lock()
_SNAPSHOT_INTERVAL = 60  # 秒 - 历史快照间隔
_PERSIST_INTERVAL = 60  # 秒 - 持久化落盘间隔
_last_persist_ts = 0.0  # 上次持久化时间戳


def _ensure_persist_dir():
    os.makedirs(_PERSIST_DIR, exist_ok=True)


def _load_persisted_data():
    global _cumulative_counters, _history_snapshots, _last_snapshot_ts
    _ensure_persist_dir()
    try:
        if os.path.exists(_CUMULATIVE_FILE):
            with open(_CUMULATIVE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                _cumulative_counters = {
                    k: {kk: float(vv) for kk, vv in v.items()} for k, v in data.items()
                }
    except Exception:
        pass
    try:
        if os.path.exists(_HISTORY_FILE):
            with open(_HISTORY_FILE, "r", encoding="utf-8") as f:
                _history_snapshots = json.load(f)
                if _history_snapshots:
                    _last_snapshot_ts = _history_snapshots[-1].get("timestamp", 0)
    except Exception:
        pass


def _persist_data():
    global _last_persist_ts
    now = time.time()
    if now - _last_persist_ts < _PERSIST_INTERVAL:
        return
    _last_persist_ts = now
    _ensure_persist_dir()
    try:
        with _cumulative_lock:
            serializable = {k: dict(v) for k, v in _cumulative_counters.items()}
        with open(_CUMULATIVE_FILE, "w", encoding="utf-8") as f:
            json.dump(serializable, f, ensure_ascii=False, indent=2)
    except Exception:
        pass
    try:
        with _history_lock:
            snapshots = list(_history_snapshots[-1440:])
        with open(_HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(snapshots, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


# 启动时加载持久化数据
_load_persisted_data()

MODULE_MAP = {
    "engine": {"name": "ICME核心引擎", "icon": "⏱"},
    "quality_gate": {"name": "质量门禁", "icon": "✅"},
    "memory_api": {"name": "天机记忆API", "icon": "📖"},
    "trae_conversation_capture": {"name": "对话全量捕获", "icon": "📥"},
    "auto_capture": {"name": "自动捕获", "icon": "👁"},
    "backup_manager": {"name": "备份管理器", "icon": "💾"},
    "deepseek_driver": {"name": "DeepSeek大脑", "icon": "🧠"},
    "enforcement_hook": {"name": "强制记录钩子", "icon": "⚓"},
    "skill_pipeline": {"name": "技能提取流水线", "icon": "⚙️"},
    "intelligent_scheduler": {"name": "智能调度器", "icon": "🎯"},
    "tvp_bridge": {"name": "TVP协议桥接", "icon": "🌉"},
    "agent_scheduler": {"name": "Agent调度器", "icon": "🤖"},
    "async_bridge": {"name": "异步桥接层", "icon": "⚡"},
    "skill_registry": {"name": "技能注册表", "icon": "📋"},
    "learning_engine": {"name": "学习引擎", "icon": "📚"},
    "workflow_engine": {"name": "工作流引擎", "icon": "🔄"},
    "message_gateway": {"name": "消息网关", "icon": "📨"},
    "evolution_engine": {"name": "进化引擎", "icon": "🧬"},
    "evolution_loop": {"name": "进化循环", "icon": "🔄"},
    "chain_dashboard": {"name": "8链能力仪表盘", "icon": "📊"},
    "standards_compliance": {"name": "标准合规 (P15-P17)", "icon": "📋"},
    "api_exposure": {"name": "API暴露层", "icon": "🔗"},
}

_FULL_MODULE_CATALOG = {
    "engine": {
        "import_path": "core.memory.engine.ICMEEngine",
        "alias": "ICME核心引擎",
        "init_args": {"_resolve": "engine"},
    },
    "deepseek_driver": {
        "import_path": "core.shared.deepseek_driver.DeepSeekDriver",
        "alias": "DeepSeek大脑",
        "init_args": {},
    },
    "enforcement_hook": {
        "import_path": "core.enforcement.mcp_bridge.EnforcementHookMCP",
        "alias": "强制记录钩子",
        "init_args": {},
    },
    "trae_conversation_capture": {
        "import_path": None,
        "alias": "对话全量捕获守护",
        "init_args": {},
    },
    "skill_pipeline": {"import_path": None, "alias": "技能提取流水线", "init_args": {}},
    "intelligent_scheduler": {
        "import_path": "core.orchestration.intelligent_scheduler.AutoSchedulerDaemon",
        "alias": "智能调度器",
        "init_args": {"_resolve": "intelligent_scheduler"},
    },
    "tvp_bridge": {
        "import_path": "core.orchestration.tvp_bridge.TVPBridge",
        "alias": "TVP协议桥接",
        "init_args": {},
    },
    "agent_scheduler": {
        "import_path": "core.orchestration.agent_orchestrator.AgentScheduler",
        "alias": "Agent调度器",
        "init_args": {"_resolve": "agent_scheduler"},
    },
    "workflow_engine": {
        "import_path": "core.orchestration.workflow_engine.WorkflowEngine",
        "alias": "工作流引擎",
        "init_args": {},
    },
    "message_gateway": {
        "import_path": "core.shared.message_gateway.MessageGateway",
        "alias": "消息网关",
        "init_args": {},
    },
    "evolution_engine": {
        "import_path": "core.processors.evolution_engine_core.EvolutionEngine",
        "alias": "进化引擎",
        "init_args": {},
    },
    "evolution_loop": {
        "import_path": "core.processors.evolution_loop.EvolutionLoop",
        "alias": "进化循环",
        "init_args": {},
    },
    "memory_api": {"import_path": None, "alias": "天机记忆API", "init_args": {}},
    "event_bus": {
        "import_path": None,
        "alias": "事件总线",
        "init_args": {},
    },
    "quality_gate": {
        "import_path": "core.processors.quality_gate_core.QualityGate",
        "alias": "质量门禁",
        "init_args": {},
    },
    "llm_bridge": {
        "import_path": "core.shared.llm_bridge.LLMBridge",
        "alias": "LLM桥接器",
        "init_args": {},
    },
    "deepseek_proactive": {
        "import_path": None,
        "alias": "DeepSeek主动增强",
        "init_args": {},
    },
    "auto_scheduler": {"import_path": None, "alias": "智能调度守护", "init_args": {}},
    "tvp_orchestrator": {
        "import_path": None,
        "alias": "TVP协议编排器",
        "init_args": {},
    },
    "evolution_bus": {
        "import_path": "core.processors.evolution_bus.EvolutionBus",
        "alias": "进化信号总线",
        "init_args": {},
    },
    "causal_recorder": {
        "import_path": "core.shared.driver.causal.CausalPairRecorder",
        "alias": "因果对记录器",
        "init_args": {},
    },
    "monitor_bridge": {"import_path": None, "alias": "监控桥接器", "init_args": {}},
    "realtime_monitor": {"import_path": None, "alias": "实时监控器", "init_args": {}},
    "hybrid_engine": {
        "import_path": "core.memory.hybrid_engine.ICMEStorageEngine",
        "alias": "混合检索引擎",
        "init_args": {},
    },
    "dynamic_data_injector": {
        "import_path": None,
        "alias": "动态数据注入器",
        "init_args": {},
    },
    "memory_router": {
        "import_path": "core.shared.router.LayerRouter",
        "alias": "记忆路由器",
        "init_args": {},
    },
    "skill_tracker": {
        "import_path": "core.shared.skill_registry.SkillLifecycleTracker",
        "alias": "Skill生命周期追踪",
        "init_args": {},
    },
    "chinese_tokenizer": {"import_path": None, "alias": "中文分词器", "init_args": {}},
    "encoding_safe": {"import_path": None, "alias": "编码安全模块", "init_args": {}},
    "namespace_manager": {
        "import_path": "core.shared.namespace_manager.NamespaceManager",
        "alias": "命名空间管理器",
        "init_args": {},
    },
    "conflict_resolver": {"import_path": None, "alias": "冲突解决器", "init_args": {}},
    "preference_drift_detector": {
        "import_path": None,
        "alias": "偏好漂移检测器",
        "init_args": {},
    },
    "daemon_watchdog": {"import_path": None, "alias": "守护看门狗", "init_args": {}},
    "daemon_autobackup": {
        "import_path": None,
        "alias": "守护自动备份",
        "init_args": {},
    },
    "daemon_autorepair": {
        "import_path": None,
        "alias": "守护自动修复",
        "init_args": {},
    },
    "daemon_integrity": {
        "import_path": None,
        "alias": "守护完整性检查",
        "init_args": {},
    },
    "agent_build": {"import_path": None, "alias": "Agent构建器", "init_args": {}},
    "agent_test": {"import_path": None, "alias": "Agent测试器", "init_args": {}},
    "agent_recovery": {"import_path": None, "alias": "Agent恢复器", "init_args": {}},
    "agent_pipeline_logger": {
        "import_path": None,
        "alias": "Agent流水线日志",
        "init_args": {},
    },
    "agent_orchestrator": {
        "import_path": "core.orchestration.pipeline.AgentPipeline",
        "alias": "Agent编排器",
        "init_args": {"_resolve": "agent_orchestrator"},
    },
    "sqlite_store": {
        "import_path": "core.memory.sqlite_store.SQLiteMemoryStore",
        "alias": "SQLite存储引擎",
        "init_args": {"_resolve": "sqlite_store"},
    },
    "config": {
        "import_path": "core.shared.config_models.ICMEConfig",
        "alias": "ICME配置中心",
        "init_args": {"_resolve": "config"},
    },
    "models": {
        "import_path": None,
        "alias": "Pydantic数据模型",
        "init_args": {},
    },
    "learning_loop": {
        "import_path": "core.processors.learning_loop_engine.ClosedLoopLearningEngine",
        "alias": "闭环学习引擎",
        "init_args": {"_resolve": "learning_loop"},
    },
    "governance_pipeline": {
        "import_path": "core.enforcement.governance_pipeline.GovernancePipeline",
        "alias": "治理流水线",
        "init_args": {"_resolve": "governance_pipeline"},
    },
    "search_indexer": {
        "import_path": "indexing.embeddings.EmbeddingService",
        "alias": "语义索引器",
        "init_args": {"_resolve": "search_indexer"},
    },
    "chain_dashboard": {
        "import_path": "core.shared.chain_dashboard.ChainDashboardBuilder",
        "alias": "8链能力仪表盘",
        "init_args": {},
    },
    "standards_compliance": {
        "import_path": "core.enforcement.standards_compliance.StandardsComplianceBridge",
        "alias": "标准合规 (P15-P17)",
        "init_args": {},
    },
    "api_exposure": {
        "import_path": "core.orchestration.api_exposure.APIEndpointRegistry",
        "alias": "API暴露层",
        "init_args": {},
    },
    "knowledge_extractor": {
        "import_path": "core.shared.knowledge_extractor.KnowledgeExtractor",
        "alias": "知识抽取器",
        "init_args": {},
    },
    "resilience": {
        "import_path": "core.enforcement.resilience.ResilienceManager",
        "alias": "韧性降级管理器",
        "init_args": {},
    },
    # [FIX-AUDIT-1/2-4/5-2/3] 补齐前端MODULE_CONTAINERS引用但catalog缺失的模块
    # 根因: 前端"强制记录系统/学习进化引擎/基础设施层"分类引用了这些模块,
    #       但它们不在_FULL_MODULE_CATALOG中, 若不在container则不进入modules_status,
    #       前端getModuleStatus返回'unknown', 导致显示1/2、4/5、2/3
    "auto_capture": {
        "import_path": None,
        "alias": "自动捕获",
        "init_args": {},
    },
    "backup_manager": {
        "import_path": None,
        "alias": "备份管理器",
        "init_args": {},
    },
    "skill_registry": {
        "import_path": None,
        "alias": "技能注册表",
        "init_args": {},
    },
    "learning_engine": {
        "import_path": None,
        "alias": "学习引擎",
        "init_args": {},
    },
    "async_bridge": {
        "import_path": None,
        "alias": "异步桥接层",
        "init_args": {},
    },
}

