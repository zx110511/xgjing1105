# -*- coding: utf-8-sig -*-
"""天机v10.0.1 共享内核Protocol门禁域+晋升域接口  [v10-ready]

定义6个Protocol接口：
门禁域 (3个):
- IGateStrategy: 门禁策略接口
- IQualityGate: 质量门禁接口
- IGatePolicy: 门禁策略规则接口

晋升域 (3个):
- IConsolidationStrategy: 晋升策略接口
- IPromotionGate: 晋升门禁接口
- IConsolidationScheduler: 晋升调度接口

架构定位: core/shared/ Ω基点层 — 门禁+晋升聚阵契约
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from .protocols_base import GateResult, GateVerdict


# ============================================================================
# 门禁域 (3个) — IGateStrategy / IQualityGate / IGatePolicy
# ============================================================================


@runtime_checkable
class IGateStrategy(Protocol):
    """门禁策略接口  [v10-ready]

    本地实现: LocalGateStrategy (本地三问推演 + 静态阈值, 单进程默认)
    远程实现: RemoteGateStrategy (灵境集中式门禁服务)

    切换方式: check() 产出 GateResult 判决，
    分布式模式下阈值自适应由远程门禁服务集中演化。
    """

    def check(self, content: str, metadata: dict[str, Any]) -> GateResult:
        """执行门禁判定。

        Args:
            content: 待判定内容文本。
            metadata: 内容元数据 (来源/标签/会话等)。

        Returns:
            门禁判决 GateResult。
        """
        ...

    def get_verdict(self, content: str, metadata: dict[str, Any]) -> GateVerdict:
        """仅返回判决枚举。

        Args:
            content: 待判定内容文本。
            metadata: 内容元数据。

        Returns:
            判决枚举 GateVerdict。
        """
        ...


@runtime_checkable
class IQualityGate(Protocol):
    """质量门禁接口  [v10-ready]

    本地实现: QualityGate (core 三问推演实现, 单进程默认)
    远程实现: RemoteQualityGate (灵境质量评估服务)

    切换方式: evaluate() 对条目做综合质量评估，
    分布式模式下评估模型与配置由远程服务托管。
    """

    def evaluate(self, entry: dict[str, Any]) -> GateResult:
        """评估条目质量。

        Args:
            entry: 待评估记忆条目字典。

        Returns:
            质量判决 GateResult。
        """
        ...

    def get_config(self) -> dict[str, Any]:
        """获取门禁配置。

        Returns:
            当前生效的门禁配置字典。
        """
        ...


@runtime_checkable
class IGatePolicy(Protocol):
    """门禁策略规则接口  [v10-ready]

    本地实现: LocalGatePolicy (进程内策略阈值)
    远程实现: RemoteGatePolicy (灵境策略中心动态下发)

    切换方式: 描述某类门禁规则的适用性与阈值，
    分布式模式下策略可被集中管理与热更新。
    """

    def should_apply(self, metadata: dict[str, Any]) -> bool:
        """判定本策略是否适用于该上下文。

        Args:
            metadata: 内容元数据。

        Returns:
            是否应用本策略。
        """
        ...

    def get_threshold(self, key: str) -> float:
        """获取指定阈值。

        Args:
            key: 阈值名称 (如 min_value_score)。

        Returns:
            阈值数值。
        """
        ...


# ============================================================================
# 晋升域 (3个) — IConsolidationStrategy / IPromotionGate / IConsolidationScheduler
# ============================================================================


@runtime_checkable
class IConsolidationStrategy(Protocol):
    """晋升策略接口  [v10-ready]

    本地实现: LocalConsolidationStrategy (本地多因子评分, 单进程默认)
    远程实现: RemoteConsolidationStrategy (灵境集中式晋升决策)

    切换方式: 选取候选并执行跨层晋升，
    分布式模式下晋升决策由远程服务统一编排。
    """

    def select_candidates(
        self, layer: str, *, limit: int = 100
    ) -> list[dict[str, Any]]:
        """筛选待晋升候选条目。

        Args:
            layer: 源记忆层级。
            limit: 候选数量上限。

        Returns:
            候选条目字典列表。
        """
        ...

    def promote(self, entry: dict[str, Any], to_layer: str) -> bool:
        """将条目晋升至目标层。

        Args:
            entry: 待晋升条目字典。
            to_layer: 目标记忆层级。

        Returns:
            晋升是否成功。
        """
        ...


@runtime_checkable
class IPromotionGate(Protocol):
    """晋升门禁接口  [v10-ready]

    本地实现: LocalPromotionGate (本地评分判定)
    远程实现: RemotePromotionGate (灵境晋升评分服务)

    切换方式: 在晋升前对条目打分与放行判定，
    分布式模式下评分模型可远程托管。
    """

    def can_promote(
        self, entry: dict[str, Any], from_layer: str, to_layer: str
    ) -> bool:
        """判定条目能否跨层晋升。

        Args:
            entry: 待判定条目字典。
            from_layer: 源层级。
            to_layer: 目标层级。

        Returns:
            是否允许晋升。
        """
        ...

    def score(self, entry: dict[str, Any]) -> float:
        """计算条目晋升评分。

        Args:
            entry: 待评分条目字典。

        Returns:
            晋升评分 (越高越优先)。
        """
        ...


@runtime_checkable
class IConsolidationScheduler(Protocol):
    """晋升调度接口  [v10-ready]

    本地实现: LocalConsolidationScheduler (进程内定时调度)
    远程实现: RemoteConsolidationScheduler (灵境分布式调度器)

    切换方式: 规划各层固结窗口与触发时机，
    分布式模式下由中心调度协调多节点晋升任务。
    """

    def schedule(self, layer: str, interval_seconds: int) -> None:
        """登记某层的固结调度。

        Args:
            layer: 记忆层级。
            interval_seconds: 固结间隔 (秒)。
        """
        ...

    def get_next_window(self, layer: str) -> float:
        """获取下一次固结窗口时间。

        Args:
            layer: 记忆层级。

        Returns:
            下次固结的 Unix 时间戳 (秒)。
        """
        ...


__all__ = [
    # 门禁域
    "IGateStrategy",
    "IQualityGate",
    "IGatePolicy",
    # 晋升域
    "IConsolidationStrategy",
    "IPromotionGate",
    "IConsolidationScheduler",
]
