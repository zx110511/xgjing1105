# -*- coding: utf-8-sig -*-
"""tianji_mcp_server_memory_graph.py — TianjiMCPServerMemory_GraphMixin (SSS-PhaseB)

从 tianji_mcp_server.py 拆分的方法组: memory_graph
"""

import io
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

# ── 共享常量 (从core导入) ──────────────────────────────
try:
    from tianji_mcp_server_core import (  # type: ignore
        SYSTEM_NAME, TIANJI_API_URL, _encoding_safe_dict, _encoding_safe_text
    )
except ImportError:
    try:
        from .tianji_mcp_server_core import (  # type: ignore
            SYSTEM_NAME, TIANJI_API_URL, _encoding_safe_dict, _encoding_safe_text
        )
    except ImportError:
        SYSTEM_NAME = "天机-忆库"
        TIANJI_API_URL = "http://127.0.0.1:8771"
        def _encoding_safe_text(t, l=""): return str(t)  # noqa: E701
        def _encoding_safe_dict(d, l=""): return d if isinstance(d, dict) else {}  # noqa: E701


class TianjiMCPServerMemory_GraphMixin:
    """memory_graph方法组Mixin"""

    def _handle_memory_build_graph(self, args: dict) -> dict:
        layer = args.get("layer", "episodic")
        limit = args.get("limit", 100)
        try:
            from agents.graphbuilder import GraphBuilderAgent

            # [FIX-MCP-Bug7] 从容器获取AMIM实例传入，避免AMIM未配置错误
            amim_instance = None
            try:
                from core.shared.tianji_container import get_container
                container = get_container()
                if container:
                    # 尝试多种AMIM获取方式
                    amim_instance = (
                        getattr(container, "_amim", None)
                        or (container._modules.get("amim").instance if container._modules.get("amim") else None)
                        or (container._modules.get("amim_manager").instance if container._modules.get("amim_manager") else None)
                    )
            except Exception:
                pass

            agent = GraphBuilderAgent(amim=amim_instance)
            result = agent.build_from_memory(layer=layer, limit=limit)
            return {"status": "success", **result, "system": SYSTEM_NAME}
        except Exception as e:
            return {"status": "error", "message": str(e), "system": SYSTEM_NAME}

    def _handle_memory_query_graph(self, args: dict) -> dict:
        query = args.get("query", "")
        hops = args.get("hops", 2)
        top_k = args.get("top_k", 10)
        try:
            from agents.graphbuilder import GraphBuilderAgent

            agent = GraphBuilderAgent()
            result = agent.query_graph(query=query, hops=hops, top_k=top_k)
            return {"status": "success", **result, "system": SYSTEM_NAME}
        except Exception as e:
            return {"status": "error", "message": str(e), "system": SYSTEM_NAME}

    def _handle_memory_evolve_self(self, args: dict) -> dict:
        goal = args.get("goal", "系统自优化")
        max_iterations = args.get("max_iterations", 10)
        try:
            from agents.evolver import EvolverAgent

            agent = EvolverAgent()
            result = agent.recursive_improve(goal=goal, max_iterations=max_iterations)
            return {"status": "success", **result, "system": SYSTEM_NAME}
        except Exception as e:
            return {"status": "error", "message": str(e), "system": SYSTEM_NAME}

    def _handle_memory_learn_skill(self, args: dict) -> dict:
        name = args.get("name", "")
        demonstration = args.get("demonstration", "")
        category = args.get("category", "general")
        try:
            from core.shared.skill_learner import memory_learn_skill

            result = memory_learn_skill(
                name=name, demonstration=demonstration, category=category
            )
            return {"status": "success", **result, "system": SYSTEM_NAME}
        except Exception as e:
            return {"status": "error", "message": str(e), "system": SYSTEM_NAME}

    def _handle_memory_capture_multimodal(self, args: dict) -> dict:
        content = args.get("content", "")
        modality_hint = args.get("modality_hint")
        context = args.get("context", "")
        layer = args.get("layer", "episodic")
        try:
            from agents.multimodal import memory_capture_multimodal

            result = memory_capture_multimodal(
                content=content,
                modality_hint=modality_hint,
                context=context,
                layer=layer,
            )
            return {"status": "success", **result, "system": SYSTEM_NAME}
        except Exception as e:
            return {"status": "error", "message": str(e), "system": SYSTEM_NAME}
