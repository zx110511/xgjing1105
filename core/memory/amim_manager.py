# -*- coding: utf-8-sig -*-
"""AMIM — Agent MCP集成管理器

从 amim.py 拆分 (SSS-PhaseB)
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path

# SSS-PhaseE: 修复AgentDefinition/AgentLayer导入缺失
from .amim_models import TOOL_AGENT_MAPPING, AgentDefinition, AgentLayer

logger = logging.getLogger(__name__)


class AgentMCPIntegrationManager:
    """
    天机v9.1 M37 — Agent-MCP集成桥接模块

    职责:
      1. 统一加载20个Agent定义
      2. 维护 24工具↔Agent 的归属映射
      3. 生成 _AGENT_REGISTRY.json (写入.trae)
      4. 生成 agent_orchestrator.py 中的 AGENT_CAPABILITY_MATRIX (同步)
      5. 为灵境生成 AgentService 描述 JSON
      6. 验证 Agent↔MCP服务器↔工具 的一致性
    """

    VERSION = "1.0.0"
    MODULE_ID = "M37"

    AGENT_DEFINITIONS: list[AgentDefinition] = [
        AgentDefinition(
            agent_id="tiewei",
            name="铁卫",
            layer=AgentLayer.L0,
            role="质量守护",
            emoji="🛡️",
            capabilities=["SG门禁", "功能验证", "安全测试", "覆盖率分析"],
            tools=[
                "memory_recall",
                "security-scanner",
                "performance-profiler",
                "execute_command",
            ],
            mcp_server="security-scanner",
            skill_ids=["memory/recall:1.0", "system/diagnose:1.0"],
            runtime_class="TieweiAgent",
            lingjing_service_id="svc-quality-gate",
            lingjing_port=8810,
            health_endpoint="/health/quality-gate",
            collaboration_partners=["tianshu", "zhenshan", "mingjing"],
        ),
        AgentDefinition(
            agent_id="yiku",
            name="忆库",
            layer=AgentLayer.L1,
            role="记忆架构师",
            emoji="💾",
            capabilities=["ICME六层管理", "语义检索", "容量监控", "巩固晋升"],
            tools=[
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
            mcp_server="memory-engine-global",
            skill_ids=[
                "memory/remember:1.0",
                "memory/recall:1.0",
                "memory/auto-capture:1.0",
            ],
            runtime_class="YikuAgent",
            lingjing_service_id="svc-memory-core",
            lingjing_port=8820,
            health_endpoint="/health/memory",
            collaboration_partners=["tianshu", "dongcha", "tiansuan", "kuangshi"],
        ),
        AgentDefinition(
            agent_id="dongcha",
            name="洞察",
            layer=AgentLayer.L1,
            role="上下文分析师",
            emoji="🔎",
            capabilities=["意图识别", "实体抽取", "情感分析", "关键词提取"],
            tools=[
                "context_extract",
                "memory_recall",
                "tianji_classify",
                "tianji_summarize_conversation",
                "tianji_intercept",
            ],
            mcp_server="agent-framework-global",
            skill_ids=["context/extract:1.0"],
            runtime_class="DongchaAgent",
            lingjing_service_id="svc-context-analyzer",
            lingjing_port=8821,
            health_endpoint="/health/context",
            collaboration_partners=["tianshu", "yiku", "lingxi"],
        ),
        AgentDefinition(
            agent_id="luling",
            name="律令",
            layer=AgentLayer.L1,
            role="规则守护者",
            emoji="⚖️",
            capabilities=["规则匹配", "合规检查", "冲突检测", "门禁执行"],
            tools=["rule_evaluate", "security-scanner", "memory_recall"],
            mcp_server="agent-framework-global",
            skill_ids=[],
            runtime_class="LulingAgent",
            lingjing_service_id="svc-rule-engine",
            lingjing_port=8822,
            health_endpoint="/health/rules",
            collaboration_partners=["tianshu", "tiewei", "mingjing"],
        ),
        AgentDefinition(
            agent_id="lingxi",
            name="灵犀",
            layer=AgentLayer.L1,
            role="会话监控",
            emoji="🦋",
            capabilities=["对话完整性", "意图连续性", "上下文恢复", "异常检测"],
            tools=["context_extract", "memory_recall", "tianji_intercept"],
            mcp_server="agent-framework-global",
            skill_ids=[
                "context/extract:1.0",
                "agent/dispatch:1.0",
                "agent/transparent-dispatch:1.0",
            ],
            runtime_class="LingxiAgent",
            lingjing_service_id="svc-session-guardian",
            lingjing_port=8823,
            health_endpoint="/health/session",
            collaboration_partners=["tianshu", "dongcha"],
        ),
        AgentDefinition(
            agent_id="tianshu",
            name="天枢",
            layer=AgentLayer.L2,
            role="总指挥",
            emoji="🎯",
            capabilities=["编排", "决策", "调度", "分发", "全局管理"],
            tools=[
                "agent_dispatch",
                "system_status",
                "context_extract",
                "rule_evaluate",
                "memory_remember",
                "memory_recall",
                "execute_command",
            ],
            mcp_server="agent-framework-global",
            skill_ids=[
                "agent/dispatch:1.0",
                "agent/transparent-dispatch:1.0",
                "context/extract:1.0",
            ],
            runtime_class="TianshuAgent",
            lingjing_service_id="svc-orchestrator",
            lingjing_port=8800,
            health_endpoint="/health/orchestrator",
            collaboration_partners=[
                "wenzong",
                "jingwei",
                "yiku",
                "dongcha",
                "luling",
                "lingxi",
                "miaobi",
                "mingjing",
                "tiansuan",
                "kuangshi",
                "baiqiao",
                "shiguan",
                "jinshu",
                "qianli",
                "gongzao",
                "zhenshan",
                "zhuiguang",
                "tiewei",
                "tianji",
                "lianli",
                "huasheng",
                "wanxiang",
            ],
        ),
        AgentDefinition(
            agent_id="wenzong",
            name="文宗",
            layer=AgentLayer.L2,
            role="主编",
            emoji="📝",
            capabilities=["项目管理", "内容审核", "进度追踪", "团队协调"],
            tools=[
                "agent_dispatch",
                "system_status",
                "memory_recall",
                "execute_command",
            ],
            mcp_server="agent-framework-global",
            skill_ids=[],
            runtime_class="WenzongAgent",
            lingjing_service_id="svc-editor-chief",
            lingjing_port=8801,
            health_endpoint="/health/editor",
            collaboration_partners=["tianshu", "miaobi", "mingjing", "shiguan"],
        ),
        AgentDefinition(
            agent_id="jingwei",
            name="经纬",
            layer=AgentLayer.L2,
            role="架构师",
            emoji="📐",
            capabilities=["架构设计", "技术选型", "路径规划", "重构策略"],
            tools=[
                "agent_dispatch",
                "rule_evaluate",
                "memory_recall",
                "execute_command",
            ],
            mcp_server="agent-framework-global",
            skill_ids=[],
            runtime_class="JingweiAgent",
            lingjing_service_id="svc-architect",
            lingjing_port=8802,
            health_endpoint="/health/architect",
            collaboration_partners=["tianshu", "wenzong", "gongzao"],
        ),
        AgentDefinition(
            agent_id="miaobi",
            name="妙笔",
            layer=AgentLayer.L2,
            role="创作者",
            emoji="✍️",
            capabilities=["创作", "写作", "创意生成", "角色塑造", "世界观构建"],
            tools=[
                "memory_recall",
                "memory_remember",
                "tianji_semantic_search",
                "tianji_extract_knowledge",
            ],
            mcp_server="memory-engine-global",
            skill_ids=["novel/chapter-create:1.0", "novel/worldbuilding-expand:1.0"],
            runtime_class="MiaobiAgent",
            lingjing_service_id="svc-creator",
            lingjing_port=8803,
            health_endpoint="/health/creator",
            collaboration_partners=[
                "tianshu",
                "wenzong",
                "mingjing",
                "yiku",
                "kuangshi",
            ],
        ),
        AgentDefinition(
            agent_id="mingjing",
            name="明镜",
            layer=AgentLayer.L2,
            role="审校者",
            emoji="🔍",
            capabilities=["审校", "质量评估", "一致性检查", "风格验证"],
            tools=["memory_recall", "rule_evaluate", "security-scanner"],
            mcp_server="agent-framework-global",
            skill_ids=[
                "novel/consistency-check:1.0",
                "novel/setting-consistency-deep:1.0",
            ],
            runtime_class="MingjingAgent",
            lingjing_service_id="svc-reviewer",
            lingjing_port=8804,
            health_endpoint="/health/reviewer",
            collaboration_partners=["tianshu", "wenzong", "tiewei", "miaobi"],
        ),
        AgentDefinition(
            agent_id="tiansuan",
            name="天算",
            layer=AgentLayer.L2,
            role="数据分析师",
            emoji="📊",
            capabilities=["统计分析", "可视化", "模式识别", "报告撰写"],
            tools=[
                "memory_recall",
                "memory_stats",
                "tianji_summarize",
                "tianji_semantic_search",
            ],
            mcp_server="memory-engine-global",
            skill_ids=[],
            runtime_class="TiansuanAgent",
            lingjing_service_id="svc-analyst",
            lingjing_port=8805,
            health_endpoint="/health/analyst",
            collaboration_partners=["tianshu", "yiku", "qianli"],
        ),
        AgentDefinition(
            agent_id="kuangshi",
            name="矿师",
            layer=AgentLayer.L2,
            role="语料处理",
            emoji="⛏️",
            capabilities=["语料导入", "数据清洗", "分类标注", "批量处理"],
            tools=[
                "memory_remember",
                "execute_command",
                "memory_recall",
                "tianji_auto_tag",
                "tianji_classify",
            ],
            mcp_server="memory-engine-global",
            skill_ids=[
                "corpus/batch-import:1.0",
                "corpus/extract:1.0",
                "corpus/quality-score:1.0",
            ],
            runtime_class="KuangshiAgent",
            lingjing_service_id="svc-corpus-miner",
            lingjing_port=8806,
            health_endpoint="/health/corpus",
            collaboration_partners=["tianshu", "yiku", "miaobi"],
        ),
        AgentDefinition(
            agent_id="baiqiao",
            name="百巧",
            layer=AgentLayer.L3,
            role="技能代理",
            emoji="⚡",
            capabilities=["技能调用", "工作流编排", "参数验证", "结果格式化"],
            tools=["execute_command", "agent_dispatch"],
            mcp_server="command-executor",
            skill_ids=[
                "agent/dispatch:1.0",
                "novel/format-export:1.0",
                "novel/version-track:1.0",
            ],
            runtime_class="BaiqiaoAgent",
            lingjing_service_id="svc-skill-invoker",
            lingjing_port=8830,
            health_endpoint="/health/skills",
            collaboration_partners=["tianshu", "gongzao", "jinshu"],
        ),
        AgentDefinition(
            agent_id="shiguan",
            name="史官",
            layer=AgentLayer.L3,
            role="版本追踪",
            emoji="📜",
            capabilities=["版本管理", "历史归档", "变更分析", "回滚支持"],
            tools=["memory_recall", "memory_remember", "tianji_export"],
            mcp_server="memory-engine-global",
            skill_ids=["novel/version-track:1.0"],
            runtime_class="ShiguanAgent",
            lingjing_service_id="svc-history-tracker",
            lingjing_port=8831,
            health_endpoint="/health/history",
            collaboration_partners=["tianshu", "wenzong", "yiku"],
        ),
        AgentDefinition(
            agent_id="jinshu",
            name="锦书",
            layer=AgentLayer.L3,
            role="成品导出",
            emoji="📖",
            capabilities=["格式导出", "成品美化", "模板应用", "输出验证"],
            tools=["execute_command", "memory_recall", "tianji_export"],
            mcp_server="command-executor",
            skill_ids=["novel/format-export:1.0"],
            runtime_class="JinshuAgent",
            lingjing_service_id="svc-exporter",
            lingjing_port=8832,
            health_endpoint="/health/export",
            collaboration_partners=["tianshu", "baiqiao", "shiguan"],
        ),
        AgentDefinition(
            agent_id="jianheng",
            name="鉴衡",
            layer=AgentLayer.L3,
            role="全维审计师",
            emoji="🔬",
            capabilities=[
                "5维全量审计",
                "功能完整性检查",
                "系统稳定性审计",
                "性能基准测试",
                "安全合规扫描",
                "数据准确性验证",
                "审计报告生成",
                "历史趋势分析",
            ],
            tools=[
                "audit_run",
                "audit_status",
                "audit_history",
                "audit_report",
                "memory_recall",
                "system_status",
            ],
            mcp_server="memory-engine-global",
            skill_ids=["system/diagnose:1.0", ".audit:1.0"],
            runtime_class="JianhengAgent",
            lingjing_service_id="svc-auditor",
            lingjing_port=8835,
            health_endpoint="/health/auditor",
            collaboration_partners=[
                "tianshu",
                "zhenshan",
                "zhuiguang",
                "qianli",
                "tiewei",
                "yiku",
                "luling",
            ],
        ),
        AgentDefinition(
            agent_id="qianli",
            name="千里",
            layer=AgentLayer.L4,
            role="系统监控",
            emoji="👁",
            capabilities=["实时监控", "性能采集", "智能告警", "趋势分析"],
            tools=[
                "system_status",
                "ops-engine",
                "performance-profiler",
                "memory_recall",
                "tianji_health",
            ],
            mcp_server="performance-profiler",
            skill_ids=["system/diagnose:1.0"],
            runtime_class="QianliAgent",
            lingjing_service_id="svc-monitor",
            lingjing_port=8840,
            health_endpoint="/health/monitor",
            collaboration_partners=["tianshu", "gongzao", "zhuiguang", "tiansuan"],
        ),
        AgentDefinition(
            agent_id="gongzao",
            name="工造",
            layer=AgentLayer.L4,
            role="DevOps",
            emoji="🚀",
            capabilities=["CI/CD", "环境管理", "服务部署", "资源调度"],
            tools=["execute_command", "ops-engine", "agent_dispatch"],
            mcp_server="ops-engine",
            skill_ids=[],
            runtime_class="GongzaoAgent",
            lingjing_service_id="svc-devops",
            lingjing_port=8841,
            health_endpoint="/health/devops",
            collaboration_partners=["tianshu", "jingwei", "qianli", "baiqiao"],
        ),
        AgentDefinition(
            agent_id="zhenshan",
            name="镇山",
            layer=AgentLayer.L4,
            role="安全审计",
            emoji="🔒",
            capabilities=["漏洞扫描", "合规检查", "密钥管理", "数据保护"],
            tools=["security-scanner", "execute_command", "memory_recall"],
            mcp_server="security-scanner",
            skill_ids=[],
            runtime_class="ZhenshanAgent",
            lingjing_service_id="svc-security",
            lingjing_port=8842,
            health_endpoint="/health/security",
            collaboration_partners=["tianshu", "tiewei", "qianli"],
        ),
        AgentDefinition(
            agent_id="zhuiguang",
            name="追光",
            layer=AgentLayer.L4,
            role="性能优化",
            emoji="⚡",
            capabilities=["性能剖析", "瓶颈分析", "基准测试", "资源优化"],
            tools=["performance-profiler", "execute_command", "memory_recall"],
            mcp_server="performance-profiler",
            skill_ids=[],
            runtime_class="ZhuiguangAgent",
            lingjing_service_id="svc-performance",
            lingjing_port=8843,
            health_endpoint="/health/performance",
            collaboration_partners=["tianshu", "qianli", "gongzao"],
        ),
        AgentDefinition(
            agent_id="tianji",
            name="天机",
            layer=AgentLayer.L0,
            role="系统总控",
            emoji="🏛️",
            capabilities=["全局编排", "模块协调", "生命周期管理", "自进化闭环"],
            tools=[
                "agent_dispatch",
                "system_status",
                "tianji_health",
                "tianji_amim_status",
                "tianji_tool_owner",
                "execute_command",
            ],
            mcp_server="agent-framework-global",
            skill_ids=["agent/dispatch:1.0", "system/diagnose:1.0"],
            runtime_class="OrchestratorAgent",
            lingjing_service_id="svc-tianji-core",
            lingjing_port=8799,
            health_endpoint="/health/tianji",
            collaboration_partners=["tianshu", "qianli", "gongzao"],
        ),
        AgentDefinition(
            agent_id="lianli",
            name="连理",
            layer=AgentLayer.L2,
            role="知识图谱构建师",
            emoji="🕸️",
            capabilities=[
                "实体抽取",
                "关系识别",
                "图谱构建",
                "图谱查询",
                "多跳推理",
                "路径查找",
            ],
            tools=[
                "tianji_extract_knowledge",
                "memory_build_graph",
                "memory_query_graph",
                "memory_recall",
                "memory_remember",
            ],
            mcp_server="memory-engine-global",
            skill_ids=["memory/remember:1.0", "memory/recall:1.0"],
            runtime_class="GraphBuilderAgent",
            lingjing_service_id="svc-graph-builder",
            lingjing_port=8807,
            health_endpoint="/health/graph",
            collaboration_partners=["tianshu", "yiku", "huasheng", "dongcha"],
        ),
        AgentDefinition(
            agent_id="huasheng",
            name="化生",
            layer=AgentLayer.L3,
            role="进化工程师",
            emoji="🧬",
            capabilities=["自我检查", "自我更新", "递归改进", "规则演化", "架构升级"],
            tools=[
                "memory_evolve_self",
                "memory_remember",
                "memory_recall",
                "execute_command",
                "system_status",
            ],
            mcp_server="memory-engine-global",
            skill_ids=[
                "agent/dispatch:1.0",
                "memory/remember:1.0",
                "memory/recall:1.0",
            ],
            runtime_class="EvolverAgent",
            lingjing_service_id="svc-evolver",
            lingjing_port=8833,
            health_endpoint="/health/evolver",
            collaboration_partners=["tianshu", "yiku", "lianli", "tiewei", "zhenshan"],
        ),
        AgentDefinition(
            agent_id="wanxiang",
            name="万象",
            layer=AgentLayer.L1,
            role="多模态感知师",
            emoji="👁️",
            capabilities=[
                "图像理解",
                "表格解析",
                "公式识别",
                "模态分类",
                "多模态统一存储",
            ],
            tools=[
                "memory_capture_multimodal",
                "tianji_classify",
                "tianji_extract_knowledge",
                "memory_recall",
                "memory_remember",
            ],
            mcp_server="memory-engine-global",
            skill_ids=["memory/remember:1.0", "memory/recall:1.0"],
            runtime_class="MultimodalAgent",
            lingjing_service_id="svc-multimodal",
            lingjing_port=8824,
            health_endpoint="/health/multimodal",
            collaboration_partners=["tianshu", "yiku", "lianli", "dongcha"],
        ),
    ]

    def __init__(self):
        self._agent_map: dict[str, AgentDefinition] = {}
        self._mcp_server_map: dict[str, list[str]] = {}
        self._tool_owner_map: dict[str, str] = {}
        self._build_maps()
        logger.info(
            f"[AMIM M{self.MODULE_ID}] 初始化完成: {len(self._agent_map)} Agent, "
            f"{len(TOOL_AGENT_MAPPING)} 工具, {len(self._mcp_server_map)} MCP服务器"
        )

    def _build_maps(self):
        self._agent_map.clear()
        self._mcp_server_map.clear()
        self._tool_owner_map.clear()

        for agent in self.AGENT_DEFINITIONS:
            self._agent_map[agent.agent_id] = agent
            if agent.mcp_server not in self._mcp_server_map:
                self._mcp_server_map[agent.mcp_server] = []
            self._mcp_server_map[agent.mcp_server].append(agent.agent_id)

        for tool_name, info in TOOL_AGENT_MAPPING.items():
            self._tool_owner_map[tool_name] = info["owner"]

    def get_agent(self, agent_id: str) -> AgentDefinition | None:
        return self._agent_map.get(agent_id)

    def get_agents_by_layer(self, layer: AgentLayer) -> list[AgentDefinition]:
        return [a for a in self.AGENT_DEFINITIONS if a.layer == layer]

    def get_agents_by_mcp_server(self, server: str) -> list[AgentDefinition]:
        return [
            self._agent_map[aid]
            for aid in self._mcp_server_map.get(server, [])
            if aid in self._agent_map
        ]

    def get_agents_for_tool(self, tool_name: str) -> list[AgentDefinition]:
        tool_info = TOOL_AGENT_MAPPING.get(tool_name)
        if not tool_info:
            return []
        agent_ids = [tool_info["owner"]] + tool_info.get("delegates", [])
        if "*" in tool_info.get("delegates", []):
            return list(self._agent_map.values())
        return [self._agent_map[aid] for aid in agent_ids if aid in self._agent_map]

    def get_tool_owner(self, tool_name: str) -> str | None:
        return self._tool_owner_map.get(tool_name)

    def can_agent_use_tool(self, agent_id: str, tool_name: str) -> bool:
        agent = self._agent_map.get(agent_id)
        if not agent:
            return False
        if tool_name in agent.tools:
            return True
        tool_info = TOOL_AGENT_MAPPING.get(tool_name)
        if not tool_info:
            return False
        if tool_info["owner"] == agent_id:
            return True
        delegates = tool_info.get("delegates", [])
        if "*" in delegates:
            return True
        return agent_id in delegates

    @property
    def agent_count(self) -> int:
        return len(self._agent_map)

    @property
    def tool_count(self) -> int:
        return len(TOOL_AGENT_MAPPING)

    def generate_registry_json(self) -> dict:
        agents = {}
        for agent in self.AGENT_DEFINITIONS:
            agents[agent.agent_id] = {
                "name": agent.name,
                "layer": f"L{agent.layer.value}",
                "role": agent.role,
                "emoji": agent.emoji,
                "capabilities": agent.capabilities,
                "tools": agent.tools,
                "mcp_server": agent.mcp_server,
                "runtime_class": agent.runtime_class,
                "lingjing_service_id": agent.lingjing_service_id,
                "lingjing_port": agent.lingjing_port,
                "health_endpoint": agent.health_endpoint,
                "collaboration_partners": agent.collaboration_partners,
            }
        return {
            "_meta": {
                "source": "core/amim.py",
                "version": self.VERSION,
                "module": self.MODULE_ID,
                "agent_count": self.agent_count,
                "generated_at": datetime.now().isoformat(),
            },
            "agents": agents,
        }

    def generate_capability_matrix(self) -> str:
        lines = ["AGENT_CAPABILITY_MATRIX: Dict[str, Dict] = {"]
        for agent in self.AGENT_DEFINITIONS:
            caps = json.dumps(agent.capabilities, ensure_ascii=False)
            tools = json.dumps(agent.tools, ensure_ascii=False)
            lines.append(
                f'    "{agent.agent_id}": {{'
                f'"name":"{agent.name}","layer":"L{agent.layer.value}",'
                f'"role":"{agent.role}","emoji":"{agent.emoji}",'
            )
            lines.append(f'        "capabilities":{caps},')
            lines.append(f'        "tools":{tools}}},')
        lines.append("}")
        return "\n".join(lines)

    def generate_lingjing_services(self, include_future: bool = False) -> dict:
        services = {}
        for agent in self.AGENT_DEFINITIONS:
            if agent.lingjing_service_id:
                services[agent.lingjing_service_id] = {
                    "agent_id": agent.agent_id,
                    "agent_name": agent.name,
                    "agent_emoji": agent.emoji,
                    "layer": f"L{agent.layer.value}",
                    "port": agent.lingjing_port,
                    "health_endpoint": agent.health_endpoint,
                    "tools": agent.tools,
                    "mcp_server": agent.mcp_server,
                    "grpc_proto": agent.grpc_proto,
                    "capabilities": agent.capabilities,
                }

        meta = {
            "_meta": {
                "source": "core/amim.py -> generate_lingjing_services()",
                "version": self.VERSION,
                "migration_target": "灵境架构 Phase 1+",
                "service_count": len(services),
                "future_tools_count": len(LINGJING_FUTURE_TOOLS)
                if include_future
                else 0,
            },
        }

        result = {**meta, "services": services}
        if include_future:
            result["future_tools"] = LINGJING_FUTURE_TOOLS
        return result

    def validate(self) -> list[str]:
        issues = []

        for agent in self.AGENT_DEFINITIONS:
            if agent.mcp_server not in KNOWN_MCP_SERVERS:
                issues.append(f"[{agent.agent_id}] 未知MCP服务器: {agent.mcp_server}")
            for tool in agent.tools:
                if tool not in KNOWN_TOOLS:
                    issues.append(f"[{agent.agent_id}] 未知工具: {tool}")

        mcp_coverage: set[str] = set()
        for agent in self.AGENT_DEFINITIONS:
            mcp_coverage.add(agent.mcp_server)
        for s in KNOWN_MCP_SERVERS:
            if s not in mcp_coverage:
                issues.append(f"MCP服务器 '{s}' 无Agent绑定")

        tool_owners: set[str] = set()
        for tool_name, info in TOOL_AGENT_MAPPING.items():
            owner = info["owner"]
            tool_owners.add(owner)
            if owner not in self._agent_map:
                issues.append(
                    f"工具 '{tool_name}' 的归属Agent '{owner}' 不在Agent列表中"
                )

        for agent in self.AGENT_DEFINITIONS:
            if not agent.tools:
                issues.append(f"[{agent.agent_id}] {agent.name} 未绑定任何工具")

        for agent in self.AGENT_DEFINITIONS:
            agent_ids = [a.agent_id for a in self.AGENT_DEFINITIONS]
            if agent_ids.count(agent.agent_id) > 1:
                issues.append(f"[{agent.agent_id}] 重复的Agent ID")

        return issues

    def health(self) -> dict:
        issues = self.validate()
        return {
            "module": self.MODULE_ID,
            "version": self.VERSION,
            "status": "healthy" if len(issues) == 0 else "degraded",
            "agent_count": self.agent_count,
            "tool_count": self.tool_count,
            "mcp_server_count": len(self._mcp_server_map),
            "validation_issues": len(issues),
            "issues": issues if issues else None,
        }

    def write_registry_to_file(self, target_path: str | None = None) -> Path:
        if target_path is None:
            target_path = str(
                Path(__file__).parent.parent
                / ".trae"
                / "agents"
                / "_AGENT_REGISTRY.json"
            )

        registry_json = self.generate_registry_json()
        path = Path(target_path)
        path.parent.mkdir(parents=True, exist_ok=True)

        with open(path, "w", encoding="utf-8") as f:
            json.dump(registry_json, f, ensure_ascii=False, indent=2)

        logger.info(
            f"[AMIM] _AGENT_REGISTRY.json 已同步写入: {path} ({self.agent_count} Agent)"
        )
        return path

    def verify_consistency_with_existing(
        self, registry_path: str | None = None
    ) -> dict:
        if registry_path is None:
            registry_path = str(
                Path(__file__).parent.parent
                / ".trae"
                / "agents"
                / "_AGENT_REGISTRY.json"
            )

        path = Path(registry_path)
        issues = []

        if not path.exists():
            return {
                "consistent": False,
                "issues": [f"Registry文件不存在: {registry_path}"],
            }

        with open(path, encoding="utf-8") as f:
            existing = json.load(f)

        existing_agents = existing.get("agents", {})
        for agent in self.AGENT_DEFINITIONS:
            if agent.agent_id not in existing_agents:
                issues.append(
                    f"[缺失] Agent '{agent.agent_id}' 在AMIM中定义但不在Registry文件中"
                )

        for agent_id in existing_agents:
            if agent_id not in self._agent_map:
                issues.append(
                    f"[多余] Agent '{agent_id}' 在Registry文件中但不在AMIM定义中"
                )

        for agent in self.AGENT_DEFINITIONS:
            if agent.agent_id in existing_agents:
                ea = existing_agents[agent.agent_id]
                if ea.get("tools") != agent.tools:
                    issues.append(f"[不一致] '{agent.agent_id}' tools不匹配")
                if ea.get("mcp_server") != agent.mcp_server:
                    issues.append(f"[不一致] '{agent.agent_id}' mcp_server不匹配")

        return {
            "consistent": len(issues) == 0,
            "issues": issues,
            "amim_agents": self.agent_count,
            "registry_agents": len(existing_agents),
        }


__all__ = ["AgentMCPIntegrationManager"]
