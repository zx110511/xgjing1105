# -*- coding: utf-8-sig -*-
"""AMIM — MCP服务器路由器

从 amim.py 拆分 (SSS-PhaseB)
"""

from __future__ import annotations
import json
import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path

class MCPServerRouter:
    """
    M35-EvolutionBus + M29-MCPServer 的桥接路由

    天机v9.1模式: 直接方法调用
    灵境模式: 通过EvolutionBus发布事件 -> MCP Server序列化/反序列化
    """

    def __init__(self, amim: AgentMCPIntegrationManager, mode: str = "tianji"):
        self.amim = amim
        self.mode = mode
        self._tool_handlers: dict[str, Callable] = {}

    def register_handler(self, tool_name: str, handler: Callable):
        self._tool_handlers[tool_name] = handler

    def route_tool_call(self, agent_id: str, tool_name: str, arguments: dict) -> dict:
        agent = self.amim.get_agent(agent_id)
        if not agent:
            return {
                "success": False,
                "error": f"未知Agent: {agent_id}",
                "fallback": True,
            }

        if tool_name not in agent.tools:
            return {
                "success": False,
                "error": f"Agent '{agent.name}' 无权调用工具 '{tool_name}'",
                "fallback": True,
            }

        if self.mode == "tianji":
            return self._route_local(agent, tool_name, arguments)
        else:
            return self._route_lingjing(agent, tool_name, arguments)

    def _route_local(
        self, agent: AgentDefinition, tool_name: str, arguments: dict
    ) -> dict:
        handler = self._tool_handlers.get(tool_name)
        if handler:
            try:
                result = handler(arguments)
                return {
                    "success": True,
                    "data": result,
                    "agent": agent.agent_id,
                    "mode": "tianji",
                }
            except Exception as e:
                return {
                    "success": False,
                    "error": str(e),
                    "agent": agent.agent_id,
                    "fallback": True,
                }
        return {
            "success": False,
            "error": f"工具 '{tool_name}' 在本地模式下无可用的本地处理器",
            "agent": agent.agent_id,
            "fallback": True,
            "hint": "请确认工具处理器已通过 register_handler() 注册",
        }

    def _route_lingjing(
        self, agent: AgentDefinition, tool_name: str, arguments: dict
    ) -> dict:
        event = {
            "type": "MCP_TOOL_CALL",
            "source_agent": agent.agent_id,
            "target_mcp": agent.mcp_server,
            "tool": tool_name,
            "arguments": arguments,
            "timestamp": datetime.now().isoformat(),
        }
        return {
            "success": True,
            "event": event,
            "agent": agent.agent_id,
            "mode": "lingjing",
            "status": "published_to_event_bus",
        }

    def validate_routes(self) -> list[str]:
        issues = []
        for agent in self.amim.AGENT_DEFINITIONS:
            for tool_name in agent.tools:
                if tool_name not in self._tool_handlers and self.mode == "tianji":
                    issues.append(
                        f"[路由] Agent '{agent.agent_id}' 的工具 '{tool_name}' 无本地处理器注册"
                    )
        return issues

    def health(self) -> dict:
        return {
            "mode": self.mode,
            "handlers_registered": len(self._tool_handlers),
            "route_issues": len(self.validate_routes()),
        }


__all__ = ["MCPServerRouter"]
