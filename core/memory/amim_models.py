# -*- coding: utf-8-sig -*-
"""AMIM — Agent定义+MCP工具绑定模型

从 amim.py 拆分 (SSS-PhaseB)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class AgentLayer(Enum):
    L0 = 0  # 基础设施守护 (铁卫)
    L1 = 1  # 数据/上下文层 (忆库/洞察/律令/灵犀)
    L2 = 2  # 决策/创作层 (天枢/文宗/经纬/妙笔/明镜/天算/矿师)
    L3 = 3  # 执行/工具层 (百巧/史官/锦书)
    L4 = 4  # 运维/观测层 (千里/工造/镇山/追光)


@dataclass
class AgentDefinition:
    agent_id: str
    name: str
    layer: AgentLayer
    role: str
    emoji: str
    capabilities: list[str]
    tools: list[str]
    mcp_server: str
    skill_ids: list[str] = field(default_factory=list)
    runtime_class: str | None = None

    lingjing_service_id: str | None = None
    lingjing_port: int | None = None
    health_endpoint: str | None = None
    grpc_proto: str | None = None
    collaboration_partners: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "agent_id": self.agent_id,
            "name": self.name,
            "layer": self.layer.name,
            "layer_value": self.layer.value,
            "role": self.role,
            "emoji": self.emoji,
            "capabilities": self.capabilities,
            "tools": self.tools,
            "mcp_server": self.mcp_server,
            "skill_ids": self.skill_ids,
            "runtime_class": self.runtime_class,
            "lingjing_service_id": self.lingjing_service_id,
            "lingjing_port": self.lingjing_port,
            "health_endpoint": self.health_endpoint,
            "grpc_proto": self.grpc_proto,
            "collaboration_partners": self.collaboration_partners,
        }

    def to_tvp(self) -> str:
        return f"[TVP] {self.emoji} @{self.name}({self.agent_id}) L{self.layer.value} -> {self.mcp_server}"


@dataclass
class MCPToolBinding:
    tool_name: str
    description: str
    owner_agent_id: str
    delegate_agent_ids: list[str] = field(default_factory=list)
    mcp_server: str = "memory-engine-global"
    is_lingjing_ready: bool = False
    input_schema: dict | None = None


TOOL_AGENT_MAPPING: dict[str, dict] = {
    "memory_remember": {
        "owner": "yiku",
        "delegates": ["tianshu", "miaobi", "kuangshi", "shiguan"],
        "description": "写入新记忆条目到ICME六层记忆系统",
    },
    "memory_recall": {
        "owner": "yiku",
        "delegates": ["*"],
        "description": "语义检索记忆——全员可用",
    },
    "memory_forget": {
        "owner": "yiku",
        "delegates": [],
        "description": "遗忘指定记忆条目",
    },
    "memory_stats": {
        "owner": "yiku",
        "delegates": ["tiansuan", "qianli"],
        "description": "获取记忆系统统计信息",
    },
    "memory_capacity": {
        "owner": "yiku",
        "delegates": ["qianli"],
        "description": "ICME六层容量监控",
    },
    "memory_consolidate": {
        "owner": "yiku",
        "delegates": [],
        "description": "记忆巩固晋升(工作记忆→长期记忆)",
    },
    "search_memories": {
        "owner": "yiku",
        "delegates": ["dongcha", "tiansuan"],
        "description": "全文搜索记忆条目",
    },
    "get_memory": {
        "owner": "yiku",
        "delegates": ["*"],
        "description": "按ID获取单条记忆",
    },
    "list_memories": {
        "owner": "yiku",
        "delegates": ["*"],
        "description": "列表查询记忆条目",
    },
    "build_working_representation": {
        "owner": "yiku",
        "delegates": [],
        "description": "构建工作记忆表示(ICME核心)",
    },
    "run_reflective_cycle": {
        "owner": "yiku",
        "delegates": [],
        "description": "运行记忆反思循环",
    },
    "get_session_digest": {
        "owner": "yiku",
        "delegates": ["dongcha", "lingxi"],
        "description": "获取会话摘要信息",
    },
    "explain_memory_lineage": {
        "owner": "yiku",
        "delegates": [],
        "description": "解释记忆谱系(父子+融合关系)",
    },
    "tianji_health": {
        "owner": "qianli",
        "delegates": ["tianshu", "gongzao"],
        "description": "天机系统全组件健康检查",
    },
    "tianji_help": {
        "owner": "tianshu",
        "delegates": ["*"],
        "description": "天机帮助系统",
    },
    "tianji_classify": {
        "owner": "dongcha",
        "delegates": ["kuangshi"],
        "description": "天机语义分类",
    },
    "tianji_auto_tag": {
        "owner": "kuangshi",
        "delegates": ["dongcha"],
        "description": "天机自动标签生成",
    },
    "tianji_summarize": {
        "owner": "tiansuan",
        "delegates": ["dongcha"],
        "description": "天机内容摘要",
    },
    "tianji_extract_knowledge": {
        "owner": "dongcha",
        "delegates": ["miaobi", "tiansuan"],
        "description": "天机知识提取",
    },
    "tianji_expand_query": {
        "owner": "dongcha",
        "delegates": ["miaobi"],
        "description": "天机查询扩展",
    },
    "tianji_semantic_search": {
        "owner": "dongcha",
        "delegates": ["miaobi", "tiansuan"],
        "description": "天机语义搜索",
    },
    "tianji_intercept": {
        "owner": "lingxi",
        "delegates": ["dongcha"],
        "description": "天机会话拦截/上下文保护",
    },
    "tianji_normalize": {
        "owner": "dongcha",
        "delegates": ["yiku", "lingxi"],
        "description": "TCL术语归一化(统一规范语言)",
    },
    "tianji_disambiguate": {
        "owner": "dongcha",
        "delegates": ["lingxi", "yiku"],
        "description": "TCL多义词消歧",
    },
    "tianji_export": {
        "owner": "jinshu",
        "delegates": ["shiguan"],
        "description": "天机数据导出",
    },
    "tianji_summarize_conversation": {
        "owner": "dongcha",
        "delegates": ["lingxi"],
        "description": "天机会话摘要",
    },
    "agent_dispatch": {
        "owner": "tianshu",
        "delegates": ["wenzong", "jingwei", "baiqiao", "gongzao"],
        "description": "Agent调度分发",
    },
    "system_status": {
        "owner": "qianli",
        "delegates": ["tianshu", "wenzong", "gongzao", "lingxi"],
        "description": "系统全局状态查询",
    },
    "context_extract": {
        "owner": "dongcha",
        "delegates": ["lingxi", "tianshu"],
        "description": "上下文结构化提取",
    },
    "rule_evaluate": {
        "owner": "luling",
        "delegates": ["tianshu", "jingwei", "mingjing"],
        "description": "规则引擎评估",
    },
    "execute_command": {
        "owner": "baiqiao",
        "delegates": [
            "tianshu",
            "wenzong",
            "jingwei",
            "gongzao",
            "zhenshan",
            "zhuiguang",
        ],
        "description": "执行系统命令",
    },
    "security-scanner": {
        "owner": "zhenshan",
        "delegates": ["tiewei", "luling", "mingjing"],
        "description": "安全扫描工具",
    },
    "performance-profiler": {
        "owner": "zhuiguang",
        "delegates": ["qianli", "tiewei"],
        "description": "性能剖析工具",
    },
    "ops-engine": {
        "owner": "gongzao",
        "delegates": ["qianli"],
        "description": "运维引擎操作",
    },
    "tianji_tool_owner": {
        "owner": "tianshu",
        "delegates": ["*"],
        "description": "查询工具归属Agent、MCP服务器和委托权限",
    },
    "tianji_amim_status": {
        "owner": "tianshu",
        "delegates": ["*"],
        "description": "获取AMIM M37集成桥接模块状态和统计信息",
    },
    "memory_build_graph": {
        "owner": "lianli",
        "delegates": ["tianshu", "dongcha"],
        "description": "触发知识图谱构建——从记忆层抽取三元组并写入图谱存储",
    },
    "memory_query_graph": {
        "owner": "lianli",
        "delegates": ["tianshu", "tiansuan", "dongcha"],
        "description": "查询知识图谱——多跳推理和路径查找",
    },
    "memory_evolve_self": {
        "owner": "huasheng",
        "delegates": ["tianshu"],
        "description": "触发天机自我进化——Godel三循环(检查→更新→递归)",
    },
    "memory_learn_skill": {
        "owner": "huasheng",
        "delegates": ["tianshu", "baiqiao"],
        "description": "从演示中学习新技能——写入程序记忆层",
    },
    "memory_capture_multimodal": {
        "owner": "wanxiang",
        "delegates": ["tianshu", "dongcha"],
        "description": "捕获多模态记忆——图像/表格/公式解析并统一存储",
    },
}

LINGJING_FUTURE_TOOLS: dict[str, dict] = {
    "agent_scale": {"owner": "tianshu", "phase": 1, "description": "Agent水平扩展"},
    "agent_health": {
        "owner": "qianli",
        "phase": 1,
        "description": "Agent健康检查(分布式)",
    },
    "agent_route": {"owner": "tianshu", "phase": 2, "description": "Agent动态路由"},
    "agent_register": {"owner": "tianshu", "phase": 1, "description": "Agent服务注册"},
    "agent_deregister": {
        "owner": "tianshu",
        "phase": 3,
        "description": "Agent服务注销",
    },
    "agent_heartbeat": {"owner": "qianli", "phase": 1, "description": "Agent心跳检测"},
    "service_discover": {"owner": "tianshu", "phase": 2, "description": "服务发现"},
    "service_config_push": {
        "owner": "gongzao",
        "phase": 3,
        "description": "服务配置推送",
    },
    "service_config_pull": {
        "owner": "gongzao",
        "phase": 2,
        "description": "服务配置拉取",
    },
    "distributed_lock": {"owner": "tianshu", "phase": 2, "description": "分布式锁"},
    "distributed_cache": {"owner": "yiku", "phase": 3, "description": "分布式缓存"},
    "message_publish": {
        "owner": "tianshu",
        "phase": 2,
        "description": "消息发布(Kafka)",
    },
    "message_subscribe": {
        "owner": "tianshu",
        "phase": 2,
        "description": "消息订阅(Kafka)",
    },
    "stream_process": {"owner": "dongcha", "phase": 4, "description": "流式处理"},
    "stream_aggregate": {"owner": "tiansuan", "phase": 4, "description": "流式聚合"},
    "circuit_breaker": {"owner": "tiewei", "phase": 3, "description": "熔断器"},
    "rate_limiter": {"owner": "tiewei", "phase": 2, "description": "限流器"},
}

KNOWN_TOOLS: set[str] = set(TOOL_AGENT_MAPPING.keys())

KNOWN_MCP_SERVERS: set[str] = {
    "memory-engine-global",
    "agent-framework-global",
    "command-executor",
    "ops-engine",
    "performance-profiler",
    "security-scanner",
}


__all__ = [
    "AgentLayer",
    "AgentDefinition",
    "MCPToolBinding",
    "TOOL_AGENT_MAPPING",
    "KNOWN_TOOLS",
    "KNOWN_MCP_SERVERS",
]
