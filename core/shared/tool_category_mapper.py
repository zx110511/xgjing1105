"""
工具分类映射器 (Tool Category Mapper) — [v1.0]

从能力矩阵动态派生工具分类，替代 mcp_bridge.py 中的硬编码 _TOOL_CATEGORIES。

核心能力:
  1. 从CapabilityRegistry提取工具分类信息
  2. 建立工具名称到分类的双向映射
  3. 提供与现有_TOOL_CATEGORIES兼容的接口
  4. 支持动态更新（当能力矩阵变化时自动同步）

架构位置: 天机/core/shared/tool_category_mapper.py
依赖: core/orchestration/registry.py (CapabilityRegistry)
"""

from __future__ import annotations

import time

from core.orchestration.registry import DEFAULT_REGISTRY, CapabilityRegistry


class ToolCategoryMapper:
    """
    工具分类映射器 — 从能力矩阵动态派生工具分类

    用法:
        mapper = ToolCategoryMapper()
        mapper.get_tools_by_category("memory_ops")  # -> ["memory_remember", ...]
        mapper.get_category_for_tool("memory_recall")  # -> "memory_ops"
        mapper.get_all_categories()  # -> {"memory_ops": [...], ...}
        mapper.refresh()  # 从能力矩阵重新加载

    兼容性: 提供与 mcp_bridge.py 中 _TOOL_CATEGORIES 相同的接口
    """

    _DEFAULT_CATEGORY_MAPPING: dict[str, list[str]] = {
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

    _CAPABILITY_CATEGORY_KEYWORDS: dict[str, list[str]] = {
        "memory_ops": ["记忆", "ICME", "语义检索", "容量监控", "巩固"],
        "search": ["搜索", "检索", "查询", "查找"],
        "llm_intel": ["分类", "标签", "摘要", "提取", "知识"],
        "knowledge_graph": ["图谱", "实体", "关系", "推理"],
        "context": ["上下文", "意图", "拦截", "抽取", "消歧"],
        "system": ["健康", "状态", "帮助", "规则", "评估", "编排", "调度"],
        "conversation": ["会话", "对话", "摘要", "谱系"],
        "export": ["导出", "列表", "获取", "输出"],
        "agent": ["代理", "分发", "调度"],
        "advanced_memory": ["学习", "多模态", "反射", "进化"],
        "command": ["执行", "命令", "进程", "脚本", "运行"],
        "ops": ["部署", "运维", "资源", "服务", "CI/CD"],
        "security": ["安全", "漏洞", "合规", "扫描", "密钥"],
        "performance": ["性能", "剖析", "瓶颈", "基准", "优化"],
    }

    def __init__(self, registry: CapabilityRegistry | None = None):
        self._registry = registry if registry is not None else DEFAULT_REGISTRY
        self._categories: dict[str, list[str]] = {}
        self._tool_to_category: dict[str, str] = {}
        self._last_refresh_time: float = 0.0
        self._initialized: bool = False
        self._refresh()

    def _refresh(self):
        """从能力矩阵重新加载工具分类"""
        self._categories = {}
        self._tool_to_category = {}

        all_tools = self._collect_all_tools()
        categorized_tools = self._categorize_tools(all_tools)

        for category, tools in categorized_tools.items():
            self._categories[category] = sorted(list(set(tools)))
            for tool in tools:
                self._tool_to_category[tool] = category

        self._last_refresh_time = time.time()
        self._initialized = True

    def _collect_all_tools(self) -> set[str]:
        """从能力矩阵收集所有工具"""
        tools: set[str] = set()
        for agent_id in self._registry.list_agents():
            agent_tools = self._registry.get_tools(agent_id)
            tools.update(agent_tools)
        return tools

    def _categorize_tools(self, tools: set[str]) -> dict[str, list[str]]:
        """基于能力矩阵和预设规则对工具进行分类"""
        categorized: dict[str, list[str]] = {
            cat: [] for cat in self._DEFAULT_CATEGORY_MAPPING.keys()
        }
        categorized["uncategorized"] = []

        categorized_tools: set[str] = set()

        for category, default_tools in self._DEFAULT_CATEGORY_MAPPING.items():
            for tool in default_tools:
                if tool in tools:
                    categorized[category].append(tool)
                    categorized_tools.add(tool)

        for tool in tools:
            if tool in categorized_tools:
                continue

            matched_category = self._infer_category_from_matrix(tool)
            if matched_category:
                categorized[matched_category].append(tool)
                categorized_tools.add(tool)
            else:
                categorized["uncategorized"].append(tool)

        for cat in list(categorized.keys()):
            if not categorized[cat]:
                del categorized[cat]

        return categorized

    def _infer_category_from_matrix(self, tool_name: str) -> str | None:
        """从能力矩阵推断工具分类"""
        agents_with_tool = self._registry.find_by_tool(tool_name)
        if not agents_with_tool:
            return None

        category_scores: dict[str, int] = {}

        for agent_id in agents_with_tool:
            capabilities = self._registry.get_capabilities(agent_id)
            role = self._registry.get_role(agent_id)
            layer = self._registry.get_layer(agent_id)

            all_text = " ".join(capabilities) + " " + role + " " + layer

            for category, keywords in self._CAPABILITY_CATEGORY_KEYWORDS.items():
                score = sum(1 for kw in keywords if kw in all_text)
                if score > 0:
                    category_scores[category] = category_scores.get(category, 0) + score

        if not category_scores:
            return self._infer_category_from_name(tool_name)

        max_score = max(category_scores.values())
        if max_score == 0:
            return self._infer_category_from_name(tool_name)

        for category, score in sorted(category_scores.items(), key=lambda x: -x[1]):
            if score == max_score:
                return category

        return None

    def _infer_category_from_name(self, tool_name: str) -> str | None:
        """从工具名称推断分类"""
        name_patterns = {
            "memory_": "memory_ops",
            "search_": "search",
            "tianji_classify": "llm_intel",
            "tianji_auto_tag": "llm_intel",
            "tianji_summarize": "llm_intel",
            "tianji_extract": "llm_intel",
            "tianji_semantic_search": "search",
            "tianji_expand_query": "search",
            "graph": "knowledge_graph",
            "context_": "context",
            "build_working": "context",
            "tianji_intercept": "context",
            "tianji_normalize": "context",
            "tianji_disambiguate": "context",
            "tianji_health": "system",
            "tianji_help": "system",
            "system_status": "system",
            "tianji_tool_owner": "system",
            "rule_evaluate": "system",
            "session": "conversation",
            "lineage": "conversation",
            "export": "export",
            "list_memories": "export",
            "get_memory": "export",
            "agent_dispatch": "agent",
            "learn_skill": "advanced_memory",
            "multimodal": "advanced_memory",
            "reflective": "advanced_memory",
            "execute_command": "command",
            "check_command": "command",
            "stop_command": "command",
            "process": "command",
            "script": "command",
            "deploy": "ops",
            "rollback": "ops",
            "resource": "ops",
            "scale": "ops",
            "service": "ops",
            "vulnerabilities": "security",
            "compliance": "security",
            "security": "security",
            "permissions": "security",
            "profile": "performance",
            "metrics": "performance",
            "bottleneck": "performance",
            "analyze_bottleneck": "performance",
        }

        for pattern, category in name_patterns.items():
            if pattern in tool_name:
                return category

        return None

    def get_tools_by_category(self, category: str) -> list[str]:
        """获取指定分类的工具名列表"""
        return self._categories.get(category, [])

    def get_category_for_tool(self, tool_name: str) -> str | None:
        """获取工具所属的分类"""
        return self._tool_to_category.get(tool_name)

    def get_all_categories(self) -> dict[str, list[str]]:
        """获取所有工具分类"""
        return {cat: list(tools) for cat, tools in self._categories.items()}

    def list_all_categories(self) -> list[str]:
        """列出所有分类名称"""
        return list(self._categories.keys())

    def list_all_tools(self) -> list[str]:
        """列出所有已分类的工具"""
        return list(self._tool_to_category.keys())

    def refresh(self):
        """从能力矩阵重新加载分类"""
        self._refresh()

    @property
    def last_refresh_time(self) -> float:
        """上次刷新时间"""
        return self._last_refresh_time

    @property
    def is_initialized(self) -> bool:
        """是否已初始化"""
        return self._initialized

    def get_category_count(self) -> int:
        """获取分类数量"""
        return len(self._categories)

    def get_tool_count(self) -> int:
        """获取工具总数"""
        return len(self._tool_to_category)


DEFAULT_MAPPER = ToolCategoryMapper()


def get_tool_category_mapper() -> ToolCategoryMapper:
    """获取全局ToolCategoryMapper单例"""
    return DEFAULT_MAPPER
