# -*- coding: utf-8-sig -*-
"""天机v10.0.1 统一异常体系  [v10-ready]

所有天机模块的异常必须继承TianjiError，确保：
1. 统一的错误码体系 (error_code字段)
2. 统一的严重级别 (severity字段)
3. 可追溯的错误链 (cause字段)
4. 与降级SOP对齐 (L0/L1/L2/L3)

架构定位: core/shared/ Ω基点层 — 全系统统一异常
版本: 1.0.0
"""
from __future__ import annotations
from typing import Any
from enum import Enum


class ErrorSeverity(Enum):
    """错误严重级别  [v10-ready]"""
    LOW = "low"           # 可忽略，自动恢复
    MEDIUM = "medium"     # 需要关注，可能降级
    HIGH = "high"         # 严重，触发L1降级
    CRITICAL = "critical" # 致命，触发L2/L3降级


class TianjiError(Exception):
    """天机统一异常基类  [v10-ready]

    所有天机模块异常必须继承此类。

    Attributes:
        error_code: 错误码 (格式: DOMAIN-NNN, 如 STORAGE-001)
        severity: 错误严重级别
        cause: 原始异常（错误链追踪）
        context: 额外上下文信息
    """

    def __init__(
        self,
        message: str,
        *,
        error_code: str = "TIANJI-000",
        severity: ErrorSeverity = ErrorSeverity.MEDIUM,
        cause: Exception | None = None,
        context: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.error_code = error_code
        self.severity = severity
        self.cause = cause
        self.context = context or {}

    def __str__(self) -> str:
        base = f"[{self.error_code}] {super().__str__()}"
        if self.cause:
            base += f" (caused by: {type(self.cause).__name__}: {self.cause})"
        return base


# === 存储域异常 ===  [v10-ready]

class StorageError(TianjiError):
    """存储层通用异常"""
    def __init__(self, message: str, **kwargs: Any) -> None:
        super().__init__(message, error_code=kwargs.pop("error_code", "STORAGE-000"), **kwargs)

class StorageWriteError(StorageError):
    """写入失败"""
    def __init__(self, message: str = "存储写入失败", **kwargs: Any) -> None:
        super().__init__(message, error_code="STORAGE-001", **kwargs)

class StorageReadError(StorageError):
    """读取失败"""
    def __init__(self, message: str = "存储读取失败", **kwargs: Any) -> None:
        super().__init__(message, error_code="STORAGE-002", **kwargs)

class StorageCapacityError(StorageError):
    """容量不足"""
    def __init__(self, message: str = "存储容量不足", **kwargs: Any) -> None:
        super().__init__(message, error_code="STORAGE-003", severity=ErrorSeverity.HIGH, **kwargs)


# === 门禁域异常 ===  [v10-ready]

class GateError(TianjiError):
    """门禁通用异常"""
    def __init__(self, message: str, **kwargs: Any) -> None:
        super().__init__(message, error_code=kwargs.pop("error_code", "GATE-000"), **kwargs)

class GateRejectError(GateError):
    """门禁拒绝"""
    def __init__(self, message: str = "门禁拒绝写入", **kwargs: Any) -> None:
        super().__init__(message, error_code="GATE-001", **kwargs)

class GateTimeoutError(GateError):
    """门禁超时"""
    def __init__(self, message: str = "门禁评估超时", **kwargs: Any) -> None:
        super().__init__(message, error_code="GATE-002", severity=ErrorSeverity.HIGH, **kwargs)


# === 路由域异常 ===  [v10-ready]

class RouteError(TianjiError):
    """路由通用异常"""
    def __init__(self, message: str, **kwargs: Any) -> None:
        super().__init__(message, error_code=kwargs.pop("error_code", "ROUTE-000"), **kwargs)

class LayerNotFoundError(RouteError):
    """层级不存在"""
    def __init__(self, layer: str, **kwargs: Any) -> None:
        super().__init__(f"层级不存在: {layer}", error_code="ROUTE-001", **kwargs)

class InvalidLayerError(RouteError):
    """无效层级"""
    def __init__(self, layer: str, **kwargs: Any) -> None:
        super().__init__(f"无效层级: {layer}", error_code="ROUTE-002", **kwargs)


# === 搜索域异常 ===  [v10-ready]

class SearchError(TianjiError):
    """搜索通用异常"""
    def __init__(self, message: str = "搜索失败", **kwargs: Any) -> None:
        super().__init__(message, error_code=kwargs.pop("error_code", "SEARCH-000"), **kwargs)

class SearchTimeoutError(SearchError):
    """搜索超时"""
    def __init__(self, message: str = "搜索超时", **kwargs: Any) -> None:
        super().__init__(message, error_code="SEARCH-001", severity=ErrorSeverity.HIGH, **kwargs)


# === 插件域异常 ===  [v10-ready]

class PluginError(TianjiError):
    """插件通用异常"""
    def __init__(self, message: str, **kwargs: Any) -> None:
        super().__init__(message, error_code=kwargs.pop("error_code", "PLUGIN-000"), **kwargs)

class PluginLoadError(PluginError):
    """插件加载失败"""
    def __init__(self, plugin_name: str, **kwargs: Any) -> None:
        super().__init__(f"插件加载失败: {plugin_name}", error_code="PLUGIN-001", **kwargs)

class PluginExecutionError(PluginError):
    """插件执行异常"""
    def __init__(self, plugin_name: str, **kwargs: Any) -> None:
        super().__init__(f"插件执行异常: {plugin_name}", error_code="PLUGIN-002", **kwargs)


# === 调度域异常 ===  [v10-ready]

class SchedulerError(TianjiError):
    """调度通用异常"""
    def __init__(self, message: str = "调度失败", **kwargs: Any) -> None:
        super().__init__(message, error_code=kwargs.pop("error_code", "SCHED-000"), **kwargs)

class AgentNotAvailableError(SchedulerError):
    """Agent不可用"""
    def __init__(self, agent_name: str, **kwargs: Any) -> None:
        super().__init__(f"Agent不可用: {agent_name}", error_code="SCHED-001", **kwargs)


# === 晋升域异常 ===  [v10-ready]

class ConsolidationError(TianjiError):
    """晋升通用异常"""
    def __init__(self, message: str = "晋升失败", **kwargs: Any) -> None:
        super().__init__(message, error_code=kwargs.pop("error_code", "CONSOL-000"), **kwargs)


# === 图谱域异常 ===  [v10-ready]

class GraphError(TianjiError):
    """图谱通用异常"""
    def __init__(self, message: str = "图谱操作失败", **kwargs: Any) -> None:
        super().__init__(message, error_code=kwargs.pop("error_code", "GRAPH-000"), **kwargs)


# === TCL域异常 ===  [v10-ready]

class TCLError(TianjiError):
    """TCL归一化异常"""
    def __init__(self, message: str = "TCL归一化失败", **kwargs: Any) -> None:
        super().__init__(message, error_code=kwargs.pop("error_code", "TCL-000"), **kwargs)

class TCLDisambiguationError(TCLError):
    """消歧失败"""
    def __init__(self, term: str, **kwargs: Any) -> None:
        super().__init__(f"消歧失败: {term}", error_code="TCL-001", **kwargs)


# === 配置域异常 ===  [v10-ready]

class ConfigError(TianjiError):
    """配置异常"""
    def __init__(self, message: str = "配置错误", **kwargs: Any) -> None:
        super().__init__(message, error_code=kwargs.pop("error_code", "CONFIG-000"), **kwargs)

class ConfigNotFoundError(ConfigError):
    """配置项不存在"""
    def __init__(self, key: str, **kwargs: Any) -> None:
        super().__init__(f"配置项不存在: {key}", error_code="CONFIG-001", **kwargs)


# === 资产域异常 ===  [v10-ready]

class AssetError(TianjiError):
    """资产操作异常"""
    def __init__(self, message: str = "资产操作失败", **kwargs: Any) -> None:
        super().__init__(message, error_code=kwargs.pop("error_code", "ASSET-000"), **kwargs)

class AssetBindingError(AssetError):
    """资产绑定失败"""
    def __init__(self, message: str = "资产绑定失败", **kwargs: Any) -> None:
        super().__init__(message, error_code="ASSET-001", **kwargs)
