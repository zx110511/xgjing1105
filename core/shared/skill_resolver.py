"""
天机技能解析器 (Tianji Skill Resolver) v1.0
============================================
将用户对话意图自动匹配到Skill集合,
实现"意图→技能→MCP工具"的智能选择链路。

核心能力:
  1. 关键词匹配 — user_input关键词 ∩ Skill.tags/description
  2. 语义相似度 — TF-IDF向量匹配 (复用天机已有索引)
  3. LLM判断 — 复杂场景让LLM从候选Skills中选择
  4. 工具映射 — 将Skill转换为OpenAI function_call格式

架构位置: 天机/core/skill_resolver.py
依赖: core/skill_registry.py (SkillRegistry), core/mcp_bridge.py (MCPBridge)
"""

from __future__ import annotations

import json
import logging
import re
import time
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger("tianji.skill_resolver")

# 意图关键词 → Skill分类映射
_INTENT_KEYWORD_MAP = {
    "memory_ops": [
        "记忆", "存储", "保存", "记住", "记录", "回忆", "回想",
        "remember", "save", "store", "recall", "memory",
    ],
    "search": [
        "搜索", "查找", "寻找", "检索", "查询", "找",
        "search", "find", "lookup", "query",
    ],
    "llm_intel": [
        "分类", "标签", "摘要", "总结", "提取", "知识",
        "classify", "tag", "summarize", "extract", "knowledge",
    ],
    "knowledge_graph": [
        "图谱", "知识图谱", "关系", "三元组", "推理",
        "graph", "triple", "relation", "reasoning",
    ],
    "context": [
        "上下文", "语境", "归一化", "消歧", "理解",
        "context", "normalize", "disambiguate",
    ],
    "conversation": [
        "对话", "会话", "聊天记录", "历史",
        "conversation", "session", "chat history",
    ],
    "export": [
        "导出", "下载", "备份", "列表",
        "export", "download", "backup", "list",
    ],
    "agent": [
        "调度", "代理", "智能体", "专家", "审查", "调试",
        "dispatch", "agent", "expert", "review", "debug",
    ],
    "advanced_memory": [
        "反思", "巩固", "学习", "多模态",
        "reflect", "consolidate", "learn", "multimodal",
    ],
    "system": [
        "状态", "健康", "帮助", "系统",
        "status", "health", "help", "system",
    ],
    "command": [
        "执行", "运行", "命令", "脚本", "进程", "终端", "命令行",
        "查看文件", "读取文件", "列出目录", "打开文件",
        "execute", "run", "command", "script", "process", "terminal", "shell",
        "list processes", "kill process",
    ],
    "ops": [
        "部署", "服务", "运维", "回滚", "扩缩", "资源",
        "CPU", "内存", "磁盘", "网络",
        "deploy", "service", "ops", "rollback", "scale", "resource",
    ],
    "security": [
        "安全", "漏洞", "扫描", "合规", "权限", "依赖",
        "security", "vulnerability", "scan", "compliance", "permission",
    ],
    "performance": [
        "性能", "瓶颈", "剖析", "QPS", "延迟", "吞吐",
        "热点", "CPU占用", "内存占用",
        "performance", "bottleneck", "profile", "latency", "throughput",
    ],
}

# 每个分类对应的推荐提示语
_CATEGORY_SUGGESTIONS = {
    "memory_ops": "记忆操作",
    "search": "智能搜索",
    "llm_intel": "AI分析",
    "knowledge_graph": "知识图谱",
    "context": "上下文理解",
    "conversation": "对话管理",
    "export": "数据导出",
    "agent": "Agent调度",
    "advanced_memory": "高级记忆",
    "system": "系统信息",
    "command": "命令执行",
    "ops": "运维管理",
    "security": "安全审计",
    "performance": "性能剖析",
}


class SkillResolver:
    """对话意图 → Skill集合 解析器

    输入: 用户消息 + 对话历史上下文
    输出: 相关Skill列表 (按相关性排序, top-k)

    匹配策略 (三级递进):
      L1 关键词匹配: user_input关键词 ∩ _INTENT_KEYWORD_MAP
      L2 语义相似度: TF-IDF向量匹配 (复用天机已有索引)
      L3 LLM判断: 复杂场景让LLM从候选Skills中选择
    """

    VERSION = "1.0.0"

    def __init__(self):
        self._mcp_bridge = None
        self._skill_registry = None
        self._resolve_count = 0
        self._cache: Dict[str, Tuple[float, List[Dict]]] = {}
        self._cache_ttl = 60.0  # 缓存60秒
        self._init_time = time.time()

    def _get_mcp_bridge(self):
        """延迟加载MCPBridge"""
        if self._mcp_bridge is None:
            try:
                from core.shared.mcp_bridge import get_mcp_bridge
                self._mcp_bridge = get_mcp_bridge()
            except ImportError:
                logger.warning("SkillResolver: MCPBridge不可用")
        return self._mcp_bridge

    def _get_skill_registry(self):
        """延迟加载SkillRegistry (v9.1修复: 使用正确的Skills目录)"""
        if self._skill_registry is None:
            try:
                from core.shared.skill_registry import SkillRegistry
                from pathlib import Path
                # v9.1修复: 优先使用.agents/skills, 回退到.trae/skills
                _root = Path(__file__).resolve().parent.parent
                _skills_dir = _root / ".agents" / "skills"
                if not _skills_dir.exists() or not any(_skills_dir.iterdir()):
                    _skills_dir = _root / ".trae" / "skills"
                self._skill_registry = SkillRegistry(skills_dir=_skills_dir)
                self._skill_registry.discover()
            except ImportError:
                logger.warning("SkillResolver: SkillRegistry不可用")
        return self._skill_registry

    def resolve(
        self,
        user_input: str,
        context: Optional[List[Dict]] = None,
        top_k: int = 5,
    ) -> List[Dict]:
        """解析用户意图, 返回最相关的Skills

        Args:
            user_input: 用户输入文本
            context: 对话历史 (可选)
            top_k: 返回最多top_k个Skills

        Returns:
            排序后的Skill信息列表, 每项包含:
              - name: 工具名
              - description: 描述
              - category: 分类
              - relevance: 相关性分数 (0-1)
              - suggestion: 推荐提示语
        """
        self._resolve_count += 1

        # 缓存检查
        cache_key = f"{user_input[:100]}:{top_k}"
        now = time.time()
        if cache_key in self._cache:
            cached_time, cached_result = self._cache[cache_key]
            if now - cached_time < self._cache_ttl:
                return cached_result

        # L1: 关键词匹配
        matched_categories = self._keyword_match(user_input)

        # L2: 如果关键词匹配不足, 尝试语义搜索
        if len(matched_categories) < 2:
            semantic_categories = self._semantic_match(user_input)
            for cat in semantic_categories:
                if cat not in matched_categories:
                    matched_categories.append(cat)

        # 构建结果
        bridge = self._get_mcp_bridge()
        results = []

        for category in matched_categories:
            tools = bridge.get_tools_by_category(category) if bridge else []
            suggestion = _CATEGORY_SUGGESTIONS.get(category, category)

            for tool_name in tools:
                # 获取工具定义
                tool_defs = bridge.get_tool_definitions() if bridge else []
                tool_def = next(
                    (t for t in tool_defs if t["function"]["name"] == tool_name),
                    None
                )

                if tool_def:
                    func = tool_def["function"]
                    results.append({
                        "name": func["name"],
                        "description": func.get("description", ""),
                        "category": category,
                        "relevance": self._calc_relevance(
                            user_input, func["name"], func.get("description", ""), category
                        ),
                        "suggestion": suggestion,
                    })

        # 按相关性排序
        results.sort(key=lambda x: x["relevance"], reverse=True)

        # 截取top_k
        results = results[:top_k]

        # 缓存
        self._cache[cache_key] = (now, results)
        return results

    def _keyword_match(self, user_input: str) -> List[str]:
        """L1: 关键词匹配"""
        input_lower = user_input.lower()
        matched = []

        for category, keywords in _INTENT_KEYWORD_MAP.items():
            for kw in keywords:
                if kw in input_lower:
                    if category not in matched:
                        matched.append(category)
                    break

        return matched

    def _semantic_match(self, user_input: str) -> List[str]:
        """L2: 语义相似度匹配 (使用天机语义搜索API)"""
        try:
            import urllib.request
            req = urllib.request.Request(
                "http://127.0.0.1:8771/api/llm/expand_query",
                data=json.dumps({"query": user_input}).encode(),
                headers={"Content-Type": "application/json"},
            )
            resp = urllib.request.urlopen(req, timeout=10)
            data = json.loads(resp.read().decode())
            if data.get("success") and data.get("expansions"):
                expanded = " ".join(data["expansions"])
                return self._keyword_match(expanded)
        except Exception:
            pass
        return []

    def _calc_relevance(
        self, user_input: str, tool_name: str, description: str, category: str
    ) -> float:
        """计算相关性分数 (0-1)"""
        score = 0.0
        input_lower = user_input.lower()

        # 关键词命中加分
        keywords = _INTENT_KEYWORD_MAP.get(category, [])
        hit_count = sum(1 for kw in keywords if kw in input_lower)
        if keywords:
            score += min(hit_count / len(keywords), 1.0) * 0.5

        # 工具名匹配加分
        name_parts = tool_name.replace("_", " ").split()
        for part in name_parts:
            if part in input_lower:
                score += 0.2
                break

        # 描述匹配加分
        desc_lower = description.lower()
        for word in input_lower.split():
            if len(word) > 1 and word in desc_lower:
                score += 0.1

        return min(score, 1.0)

    def to_tool_definitions(self, skills: List[Dict]) -> List[Dict]:
        """将选定的Skills转换为OpenAI function_call格式

        Args:
            skills: resolve()返回的Skill列表

        Returns:
            OpenAI tools格式列表
        """
        bridge = self._get_mcp_bridge()
        if not bridge:
            return []

        all_defs = bridge.get_tool_definitions()
        selected_names = {s["name"] for s in skills}

        return [t for t in all_defs if t["function"]["name"] in selected_names]

    def get_suggested_replies(self, skills: List[Dict]) -> List[str]:
        """基于匹配的Skills生成推荐回复选项

        Args:
            skills: resolve()返回的Skill列表

        Returns:
            2-4个推荐回复文本
        """
        suggestions = []
        seen_categories = set()

        for skill in skills[:4]:
            cat = skill["category"]
            if cat in seen_categories:
                continue
            seen_categories.add(cat)

            name = skill["name"]
            desc = skill["description"][:30]

            if cat == "memory_ops":
                suggestions.append(f"帮我记住: {desc}")
            elif cat == "search":
                suggestions.append(f"搜索: {desc}")
            elif cat == "llm_intel":
                suggestions.append(f"分析: {desc}")
            elif cat == "agent":
                suggestions.append(f"调度专家: {desc}")
            else:
                suggestions.append(f"使用{skill['suggestion']}: {desc}")

        # 确保至少有2个
        if len(suggestions) < 2:
            suggestions.extend([
                "搜索我的记忆",
                "帮我记住这段内容",
            ])

        return suggestions[:4]

    def health(self) -> Dict[str, Any]:
        """健康检查"""
        bridge = self._get_mcp_bridge()
        return {
            "status": "healthy" if bridge else "degraded",
            "version": self.VERSION,
            "resolve_count": self._resolve_count,
            "cache_size": len(self._cache),
            "mcp_bridge_available": bridge is not None,
            "uptime_seconds": time.time() - self._init_time,
        }


# 全局单例
_resolver_instance: Optional[SkillResolver] = None


def get_skill_resolver() -> SkillResolver:
    """获取全局SkillResolver单例"""
    global _resolver_instance
    if _resolver_instance is None:
        _resolver_instance = SkillResolver()
    return _resolver_instance
