# -*- coding: utf-8-sig -*-
"""amim.py — re-export兼容层 (SSS-PhaseB拆分后)

实际定义已拆分至子模块，本文件保持导入路径兼容。
"""

from .amim_manager import *
from .amim_models import *
from .amim_router import *

__all__ = [
    "AgentLayer",
    "AgentDefinition",
    "MCPToolBinding",
    "AgentMCPIntegrationManager",
    "MCPServerRouter",
    "TOOL_AGENT_MAPPING",
]
