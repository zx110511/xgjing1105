r"""
主动记忆模块 - Active Memory Module
提供大模型主动管理记忆的协议和工具
v7.0: 新增 InterceptLayer 拦截层 + 平台适配
v8.7: 新增 TraeConversationCapture 全量对话捕获
"""

from .protocol import (
    ActiveMemoryProtocol,
    ActiveMemoryConfig,
    MemoryAction,
    MemoryDecision,
    RetrievalStrategy,
    KnowledgeTriple,
    InterceptLayer,
    InterceptSession,
    Platform,
)

try:
    from .trae_capture import TraeConversationCapture
except ImportError:
    TraeConversationCapture = None

__all__ = [
    "ActiveMemoryProtocol",
    "ActiveMemoryConfig",
    "MemoryAction",
    "MemoryDecision",
    "RetrievalStrategy",
    "KnowledgeTriple",
    "InterceptLayer",
    "InterceptSession",
    "Platform",
    "TraeConversationCapture",
]
