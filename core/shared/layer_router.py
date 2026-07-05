# -*- coding: utf-8-sig -*-
r"""六层分级分发路由器 — 兼容层 (thin wrapper)  [v10-ready]

本模块自 v10.0.1 起瘦身为兼容层：核心路由逻辑已迁移至
core/routing/ 子包的 LayerRoutingStrategy (实现 ITaskRouter 协议)。

为不破坏 v9.1 现有 import 路径，本文件保留:
  - LayerRouter 类 (内部委托 LayerRoutingStrategy)
  - LayerName / LayerTarget / PromotionGate 类型重新导出
  - 各层常量 (LAYER_MAX_SIZE / KEYWORD_PATTERNS 等) 重新导出

迁移指引:
  新代码请直接使用 `from core.routing import LayerRoutingStrategy`，
  其 route(task)->str 实现 ITaskRouter 协议；多目标分发使用 route_content()。

历史 import (继续可用):
  from core.shared.layer_router import LayerRouter

架构定位: core/ 记忆层级路由兼容层
版本: 1.0.0 (thin wrapper)
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from core.routing.layer_strategy import (
    KEYWORD_PATTERNS,
    LAYER_INDEX_FIELD,
    LAYER_MAX_SIZE,
    LAYER_PRIORITY_ORDER,
    LAYER_PROMOTION_THRESHOLD,
    MULTI_TURN_THRESHOLD,
    LayerName,
    LayerRoutingStrategy,
    LayerTarget,
    PromotionGate,
)

logger = logging.getLogger("tianji.layer_router")


class LayerRouter:
    """六层分级分发路由器 — 兼容层  [v10-ready]

    内部委托 LayerRoutingStrategy 完成全部路由/去重/重组/门禁逻辑，
    保持与 v9.1 完全一致的对外方法签名。
    """

    DEDUP_THRESHOLD = LayerRoutingStrategy.DEDUP_THRESHOLD

    def __init__(self, engine: Any = None, quality_gate: Any = None) -> None:
        """初始化兼容层路由器。  [v10-ready]

        Args:
            engine: 记忆引擎 (可选)。
            quality_gate: 质量门禁 (可选)。
        """
        self._strategy = LayerRoutingStrategy(engine=engine, quality_gate=quality_gate)

    @property
    def strategy(self) -> LayerRoutingStrategy:
        """暴露内部委托的路由策略实例。  [v10-ready]"""
        return self._strategy

    def set_engine(self, engine: Any) -> None:
        """注入记忆引擎。  [v10-ready]"""
        self._strategy.set_engine(engine)

    def set_quality_gate(self, gate: Any) -> None:
        """注入质量门禁。  [v10-ready]"""
        self._strategy.set_quality_gate(gate)

    def route(self, content: str, context: Optional[Dict] = None) -> List[Dict]:
        """内容级分级分发 (多目标)。  [v10-ready]

        兼容原签名: 接收内容文本与上下文，返回多目标层级列表。
        """
        return self._strategy.route_content(content, context)

    def deduplicate(self, content: str, layer: str) -> bool:
        """语义去重。  [v10-ready]"""
        return self._strategy.deduplicate(content, layer)

    def deredundate(self, content: str, layer: str) -> str:
        """去冗余。  [v10-ready]"""
        return self._strategy.deredundate(content, layer)

    def reorganize(self, content: str, layer: str) -> str:
        """重组新知识。  [v10-ready]"""
        return self._strategy.reorganize(content, layer)

    def check_promotion_gate(
        self, content: str, source_layer: str, target_layer: str
    ) -> PromotionGate:
        """层级转换门禁检查。  [v10-ready]"""
        return self._strategy.check_promotion_gate(content, source_layer, target_layer)

    def get_layer_index_fields(self, layer: str) -> List[str]:
        """获取层内索引字段。  [v10-ready]"""
        return self._strategy.get_layer_index_fields(layer)

    def get_stats(self) -> Dict:
        """获取路由统计快照。  [v10-ready]"""
        return self._strategy.get_stats()


__all__ = [
    "LayerRouter",
    "LayerName",
    "LayerTarget",
    "PromotionGate",
    "LAYER_PRIORITY_ORDER",
    "LAYER_MAX_SIZE",
    "LAYER_PROMOTION_THRESHOLD",
    "LAYER_INDEX_FIELD",
    "KEYWORD_PATTERNS",
    "MULTI_TURN_THRESHOLD",
]
