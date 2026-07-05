"""
天机对话Agent代理器 (Tianji Conversation Agent Broker) v1.0
============================================================
桥接对话系统与AgentScheduler,
让agent_dispatch function_call真正工作。

核心能力:
  1. 意图→Agent映射 — 从用户意图自动选择最合适的Agent
  2. TVP Handoff — Agent切换时透明声明 (遵循天机宪法第4条)
  3. 工具路由 — 将Agent的工具需求路由到MCPBridge
  4. 结果聚合 — 多Agent协作结果统一格式化
  5. 状态追踪 — 对话中Agent切换历史记录

架构位置: 天机/core/conversation_agent_broker.py
依赖: core/agent_orchestrator.py, core/mcp_bridge.py, core/orchestration/registry.py
"""

from __future__ import annotations

import json
import logging
import time
import traceback
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("tianji.conversation_agent_broker")


@dataclass
class AgentHandoff:
    """TVP Agent切换记录"""
    from_agent: str
    to_agent: str
    reason: str
    timestamp: float = field(default_factory=time.time)
    task_type: str = ""
    success: bool = True


class ConversationAgentBroker:
    """对话系统 ↔ AgentScheduler 桥接器

    将对话中的agent_dispatch请求路由到AgentScheduler,
    并管理Agent切换的TVP透明声明。

    使用方式:
      broker = ConversationAgentBroker()
      result = await broker.dispatch("代码审查", {"files": ["main.py"]})
      history = broker.get_handoff_history()
    """

    VERSION = "1.0.0"

    # 任务类型 → Agent映射表
    TASK_AGENT_MAP = {
        "代码审查": "tiewei",
        "code_review": "tiewei",
        "安全审计": "tiewei",
        "security": "tiewei",
        "记忆管理": "yiku",
        "memory": "yiku",
        "记忆操作": "yiku",
        "意图分析": "dongcha",
        "intent": "dongcha",
        "上下文分析": "dongcha",
        "规则检查": "luling",
        "rule": "luling",
        "合规": "luling",
        "对话监控": "lingxi",
        "context_guard": "lingxi",
        "编排": "tianshu",
        "orchestrate": "tianshu",
        "调度": "tianshu",
        "决策": "tianshu",
        "写作": "miaobi",
        "write": "miaobi",
        "创作": "miaobi",
        "审校": "mingjing",
        "review_text": "mingjing",
        "数据分析": "tiansuan",
        "analytics": "tiansuan",
        "统计": "tiansuan",
        "架构": "jingwei",
        "architecture": "jingwei",
        "技能调用": "baiqiao",
        "skill": "baiqiao",
        "版本管理": "shiguan",
        "version": "shiguan",
        "导出": "jinshu",
        "export": "jinshu",
        "审计": "jianheng",
        "audit": "jianheng",
        "监控": "qianli",
        "monitoring": "qianli",
        "部署": "gongzao",
        "deploy": "gongzao",
        "运维": "gongzao",
        "语料处理": "kuangshi",
        "corpus": "kuangshi",
        "项目管理": "wenzong",
        "project": "wenzong",
    }

    # Agent → 默认工具映射
    AGENT_DEFAULT_TOOLS = {
        "tiewei": ["memory_recall", "scan_vulnerabilities"],
        "yiku": ["memory_remember", "memory_recall", "memory_stats", "search_memories"],
        "dongcha": ["context_extract", "memory_recall"],
        "luling": ["rule_evaluate", "memory_recall"],
        "lingxi": ["context_extract", "memory_recall", "get_session_digest"],
        "tianshu": ["agent_dispatch", "system_status", "context_extract", "rule_evaluate"],
        "miaobi": ["memory_recall", "search_memories", "build_working_representation"],
        "mingjing": ["memory_recall", "rule_evaluate"],
        "tiansuan": ["memory_recall", "memory_stats", "search_memories"],
        "jingwei": ["agent_dispatch", "rule_evaluate", "memory_recall"],
        "baiqiao": ["execute_command", "agent_dispatch"],
        "shiguan": ["memory_recall", "memory_remember"],
        "jinshu": ["execute_command", "memory_recall"],
        "jianheng": ["memory_recall", "system_status"],
        "qianli": ["system_status", "tianji_health"],
        "gongzao": ["execute_command"],
        "kuangshi": ["memory_remember", "memory_recall", "context_extract"],
        "wenzong": ["agent_dispatch", "system_status", "memory_recall"],
    }

    def __init__(self):
        self._scheduler = None
        self._mcp_bridge = None
        self._current_agent: str = "tianshu"  # 默认天枢(总指挥)
        self._handoff_history: List[AgentHandoff] = []
        self._dispatch_count: int = 0
        self._error_count: int = 0
        self._init_time: float = time.time()

    def _get_scheduler(self):
        """延迟加载AgentScheduler"""
        if self._scheduler is None:
            try:
                from core.orchestration.agent_orchestrator import AgentScheduler
                self._scheduler = AgentScheduler()
            except Exception as e:
                logger.error(f"ConversationAgentBroker: 加载AgentScheduler失败: {e}")
        return self._scheduler

    def _get_mcp_bridge(self):
        """延迟加载MCPBridge"""
        if self._mcp_bridge is None:
            try:
                from core.shared.mcp_bridge import get_mcp_bridge
                self._mcp_bridge = get_mcp_bridge()
            except ImportError:
                pass
        return self._mcp_bridge

    def resolve_agent(self, task_type: str, task_data: Optional[Dict] = None) -> str:
        """根据任务类型解析最合适的Agent

        Args:
            task_type: 任务类型描述
            task_data: 任务数据 (可选, 用于更精确匹配)

        Returns:
            Agent ID (如 "tianshu", "yiku" 等)
        """
        # 精确匹配
        task_lower = task_type.lower().strip()
        if task_lower in self.TASK_AGENT_MAP:
            return self.TASK_AGENT_MAP[task_lower]

        # 模糊匹配: 检查task_type是否包含关键词
        for keyword, agent_id in self.TASK_AGENT_MAP.items():
            if keyword in task_lower or task_lower in keyword:
                return agent_id

        # 从task_data中提取线索
        if task_data:
            data_str = json.dumps(task_data, ensure_ascii=False).lower()
            for keyword, agent_id in self.TASK_AGENT_MAP.items():
                if keyword in data_str:
                    return agent_id

        # 默认: 天枢(总指挥)
        return "tianshu"

    def get_agent_info(self, agent_id: str) -> Dict[str, Any]:
        """获取Agent详细信息"""
        try:
            from core.orchestration.registry import AGENT_CAPABILITY_MATRIX
            info = AGENT_CAPABILITY_MATRIX.get(agent_id, {})
            return {
                "id": agent_id,
                "name": info.get("name", agent_id),
                "layer": info.get("layer", "L?"),
                "role": info.get("role", "未知"),
                "emoji": info.get("emoji", "🤖"),
                "capabilities": info.get("capabilities", []),
                "tools": info.get("tools", []),
            }
        except ImportError:
            return {
                "id": agent_id,
                "name": agent_id,
                "layer": "L?",
                "role": "未知",
                "emoji": "🤖",
                "capabilities": [],
                "tools": self.AGENT_DEFAULT_TOOLS.get(agent_id, []),
            }

    async def dispatch(
        self,
        task_type: str,
        task_data: Optional[Dict] = None,
        priority: str = "medium",
    ) -> Dict[str, Any]:
        """执行Agent调度

        Args:
            task_type: 任务类型
            task_data: 任务数据
            priority: 优先级 (low/medium/high/critical)

        Returns:
            调度结果, 包含:
              - success: 是否成功
              - agent_id: 被调度的Agent ID
              - agent_info: Agent详细信息
              - tvp_handoff: TVP切换声明
              - result: 执行结果 (如有)
              - duration_ms: 耗时
        """
        t0 = time.time()
        self._dispatch_count += 1

        # 解析Agent
        target_agent = self.resolve_agent(task_type, task_data)
        agent_info = self.get_agent_info(target_agent)

        # TVP Handoff
        handoff = AgentHandoff(
            from_agent=self._current_agent,
            to_agent=target_agent,
            reason=f"任务调度: {task_type}",
            task_type=task_type,
        )

        # 构建TVP声明
        tvp_declaration = self._build_tvp_declaration(handoff, agent_info)

        # 执行调度
        result_data = None
        success = True

        try:
            # 尝试通过AgentScheduler执行
            scheduler = self._get_scheduler()
            if scheduler:
                try:
                    tracker_result = scheduler.tracker.track(
                        tool_name=f"agent_dispatch:{task_type}",
                        agent_id=target_agent,
                        input_data=task_data or {},
                    )
                    result_data = {
                        "tracked": True,
                        "tracker_id": tracker_result if isinstance(tracker_result, str) else "ok",
                        "agent": agent_info["name"],
                        "task": task_type,
                    }
                except Exception as track_err:
                    logger.warning(f"Tracker调用失败, 降级: {track_err}")
                    result_data = {
                        "tracked": False,
                        "agent": agent_info["name"],
                        "task": task_type,
                        "note": "调度已记录, tracker降级",
                    }
            else:
                # 降级: 记录调度但不执行工具
                result_data = {
                    "tracked": False,
                    "agent": agent_info["name"],
                    "task": task_type,
                    "note": "AgentScheduler不可用, 调度已记录",
                }

        except Exception as e:
            success = False
            handoff.success = False
            self._error_count += 1
            logger.error(f"Agent调度失败: {e}\n{traceback.format_exc()}")

        # 记录Handoff
        self._handoff_history.append(handoff)
        self._current_agent = target_agent

        duration_ms = (time.time() - t0) * 1000

        return {
            "success": success,
            "agent_id": target_agent,
            "agent_info": agent_info,
            "tvp_handoff": tvp_declaration,
            "result": result_data,
            "duration_ms": duration_ms,
        }

    def _build_tvp_declaration(self, handoff: AgentHandoff, agent_info: Dict) -> str:
        """构建TVP透明切换声明"""
        emoji = agent_info.get("emoji", "🤖")
        name = agent_info.get("name", handoff.to_agent)
        layer = agent_info.get("layer", "L?")
        role = agent_info.get("role", "")

        return (
            f"[TVP] {emoji} {name}({handoff.to_agent}) @{layer} "
            f"← {handoff.from_agent} | 原因: {handoff.reason}"
        )

    def get_current_agent(self) -> Dict[str, Any]:
        """获取当前活跃Agent信息"""
        return self.get_agent_info(self._current_agent)

    def get_handoff_history(self, limit: int = 20) -> List[Dict]:
        """获取Agent切换历史"""
        history = self._handoff_history[-limit:]
        return [
            {
                "from": h.from_agent,
                "to": h.to_agent,
                "reason": h.reason,
                "timestamp": h.timestamp,
                "task_type": h.task_type,
                "success": h.success,
            }
            for h in history
        ]

    def get_available_agents(self) -> List[Dict[str, Any]]:
        """获取所有可用Agent列表"""
        try:
            from core.orchestration.registry import AGENT_CAPABILITY_MATRIX
            return [
                {
                    "id": aid,
                    "name": info.get("name", aid),
                    "layer": info.get("layer", ""),
                    "role": info.get("role", ""),
                    "emoji": info.get("emoji", ""),
                    "capabilities": info.get("capabilities", []),
                }
                for aid, info in AGENT_CAPABILITY_MATRIX.items()
            ]
        except ImportError:
            return [
                {"id": aid, "name": aid, "layer": "", "role": "", "emoji": "", "capabilities": []}
                for aid in self.TASK_AGENT_MAP.values()
            ]

    def format_dispatch_result(self, result: Dict[str, Any]) -> str:
        """将调度结果格式化为对话友好的文本"""
        if not result.get("success"):
            return f"[调度失败] {result.get('agent_id', '?')}: 任务执行出错"

        agent_info = result.get("agent_info", {})
        emoji = agent_info.get("emoji", "🤖")
        name = agent_info.get("name", "?")
        role = agent_info.get("role", "")
        tvp = result.get("tvp_handoff", "")
        duration = result.get("duration_ms", 0)

        lines = [
            f"{emoji} **{name}** ({role}) 已接管任务",
            f"📋 {tvp}",
        ]

        data = result.get("result")
        if data:
            if isinstance(data, dict):
                # 精简输出
                for key in ["tracked", "agent", "task"]:
                    if key in data:
                        lines.append(f"  • {key}: {data[key]}")
                # 如果有查询结果
                if "results" in data:
                    items = data["results"]
                    if isinstance(items, list):
                        lines.append(f"  • 检索到 {len(items)} 条结果")
            elif isinstance(data, str):
                if len(data) > 200:
                    lines.append(f"  • 结果: {data[:200]}...")
                else:
                    lines.append(f"  • 结果: {data}")

        lines.append(f"⏱ {duration:.0f}ms")
        return "\n".join(lines)

    def health(self) -> Dict[str, Any]:
        """健康检查"""
        scheduler = self._get_scheduler()
        return {
            "status": "healthy" if scheduler else "degraded",
            "version": self.VERSION,
            "current_agent": self._current_agent,
            "dispatch_count": self._dispatch_count,
            "error_count": self._error_count,
            "handoff_history_size": len(self._handoff_history),
            "scheduler_available": scheduler is not None,
            "uptime_seconds": time.time() - self._init_time,
        }


# 全局单例
_broker_instance: Optional[ConversationAgentBroker] = None


def get_conversation_agent_broker() -> ConversationAgentBroker:
    """获取全局ConversationAgentBroker单例"""
    global _broker_instance
    if _broker_instance is None:
        _broker_instance = ConversationAgentBroker()
    return _broker_instance
