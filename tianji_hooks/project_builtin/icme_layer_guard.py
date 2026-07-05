# -*- coding: utf-8-sig -*-
"""ICME层路由守卫钩子 — P1强制级, PRE阶段

天机ICME六层记忆架构:
  L0 Sensory → L1 Working → L2 Short-Term → L3 Episodic → L4 Semantic → L5 Meta

此钩子确保记忆操作路由到正确的层级:
  - 写入: 按操作类型自动路由到目标层
  - 检索: 跨层搜索, 从高层到低层
  - 固结: 验证晋升方向(只能低→高)

版本: 1.0.0
"""

from __future__ import annotations

import sys
import logging
from pathlib import Path
from typing import Optional

# 确保全局hooks在path中
_GLOBAL_HOOKS_ROOT = str(Path(__file__).resolve().parent.parent.parent.parent.parent)
if _GLOBAL_HOOKS_ROOT not in sys.path:
    sys.path.insert(0, _GLOBAL_HOOKS_ROOT)

from hooks.base import (
    SyncHook,
    HookPhase,
    HookPriority,
    HookResult,
    HookContext,
    HookVerdict,
)

logger = logging.getLogger("tianji.hooks.icme_layer_guard")


# ICME层级定义
ICME_LAYERS = ["sensory", "working", "short_term", "episodic", "semantic", "meta"]
LAYER_ORDER = {name: idx for idx, name in enumerate(ICME_LAYERS)}

# 操作→目标层映射
OPERATION_LAYER_MAP = {
    "memory_write_raw": "sensory",
    "memory_write_context": "working",
    "memory_write_short": "short_term",
    "memory_write_event": "episodic",
    "memory_write_knowledge": "semantic",
    "memory_write_strategy": "meta",
    "memory_consolidate": "auto",
    "memory_recall": "auto",
    "memory_delete": "auto",
}


class ICMELayerGuardHook(SyncHook):
    """ICME层路由守卫钩子"""

    def __init__(self):
        super().__init__(
            name="icme_layer_guard",
            phase=HookPhase.PRE,
            priority=HookPriority.P1_MANDATORY,
            enabled=True,
            fail_safe=True,
            tags=["icme", "memory", "P1"],
        )

    def execute(self, context: HookContext) -> HookResult:
        operation = context.operation
        payload = context.payload

        if not operation.startswith("memory_"):
            return HookResult(hook_id=self._hook_id, hook_name=self.name, verdict=HookVerdict.PASS, message="not_memory_operation")

        target_layer = payload.get("layer", "")
        expected_layer = OPERATION_LAYER_MAP.get(operation)

        if operation == "memory_consolidate":
            return self._validate_consolidation(context, payload)
        if operation == "memory_recall":
            return self._validate_recall(context, payload)
        if operation == "memory_delete":
            return self._validate_delete(context, payload)

        if expected_layer and expected_layer != "auto":
            if not target_layer:
                return HookResult(
                    hook_id=self._hook_id, hook_name=self.name,
                    verdict=HookVerdict.MODIFY, message=f"auto_route_to_{expected_layer}",
                    modified_context={"payload": {**payload, "layer": expected_layer}},
                    metadata={"auto_routed": True, "target_layer": expected_layer},
                )
            if target_layer not in ICME_LAYERS:
                return HookResult(
                    hook_id=self._hook_id, hook_name=self.name,
                    verdict=HookVerdict.BLOCK, success=False,
                    message=f"无效的ICME层级: {target_layer}",
                    metadata={"invalid_layer": target_layer, "valid_layers": ICME_LAYERS},
                )

        return HookResult(hook_id=self._hook_id, hook_name=self.name, verdict=HookVerdict.PASS, message="icme_layer_valid")

    def _validate_consolidation(self, context: HookContext, payload: dict) -> HookResult:
        from_layer = payload.get("from_layer", "")
        to_layer = payload.get("to_layer", "")
        if not from_layer or not to_layer:
            return HookResult(hook_id=self._hook_id, hook_name=self.name, verdict=HookVerdict.BLOCK, success=False, message="固结操作缺少from_layer或to_layer")
        if from_layer not in LAYER_ORDER or to_layer not in LAYER_ORDER:
            return HookResult(hook_id=self._hook_id, hook_name=self.name, verdict=HookVerdict.BLOCK, success=False, message=f"无效的固结层级: {from_layer} → {to_layer}")
        from_idx, to_idx = LAYER_ORDER[from_layer], LAYER_ORDER[to_layer]
        if to_idx <= from_idx:
            return HookResult(hook_id=self._hook_id, hook_name=self.name, verdict=HookVerdict.BLOCK, success=False, message=f"固结方向错误: {from_layer}(L{from_idx}) → {to_layer}(L{to_idx}), 必须低→高", metadata={"from": from_layer, "to": to_layer})
        return HookResult(hook_id=self._hook_id, hook_name=self.name, verdict=HookVerdict.PASS, message="consolidation_direction_valid", metadata={"from": from_layer, "to": to_layer})

    def _validate_recall(self, context: HookContext, payload: dict) -> HookResult:
        layers = payload.get("layers", [])
        if layers:
            invalid = [l for l in layers if l not in ICME_LAYERS]
            if invalid:
                return HookResult(hook_id=self._hook_id, hook_name=self.name, verdict=HookVerdict.BLOCK, success=False, message=f"检索包含无效层级: {invalid}")
        return HookResult(hook_id=self._hook_id, hook_name=self.name, verdict=HookVerdict.PASS, message="recall_layers_valid")

    def _validate_delete(self, context: HookContext, payload: dict) -> HookResult:
        soft_delete = payload.get("soft_delete", True)
        if not soft_delete:
            return HookResult(hook_id=self._hook_id, hook_name=self.name, verdict=HookVerdict.BLOCK, success=False, message="禁止硬删除天机记忆数据, 仅允许软删除(soft_delete=True)")
        return HookResult(hook_id=self._hook_id, hook_name=self.name, verdict=HookVerdict.PASS, message="soft_delete_allowed")
