"""
天机MCP桥接器 (Tianji MCP Bridge) v1.0
==========================================
将MCP Server的29+工具桥接到对话系统,
让Chat能通过OpenAI function_call格式动态调用全部MCP工具。

核心能力:
  1. 动态工具发现 — 从TianjiMCPServer.ALL_TOOLS自动生成OpenAI格式工具集
  2. 工具执行桥接 — 将function_call请求路由到MCP Server内部方法
  3. 结果格式化 — 将MCP返回值转换为对话友好的自然语言
  4. 安全过滤 — 排除不适合对话场景的内部工具

架构位置: 天机/core/mcp_bridge.py
依赖: mcp/tianji_mcp_server.py (TianjiMCPServer)
"""

from __future__ import annotations

import json
import logging
import os
import time
import traceback
from collections.abc import Callable
from typing import Any

logger = logging.getLogger("tianji.mcp_bridge")

# 对话场景下排除的工具 (内部/调试用途, 不暴露给LLM)
_CHAT_EXCLUDED_TOOLS = {
    "trae_stream_capture",  # Trae IDE专用
    "trae_stream_snapshot",  # Trae IDE专用
    "trae_monitoring_stats",  # 内部监控
    "tianji_amim_status",  # 内部AMIM
    "tianji_operation_header",  # 内部操作头
    "memory_evolve_self",  # 危险: 自进化不应由对话触发
}

# 工具分类 — 从ToolCategoryMapper动态获取，硬编码作为fallback
_TOOL_CATEGORIES_FALLBACK = {
    "memory_ops": [
        "memory_remember",
        "memory_recall",
        "memory_forget",
        "memory_stats",
        "memory_capacity",
        "memory_consolidate",
    ],
    "search": [
        "search_memories",
        "tianji_semantic_search",
        "tianji_expand_query",
    ],
    "llm_intel": [
        "tianji_classify",
        "tianji_auto_tag",
        "tianji_summarize",
        "tianji_extract_knowledge",
    ],
    "knowledge_graph": [
        "memory_build_graph",
        "memory_query_graph",
    ],
    "context": [
        "build_working_representation",
        "tianji_intercept",
        "context_extract",
        "tianji_normalize",
        "tianji_disambiguate",
    ],
    "system": [
        "tianji_health",
        "tianji_help",
        "system_status",
        "tianji_tool_owner",
        "rule_evaluate",
    ],
    "conversation": [
        "get_session_digest",
        "tianji_summarize_conversation",
        "explain_memory_lineage",
    ],
    "export": [
        "tianji_export",
        "list_memories",
        "get_memory",
    ],
    "agent": [
        "agent_dispatch",
    ],
    "advanced_memory": [
        "memory_learn_skill",
        "memory_capture_multimodal",
        "run_reflective_cycle",
    ],
    "command": [
        "execute_command",
        "check_command",
        "stop_command",
        "list_processes",
        "get_process_info",
        "kill_process",
        "run_script",
        "get_script_status",
        "list_scripts",
    ],
    "ops": [
        "deploy_service",
        "check_deployment",
        "rollback_deployment",
        "get_resource_usage",
        "scale_service",
        "list_services",
    ],
    "security": [
        "scan_vulnerabilities",
        "check_compliance",
        "get_security_report",
        "scan_dependencies",
        "check_permissions",
        "list_security_policies",
    ],
    "performance": [
        "profile_function",
        "get_performance_metrics",
        "analyze_bottleneck",
        "get_memory_profile",
        "get_cpu_profile",
        "list_profiling_sessions",
    ],
}


def _load_tool_categories() -> dict[str, list[str]]:
    """从ToolCategoryMapper动态加载工具分类，失败时返回fallback"""
    try:
        from .tool_category_mapper import get_tool_category_mapper

        mapper = get_tool_category_mapper()
        return mapper.get_all_categories()
    except Exception as e:
        logger.warning(
            f"Failed to load tool categories from mapper: {e}, using fallback"
        )
        return dict(_TOOL_CATEGORIES_FALLBACK)


_TOOL_CATEGORIES = _load_tool_categories()

# 外部MCP Server工具定义 (通过API转发调用)
_EXTERNAL_MCP_TOOLS: list[dict[str, Any]] = [
    # === command-executor (9 tools) ===
    {
        "name": "execute_command",
        "description": "执行系统命令并返回结果。支持超时设置和工作目录指定。可用于运行脚本、查看文件、执行程序等。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "要执行的命令"},
                "timeout": {
                    "type": "integer",
                    "description": "超时时间(秒)",
                    "default": 30,
                },
                "cwd": {"type": "string", "description": "工作目录"},
            },
            "required": ["command"],
        },
    },
    {
        "name": "check_command",
        "description": "检查异步命令的执行状态和输出。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "command_id": {"type": "string", "description": "命令ID"},
            },
            "required": ["command_id"],
        },
    },
    {
        "name": "stop_command",
        "description": "停止正在运行的异步命令。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "command_id": {"type": "string", "description": "命令ID"},
            },
            "required": ["command_id"],
        },
    },
    {
        "name": "list_processes",
        "description": "列出当前运行的系统进程。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "filter": {"type": "string", "description": "进程名过滤"},
            },
        },
    },
    {
        "name": "get_process_info",
        "description": "获取指定进程的详细信息。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "pid": {"type": "integer", "description": "进程ID"},
            },
            "required": ["pid"],
        },
    },
    {
        "name": "kill_process",
        "description": "终止指定进程。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "pid": {"type": "integer", "description": "进程ID"},
                "force": {
                    "type": "boolean",
                    "description": "是否强制终止",
                    "default": False,
                },
            },
            "required": ["pid"],
        },
    },
    {
        "name": "run_script",
        "description": "运行项目中的脚本文件。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "script_path": {"type": "string", "description": "脚本路径"},
                "args": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "脚本参数",
                },
            },
            "required": ["script_path"],
        },
    },
    {
        "name": "get_script_status",
        "description": "获取脚本运行状态。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "script_id": {"type": "string", "description": "脚本运行ID"},
            },
            "required": ["script_id"],
        },
    },
    {
        "name": "list_scripts",
        "description": "列出项目scripts目录中的可用脚本。",
        "inputSchema": {"type": "object", "properties": {}},
    },
    # === ops-engine (6 tools) ===
    {
        "name": "deploy_service",
        "description": "部署指定服务到目标环境。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "service_name": {"type": "string", "description": "服务名称"},
                "environment": {
                    "type": "string",
                    "description": "目标环境",
                    "enum": ["dev", "staging", "production"],
                },
                "config": {"type": "object", "description": "部署配置"},
            },
            "required": ["service_name"],
        },
    },
    {
        "name": "check_deployment",
        "description": "检查服务部署状态。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "service_name": {"type": "string", "description": "服务名称"},
            },
            "required": ["service_name"],
        },
    },
    {
        "name": "rollback_deployment",
        "description": "回滚服务到上一版本。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "service_name": {"type": "string", "description": "服务名称"},
                "version": {"type": "string", "description": "目标版本"},
            },
            "required": ["service_name"],
        },
    },
    {
        "name": "get_resource_usage",
        "description": "获取系统资源使用情况(CPU/内存/磁盘/网络)。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "resource_type": {
                    "type": "string",
                    "description": "资源类型",
                    "enum": ["cpu", "memory", "disk", "network", "all"],
                    "default": "all",
                },
                "duration": {
                    "type": "string",
                    "description": "统计周期",
                    "default": "1h",
                },
            },
        },
    },
    {
        "name": "scale_service",
        "description": "调整服务实例数量。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "service_name": {"type": "string", "description": "服务名称"},
                "replicas": {"type": "integer", "description": "目标实例数"},
            },
            "required": ["service_name", "replicas"],
        },
    },
    {
        "name": "list_services",
        "description": "列出所有已部署的服务及其状态。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "filter": {"type": "string", "description": "服务名过滤"},
            },
        },
    },
    # === security-scanner (6 tools) ===
    {
        "name": "scan_vulnerabilities",
        "description": "扫描代码库中的安全漏洞，包括OWASP Top 10和CWE常见漏洞。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "target_path": {"type": "string", "description": "扫描目标路径"},
                "scan_type": {
                    "type": "string",
                    "description": "扫描类型",
                    "enum": ["full", "quick", "dependency", "code"],
                    "default": "quick",
                },
                "severity": {
                    "type": "string",
                    "description": "最低严重级别",
                    "enum": ["low", "medium", "high", "critical"],
                    "default": "medium",
                },
            },
            "required": ["target_path"],
        },
    },
    {
        "name": "check_compliance",
        "description": "检查代码是否符合安全合规标准(OWASP/ISO/SOC2等)。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "standard": {
                    "type": "string",
                    "description": "合规标准",
                    "enum": ["owasp", "iso27001", "soc2", "gdpr", "all"],
                },
                "target_path": {"type": "string", "description": "检查目标路径"},
            },
            "required": ["standard"],
        },
    },
    {
        "name": "get_security_report",
        "description": "生成安全扫描报告，包含漏洞摘要和修复建议。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "report_type": {
                    "type": "string",
                    "description": "报告类型",
                    "enum": ["summary", "detailed", "executive"],
                    "default": "summary",
                },
                "format": {
                    "type": "string",
                    "description": "输出格式",
                    "enum": ["json", "markdown", "html"],
                    "default": "json",
                },
            },
        },
    },
    {
        "name": "scan_dependencies",
        "description": "扫描项目依赖中的已知漏洞。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "target_path": {"type": "string", "description": "项目路径"},
                "include_dev": {
                    "type": "boolean",
                    "description": "包含开发依赖",
                    "default": True,
                },
            },
        },
    },
    {
        "name": "check_permissions",
        "description": "检查文件和目录的权限配置是否安全。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "target_path": {"type": "string", "description": "检查目标路径"},
                "check_type": {
                    "type": "string",
                    "description": "检查类型",
                    "enum": ["file", "directory", "all"],
                    "default": "all",
                },
            },
        },
    },
    {
        "name": "list_security_policies",
        "description": "列出当前生效的安全策略和规则。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "policy_type": {
                    "type": "string",
                    "description": "策略类型",
                    "enum": ["all", "enforcement", "monitoring", "alerting"],
                },
            },
        },
    },
    # === performance-profiler (6 tools) ===
    {
        "name": "profile_function",
        "description": "对指定函数进行性能剖析，返回执行时间和调用统计。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "module_path": {"type": "string", "description": "模块路径"},
                "function_name": {"type": "string", "description": "函数名"},
                "duration": {
                    "type": "integer",
                    "description": "剖析时长(秒)",
                    "default": 10,
                },
            },
            "required": ["module_path", "function_name"],
        },
    },
    {
        "name": "get_performance_metrics",
        "description": "获取系统性能指标，包括QPS、延迟、吞吐量等。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "metric_type": {
                    "type": "string",
                    "description": "指标类型",
                    "enum": ["qps", "latency", "throughput", "all"],
                    "default": "all",
                },
                "time_range": {
                    "type": "string",
                    "description": "时间范围",
                    "default": "1h",
                },
            },
        },
    },
    {
        "name": "analyze_bottleneck",
        "description": "分析系统性能瓶颈并提供优化建议。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "target": {
                    "type": "string",
                    "description": "分析目标",
                    "enum": ["cpu", "memory", "io", "network", "all"],
                    "default": "all",
                },
                "threshold": {
                    "type": "number",
                    "description": "告警阈值",
                    "default": 0.8,
                },
            },
        },
    },
    {
        "name": "get_memory_profile",
        "description": "获取内存使用详情和对象分配统计。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "top_n": {
                    "type": "integer",
                    "description": "显示前N个内存消耗者",
                    "default": 20,
                },
            },
        },
    },
    {
        "name": "get_cpu_profile",
        "description": "获取CPU使用详情和热点函数统计。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "top_n": {
                    "type": "integer",
                    "description": "显示前N个CPU消耗者",
                    "default": 20,
                },
            },
        },
    },
    {
        "name": "list_profiling_sessions",
        "description": "列出所有性能剖析会话。",
        "inputSchema": {"type": "object", "properties": {}},
    },
]

# 外部工具名→所属server映射 (用于API转发)
_EXTERNAL_TOOL_SERVER: dict[str, str] = {}
for _t in _EXTERNAL_MCP_TOOLS:
    _name = _t["name"]
    if _name in (
        "execute_command",
        "check_command",
        "stop_command",
        "list_processes",
        "get_process_info",
        "kill_process",
        "run_script",
        "get_script_status",
        "list_scripts",
    ):
        _EXTERNAL_TOOL_SERVER[_name] = "command-executor"
    elif _name in (
        "deploy_service",
        "check_deployment",
        "rollback_deployment",
        "get_resource_usage",
        "scale_service",
        "list_services",
    ):
        _EXTERNAL_TOOL_SERVER[_name] = "ops-engine"
    elif _name in (
        "scan_vulnerabilities",
        "check_compliance",
        "get_security_report",
        "scan_dependencies",
        "check_permissions",
        "list_security_policies",
    ):
        _EXTERNAL_TOOL_SERVER[_name] = "security-scanner"
    elif _name in (
        "profile_function",
        "get_performance_metrics",
        "analyze_bottleneck",
        "get_memory_profile",
        "get_cpu_profile",
        "list_profiling_sessions",
    ):
        _EXTERNAL_TOOL_SERVER[_name] = "performance-profiler"


class MCPBridge:
    """MCP Server → 对话系统 桥接器

    将 tianji_mcp_server.py 的29+工具转换为OpenAI function_call格式,
    并提供统一的执行入口。

    使用方式:
      bridge = MCPBridge()
      tools = await bridge.get_tool_definitions()
      result = await bridge.call_tool("memory_recall", {"query": "测试"})
    """

    VERSION = "1.0.0"

    def __init__(self):
        self._server: Any = None
        self._tool_map: dict[str, Callable] = {}
        self._tool_defs_cache: list[dict] | None = None
        self._tool_defs_cache_time: float = 0.0
        self._call_count: int = 0
        self._error_count: int = 0
        self._last_error: str = ""
        self._init_time: float = time.time()

    def _get_server(self) -> Any:
        """延迟加载TianjiMCPServer实例 (直接import, 零开销)"""
        if self._server is not None:
            return self._server
        try:
            from mcp.tianji_mcp_server import TianjiMCPServer

            self._server = TianjiMCPServer()
            # 构建工具名→方法映射
            self._build_tool_map()
            return self._server
        except Exception as e:
            logger.error(f"MCPBridge: 加载TianjiMCPServer失败: {e}")
            return None

    def _build_tool_map(self):
        """构建工具名→内部方法的映射"""
        if not self._server:
            return
        # MCP Server的内部方法命名: _handle_xxx
        method_map = {
            "memory_remember": "_handle_remember",
            "memory_recall": "_handle_recall",
            "memory_forget": "_handle_forget",
            "memory_stats": "_handle_stats",
            "memory_capacity": "_handle_capacity",
            "memory_consolidate": "_handle_consolidate",
            "search_memories": "_handle_search",
            "get_memory": "_handle_get_memory",
            "list_memories": "_handle_list_memories",
            "build_working_representation": "_handle_build_repr",
            "run_reflective_cycle": "_handle_reflective",
            "get_session_digest": "_handle_session_digest",
            "explain_memory_lineage": "_handle_lineage",
            "tianji_health": "_handle_health",
            "tianji_help": "_handle_help",
            "tianji_classify": "_handle_classify",
            "tianji_auto_tag": "_handle_auto_tag",
            "tianji_summarize": "_handle_summarize",
            "tianji_extract_knowledge": "_handle_extract_knowledge",
            "tianji_expand_query": "_handle_expand_query",
            "tianji_semantic_search": "_handle_semantic_search",
            "tianji_intercept": "_handle_intercept",
            "tianji_export": "_handle_export",
            "tianji_summarize_conversation": "_handle_summarize_conv",
            "tianji_normalize": "_handle_normalize",
            "tianji_disambiguate": "_handle_disambiguate",
            "tianji_tool_owner": "_handle_tool_owner",
            "tianji_amim_status": "_handle_amim_status",
            "tianji_operation_header": "_handle_operation_header",
            "trae_stream_capture": "_handle_stream_capture",
            "trae_stream_snapshot": "_handle_stream_snapshot",
            "trae_monitoring_stats": "_handle_monitoring_stats",
            "memory_build_graph": "_handle_build_graph",
            "memory_query_graph": "_handle_query_graph",
            "memory_evolve_self": "_handle_evolve_self",
            "memory_learn_skill": "_handle_learn_skill",
            "memory_capture_multimodal": "_handle_capture_multimodal",
            "context_extract": "_handle_context_extract",
            "agent_dispatch": "_handle_agent_dispatch",
            "system_status": "_handle_system_status",
            "rule_evaluate": "_handle_rule_evaluate",
        }
        for tool_name, method_name in method_map.items():
            method = getattr(self._server, method_name, None)
            if method and callable(method):
                self._tool_map[tool_name] = method

    def get_tool_definitions(self, include_excluded: bool = False) -> list[dict]:
        """返回OpenAI function_call格式的全部工具定义

        Args:
            include_excluded: 是否包含内部调试工具

        Returns:
            OpenAI tools格式的列表
        """
        # 缓存 (5秒有效期)
        now = time.time()
        if self._tool_defs_cache and (now - self._tool_defs_cache_time) < 5.0:
            if not include_excluded:
                return [
                    t
                    for t in self._tool_defs_cache
                    if t["function"]["name"] not in _CHAT_EXCLUDED_TOOLS
                ]
            return self._tool_defs_cache

        try:
            from mcp.tianji_mcp_server import ALL_TOOLS
        except ImportError:
            logger.error("MCPBridge: 无法导入ALL_TOOLS")
            return self._fallback_tool_definitions()

        openai_tools = []
        for tool in ALL_TOOLS:
            name = tool.get("name", "")
            if not include_excluded and name in _CHAT_EXCLUDED_TOOLS:
                continue

            schema = tool.get("inputSchema", {})
            # 转换inputSchema → OpenAI function parameters格式
            parameters = self._convert_schema(schema)
            parameters["properties"] = parameters.get("properties", {})
            # 确保有type字段
            if "type" not in parameters:
                parameters["type"] = "object"

            openai_tools.append(
                {
                    "type": "function",
                    "function": {
                        "name": name,
                        "description": tool.get("description", tool.get("title", "")),
                        "parameters": parameters,
                    },
                }
            )

        # 合并外部MCP Server工具 (command-executor/ops-engine/security-scanner/performance-profiler)
        for tool in _EXTERNAL_MCP_TOOLS:
            name = tool.get("name", "")
            if not include_excluded and name in _CHAT_EXCLUDED_TOOLS:
                continue
            schema = tool.get("inputSchema", {})
            parameters = self._convert_schema(schema)
            parameters["properties"] = parameters.get("properties", {})
            if "type" not in parameters:
                parameters["type"] = "object"
            openai_tools.append(
                {
                    "type": "function",
                    "function": {
                        "name": name,
                        "description": tool.get("description", tool.get("title", "")),
                        "parameters": parameters,
                    },
                }
            )

        self._tool_defs_cache = openai_tools
        self._tool_defs_cache_time = now
        return openai_tools

    def _convert_schema(self, schema: dict) -> dict:
        """将MCP inputSchema转换为OpenAI function parameters格式

        MCP格式和OpenAI格式基本兼容, 只需微调:
        - 移除title字段 (OpenAI不需要)
        - 确保required是数组
        """
        result = {}
        if "type" in schema:
            result["type"] = schema["type"]
        if "properties" in schema:
            result["properties"] = schema["properties"]
        if "required" in schema:
            req = schema["required"]
            if isinstance(req, list):
                result["required"] = req
        # 保留default值
        for key in schema:
            if key not in ("type", "properties", "required", "title"):
                result[key] = schema[key]
        return result

    def _fallback_tool_definitions(self) -> list[dict]:
        """降级: 当无法导入ALL_TOOLS时, 提供核心工具集"""
        return [
            {
                "type": "function",
                "function": {
                    "name": "memory_recall",
                    "description": "从天机记忆系统检索相关内容",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {"type": "string", "description": "搜索查询"},
                        },
                        "required": ["query"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "memory_remember",
                    "description": "将内容存储到天机记忆系统",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "content": {
                                "type": "string",
                                "description": "要存储的内容",
                            },
                            "layer": {
                                "type": "string",
                                "enum": [
                                    "sensory",
                                    "working",
                                    "short_term",
                                    "episodic",
                                    "semantic",
                                    "meta",
                                ],
                                "description": "目标记忆层",
                            },
                            "tags": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "标签列表",
                            },
                        },
                        "required": ["content"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "tianji_classify",
                    "description": "使用LLM对内容进行智能分类",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "content": {
                                "type": "string",
                                "description": "要分类的内容",
                            },
                        },
                        "required": ["content"],
                    },
                },
            },
        ]

    async def call_tool(self, tool_name: str, args: dict[str, Any]) -> dict[str, Any]:
        """执行MCP工具调用

        Args:
            tool_name: 工具名称 (如 "memory_recall")
            args: 工具参数 (如 {"query": "测试"})

        Returns:
            {"success": bool, "data": Any, "error": str|None, "tool_name": str, "duration_ms": float}
        """
        t0 = time.time()
        self._call_count += 1

        # 安全检查
        if tool_name in _CHAT_EXCLUDED_TOOLS:
            return {
                "success": False,
                "data": None,
                "error": f"工具 {tool_name} 在对话场景下不可用",
                "tool_name": tool_name,
                "duration_ms": 0.0,
            }

        # 获取server实例
        server = self._get_server()
        if not server:
            self._error_count += 1
            self._last_error = "MCP Server不可用"
            return {
                "success": False,
                "data": None,
                "error": "MCP Server不可用",
                "tool_name": tool_name,
                "duration_ms": (time.time() - t0) * 1000,
            }

        # 查找方法
        method = self._tool_map.get(tool_name)
        if not method:
            # 尝试动态查找
            method_name = f"_handle_{tool_name}"
            # 处理特殊命名
            name_mappings = {
                "memory_recall": "_handle_recall",
                "memory_remember": "_handle_remember",
                "memory_forget": "_handle_forget",
                "memory_stats": "_handle_stats",
                "memory_capacity": "_handle_capacity",
                "memory_consolidate": "_handle_consolidate",
                "search_memories": "_handle_search",
                "tianji_semantic_search": "_handle_semantic_search",
                "tianji_summarize_conversation": "_handle_summarize_conv",
            }
            method_name = name_mappings.get(tool_name, method_name)
            method = getattr(server, method_name, None)

        if not method or not callable(method):
            # 尝试外部MCP Server工具 (通过API转发)
            if tool_name in _EXTERNAL_TOOL_SERVER:
                return await self._call_external_tool(tool_name, args, t0)
            self._error_count += 1
            self._last_error = f"工具 {tool_name} 未找到对应方法"
            return {
                "success": False,
                "data": None,
                "error": f"工具 {tool_name} 未找到",
                "tool_name": tool_name,
                "duration_ms": (time.time() - t0) * 1000,
            }

        # 执行调用
        try:
            result = method(args)
            duration_ms = (time.time() - t0) * 1000

            # 解析结果 (MCP方法返回dict)
            if isinstance(result, dict):
                # 检查是否是MCP标准响应格式
                if "content" in result:
                    content_list = result.get("content", [])
                    if isinstance(content_list, list) and len(content_list) > 0:
                        text_parts = []
                        for item in content_list:
                            if isinstance(item, dict) and "text" in item:
                                text_parts.append(item["text"])
                            elif isinstance(item, str):
                                text_parts.append(item)
                        data = "\n".join(text_parts) if text_parts else str(result)
                    else:
                        data = str(result)
                elif "result" in result:
                    data = result["result"]
                else:
                    data = result

                return {
                    "success": True,
                    "data": data,
                    "error": None,
                    "tool_name": tool_name,
                    "duration_ms": duration_ms,
                }
            else:
                return {
                    "success": True,
                    "data": str(result),
                    "error": None,
                    "tool_name": tool_name,
                    "duration_ms": duration_ms,
                }

        except Exception as e:
            duration_ms = (time.time() - t0) * 1000
            self._error_count += 1
            self._last_error = str(e)
            logger.error(
                f"MCPBridge.call_tool({tool_name}) 失败: {e}\n{traceback.format_exc()}"
            )
            return {
                "success": False,
                "data": None,
                "error": str(e),
                "tool_name": tool_name,
                "duration_ms": duration_ms,
            }

    async def _call_external_tool(
        self, tool_name: str, args: dict[str, Any], t0: float
    ) -> dict[str, Any]:
        """通过天机API转发调用外部MCP Server工具

        外部MCP Server (command-executor等) 通过 /api/mcp/tools/{name} 路由执行。
        """
        import httpx

        api_url = os.environ.get("TIANJI_API_URL", "http://127.0.0.1:8771")
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.post(
                    f"{api_url}/api/mcp/tools/{tool_name}",
                    json=args,
                    headers={"Content-Type": "application/json"},
                )
                data = resp.json()
                duration_ms = (time.time() - t0) * 1000
                return {
                    "success": True,
                    "data": data,
                    "error": None,
                    "tool_name": tool_name,
                    "duration_ms": duration_ms,
                }
        except Exception as e:
            duration_ms = (time.time() - t0) * 1000
            self._error_count += 1
            self._last_error = str(e)
            logger.error(f"MCPBridge._call_external_tool({tool_name}) 失败: {e}")
            return {
                "success": False,
                "data": None,
                "error": f"外部工具调用失败: {str(e)}",
                "tool_name": tool_name,
                "duration_ms": duration_ms,
            }

    def format_result_for_llm(self, result: dict[str, Any]) -> str:
        """将工具执行结果格式化为LLM可理解的自然语言

        Args:
            result: call_tool的返回值

        Returns:
            格式化后的文本
        """
        if not result.get("success"):
            return f"[工具调用失败] {result.get('tool_name', '?')}: {result.get('error', '未知错误')}"

        data = result.get("data")
        tool_name = result.get("tool_name", "")
        duration = result.get("duration_ms", 0)

        if data is None:
            return f"[{tool_name}] 执行完成 ({duration:.0f}ms)"

        # 尝试解析JSON
        if isinstance(data, str):
            try:
                parsed = json.loads(data)
                # 精简输出
                if isinstance(parsed, dict):
                    # 记忆检索结果
                    if "results" in parsed:
                        items = parsed["results"]
                        if isinstance(items, list):
                            summary = f"[{tool_name}] 找到 {len(items)} 条相关记忆 ({duration:.0f}ms):\n"
                            for i, item in enumerate(items[:5]):
                                if isinstance(item, dict):
                                    content = item.get(
                                        "content", item.get("text", str(item))
                                    )[:100]
                                    summary += f"  {i + 1}. {content}...\n"
                                else:
                                    summary += f"  {i + 1}. {str(item)[:100]}\n"
                            if len(items) > 5:
                                summary += f"  ... 还有 {len(items) - 5} 条结果"
                            return summary
                    # 统计结果
                    if "total_entries" in parsed:
                        return (
                            f"[{tool_name}] 记忆统计: {parsed.get('total_entries', 0)}条总条目, "
                            f"访问量={parsed.get('total_accesses', 0)} ({duration:.0f}ms)"
                        )
                    # LLM功能结果
                    if "layer" in parsed:
                        return (
                            f"[{tool_name}] 分类结果: layer={parsed['layer']}, "
                            f"confidence={parsed.get('confidence', 'N/A')} ({duration:.0f}ms)"
                        )
                    if "tags" in parsed:
                        tags = parsed["tags"]
                        if isinstance(tags, list):
                            return f"[{tool_name}] 标签: {', '.join(str(t) for t in tags[:10])} ({duration:.0f}ms)"
                    if "summary" in parsed:
                        return f"[{tool_name}] 摘要: {parsed['summary'][:200]} ({duration:.0f}ms)"
                    if "triples" in parsed:
                        triples = parsed["triples"]
                        if isinstance(triples, list):
                            lines = [
                                f"[{tool_name}] 提取 {len(triples)} 个知识三元组 ({duration:.0f}ms):"
                            ]
                            for t in triples[:5]:
                                if isinstance(t, dict):
                                    lines.append(
                                        f"  - {t.get('subject', '?')} → {t.get('relation', '?')} → {t.get('object', '?')}"
                                    )
                            return "\n".join(lines)
                    if "expansions" in parsed:
                        exps = parsed["expansions"]
                        if isinstance(exps, list):
                            return f"[{tool_name}] 查询扩展: {', '.join(str(e) for e in exps[:8])} ({duration:.0f}ms)"

                    # 通用dict
                    return f"[{tool_name}] 结果 ({duration:.0f}ms): {json.dumps(parsed, ensure_ascii=False)[:500]}"
                elif isinstance(parsed, list):
                    return f"[{tool_name}] 返回 {len(parsed)} 项 ({duration:.0f}ms)"
            except (json.JSONDecodeError, TypeError):
                pass

            # 纯文本
            if len(data) > 500:
                return f"[{tool_name}] ({duration:.0f}ms): {data[:500]}..."
            return f"[{tool_name}] ({duration:.0f}ms): {data}"

        if isinstance(data, dict):
            return f"[{tool_name}] ({duration:.0f}ms): {json.dumps(data, ensure_ascii=False)[:500]}"

        return f"[{tool_name}] ({duration:.0f}ms): {str(data)[:300]}"

    def get_tools_by_category(self, category: str) -> list[str]:
        """获取指定分类的工具名列表"""
        return _TOOL_CATEGORIES.get(category, [])

    def get_all_categories(self) -> dict[str, list[str]]:
        """获取所有工具分类"""
        return dict(_TOOL_CATEGORIES)

    def health(self) -> dict[str, Any]:
        """健康检查"""
        server = self._get_server()
        return {
            "status": "healthy" if server else "degraded",
            "version": self.VERSION,
            "total_tools_available": len(self._tool_map),
            "total_tools_excluded": len(_CHAT_EXCLUDED_TOOLS),
            "call_count": self._call_count,
            "error_count": self._error_count,
            "last_error": self._last_error or None,
            "uptime_seconds": time.time() - self._init_time,
        }


# 全局单例
_bridge_instance: MCPBridge | None = None


def get_mcp_bridge() -> MCPBridge:
    """获取全局MCPBridge单例"""
    global _bridge_instance
    if _bridge_instance is None:
        _bridge_instance = MCPBridge()
    return _bridge_instance
