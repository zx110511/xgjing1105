# -*- coding: utf-8-sig -*-
r"""天机固结编排处理器 (Consolidation Processor) v1.0
=====================================================
道一·记忆道 · 地煞-03 质量门禁的编排扩展

为记忆固结提供多策略编排能力，支持渐进式/紧急式/均衡式三种编排策略。

编排策略:
  - PROGRESSIVE: 渐进式 — 按promotion_score从高到低逐步晋升
  - EMERGENCY: 紧急式 — 硬上限触发时快速降级/归档
  - BALANCED: 均衡式 — 兼顾质量与速度的折中策略

核心能力:
  - 编排决策: 根据层容量状态选择最优固结策略
  - 批量执行: 调用engine.consolidate_batch执行固结
  - 结果追踪: 记录固结效果到进化闭环

架构位置: core/processors/consolidation_processor.py
依赖: ICMEEngine (通过构造函数注入)
"""

import logging
import time
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger("tianji.consolidation_processor")


class OrchestrationStrategy(str, Enum):
    """编排策略枚举"""
    PROGRESSIVE = "progressive"
    EMERGENCY = "emergency"
    BALANCED = "balanced"


class ConsolidationProcessor:
    """固结编排处理器 — 多策略固结编排与执行

    核心逻辑:
      1. 根据层容量状态选择编排策略
      2. 调用engine的固结方法执行批量固结
      3. 追踪固结效果并反馈到进化闭环

    使用方式:
      processor = ConsolidationProcessor(engine=icme_engine)
      result = processor.process(layer="semantic", strategy=OrchestrationStrategy.BALANCED)
    """

    # 策略对应的默认参数
    STRATEGY_PARAMS = {
        OrchestrationStrategy.PROGRESSIVE: {
            "threshold": 0.7,
            "max_entries": 30,
            "use_quality_promotion": True,
        },
        OrchestrationStrategy.EMERGENCY: {
            "threshold": 0.3,
            "max_entries": 100,
            "use_quality_promotion": False,
        },
        OrchestrationStrategy.BALANCED: {
            "threshold": 0.5,
            "max_entries": 50,
            "use_quality_promotion": True,
        },
    }

    def __init__(self, engine=None):
        self._engine = engine
        self._stats = {
            "total_orchestrations": 0,
            "progressive_count": 0,
            "emergency_count": 0,
            "balanced_count": 0,
            "total_consolidated": 0,
        }

    def process(
        self,
        layer: str,
        strategy: Optional[OrchestrationStrategy] = None,
        custom_params: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """执行固结编排

        Args:
            layer: 目标层名称
            strategy: 编排策略 (None=自动选择)
            custom_params: 自定义参数覆盖

        Returns:
            编排结果字典
        """
        if self._engine is None:
            return {"status": "error", "error": "engine_not_available"}

        # 自动选择策略
        if strategy is None:
            strategy = self._select_strategy(layer)

        # 获取策略参数
        params = dict(self.STRATEGY_PARAMS.get(strategy, self.STRATEGY_PARAMS[OrchestrationStrategy.BALANCED]))
        if custom_params:
            params.update(custom_params)

        start_time = time.time()

        try:
            result = self._engine.consolidate_batch(
                from_layer=layer,
                threshold=params.get("threshold", 0.5),
                max_entries=params.get("max_entries", 50),
                use_quality_promotion=params.get("use_quality_promotion", True),
            )

            elapsed = time.time() - start_time

            # 更新统计
            self._stats["total_orchestrations"] += 1
            self._stats[f"{strategy.value}_count"] += 1
            self._stats["total_consolidated"] += result.get("consolidated", 0)

            # 反馈到进化闭环
            if hasattr(self._engine, '_evo_loop') and self._engine._evo_loop:
                try:
                    self._engine._evo_loop.record_action(
                        action="consolidation_orchestration",
                        state_before={"layer": layer, "strategy": strategy.value},
                        state_after={
                            "consolidated": result.get("consolidated", 0),
                            "elapsed_ms": round(elapsed * 1000, 1),
                        },
                    )
                except Exception:
                    pass

            return {
                "status": "completed",
                "layer": layer,
                "strategy": strategy.value,
                "result": result,
                "elapsed_ms": round(elapsed * 1000, 1),
            }

        except Exception as e:
            logger.error(f"Consolidation orchestration failed for {layer}: {e}")
            return {
                "status": "error",
                "layer": layer,
                "strategy": strategy.value if strategy else "auto",
                "error": str(e),
            }

    def _select_strategy(self, layer: str) -> OrchestrationStrategy:
        """根据层容量状态自动选择编排策略"""
        if self._engine is None:
            return OrchestrationStrategy.BALANCED

        try:
            capacity_info = self._engine.get_layer_capacity_info()
            layer_info = capacity_info.get(layer, {})
            usage_ratio = layer_info.get("usage_ratio", 0)
            at_hard_cap = layer_info.get("at_hard_cap", False)
            margin_level = "red"

            # 获取margin level
            if hasattr(self._engine, '_get_margin_level'):
                margin_level = self._engine._get_margin_level(layer)

            if at_hard_cap or margin_level == "red":
                return OrchestrationStrategy.EMERGENCY
            elif usage_ratio > 0.7 or margin_level in ("orange", "yellow"):
                return OrchestrationStrategy.BALANCED
            else:
                return OrchestrationStrategy.PROGRESSIVE

        except Exception:
            return OrchestrationStrategy.BALANCED

    def get_stats(self) -> dict[str, Any]:
        """获取编排器统计信息"""
        return dict(self._stats)
