r"""
对话结束钩子系统 v1.0
=====================
实现对话结束时的自动触发机制，确保每次对话都自动录入天机记忆系统。

核心设计:
  1. 钩子基类: 定义统一的对话结束钩子接口
  2. 平台适配: 支持Trae/Qoder/其他IDE
  3. 自动触发: 对话结束时自动调用capture_conversation
  4. 容错机制: 钩子失败不影响主流程

触发链路:
  对话结束 → ConversationHookManager.trigger() → 各平台钩子 → 天机API
"""

import time
import logging
import threading
from typing import Any, Optional, Dict, List, Callable
from dataclasses import dataclass, field
from abc import ABC, abstractmethod
from enum import Enum

logger = logging.getLogger("tianji.conversation_hook")


class HookPriority(Enum):
    """钩子优先级"""
    CRITICAL = 0  # 必须执行
    HIGH = 1      # 高优先级
    MEDIUM = 2    # 中优先级
    LOW = 3       # 低优先级


@dataclass
class ConversationContext:
    """对话上下文"""
    session_id: str
    user_input: str
    ai_response: str
    agent_id: str = "tianshu"
    platform: str = "trae"
    conversation_id: str = ""
    mcp_calls: List[str] = field(default_factory=list)
    file_operations: List[Dict] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    timestamp: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)


class ConversationEndHook(ABC):
    """
    对话结束钩子基类

    所有平台特定的钩子都需要继承此类并实现trigger()方法。
    """

    def __init__(self, priority: HookPriority = HookPriority.MEDIUM):
        self.priority = priority
        self.enabled = True
        self._stats = {
            "total_triggers": 0,
            "success_count": 0,
            "error_count": 0,
        }

    @abstractmethod
    def trigger(self, context: ConversationContext) -> Dict[str, Any]:
        """
        触发钩子 — 子类必须实现

        参数:
            context: 对话上下文

        返回:
            执行结果字典，至少包含 {"success": bool}
        """
        pass

    def enable(self):
        """启用钩子"""
        self.enabled = True
        logger.info(f"钩子已启用: {self.__class__.__name__}")

    def disable(self):
        """禁用钩子"""
        self.enabled = False
        logger.info(f"钩子已禁用: {self.__class__.__name__}")

    def get_stats(self) -> Dict[str, Any]:
        """获取钩子统计信息"""
        return {
            "class": self.__class__.__name__,
            "priority": self.priority.name,
            "enabled": self.enabled,
            **self._stats,
        }


class TraeConversationHook(ConversationEndHook):
    """
    Trae IDE对话结束钩子

    职责:
    1. 对话结束时自动触发
    2. 调用天机capture_conversation API
    3. 记录触发日志
    """

    def __init__(self, api_base_url: str = "http://127.0.0.1:8771"):
        super().__init__(priority=HookPriority.CRITICAL)
        self.api_base_url = api_base_url
        self._timeout = 5.0  # API调用超时

    def trigger(self, context: ConversationContext) -> Dict[str, Any]:
        """
        触发Trae对话钩子

        流程:
        1. 构造API请求
        2. 调用capture_conversation端点
        3. 返回结果
        """
        if not self.enabled:
            return {"success": False, "reason": "hook_disabled"}

        self._stats["total_triggers"] += 1

        try:
            import requests

            # 构造请求
            payload = {
                "user_input": context.user_input,
                "ai_response": context.ai_response,
                "agent_id": context.agent_id,
                "conversation_id": context.conversation_id or context.session_id,
                "platform": context.platform,
                "session_id": context.session_id,
                "mcp_calls": context.mcp_calls,
                "file_operations": context.file_operations,
                "tags": context.tags,
            }

            # 调用天机API
            url = f"{self.api_base_url}/api/active/capture_conversation"
            response = requests.post(url, json=payload, timeout=self._timeout)

            if response.status_code == 200:
                result = response.json()
                self._stats["success_count"] += 1
                logger.info(
                    f"Trae钩子触发成功: turn_id={result.get('turn_id')} | "
                    f"layers={result.get('total_captured')}"
                )
                return {
                    "success": True,
                    "turn_id": result.get("turn_id"),
                    "captured_layers": result.get("captured_layers"),
                    "total_captured": result.get("total_captured"),
                }
            else:
                self._stats["error_count"] += 1
                logger.error(
                    f"Trae钩子API调用失败: status={response.status_code} | "
                    f"body={response.text[:200]}"
                )
                return {
                    "success": False,
                    "status_code": response.status_code,
                    "error": response.text[:200],
                }

        except requests.Timeout:
            self._stats["error_count"] += 1
            logger.error(f"Trae钩子超时: timeout={self._timeout}s")
            return {"success": False, "error": "timeout"}

        except Exception as e:
            self._stats["error_count"] += 1
            logger.exception(f"Trae钩子异常: {e}")
            return {"success": False, "error": str(e)}


class QoderConversationHook(ConversationEndHook):
    """
    Qoder IDE对话结束钩子

    与Trae钩子类似，但针对Qoder平台优化
    """

    def __init__(self, api_base_url: str = "http://127.0.0.1:8771"):
        super().__init__(priority=HookPriority.CRITICAL)
        self.api_base_url = api_base_url
        self._timeout = 5.0

    def trigger(self, context: ConversationContext) -> Dict[str, Any]:
        """触发Qoder对话钩子"""
        if not self.enabled:
            return {"success": False, "reason": "hook_disabled"}

        self._stats["total_triggers"] += 1

        try:
            import requests

            payload = {
                "user_input": context.user_input,
                "ai_response": context.ai_response,
                "agent_id": context.agent_id,
                "conversation_id": context.conversation_id or context.session_id,
                "platform": "qoder",  # 强制设置为qoder
                "session_id": context.session_id,
                "mcp_calls": context.mcp_calls,
                "file_operations": context.file_operations,
                "tags": context.tags,
            }

            url = f"{self.api_base_url}/api/active/capture_conversation"
            response = requests.post(url, json=payload, timeout=self._timeout)

            if response.status_code == 200:
                result = response.json()
                self._stats["success_count"] += 1
                logger.info(
                    f"Qoder钩子触发成功: turn_id={result.get('turn_id')} | "
                    f"layers={result.get('total_captured')}"
                )
                return {
                    "success": True,
                    "turn_id": result.get("turn_id"),
                    "captured_layers": result.get("captured_layers"),
                    "total_captured": result.get("total_captured"),
                }
            else:
                self._stats["error_count"] += 1
                logger.error(
                    f"Qoder钩子API调用失败: status={response.status_code}"
                )
                return {
                    "success": False,
                    "status_code": response.status_code,
                    "error": response.text[:200],
                }

        except Exception as e:
            self._stats["error_count"] += 1
            logger.exception(f"Qoder钩子异常: {e}")
            return {"success": False, "error": str(e)}


class ConversationHookManager:
    """
    对话钩子管理器

    职责:
    1. 管理所有对话结束钩子
    2. 按优先级触发钩子
    3. 容错处理（钩子失败不影响主流程）
    4. 统计监控
    """

    def __init__(self):
        self._hooks: List[ConversationEndHook] = []
        self._lock = threading.Lock()
        self._stats = {
            "total_conversations": 0,
            "total_hooks_triggered": 0,
            "total_success": 0,
            "total_errors": 0,
        }

    def register(self, hook: ConversationEndHook):
        """注册钩子"""
        with self._lock:
            self._hooks.append(hook)
            # 按优先级排序
            self._hooks.sort(key=lambda h: h.priority.value)
        logger.info(
            f"钩子已注册: {hook.__class__.__name__} | "
            f"priority={hook.priority.name} | total_hooks={len(self._hooks)}"
        )

    def unregister(self, hook_class: type):
        """注销钩子"""
        with self._lock:
            self._hooks = [h for h in self._hooks if not isinstance(h, hook_class)]
        logger.info(f"钩子已注销: {hook_class.__name__}")

    def trigger_all(self, context: ConversationContext) -> Dict[str, Any]:
        """
        触发所有钩子

        流程:
        1. 按优先级依次触发
        2. 收集所有结果
        3. 容错处理（某个钩子失败不影响其他钩子）
        4. 返回汇总结果
        """
        with self._lock:
            self._stats["total_conversations"] += 1

        results = []
        success_count = 0
        error_count = 0

        for hook in self._hooks:
            if not hook.enabled:
                continue

            try:
                result = hook.trigger(context)
                results.append({
                    "hook": hook.__class__.__name__,
                    "result": result,
                })

                if result.get("success"):
                    success_count += 1
                else:
                    error_count += 1

            except Exception as e:
                error_count += 1
                logger.exception(
                    f"钩子执行异常: {hook.__class__.__name__} | error={e}"
                )
                results.append({
                    "hook": hook.__class__.__name__,
                    "result": {"success": False, "error": str(e)},
                })

        with self._lock:
            self._stats["total_hooks_triggered"] += len(results)
            self._stats["total_success"] += success_count
            self._stats["total_errors"] += error_count

        return {
            "success": success_count > 0,
            "total_hooks": len(self._hooks),
            "success_count": success_count,
            "error_count": error_count,
            "results": results,
        }

    def trigger_by_platform(
        self, context: ConversationContext, platform: str
    ) -> Dict[str, Any]:
        """
        按平台触发钩子

        只触发匹配平台的钩子，提高效率
        """
        platform_hooks = {
            "trae": TraeConversationHook,
            "qoder": QoderConversationHook,
        }

        hook_class = platform_hooks.get(platform.lower())
        if not hook_class:
            logger.warning(f"未知平台: {platform}")
            return {"success": False, "reason": "unknown_platform"}

        for hook in self._hooks:
            if isinstance(hook, hook_class):
                return hook.trigger(context)

        logger.warning(f"平台钩子未注册: {platform}")
        return {"success": False, "reason": "hook_not_registered"}

    def get_stats(self) -> Dict[str, Any]:
        """获取管理器统计信息"""
        with self._lock:
            stats = self._stats.copy()

        stats["hooks"] = [h.get_stats() for h in self._hooks]
        return stats

    def enable_all(self):
        """启用所有钩子"""
        for hook in self._hooks:
            hook.enable()
        logger.info("所有钩子已启用")

    def disable_all(self):
        """禁用所有钩子"""
        for hook in self._hooks:
            hook.disable()
        logger.info("所有钩子已禁用")


# 全局钩子管理器实例
_hook_manager: Optional[ConversationHookManager] = None


def get_hook_manager() -> ConversationHookManager:
    """获取全局钩子管理器"""
    global _hook_manager
    if _hook_manager is None:
        _hook_manager = ConversationHookManager()
    return _hook_manager


def init_hooks(api_base_url: str = "http://127.0.0.1:8771"):
    """
    初始化钩子系统

    注册Trae和Qoder钩子
    """
    manager = get_hook_manager()

    # 注册Trae钩子
    trae_hook = TraeConversationHook(api_base_url=api_base_url)
    manager.register(trae_hook)

    # 注册Qoder钩子
    qoder_hook = QoderConversationHook(api_base_url=api_base_url)
    manager.register(qoder_hook)

    logger.info(
        f"钩子系统初始化完成: total_hooks={len(manager._hooks)} | "
        f"api_base_url={api_base_url}"
    )

    return manager


def on_conversation_end(
    user_input: str,
    ai_response: str,
    session_id: str,
    agent_id: str = "tianshu",
    platform: str = "trae",
    **kwargs,
) -> Dict[str, Any]:
    """
    对话结束入口函数 — 供外部调用

    这是Trae/Qoder IDE在对话结束时应该调用的函数。

    示例:
        from active_memory.conversation_hook import on_conversation_end

        # 对话结束时
        result = on_conversation_end(
            user_input="用户的问题",
            ai_response="AI的回答",
            session_id="session-123",
            platform="trae"
        )

    参数:
        user_input: 用户输入
        ai_response: AI响应
        session_id: 会话ID
        agent_id: Agent标识
        platform: 平台标识 (trae/qoder)
        **kwargs: 其他参数（mcp_calls, file_operations, tags等）

    返回:
        触发结果字典
    """
    context = ConversationContext(
        session_id=session_id,
        user_input=user_input,
        ai_response=ai_response,
        agent_id=agent_id,
        platform=platform,
        conversation_id=kwargs.get("conversation_id", ""),
        mcp_calls=kwargs.get("mcp_calls", []),
        file_operations=kwargs.get("file_operations", []),
        tags=kwargs.get("tags", []),
        metadata=kwargs.get("metadata", {}),
    )

    manager = get_hook_manager()
    return manager.trigger_by_platform(context, platform)
