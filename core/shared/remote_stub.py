# -*- coding: utf-8-sig -*-
"""天机统一远程Stub工厂 — 10合1 [SSS瘦身]

将原分散在 10 个子目录的 remote_stub.py 合并为单一工厂。
通过动态类生成消除 ~600 行重复代码。

使用方式:
    from core.shared.remote_stub import RemoteStubFactory

    # 生成任意远程Stub类
    RemoteGateStrategy = RemoteStubFactory.create(
        class_name="RemoteGateStrategy",
        protocol="IGateStrategy",
        methods=["check", "get_verdict"],
        category="gate",
        description="远程门禁策略 (gRPC stub)",
    )

版本: 1.0.0 | SSS-PhaseA 合并产物
"""

from __future__ import annotations

import logging
import typing
from typing import Any, Optional

if typing.TYPE_CHECKING:
    from core.shared.plugin_interface import PluginInfo

logger = logging.getLogger("tianji.remote_stub")

# 已注册的Stub类注册表
_REGISTRY: dict[str, type] = {}


class RemoteStubBase:
    """所有远程Stub的基类 — 统一初始化 + 通用接口"""

    _STUB_CATEGORY: str = "remote"
    _STUB_VERSION: str = "1.0.0"

    def __init__(self, endpoint: Optional[str] = None, *, timeout: float = 5.0, **kwargs: Any) -> None:
        self._endpoint = endpoint
        self._timeout = timeout
        self._channel: Any = kwargs.get("channel")
        self._options = kwargs

    def connect(self) -> bool:
        raise NotImplementedError(f"{self.__class__.__name__}.connect 待 v10.0 灵境 gRPC 接入")


class RemoteStubFactory:
    """远程Stub动态工厂 — 按需生成Stub类"""

    @staticmethod
    def create(
        class_name: str,
        protocol: str = "",
        methods: list[str] | None = None,
        category: str = "remote",
        description: str = "",
        module: str = "",
    ) -> type:
        """动态生成一个远程Stub类

        Args:
            class_name: 类名 (如 "RemoteGateStrategy")
            protocol: 实现的协议接口名
            methods: 需要生成的方法列表
            category: 插件分类
            description: 描述文本
            module: 所属模块路径 (用于PLUGIN_INFO)

        Returns:
            动态生成的类型
        """
        if class_name in _REGISTRY:
            return _REGISTRY[class_name]

        methods = methods or []

        # 动态生成方法
        method_dict: dict[str, Any] = {"__module__": module or __name__}

        for method_name in methods:
            def _make_stub(method: str):
                def _stub_method(self, *args: Any, **kw: Any) -> Any:
                    raise NotImplementedError(
                        f"{class_name}.{method} 待 v10.0 灵境 gRPC 接入"
                    )
                _stub_method.__name__ = method
                _stub_method.__qualname__ = f"{class_name}.{method}"
                return _stub_method

            method_dict[method_name] = _make_stub(method_name)

        # 创建类
        cls = type(class_name, (RemoteStubBase,), method_dict)
        cls.STUB_PROTOCOL = protocol
        cls.STUB_CATEGORY = category
        cls.STUB_DESCRIPTION = description

        _REGISTRY[class_name] = cls
        logger.debug("[RemoteStubFactory] Created stub class: %s (%d methods)", class_name, len(methods))
        return cls

    @staticmethod
    def create_plugin_info(name: str, category: str, protocols: list[str], description: str) -> PluginInfo:
        """创建 PLUGIN_INFO (延迟导入避免循环依赖)"""
        from core.shared.plugin_interface import PluginInfo  # noqa: E402
        return PluginInfo(
            name=name,
            version="1.0.0",
            description=description,
            category=category,
            protocols=protocols,
        )

    @staticmethod
    def list_registered() -> list[str]:
        """列出所有已注册的Stub类名"""
        return list(_REGISTRY.keys())


# ============================================================
 # 预定义常用Stub实例 (向后兼容便捷导入)
# ============================================================

# --- 门禁 ---
RemoteGateStrategy = RemoteStubFactory.create(
    class_name="RemoteGateStrategy",
    protocol="IGateStrategy",
    methods=["check", "get_verdict"],
    category="gate",
    description="远程门禁策略 (gRPC stub)",
)

# --- 路由 ---
RemoteRoutingStrategy = RemoteStubFactory.create(
    class_name="RemoteRoutingStrategy",
    protocol="ITaskRouter",
    methods=["route", "get_routing_strategy"],
    category="routing",
    description="灵境远程路由策略 (gRPC stub)",
)

# --- 存储 ---
RemoteStorageEngine = RemoteStubFactory.create(
    class_name="RemoteStorageEngine",
    protocol="IStorageBackend",
    methods=["connect", "read", "write", "delete", "query", "health_check"],
    category="storage",
    description="远程存储引擎 (gRPC stub)",
)

# --- 调度 ---
RemoteSchedulerStrategy = RemoteStubFactory.create(
    class_name="RemoteSchedulerStrategy",
    protocol="ISchedulerStrategy",
    methods=["schedule", "cancel", "status", "list_tasks"],
    category="scheduling",
    description="远程调度策略 (gRPC stub)",
)

# --- 搜索 ---
RemoteSearchStrategy = RemoteStubFactory.create(
    class_name="RemoteSearchStrategy",
    protocol="ISearchStrategy",
    methods=["search", "index", "delete_index"],
    category="search",
    description="远程搜索策略 (gRPC stub)",
)

# --- LLM ---
RemoteLLMStrategy = RemoteStubFactory.create(
    class_name="RemoteLLMStrategy",
    protocol="ILLMStrategy",
    methods=["complete", "embed", "classify", "extract"],
    category="llm",
    description="远程LLM策略 (gRPC stub)",
)

# --- 资产绑定 ---
RemoteAssetBinding = RemoteStubFactory.create(
    class_name="RemoteAssetBinding",
    protocol="IAssetBinding",
    methods=["bind", "unbind", "resolve", "list_bindings"],
    category="asset_binding",
    description="远程资产绑定 (gRPC stub)",
)

# --- 校验 ---
RemoteValidationStrategy = RemoteStubFactory.create(
    class_name="RemoteValidationStrategy",
    protocol="IValidationStrategy",
    methods=["validate", "validate_batch", "get_schema"],
    category="validation",
    description="远程校验策略 (gRPC stub)",
)

# --- 适配器 ---
RemoteAdapterStrategy = RemoteStubFactory.create(
    class_name="RemoteAdapterStrategy",
    protocol="IAdapterStrategy",
    methods=["get_platform_info", "on_event", "remember", "recall"],
    category="adapter",
    description="远程平台适配策略 (灵境跨平台网关 stub)",
)
