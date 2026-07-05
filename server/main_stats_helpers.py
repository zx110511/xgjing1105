# -*- coding: utf-8-sig -*-
"""main_stats_helpers.py — 从 main.py 拆分 (SSS-PhaseB)

stats_helpers功能组
源文件: main.py
"""

import json
import os
import signal
import sqlite3
import sys
import threading
import time
from pathlib import Path
try:
    from dotenv import load_dotenv
    _dotenv_path = Path(__file__).resolve().parent.parent / ".env"
    load_dotenv(_dotenv_path, override=True)
except ImportError:
    pass


def _get_evolution_stats(evolution_type: str) -> dict:
    try:
        from core.processors.evolution_engine import EvolutionEngine
        from core.processors.evolution_loop import EvolutionBus, EvolutionLoop

        if evolution_type == "engine":
            engines = [
                obj for obj in globals().values() if isinstance(obj, EvolutionEngine)
            ]
            return engines[0].get_stats() if engines else {}
        elif evolution_type == "loop":
            loops = [
                obj
                for obj in globals().values()
                if isinstance(obj, (EvolutionLoop, EvolutionBus))
            ]
            return loops[0].get_stats() if loops else {}
    except Exception as e:
        return {"error": str(e)}
    return {}


def _get_daemon_stats(daemon_type: str) -> dict:
    try:
        from daemon.tianji_daemon import TianjiDaemon

        daemons = [obj for obj in globals().values() if isinstance(obj, TianjiDaemon)]
        if daemons:
            daemon = daemons[0]
            if daemon_type == "watchdog" and hasattr(daemon, "watchdog"):
                return {
                    "status": "active",
                    "checks_performed": getattr(daemon.watchdog, "_checks", 0),
                }
            elif daemon_type == "autobackup" and hasattr(daemon, "autobackup"):
                return {
                    "status": "active",
                    "backups_done": getattr(daemon.autobackup, "_backups", 0),
                }
            elif daemon_type == "autorepair" and hasattr(daemon, "autorepair"):
                return {
                    "status": "active",
                    "repairs_done": getattr(daemon.autorepair, "_repairs", 0),
                }
            elif daemon_type == "integrity" and hasattr(daemon, "integrity_checker"):
                return {
                    "status": "active",
                    "checks_done": getattr(daemon.integrity_checker, "_checks", 0),
                }
    except Exception as e:
        return {"error": str(e)}
    return {"status": "not_initialized"}


def _get_agent_stats(agent_type: str) -> dict:
    try:
        agent_map = {
            "build": ("agents.build_agent", "BuildAgent"),
            "test": ("agents.test_agent", "TestAgent"),
            "recovery": ("agents.recovery_agent", "RecoveryAgent"),
            "pipeline_logger": ("agents.pipeline_logger", "PipelineLogger"),
            "orchestrator": ("agents.orchestrator", "OrchestratorAgent"),
            "runtime_recovery": ("agents.runtime_recovery", "RuntimeRecoveryAgent"),
        }

        if agent_type in agent_map:
            module_path, class_name = agent_map[agent_type]
            import importlib

            module = importlib.import_module(module_path)
            cls = getattr(module, class_name, None)
            if cls:
                instances = [obj for obj in globals().values() if isinstance(obj, cls)]
                if instances:
                    instance = instances[0]
                    if hasattr(instance, "get_stats"):
                        return instance.get_stats()
                    return {"status": "active", "class": class_name}
    except Exception as e:
        return {"error": str(e)}
    return {"status": "not_initialized"}


def _get_adapter_stats(adapter_type: str) -> dict:
    try:
        if adapter_type == "unified":
            from adapters.unified_adapter import UnifiedMemoryAdapter

            adapters = [
                obj
                for obj in globals().values()
                if isinstance(obj, UnifiedMemoryAdapter)
            ]
            return adapters[0].get_stats() if adapters else {}
        elif adapter_type == "registry":
            from adapters.ai_platform_adapters import AdapterRegistry

            registries = [
                obj for obj in globals().values() if isinstance(obj, AdapterRegistry)
            ]
            if registries:
                reg = registries[0]
                return {
                    "registered_adapters": len(getattr(reg, "_adapters", {})),
                    "active_adapters": sum(
                        1
                        for a in getattr(reg, "_adapters", {}).values()
                        if getattr(a, "enabled", False)
                    ),
                }
    except Exception as e:
        return {"error": str(e)}
    return {}


def _get_indexing_stats(indexing_type: str) -> dict:
    try:
        indexing_map = {
            "embeddings": ("indexing.embeddings", "EmbeddingService"),
            "summarizer": ("indexing.summarizer", "AutoSummarizer"),
            "knowledge_graph": ("indexing.knowledge_graph", "KnowledgeGraph"),
            "cognition": ("indexing.cognition", "CognitionPipeline"),
        }

        if indexing_type in indexing_map:
            module_path, class_name = indexing_map[indexing_type]
            import importlib

            module = importlib.import_module(module_path)
            cls = getattr(module, class_name, None)
            if cls:
                instances = [obj for obj in globals().values() if isinstance(obj, cls)]
                if instances:
                    instance = instances[0]
                    if hasattr(instance, "get_stats"):
                        return instance.get_stats()
                    return {"status": "active", "class": class_name}
    except Exception as e:
        return {"error": str(e)}
    return {"status": "not_initialized"}


def _get_llm_stats() -> dict:
    """获取LLM统计 — 优先从LLMBridge真实数据源读取"""
    try:
        from server.deps import llm_bridge

        if llm_bridge is not None and hasattr(llm_bridge, "get_stats"):
            stats = llm_bridge.get_stats()
            return {
                "is_ready": stats.get("is_ready", False),
                "status": stats.get("status", "unknown"),
                "total_calls": stats.get("total_calls", 0),
                "successful_calls": stats.get("successful_calls", 0),
                "failed_calls": stats.get("failed_calls", 0),
                "fallback_calls": stats.get("fallback_calls", 0),
                "classify_ops": stats.get("classify_ops", 0),
                "tag_ops": stats.get("tag_ops", 0),
                "assess_ops": stats.get("assess_ops", 0),
                "decide_ops": stats.get("decide_ops", 0),
                "extract_ops": stats.get("extract_ops", 0),
                "summarize_ops": stats.get("summarize_ops", 0),
                "enrich_remember_ops": stats.get("enrich_remember_ops", 0),
                "enrich_recall_ops": stats.get("enrich_recall_ops", 0),
                "evo_loop_active": stats.get("evo_loop_active", False),
                "recorder_attached": stats.get("recorder_attached", False),
                "errors": stats.get("errors", 0),
            }
    except Exception as e:
        return {"error": str(e)}

    # 回退: 尝试从llm_layer读取
    try:
        from server.deps import llm_layer

        if llm_layer is not None:
            return {
                "is_ready": getattr(llm_layer, "is_ready", False),
                "model": getattr(getattr(llm_layer, "client", None), "config", None),
                "total_calls": 0,
                "note": "仅llm_layer可用, 无详细统计",
            }
    except Exception:
        pass
    return {"is_ready": False, "status": "not_initialized"}


def _get_llm_decision_stats() -> dict:
    """获取LLM决策引擎统计 — v9.1: 接入LLMBridge真实数据"""
    try:
        from server.deps import llm_bridge

        if llm_bridge is not None and hasattr(llm_bridge, "get_stats"):
            stats = llm_bridge.get_stats()
            return {
                "decisions_made": stats.get("decide_ops", 0),
                "classifications": stats.get("classify_ops", 0),
                "value_assessments": stats.get("assess_ops", 0),
                "knowledge_extractions": stats.get("extract_ops", 0),
                "summarizations": stats.get("summarize_ops", 0),
                "query_expansions": stats.get("expand_ops", 0),
                "total_calls": stats.get("total_calls", 0),
                "successful_calls": stats.get("successful_calls", 0),
                "failed_calls": stats.get("failed_calls", 0),
            }
    except Exception:
        pass

    # 回退: 尝试从llm_layer (MemoryDecisionEngine) 读取
    try:
        from server.deps import llm_layer

        if llm_layer is not None:
            return {
                "decisions_made": getattr(llm_layer, "_decisions", 0),
                "cache_hits": getattr(llm_layer, "_cache_hits", 0),
                "cache_misses": getattr(llm_layer, "_cache_misses", 0),
                "is_ready": getattr(llm_layer, "is_ready", False),
            }
    except Exception:
        pass
    return {}


def _get_llm_cache_stats() -> dict:
    try:
        from llm_integration.cache import ResponseCache

        caches = [obj for obj in globals().values() if isinstance(obj, ResponseCache)]
        if caches:
            cache = caches[0]
            return {
                "size": len(getattr(cache, "_cache", {})),
                "hits": getattr(cache, "_hits", 0),
                "misses": getattr(cache, "_misses", 0),
            }
    except Exception as e:
        return {"error": str(e)}
    return {}

