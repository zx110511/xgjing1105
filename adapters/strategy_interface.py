# -*- coding: utf-8-sig -*-
"""天机v10.0.1 适配器策略接口层  [v10-ready]

为已有多平台适配器 (adapters/) 提供统一的 IAdapterStrategy 策略门面。

架构定位: adapters/ 适配器域 — 统一平台适配策略
版本: 1.0.0

分布式切换说明:
    本地实现: LocalAdapterStrategy (进程内平台适配, 代理到 UnifiedMemoryAdapter)
    远程实现: RemoteAdapterStrategy (灵境跨平台网关, 见 remote_stub.py)
    上层仅依赖 core.shared.protocols.IAdapterStrategy 协议，
    由工厂按运行模式返回 Local/Remote 实现，保证 v9.1 单进程不受影响。
"""
from __future__ import annotations

from dataclasses import asdict, is_dataclass
from typing import Any, Optional

try:
    from core.shared.protocols import IAdapterStrategy
    from core.shared.plugin_interface import PluginInfo
except ImportError:  # pragma: no cover - 兼容相对导入路径
    from ..core.shared.protocols import IAdapterStrategy
    from ..core.shared.plugin_interface import PluginInfo

from .base import MemorySDKConfig
from .unified_adapter import UnifiedMemoryAdapter


class _LocalUnifiedAdapter(UnifiedMemoryAdapter):
    """进程内统一适配器具体实现  [v10-ready]

    UnifiedMemoryAdapter 继承自抽象基类 PlatformAdapter，未实现
    on_event / get_platform_info 两个抽象方法，故无法直接实例化。
    此处提供最小具体实现以供 LocalAdapterStrategy 内部装配，
    不修改 unified_adapter.py 任何已有逻辑。
    """

    def __init__(
        self,
        config: Optional[MemorySDKConfig] = None,
        engine: Any = None,
        external_client: Optional[Any] = None,
        platform: str = "tianji-local",
    ) -> None:
        super().__init__(config=config, engine=engine, external_client=external_client)
        self._platform = platform

    def get_platform_info(self) -> dict[str, Any]:
        """返回本地平台信息  [v10-ready]"""
        return {
            "platform": self._platform,
            "type": "local",
            "adapter": "UnifiedMemoryAdapter",
            "base_url": self.config.base_url,
        }

    def on_event(self, event_type: str, payload: dict[str, Any]) -> dict[str, Any]:
        """处理平台事件 (本地直发)  [v10-ready]"""
        result = self.send_event(event_type, payload or {})
        return {
            "handled": True,
            "event_type": event_type,
            "platform": self._platform,
            "result": result,
        }


def _to_dict(obj: Any) -> dict[str, Any]:
    """将 dataclass / 普通对象统一转为 dict  [v10-ready]"""
    if obj is None:
        return {}
    if is_dataclass(obj) and not isinstance(obj, type):
        return asdict(obj)
    if isinstance(obj, dict):
        return obj
    if hasattr(obj, "to_dict"):
        return obj.to_dict()
    return {"value": obj}


class LocalAdapterStrategy(IAdapterStrategy):
    """本地适配器策略  [v10-ready]

    包装现有 unified_adapter.py 的逻辑，将统一适配器接口代理到
    进程内 UnifiedMemoryAdapter，实现 IAdapterStrategy 协议。

    remember / recall 直接委托现有 UnifiedMemoryAdapter 的对应方法，
    返回值统一规整为 dict / list[dict] 以符合协议契约。
    """

    def __init__(
        self,
        config: Optional[MemorySDKConfig] = None,
        engine: Any = None,
        external_client: Optional[Any] = None,
        platform: str = "tianji-local",
    ) -> None:
        """初始化本地适配器策略  [v10-ready]

        Args:
            config: 适配器 SDK 配置 (沿用 base.MemorySDKConfig)。
            engine: 可选的 ICME 引擎实例 (直接注入避免 HTTP)。
            external_client: 可选的外部记忆客户端。
            platform: 平台标识。
        """
        self._adapter = _LocalUnifiedAdapter(
            config=config,
            engine=engine,
            external_client=external_client,
            platform=platform,
        )

    def get_platform_info(self) -> dict[str, Any]:
        """获取平台信息  [v10-ready]"""
        return self._adapter.get_platform_info()

    def on_event(self, event_type: str, payload: dict[str, Any]) -> dict[str, Any]:
        """处理平台事件  [v10-ready]"""
        return self._adapter.on_event(event_type, payload)

    def remember(self, content: str, **kwargs: Any) -> dict[str, Any]:
        """通过适配器写入记忆 (委托 UnifiedMemoryAdapter.remember)  [v10-ready]"""
        result = self._adapter.remember(
            content,
            layer=kwargs.get("layer"),
            tags=kwargs.get("tags"),
            priority=kwargs.get("priority", "medium"),
        )
        return _to_dict(result)

    def recall(self, query: str, **kwargs: Any) -> list[dict[str, Any]]:
        """通过适配器检索记忆 (委托 UnifiedMemoryAdapter.recall)  [v10-ready]"""
        result = self._adapter.recall(
            query,
            layers=kwargs.get("layers"),
            limit=kwargs.get("limit", 10),
        )
        return [_to_dict(mem) for mem in getattr(result, "results", [])]

    def get_stats(self) -> dict[str, Any]:
        """获取底层适配器统计  [v10-ready]"""
        return self._adapter.get_stats()

    def close(self) -> None:
        """释放底层适配器资源  [v10-ready]"""
        self._adapter.close()


PLUGIN_INFO = PluginInfo(
    name="local_adapter",
    version="1.0.0",
    description="本地平台适配策略",
    category="adapter",
    protocols=["IAdapterStrategy"],
)
