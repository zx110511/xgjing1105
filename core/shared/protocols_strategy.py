# -*- coding: utf-8-sig -*-
"""天机v10.0.1 共享内核Protocol策略域接口  [v10-ready]

定义8个Protocol接口：
LLM域 (1个):
- ILLMStrategy: LLM策略接口

缓存域 (1个):
- ICacheStrategy: 缓存策略接口

适配器域 (1个):
- IAdapterStrategy: 适配器策略接口

验证域 (2个):
- ISerializationStrategy: 序列化策略接口
- IValidationStrategy: 验证策略接口

防腐层域 (2个):
- IDomainAdapter: 域适配器接口
- IAnticorruptionLayer: 防腐层接口

架构定位: core/shared/ Ω基点层 — 策略聚阵契约
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


# ============================================================================
# LLM域 (1个) — ILLMStrategy
# ============================================================================


@runtime_checkable
class ILLMStrategy(Protocol):
    """LLM策略接口  [v10-ready]

    本地实现: DeepSeekLLMStrategy (DeepSeek模型, 单进程默认)
    远程实现: RemoteLLMStrategy (灵境多模型路由网关)

    切换方式: 统一LLM调用接口，分布式模式下可切换为远程多模型网关。
    """

    def classify(self, content: str, context: dict[str, Any]) -> dict[str, Any]:
        """内容分类"""
        ...

    def extract_knowledge(self, content: str) -> list[dict[str, Any]]:
        """知识提取"""
        ...

    def generate_summary(self, content: str, max_len: int) -> str:
        """生成摘要"""
        ...

    def expand_query(self, query: str) -> list[str]:
        """查询扩展"""
        ...


# ============================================================================
# 缓存域 (1个) — ICacheStrategy
# ============================================================================


@runtime_checkable
class ICacheStrategy(Protocol):
    """缓存策略接口  [v10-ready]

    本地实现: MemoryCacheStrategy (进程内LRU, 单进程默认)
    远程实现: RemoteCacheStrategy (Redis/Memcached集群)

    切换方式: 统一缓存接口，分布式模式下切换为远程缓存。
    """

    def get(self, key: str) -> Any | None:
        """获取缓存值"""
        ...

    def put(self, key: str, value: Any, ttl_seconds: int | None = None) -> None:
        """写入缓存"""
        ...

    def delete(self, key: str) -> bool:
        """删除缓存条目"""
        ...

    def clear(self) -> None:
        """清空缓存"""
        ...

    def stats(self) -> dict[str, Any]:
        """获取缓存统计"""
        ...


# ============================================================================
# 适配器域 (1个) — IAdapterStrategy
# ============================================================================


@runtime_checkable
class IAdapterStrategy(Protocol):
    """适配器策略接口  [v10-ready]

    本地实现: LocalAdapterStrategy (进程内平台适配)
    远程实现: RemoteAdapterStrategy (灵境跨平台网关)

    切换方式: 统一适配器接口，分布式模式下通过远程网关适配多平台。
    """

    def get_platform_info(self) -> dict[str, Any]:
        """获取平台信息"""
        ...

    def on_event(self, event_type: str, payload: dict[str, Any]) -> dict[str, Any]:
        """处理平台事件"""
        ...

    def remember(self, content: str, **kwargs: Any) -> dict[str, Any]:
        """通过适配器写入记忆"""
        ...

    def recall(self, query: str, **kwargs: Any) -> list[dict[str, Any]]:
        """通过适配器检索记忆"""
        ...


# ============================================================================
# 验证域 (2个) — ISerializationStrategy / IValidationStrategy
# ============================================================================


@runtime_checkable
class ISerializationStrategy(Protocol):
    """序列化策略接口  [v10-ready]

    本地实现: JSONSerializationStrategy (JSON序列化, 单进程默认)
    远程实现: RemoteSerializationStrategy (灵境高效二进制序列化)

    切换方式: 统一序列化接口，分布式模式下可切换为Protobuf/MessagePack。
    """

    def serialize(self, obj: Any) -> str | bytes:
        """将对象序列化"""
        ...

    def deserialize(self, data: str | bytes, target_type: type) -> Any:
        """将数据反序列化为目标类型"""
        ...


@runtime_checkable
class IValidationStrategy(Protocol):
    """验证策略接口  [v10-ready]

    本地实现: EntryValidationStrategy (进程内条目校验)
    远程实现: RemoteValidationStrategy (灵境集中式验证服务)

    切换方式: 统一验证接口，分布式模式下可接入远程规则引擎。
    """

    def validate_entry(self, entry: dict[str, Any]) -> tuple[bool, str]:
        """验证单个记忆条目，返回(是否通过, 原因)"""
        ...

    def validate_integrity(self, entries: list[dict[str, Any]]) -> dict[str, Any]:
        """批量完整性验证，返回验证报告"""
        ...


# ============================================================================
# 防腐层域 (2个) — IDomainAdapter / IAnticorruptionLayer
# ============================================================================


@runtime_checkable
class IDomainAdapter(Protocol):
    """域适配器接口  [v10-ready]

    本地实现: PassthroughAdapter / LoggingAdapter (进程内透传)
    远程实现: 灵境跨节点适配代理 (stub 预留)

    切换方式: 每对跨域调用持有专属适配器，负责请求/响应双向转换，
    分布式模式下适配逻辑可下推至远程节点。
    """

    def adapt_request(
        self, source_domain: str, method: str, **kwargs: Any
    ) -> dict[str, Any]:
        """转换跨域请求参数。

        Args:
            source_domain: 源域标识。
            method: 目标方法名。
            **kwargs: 原始调用参数。

        Returns:
            转换后的参数字典。
        """
        ...

    def adapt_response(self, raw_response: Any) -> Any:
        """转换目标域返回结果。

        Args:
            raw_response: 目标域原始返回值。

        Returns:
            转换后的返回值。
        """
        ...

    def get_supported_methods(self) -> list[str]:
        """声明本适配器支持的方法。

        Returns:
            支持的方法名列表 (空列表表示不限制)。
        """
        ...


@runtime_checkable
class IAnticorruptionLayer(Protocol):
    """防腐层接口  [v10-ready]

    本地实现: AnticorruptionLayer (core/shared/anticorruption.py, 单进程默认)
    远程实现: 灵境分布式防腐网关 (stub 预留)

    切换方式: 统一跨域调用入口，同步经适配器直连、异步经事件总线，
    分布式模式下跨域调用经远程网关路由。
    """

    def register_adapter(self, source: str, target: str, adapter: Any) -> None:
        """注册源→目标域适配器。

        Args:
            source: 源域标识。
            target: 目标域标识。
            adapter: 适配器实例。
        """
        ...

    def call(self, source: str, target: str, method: str, **kwargs: Any) -> Any:
        """同步跨域调用。

        Args:
            source: 源域标识。
            target: 目标域标识。
            method: 目标方法名。
            **kwargs: 调用参数。

        Returns:
            转换后的调用结果。
        """
        ...

    def call_async(self, source: str, target: str, method: str, **kwargs: Any) -> None:
        """异步跨域调用。

        Args:
            source: 源域标识。
            target: 目标域标识。
            method: 目标方法名。
            **kwargs: 调用参数。
        """
        ...


__all__ = [
    # LLM域
    "ILLMStrategy",
    # 缓存域
    "ICacheStrategy",
    # 适配器域
    "IAdapterStrategy",
    # 验证域
    "ISerializationStrategy",
    "IValidationStrategy",
    # 防腐层域
    "IDomainAdapter",
    "IAnticorruptionLayer",
]
