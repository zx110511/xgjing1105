"""

能力矩阵注册中心 (Capability Registry) — [v10-ready]

=====================================================

天机Agent编排子包·职责1: 能力矩阵管理



职责边界:

  - AGENT_CAPABILITY_MATRIX 单一数据源 (由AMIM M37生成)

  - PipelineStage 流水线阶段枚举 (基础枚举, 无内部依赖)

  - CapabilityRegistry — Agent元数据解析与能力查询



设计原则:

  本模块为编排子包的最底层 (无内部依赖)，registry ← tracker ← pipeline/dispatcher

  其他子模块的 AGENT_CAPABILITY_MATRIX 均从此处导入，保证单源一致。

  v4.2扩展: 支持从 _AGENT_REGISTRY.json 动态加载，自动填充新字段默认值

位置: 天机/core/orchestration/registry.py

"""

from __future__ import annotations

import json
import os
from copy import deepcopy
from enum import Enum


class PipelineStage(str, Enum):
    ANALYZE = "analyze"
    PLAN = "plan"
    EXECUTE = "execute"
    REVIEW = "review"
    FORMAT = "format"
    VERIFY = "verify"
    DEPLOY = "deploy"
    ARCHIVE = "archive"


DEFAULT_CLEAR_METRICS = {
    "cost": {"token_usage": 0, "api_calls": 0, "model_cost": 0.0},
    "latency": {"total_ms": 0, "ttft_ms": 0, "processing_ms": 0},
    "efficacy": {"success_rate": 0.0, "quality_score": 0.0, "coverage": 0.0},
    "assurance": {
        "security_vulnerabilities": 0,
        "compliance_passed": True,
        "privacy_risk": 0.0,
    },
    "reliability": {
        "consistency_rate": 0.0,
        "recovery_rate": 0.0,
        "sla_compliance": 0.0,
    },
}

DEFAULT_TOPOLOGY_PREFERENCE = {
    "preferred": ["sequential"],
    "compatible": ["sequential", "parallel"],
    "avoid": [],
}

BUILTIN_AGENTS = {
    "trae-chat": {
        "name": "对话",
        "layer": "builtin",
        "role": "Trae内置对话入口",
        "emoji": "💬",
        "source": "trae-builtin",
        "capabilities": ["代码库问答", "文档查询", "通用对话", "上下文理解"],
        "tools": ["read", "file_system", "terminal", "web_search"],
        "clear_metrics": DEFAULT_CLEAR_METRICS,
        "topology_preference": DEFAULT_TOPOLOGY_PREFERENCE,
        "workflow_blueprint_ids": [],
    },
    "trae-agent": {
        "name": "智能体",
        "layer": "builtin",
        "role": "Trae内置智能体入口",
        "emoji": "🤖",
        "source": "trae-builtin",
        "capabilities": ["端到端任务", "多工具协作", "复杂问题解决", "流程编排"],
        "tools": ["read", "file_system", "terminal", "web_search", "agent_dispatch"],
        "clear_metrics": DEFAULT_CLEAR_METRICS,
        "topology_preference": DEFAULT_TOPOLOGY_PREFERENCE,
        "workflow_blueprint_ids": [],
    },
}


def _load_from_registry() -> dict[str, dict]:
    """从 _AGENT_REGISTRY.json 加载Agent能力矩阵"""
    import sys

    trae_agents_dir = os.path.join(
        os.path.dirname(__file__), "..", "..", ".trae", "agents"
    )
    registry_path = os.path.join(trae_agents_dir, "_AGENT_REGISTRY.json")

    if not os.path.exists(registry_path):
        trae_agents_dir = os.path.join(sys.path[0], ".trae", "agents")
        registry_path = os.path.join(trae_agents_dir, "_AGENT_REGISTRY.json")

    if not os.path.exists(registry_path):
        return {}

    try:
        with open(registry_path, encoding="utf-8-sig") as f:
            data = json.load(f)
        return data.get("agents", {})
    except Exception:
        return {}


def _fill_defaults(agent_info: dict) -> dict:
    """为Agent信息填充新字段默认值（使用deepcopy确保嵌套对象独立）"""
    if "clear_metrics" not in agent_info:
        agent_info["clear_metrics"] = deepcopy(DEFAULT_CLEAR_METRICS)
    if "topology_preference" not in agent_info:
        agent_info["topology_preference"] = deepcopy(DEFAULT_TOPOLOGY_PREFERENCE)
    if "workflow_blueprint_ids" not in agent_info:
        agent_info["workflow_blueprint_ids"] = []
    if "source" not in agent_info:
        agent_info["source"] = "tianji"
    if "tools" not in agent_info:
        agent_info["tools"] = []
    if "capabilities" not in agent_info:
        agent_info["capabilities"] = []
    return agent_info


def _build_unified_matrix() -> dict[str, dict]:
    """构建统一能力矩阵：从_AGENT_REGISTRY.json加载 + 内置Agent + 默认值填充"""
    matrix = {}

    registry_data = _load_from_registry()
    if registry_data:
        for agent_id, info in registry_data.items():
            matrix[agent_id] = _fill_defaults(info.copy())
    else:
        matrix = {
            "tiewei": {
                "name": "铁卫",
                "layer": "L0",
                "role": "质量守护",
                "emoji": "🛡️",
                "source": "tianji",
                "capabilities": ["SG门禁", "功能验证", "安全测试", "覆盖率分析"],
                "tools": [
                    "memory_recall",
                    "scan_vulnerabilities",
                    "check_compliance",
                    "profile_function",
                    "analyze_bottleneck",
                    "execute_command",
                ],
                "clear_metrics": DEFAULT_CLEAR_METRICS,
                "topology_preference": DEFAULT_TOPOLOGY_PREFERENCE,
                "workflow_blueprint_ids": [],
            },
            "yiku": {
                "name": "忆库",
                "layer": "L1",
                "role": "记忆架构师",
                "emoji": "🗃️",
                "source": "tianji",
                "capabilities": ["ICME六层管理", "语义检索", "容量监控", "巩固晋升"],
                "tools": [
                    "memory_remember",
                    "memory_recall",
                    "memory_stats",
                    "memory_capacity",
                    "build_working_representation",
                    "memory_consolidate",
                    "search_memories",
                    "get_memory",
                    "list_memories",
                    "run_reflective_cycle",
                    "get_session_digest",
                    "explain_memory_lineage",
                ],
                "clear_metrics": DEFAULT_CLEAR_METRICS,
                "topology_preference": DEFAULT_TOPOLOGY_PREFERENCE,
                "workflow_blueprint_ids": [],
            },
            "dongcha": {
                "name": "洞察",
                "layer": "L1",
                "role": "上下文分析师",
                "emoji": "🔍",
                "source": "tianji",
                "capabilities": ["意图识别", "实体抽取", "情感分析", "关键词提取"],
                "tools": [
                    "context_extract",
                    "memory_recall",
                    "tianji_classify",
                    "tianji_summarize_conversation",
                    "tianji_intercept",
                ],
                "clear_metrics": DEFAULT_CLEAR_METRICS,
                "topology_preference": DEFAULT_TOPOLOGY_PREFERENCE,
                "workflow_blueprint_ids": [],
            },
            "luling": {
                "name": "律令",
                "layer": "L1",
                "role": "规则守护者",
                "emoji": "⚖️",
                "source": "tianji",
                "capabilities": ["规则匹配", "合规检查", "冲突检测", "门禁执行"],
                "tools": ["rule_evaluate", "security-scanner", "memory_recall"],
                "clear_metrics": DEFAULT_CLEAR_METRICS,
                "topology_preference": DEFAULT_TOPOLOGY_PREFERENCE,
                "workflow_blueprint_ids": [],
            },
            "lingxi": {
                "name": "灵犀",
                "layer": "L1",
                "role": "会话监控",
                "emoji": "💠",
                "source": "tianji",
                "capabilities": ["对话完整性", "意图连续性", "上下文恢复", "异常检测"],
                "tools": ["context_extract", "memory_recall", "tianji_intercept"],
                "clear_metrics": DEFAULT_CLEAR_METRICS,
                "topology_preference": DEFAULT_TOPOLOGY_PREFERENCE,
                "workflow_blueprint_ids": [],
            },
            "tianshu": {
                "name": "天枢",
                "layer": "L2",
                "role": "总指挥",
                "emoji": "🎯",
                "source": "tianji",
                "capabilities": ["编排", "决策", "调度", "分发", "全局管理"],
                "tools": [
                    "agent_dispatch",
                    "system_status",
                    "context_extract",
                    "rule_evaluate",
                    "memory_remember",
                    "memory_recall",
                    "execute_command",
                ],
                "clear_metrics": DEFAULT_CLEAR_METRICS,
                "topology_preference": DEFAULT_TOPOLOGY_PREFERENCE,
                "workflow_blueprint_ids": [],
            },
            "wenzong": {
                "name": "文宗",
                "layer": "L2",
                "role": "主编",
                "emoji": "📖",
                "source": "tianji",
                "capabilities": ["项目管理", "内容审核", "进度追踪", "团队协调"],
                "tools": [
                    "agent_dispatch",
                    "system_status",
                    "memory_recall",
                    "execute_command",
                ],
                "clear_metrics": DEFAULT_CLEAR_METRICS,
                "topology_preference": DEFAULT_TOPOLOGY_PREFERENCE,
                "workflow_blueprint_ids": [],
            },
            "jingwei": {
                "name": "经纬",
                "layer": "L2",
                "role": "架构师",
                "emoji": "🏛️",
                "source": "tianji",
                "capabilities": ["架构设计", "技术选型", "路径规划", "重构策略"],
                "tools": [
                    "agent_dispatch",
                    "rule_evaluate",
                    "memory_recall",
                    "execute_command",
                ],
                "clear_metrics": DEFAULT_CLEAR_METRICS,
                "topology_preference": DEFAULT_TOPOLOGY_PREFERENCE,
                "workflow_blueprint_ids": [],
            },
            "miaobi": {
                "name": "妙笔",
                "layer": "L2",
                "role": "创作者",
                "emoji": "✒️",
                "source": "tianji",
                "capabilities": ["创作", "写作", "创意生成", "角色塑造", "世界观构建"],
                "tools": [
                    "memory_recall",
                    "memory_remember",
                    "tianji_semantic_search",
                    "tianji_extract_knowledge",
                ],
                "clear_metrics": DEFAULT_CLEAR_METRICS,
                "topology_preference": DEFAULT_TOPOLOGY_PREFERENCE,
                "workflow_blueprint_ids": [],
            },
            "mingjing": {
                "name": "明镜",
                "layer": "L2",
                "role": "审校者",
                "emoji": "🔍",
                "source": "tianji",
                "capabilities": ["审校", "质量评估", "一致性检查", "风格验证"],
                "tools": ["memory_recall", "rule_evaluate", "security-scanner"],
                "clear_metrics": DEFAULT_CLEAR_METRICS,
                "topology_preference": DEFAULT_TOPOLOGY_PREFERENCE,
                "workflow_blueprint_ids": [],
            },
            "tiansuan": {
                "name": "天算",
                "layer": "L2",
                "role": "数据分析师",
                "emoji": "📊",
                "source": "tianji",
                "capabilities": ["统计分析", "可视化", "模式识别", "报告撰写"],
                "tools": [
                    "memory_recall",
                    "memory_stats",
                    "get_session_digest",
                    "search_memories",
                ],
                "clear_metrics": DEFAULT_CLEAR_METRICS,
                "topology_preference": DEFAULT_TOPOLOGY_PREFERENCE,
                "workflow_blueprint_ids": [],
            },
            "kuangshi": {
                "name": "矿师",
                "layer": "L2",
                "role": "语料处理",
                "emoji": "⛏️",
                "source": "tianji",
                "capabilities": ["语料导入", "数据清洗", "分类标注", "批量处理"],
                "tools": [
                    "memory_remember",
                    "execute_command",
                    "memory_recall",
                    "context_extract",
                ],
                "clear_metrics": DEFAULT_CLEAR_METRICS,
                "topology_preference": DEFAULT_TOPOLOGY_PREFERENCE,
                "workflow_blueprint_ids": [],
            },
            "baiqiao": {
                "name": "百巧",
                "layer": "L3",
                "role": "技能代理",
                "emoji": "⚡",
                "source": "tianji",
                "capabilities": ["技能调用", "工作流编排", "参数验证", "结果格式化"],
                "tools": ["execute_command", "agent_dispatch"],
                "clear_metrics": DEFAULT_CLEAR_METRICS,
                "topology_preference": DEFAULT_TOPOLOGY_PREFERENCE,
                "workflow_blueprint_ids": [],
            },
            "shiguan": {
                "name": "史官",
                "layer": "L3",
                "role": "版本追踪",
                "emoji": "📜",
                "source": "tianji",
                "capabilities": ["版本管理", "历史归档", "变更分析", "回滚支持"],
                "tools": ["memory_recall", "memory_remember", "execute_command"],
                "clear_metrics": DEFAULT_CLEAR_METRICS,
                "topology_preference": DEFAULT_TOPOLOGY_PREFERENCE,
                "workflow_blueprint_ids": [],
            },
            "jinshu": {
                "name": "锦书",
                "layer": "L3",
                "role": "成品导出",
                "emoji": "📖",
                "source": "tianji",
                "capabilities": ["格式导出", "成品美化", "模板应用", "输出验证"],
                "tools": ["execute_command", "memory_recall", "system_status"],
                "clear_metrics": DEFAULT_CLEAR_METRICS,
                "topology_preference": DEFAULT_TOPOLOGY_PREFERENCE,
                "workflow_blueprint_ids": [],
            },
            "jianheng": {
                "name": "简衡",
                "layer": "L1",
                "role": "轻量评估师",
                "emoji": "⚖️",
                "source": "tianji",
                "capabilities": ["快速质量评估", "简易合规检查", "轻量级替代明镜"],
                "tools": ["rule_evaluate", "memory_recall"],
                "clear_metrics": DEFAULT_CLEAR_METRICS,
                "topology_preference": DEFAULT_TOPOLOGY_PREFERENCE,
                "workflow_blueprint_ids": [],
            },
            "qianli": {
                "name": "千里",
                "layer": "L4",
                "role": "系统监控",
                "emoji": "👁️",
                "source": "tianji",
                "capabilities": ["实时监控", "性能采集", "智能告警", "趋势分析"],
                "tools": [
                    "system_status",
                    "ops-engine",
                    "performance-profiler",
                    "memory_recall",
                    "tianji_health",
                ],
                "clear_metrics": DEFAULT_CLEAR_METRICS,
                "topology_preference": DEFAULT_TOPOLOGY_PREFERENCE,
                "workflow_blueprint_ids": [],
            },
            "gongzao": {
                "name": "工造",
                "layer": "L4",
                "role": "DevOps",
                "emoji": "🏗️",
                "source": "tianji",
                "capabilities": ["CI/CD", "环境管理", "服务部署", "资源调度"],
                "tools": ["execute_command", "ops-engine", "agent_dispatch"],
                "clear_metrics": DEFAULT_CLEAR_METRICS,
                "topology_preference": DEFAULT_TOPOLOGY_PREFERENCE,
                "workflow_blueprint_ids": [],
            },
            "zhenshan": {
                "name": "镇山",
                "layer": "L4",
                "role": "安全审计",
                "emoji": "🏔️",
                "source": "tianji",
                "capabilities": ["漏洞扫描", "合规检查", "密钥管理", "数据保护"],
                "tools": ["security-scanner", "execute_command", "memory_recall"],
                "clear_metrics": DEFAULT_CLEAR_METRICS,
                "topology_preference": DEFAULT_TOPOLOGY_PREFERENCE,
                "workflow_blueprint_ids": [],
            },
            "zhuiguang": {
                "name": "追光",
                "layer": "L4",
                "role": "性能优化",
                "emoji": "⚡",
                "source": "tianji",
                "capabilities": ["性能剖析", "瓶颈分析", "基准测试", "资源优化"],
                "tools": ["performance-profiler", "execute_command", "memory_recall"],
                "clear_metrics": DEFAULT_CLEAR_METRICS,
                "topology_preference": DEFAULT_TOPOLOGY_PREFERENCE,
                "workflow_blueprint_ids": [],
            },
            "lianli": {
                "name": "连理",
                "layer": "L2",
                "role": "知识图谱构建师",
                "emoji": "🕸️",
                "source": "tianji",
                "capabilities": [
                    "实体抽取",
                    "关系识别",
                    "图谱构建",
                    "图谱查询",
                    "多跳推理",
                    "路径查找",
                ],
                "tools": [
                    "build_working_representation",
                    "search_memories",
                    "memory_recall",
                    "memory_remember",
                ],
                "clear_metrics": DEFAULT_CLEAR_METRICS,
                "topology_preference": DEFAULT_TOPOLOGY_PREFERENCE,
                "workflow_blueprint_ids": [],
            },
            "huasheng": {
                "name": "化生",
                "layer": "L3",
                "role": "进化工程师",
                "emoji": "🧬",
                "source": "tianji",
                "capabilities": [
                    "自我检查",
                    "自我更新",
                    "递归改进",
                    "规则演化",
                    "架构升级",
                ],
                "tools": [
                    "memory_evolve_self",
                    "memory_remember",
                    "memory_recall",
                    "execute_command",
                    "system_status",
                ],
                "clear_metrics": DEFAULT_CLEAR_METRICS,
                "topology_preference": DEFAULT_TOPOLOGY_PREFERENCE,
                "workflow_blueprint_ids": [],
            },
            "wanxiang": {
                "name": "万象",
                "layer": "L1",
                "role": "多模态感知师",
                "emoji": "👁️‍🗨️",
                "source": "tianji",
                "capabilities": [
                    "图像理解",
                    "表格解析",
                    "公式识别",
                    "模态分类",
                    "多模态统一存储",
                ],
                "tools": [
                    "memory_capture_multimodal",
                    "tianji_classify",
                    "tianji_extract_knowledge",
                    "memory_recall",
                    "memory_remember",
                ],
                "clear_metrics": DEFAULT_CLEAR_METRICS,
                "topology_preference": DEFAULT_TOPOLOGY_PREFERENCE,
                "workflow_blueprint_ids": [],
            },
            "tianji": {
                "name": "天机",
                "layer": "L0",
                "role": "系统总控",
                "emoji": "🏛️",
                "source": "tianji",
                "capabilities": ["全局编排", "模块协调", "生命周期管理", "自进化闭环"],
                "tools": [
                    "agent_dispatch",
                    "system_status",
                    "tianji_health",
                    "tianji_amim_status",
                    "tianji_tool_owner",
                    "execute_command",
                ],
                "clear_metrics": DEFAULT_CLEAR_METRICS,
                "topology_preference": DEFAULT_TOPOLOGY_PREFERENCE,
                "workflow_blueprint_ids": [],
            },
        }

    for agent_id, info in BUILTIN_AGENTS.items():
        matrix[agent_id] = _fill_defaults(info.copy())

    return matrix


AGENT_CAPABILITY_MATRIX: dict[str, dict] = _build_unified_matrix()


class CapabilityRegistry:
    """
    能力矩阵注册中心 — 封装 AGENT_CAPABILITY_MATRIX 的查询与元数据解析

    用法:
        reg = CapabilityRegistry()
        reg.get_name("tianshu")        # -> "天枢"
        reg.get_emoji("tianshu")       # -> "🎯"
        reg.get_tools("yiku")          # -> [...]
        reg.find_by_capability("编排") # -> ["tianshu", ...]
        reg.find_by_source("trae-official") # -> ["ui-designer", ...]

    兼容性: 默认操作全局 AGENT_CAPABILITY_MATRIX (单源)。
    v4.2扩展: 支持按source过滤、CLEAR指标、拓扑偏好查询
    """

    def __init__(self, matrix: dict[str, dict] | None = None):
        self._matrix = matrix if matrix is not None else AGENT_CAPABILITY_MATRIX

    @property
    def matrix(self) -> dict[str, dict]:
        return self._matrix

    def exists(self, agent_id: str) -> bool:
        return agent_id in self._matrix

    def get_agent(self, agent_id: str) -> dict:
        return self._matrix.get(agent_id, {})

    def get_meta(self, agent_id: str) -> dict:
        info = self._matrix.get(agent_id, {})
        return {
            "agent_id": agent_id,
            "agent_name": info.get("name", agent_id),
            "agent_emoji": info.get("emoji", "🤖"),
        }

    def get_name(self, agent_id: str) -> str:
        return self._matrix.get(agent_id, {}).get("name", agent_id)

    def get_emoji(self, agent_id: str) -> str:
        return self._matrix.get(agent_id, {}).get("emoji", "🤖")

    def get_role(self, agent_id: str) -> str:
        return self._matrix.get(agent_id, {}).get("role", "")

    def get_layer(self, agent_id: str) -> str:
        return self._matrix.get(agent_id, {}).get("layer", "")

    def get_tools(self, agent_id: str) -> list[str]:
        return list(self._matrix.get(agent_id, {}).get("tools", []))

    def get_capabilities(self, agent_id: str) -> list[str]:
        return list(self._matrix.get(agent_id, {}).get("capabilities", []))

    def get_source(self, agent_id: str) -> str:
        return self._matrix.get(agent_id, {}).get("source", "tianji")

    def get_clear_metrics(self, agent_id: str) -> dict:
        return self._matrix.get(agent_id, {}).get(
            "clear_metrics", DEFAULT_CLEAR_METRICS
        )

    def get_topology_preference(self, agent_id: str) -> dict:
        return self._matrix.get(agent_id, {}).get(
            "topology_preference", DEFAULT_TOPOLOGY_PREFERENCE
        )

    def get_workflow_blueprint_ids(self, agent_id: str) -> list[str]:
        return self._matrix.get(agent_id, {}).get("workflow_blueprint_ids", [])

    def list_agents(self) -> list[str]:
        return list(self._matrix.keys())

    def find_by_capability(self, capability: str) -> list[str]:
        return [
            aid
            for aid, info in self._matrix.items()
            if any(capability in c for c in info.get("capabilities", []))
        ]

    def find_by_layer(self, layer: str) -> list[str]:
        return [aid for aid, info in self._matrix.items() if info.get("layer") == layer]

    def find_by_tool(self, tool_name: str) -> list[str]:
        return [
            aid
            for aid, info in self._matrix.items()
            if tool_name in info.get("tools", [])
        ]

    def find_by_source(self, source: str) -> list[str]:
        """按来源过滤Agent: tianji / trae-official / trae-builtin"""
        return [
            aid for aid, info in self._matrix.items() if info.get("source") == source
        ]

    def list_all_with_source(self) -> list[dict]:
        """列出全部Agent及其来源"""
        result = []
        for aid, info in self._matrix.items():
            result.append(
                {
                    "agent_id": aid,
                    "name": info.get("name", aid),
                    "layer": info.get("layer", ""),
                    "emoji": info.get("emoji", "🤖"),
                    "source": info.get("source", "tianji"),
                    "capabilities": info.get("capabilities", []),
                }
            )
        return result


DEFAULT_REGISTRY = CapabilityRegistry()
