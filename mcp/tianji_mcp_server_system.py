# -*- coding: utf-8-sig -*-
"""tianji_mcp_server_system.py — TianjiMCPServerSystemMixin (SSS-PhaseB)

从 tianji_mcp_server.py 拆分的方法组: system
"""

# ── 共享常量 (从core导入) ──────────────────────────────
try:
    from tianji_mcp_server_core import (  # type: ignore
        ADVANCED_TOOLS,
        ALL_TOOLS,
        BASIC_TOOLS,
        SYSTEM_NAME,
        SYSTEM_TAG,
        SYSTEM_VERSION,
        TIANJI_API_URL,
        TOOL_AGENT_MAPPING,
        _encoding_safe_dict,
        _encoding_safe_text,
    )
except ImportError:
    try:
        from .tianji_mcp_server_core import (  # type: ignore
            ADVANCED_TOOLS,
            ALL_TOOLS,
            BASIC_TOOLS,
            SYSTEM_NAME,
            SYSTEM_TAG,
            SYSTEM_VERSION,
            TIANJI_API_URL,
            TOOL_AGENT_MAPPING,
            _encoding_safe_dict,
            _encoding_safe_text,
        )
    except ImportError:
        SYSTEM_NAME = "天机-忆库"
        SYSTEM_VERSION = "9.1.0"
        SYSTEM_TAG = "MEM-ENGINE"  # noqa: E701
        ALL_TOOLS = []
        BASIC_TOOLS = []
        ADVANCED_TOOLS = []  # noqa: E701
        TOOL_AGENT_MAPPING = {}
        TIANJI_API_URL = "http://127.0.0.1:8771"  # noqa: E701

        def _encoding_safe_text(t, l=""):
            return str(t)  # noqa: E701

        def _encoding_safe_dict(d, l=""):
            return d if isinstance(d, dict) else {}  # noqa: E701


class TianjiMCPServerSystemMixin:
    """system方法组Mixin"""

    def _handle_intercept(self, args: dict) -> dict:
        context = args.get("context", {})
        # API expects dict, but MCP schema may pass string — auto-convert
        if isinstance(context, str):
            try:
                import json

                context = json.loads(context)
            except Exception:
                context = {}
        if not isinstance(context, dict):
            context = {}
        if isinstance(context, dict):
            sid = context.get("session_id", "")
            if sid:
                self._current_session_id = sid
        data = {
            "platform": args.get("platform", "trae"),
            "user_input": args.get("user_input", ""),
            "context": context,
        }
        result = self._api_post("/api/active/intercept_input", data)
        if result and not result.get("error"):
            return {
                "status": "success",
                "enhanced_input": result.get("enhanced_input", ""),
                "related_count": result.get("related_count", 0),
                "system": SYSTEM_NAME,
            }
        return {"status": "error", "detail": result}

    def _handle_export(self, args: dict) -> dict:
        result = self._api_post("/api/memory/export", {})
        if result and not result.get("error"):
            return {"status": "success", "export_data": result, "system": SYSTEM_NAME}
        return {"status": "error", "detail": result}

    def _handle_summarize_conv(self, args: dict) -> dict:
        data = {
            "conversation_id": args.get("conversation_id", ""),
            "max_length": args.get("max_length", 500),
            "extract_decisions": args.get("extract_decisions", True),
        }
        result = self._api_post("/api/summary/conversation", data)
        if result and not result.get("error"):
            return {
                "status": "success",
                "conversation_id": data["conversation_id"],
                "summary": result.get("summary", ""),
                "key_points": result.get("key_points", []),
                "decisions": result.get("decisions", []),
                "entities": result.get("entities", []),
                "agent_contributions": result.get("agent_contributions", {}),
                "system": SYSTEM_NAME,
            }
        if isinstance(result, dict) and "404" in str(result.get("error", "")):
            return {
                "status": "not_found",
                "conversation_id": data["conversation_id"],
                "message": "未找到该会话的记忆",
                "system": SYSTEM_NAME,
            }
        return {"status": "error", "detail": result}

    def _handle_health(self, args: dict) -> dict:
        result = self._api_get("/api/health")
        if result and not result.get("error"):
            return {"status": "success", "health": result, "system": SYSTEM_NAME}
        return {"status": "unavailable", "api_url": self.api_url}

    def _handle_help(self, args: dict) -> dict:
        return {
            "system": SYSTEM_NAME,
            "version": SYSTEM_VERSION,
            "tag": SYSTEM_TAG,
            "api_url": self.api_url,
            "tools": [
                {"name": t["name"], "description": t.get("description", "")[:80]}
                for t in ALL_TOOLS
            ],
            "basic_tools": len(BASIC_TOOLS),
            "advanced_tools": len(ADVANCED_TOOLS),
            "total_tools": len(ALL_TOOLS),
        }

    def _handle_tool_owner(self, args: dict) -> dict:
        tool_name = args.get("tool_name", "")
        if self._amim is None:
            return {
                "status": "unavailable",
                "message": "AMIM M37 未初始化",
                "system": SYSTEM_NAME,
            }
        try:
            from core.memory.amim import TOOL_AGENT_MAPPING as _LIVE_TAM
        except Exception:
            _LIVE_TAM = TOOL_AGENT_MAPPING
        if tool_name not in _LIVE_TAM:
            return {
                "status": "not_found",
                "tool_name": tool_name,
                "message": "工具不在 AMIM 映射中",
                "system": SYSTEM_NAME,
            }
        mapping = _LIVE_TAM[tool_name]
        owner_id = mapping.get("owner", "unknown")
        owner_agent = self._amim.get_agent(owner_id)
        result = {
            "status": "success",
            "tool_name": tool_name,
            "owner_agent_id": owner_id,
            "delegate_agents": mapping.get("delegates", []),
            "description": mapping.get("description", ""),
            "system": SYSTEM_NAME,
        }
        if owner_agent:
            result["owner_name"] = owner_agent.name
            result["owner_emoji"] = owner_agent.emoji
            result["owner_layer"] = f"L{owner_agent.layer.value}"
            result["owner_role"] = owner_agent.role
            result["mcp_server"] = owner_agent.mcp_server
            result["owner_capabilities"] = owner_agent.capabilities
        return result

    def _handle_amim_status(self, args: dict) -> dict:
        if self._amim is None:
            return {
                "status": "unavailable",
                "message": "AMIM M37 未初始化",
                "amim_available": self._amim is not None,
                "system": SYSTEM_NAME,
            }
        definitions = self._amim.AGENT_DEFINITIONS or []
        return {
            "status": "success",
            "amim_version": self._amim.VERSION,
            "module_id": self._amim.MODULE_ID,
            "agent_count": self._amim.agent_count,
            "tool_count": self._amim.tool_count,
            "mcp_servers": list(self._amim._mcp_server_map.keys())
            if hasattr(self._amim, "_mcp_server_map")
            else [],
            "layers": {
                "L0": len(
                    [
                        a
                        for a in definitions
                        if getattr(getattr(a, "layer", None), "value", -1) == 0
                    ]
                ),
                "L1": len(
                    [
                        a
                        for a in definitions
                        if getattr(getattr(a, "layer", None), "value", -1) == 1
                    ]
                ),
                "L2": len(
                    [
                        a
                        for a in definitions
                        if getattr(getattr(a, "layer", None), "value", -1) == 2
                    ]
                ),
                "L3": len(
                    [
                        a
                        for a in definitions
                        if getattr(getattr(a, "layer", None), "value", -1) == 3
                    ]
                ),
                "L4": len(
                    [
                        a
                        for a in definitions
                        if getattr(getattr(a, "layer", None), "value", -1) == 4
                    ]
                ),
            },
            "system": SYSTEM_NAME,
        }

    def _handle_operation_header(self, args: dict) -> dict:
        fmt = args.get("format", "text")
        result = self._api_get("/api/operations/header")

        # 增强TVP调度实时状态
        tvp_status = ""
        try:
            orch = self._api_get("/api/orchestrator/status")
            if orch and orch.get("status") == "active":
                tas = orch.get("trae_agent_scheduler", {})
                tvp = orch.get("tvp_bridge_daemon", {})
                tvp_status = (
                    f"[TVP] events={tvp.get('total_events', 0)} "
                    f"switches={tvp.get('agent_switches', 0)} "
                    f"delegations={tvp.get('delegation_declarations', 0)} "
                    f"subagents={tvp.get('subagent_declarations', 0)}"
                )
        except Exception:
            pass

        # 增余量安全状态
        margin_status = ""
        try:
            cap = self._api_get("/api/system/capacity")
            if cap and cap.get("capacity"):
                levels = []
                for ln, info in cap["capacity"].items():
                    mm_level = "green"
                    usage = info.get("usage_ratio", 0)
                    if usage > 0.9:
                        mm_level = "red"
                    elif usage > 0.75:
                        mm_level = "orange"
                    elif usage > 0.5:
                        mm_level = "yellow"
                    if mm_level != "green":
                        levels.append(f"{ln}={mm_level}")
                if levels:
                    margin_status = "[Margin] " + " ".join(levels)
        except Exception:
            pass

        if result and not result.get("error"):
            header = (
                result.get("html", "") if fmt == "html" else result.get("header", "")
            )
            # 拼接TVP和Margin状态
            parts = [p for p in [header, tvp_status, margin_status] if p]
            combined = " | ".join(parts)
            return {
                "status": "success",
                "header": combined,
                "recent_count": result.get("recent_count", 0),
                "categories": result.get("categories", []),
                "tvp_status": tvp_status,
                "margin_status": margin_status,
                "format": fmt,
                "system": SYSTEM_NAME,
            }
        return {
            "status": "success",
            "header": " | ".join([p for p in [tvp_status, margin_status] if p]),
            "recent_count": 0,
            "categories": [],
            "tvp_status": tvp_status,
            "margin_status": margin_status,
            "format": fmt,
            "system": SYSTEM_NAME,
        }

    def _handle_agent_dispatch(self, args: dict) -> dict:
        task_type = args.get("task_type", "")
        task_data = args.get("task_data", {})
        priority = args.get("priority", "medium")
        try:
            if self._amim is None:
                return {
                    "status": "error",
                    "message": "AMIM M37 未初始化",
                    "system": SYSTEM_NAME,
                }
            dispatch_result = {
                "task_type": task_type,
                "task_data": task_data,
                "priority": priority,
                "dispatched": True,
                "target_agent": None,
                "estimated_duration": "unknown",
            }
            task_agent_map = {
                "memory_query": "yiku",
                "context_analysis": "dongcha",
                "content_creation": "miaobi",
                "code_generation": "miaobi",
                "review": "mingjing",
                "test": "tiewei",
                "deployment": "gongzao",
                "security_scan": "zhenshan",
                "performance_analysis": "zhuiguang",
                "orchestration": "tianshu",
            }
            dispatch_result["target_agent"] = task_agent_map.get(task_type, "tianshu")
            return {
                "status": "success",
                **dispatch_result,
                "system": SYSTEM_NAME,
            }
        except Exception as e:
            return {"status": "error", "message": str(e), "system": SYSTEM_NAME}

    def _handle_context_extract(self, args: dict) -> dict:
        user_input = args.get("user_input", "")
        context = args.get("context")
        try:
            extracted = {
                "intent": None,
                "entities": [],
                "keywords": [],
                "sentiment": None,
                "complexity": "medium",
            }
            keywords = []
            import re

            words = re.findall(r"\b\w{3,}\b", user_input.lower())
            from collections import Counter

            word_freq = Counter(words)
            keywords = [w for w, _ in word_freq.most_common(10)]
            extracted["keywords"] = keywords
            if any(kw in user_input.lower() for kw in ["修复", "立即", "必须", "紧急"]):
                extracted["intent"] = "urgent_task"
                extracted["complexity"] = "high"
            elif any(
                kw in user_input.lower() for kw in ["查询", "检索", "搜索", "获取"]
            ):
                extracted["intent"] = "query"
                extracted["complexity"] = "low"
            elif any(kw in user_input.lower() for kw in ["分析", "审计", "评估"]):
                extracted["intent"] = "analysis"
                extracted["complexity"] = "medium"
            elif any(
                kw in user_input.lower() for kw in ["创建", "添加", "生成", "编写"]
            ):
                extracted["intent"] = "create"
                extracted["complexity"] = "medium"
            return {
                "status": "success",
                "user_input": user_input,
                "extracted": extracted,
                "context": context,
                "system": SYSTEM_NAME,
            }
        except Exception as e:
            return {"status": "error", "message": str(e), "system": SYSTEM_NAME}

    def _handle_rule_evaluate(self, args: dict) -> dict:
        rule_name = args.get("rule_name", "")
        context = args.get("context", {})
        try:
            evaluation = {
                "rule_name": rule_name,
                "passed": True,
                "violations": [],
                "warnings": [],
                "score": 1.0,
            }
            known_rules = [
                "memory_first",
                "operation_logging",
                "tvp_protocol",
                "stage_gate",
                "encoding_safe",
                "permission_matrix",
            ]
            if rule_name not in known_rules:
                evaluation["warnings"].append(f"未知规则: {rule_name}")
                evaluation["score"] = 0.5
            if rule_name == "memory_first":
                if not context.get("memory_checked"):
                    evaluation["passed"] = False
                    evaluation["violations"].append("未检查天机记忆")
                    evaluation["score"] = 0.0
            elif rule_name == "tvp_protocol":
                if not context.get("tvp_declared"):
                    evaluation["warnings"].append("未声明TVP协议")
                    evaluation["score"] = 0.7
            return {
                "status": "success",
                **evaluation,
                "system": SYSTEM_NAME,
            }
        except Exception as e:
            return {"status": "error", "message": str(e), "system": SYSTEM_NAME}

    def _handle_system_status(self, args: dict) -> dict:
        try:
            status = {
                "tianji": {
                    "api_available": self._api_available,
                    "api_url": self.api_url,
                    "tool_calls": self._tool_call_count,
                    "tool_errors": self._tool_error_count,
                },
                "mcp": {
                    "tools_total": len(ALL_TOOLS),
                    "tools_basic": len(BASIC_TOOLS),
                    "tools_advanced": len(ADVANCED_TOOLS),
                },
                "amim": {
                    "available": self._amim is not None,
                    "agents": self._amim.agent_count if self._amim else 0,
                    "tools": self._amim.tool_count if self._amim else 0,
                },
                "evo_loop": {
                    "active": self._evo_loop is not None,
                },
                "system": SYSTEM_NAME,
                "version": SYSTEM_VERSION,
            }
            if self._api_available:
                health_result = self._api_get("/api/health")
                if health_result and not health_result.get("error"):
                    status["tianji"]["engine_ready"] = health_result.get(
                        "engine_ready", False
                    )
                    status["tianji"]["embedding_ready"] = health_result.get(
                        "embedding_ready", False
                    )
                    status["tianji"]["uptime"] = health_result.get("uptime_seconds", 0)
            return {"status": "success", **status}
        except Exception as e:
            return {"status": "error", "message": str(e), "system": SYSTEM_NAME}
