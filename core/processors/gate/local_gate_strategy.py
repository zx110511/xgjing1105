# -*- coding: utf-8-sig -*-
"""天机v10.0.1 本地门禁策略 LocalGateStrategy  [v10-ready]

实现 IGateStrategy 协议，封装完整的三问推演门禁判定:
    Q1 用户活动意志 + Q2 知识因果链 (委托 PolicyEngine 评分)
    Q3 反向过滤: 冗余/矛盾/过期/噪声 (委托 NoiseFilter)

判决映射 GateResult / GateVerdict (均来自 core/shared/protocols.py)。
单进程默认实现；分布式模式由 RemoteGateStrategy 远程接管。

架构定位: core/gate/ 门禁策略子包 — 策略编排层
版本: 1.0.0
"""
from __future__ import annotations

from typing import Any, Optional

try:
    from ..config import DEFAULT_CONFIG
    from core.shared.protocols import GateResult, GateVerdict, IGateStrategy
except ImportError:  # pragma: no cover - 兼容直接执行
    from core.shared.config import DEFAULT_CONFIG  # type: ignore
    from core.shared.protocols import GateResult, GateVerdict, IGateStrategy  # type: ignore

from .noise_filter import NoiseFilter, _resolve_config
from .policy_engine import PolicyEngine


class LocalGateStrategy:
    """本地三问推演门禁策略 — IGateStrategy 实现  [v10-ready]

    本地实现: 进程内同步判定，零网络依赖，单进程默认。
    远程实现: RemoteGateStrategy (灵境集中式门禁服务, gRPC stub)。

    满足 ``isinstance(LocalGateStrategy(), IGateStrategy) == True``:
    实现 check() 返回 GateResult，get_verdict() 返回 GateVerdict。

    内部委托:
        - NoiseFilter  : Q3 反向过滤 (冗余/矛盾/过期/噪声)
        - PolicyEngine : Q1/Q2 正向评分 + 阈值判决
    """

    def __init__(
        self,
        config: Optional[Any] = None,
        noise_filter: Optional[NoiseFilter] = None,
        policy_engine: Optional[PolicyEngine] = None,
        conflict_resolver: Optional[Any] = None,
    ) -> None:
        """初始化本地门禁策略  [v10-ready]

        Args:
            config: 门禁配置；缺省使用 DEFAULT_CONFIG.quality_gate。
            noise_filter: 可选共享 NoiseFilter。
            policy_engine: 可选共享 PolicyEngine。
            conflict_resolver: 可选冲突消解器 (用于矛盾检测增强)。
        """
        self.config = _resolve_config(config)
        self._noise_filter = noise_filter or NoiseFilter(self.config)
        self._policy_engine = policy_engine or PolicyEngine(
            self.config, noise_filter=self._noise_filter
        )
        self._conflict_resolver = conflict_resolver

    # ==================================================================
    # IGateStrategy 协议方法
    # ==================================================================
    def check(self, content: str, metadata: dict[str, Any]) -> GateResult:
        """执行门禁判定，产出 GateResult  [v10-ready]

        Args:
            content: 待判定内容文本。
            metadata: 内容元数据 (layer/tags/priority/existing_entries 等)。

        Returns:
            门禁判决 GateResult (verdict/confidence/reason/suggested_layer)。
        """
        metadata = metadata or {}
        layer = metadata.get("layer", "working")

        # 策略适用性 — 跳过门禁则直接放行
        if not self._policy_engine.should_apply(metadata):
            return GateResult(
                verdict=GateVerdict.PASS.value,
                confidence=1.0,
                reason="门禁策略不适用，直接放行",
                suggested_layer=layer,
            )

        # Q3 反向过滤 (冗余/矛盾/过期/噪声)
        filt = self._noise_filter.filter(
            content, metadata, conflict_resolver=self._conflict_resolver
        )
        if filt["reject"]:
            return GateResult(
                verdict=GateVerdict.REJECT.value,
                confidence=round(1.0 - filt["score"], 4),
                reason=filt["reason"],
                suggested_layer=None,
            )
        if filt["conflict"]:
            return GateResult(
                verdict=GateVerdict.CONFLICT.value,
                confidence=filt["score"],
                reason=filt["reason"],
                suggested_layer=layer,
            )

        # Q1/Q2 正向综合评分
        score = self._policy_engine.evaluate(content, metadata)
        pass_threshold = self._policy_engine.get_threshold("pass")

        if score >= pass_threshold:
            return GateResult(
                verdict=GateVerdict.PASS.value,
                confidence=round(score, 4),
                reason=f"高质量记忆, 综合评分{score:.2f}",
                suggested_layer=layer,
            )

        fallback = self._policy_engine.determine_fallback(layer)
        return GateResult(
            verdict=GateVerdict.DOWNGRADE.value,
            confidence=round(score, 4),
            reason=f"综合质量不足({score:.2f}<{pass_threshold}), 降级至{fallback}",
            suggested_layer=fallback,
        )

    def get_verdict(self, content: str, metadata: dict[str, Any]) -> GateVerdict:
        """仅返回判决枚举  [v10-ready]

        Args:
            content: 待判定内容文本。
            metadata: 内容元数据。

        Returns:
            判决枚举 GateVerdict。
        """
        result = self.check(content, metadata)
        return GateVerdict(result.verdict)
