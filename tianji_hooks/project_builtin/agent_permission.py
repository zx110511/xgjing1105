# -*- coding: utf-8-sig -*-
"""Agent权限检查钩子 — P0宪法级, PRE阶段

天机智能体权限矩阵 — 完整版
未在矩阵中 = 禁止调用

版本: 1.0.0
"""

from __future__ import annotations

import sys
import logging
from pathlib import Path

_GLOBAL_HOOKS_ROOT = str(Path(__file__).resolve().parent.parent.parent.parent.parent)
if _GLOBAL_HOOKS_ROOT not in sys.path:
    sys.path.insert(0, _GLOBAL_HOOKS_ROOT)

from hooks.base import SyncHook, HookPhase, HookPriority, HookResult, HookContext, HookVerdict

logger = logging.getLogger("tianji.hooks.agent_permission")

PERMISSION_MATRIX = {
    "tianshu": {"allow": ["*"], "deny": [], "scope": "full"},
    "wenzong": {"allow": ["miaobi", "mingjing", "jinshu"], "deny": [], "scope": "editorial"},
    "miaobi": {"allow": ["yiku", "mingjing"], "deny": [], "scope": "creative"},
    "mingjing": {"allow": ["yiku", "miaobi"], "deny": [], "scope": "review"},
    "tiewei": {"allow": ["miaobi", "mingjing", "qianli"], "deny": [], "scope": "testing"},
    "jingwei": {"allow": ["*"], "deny": [], "scope": "read_only"},
    "yiku": {"allow": [], "deny": [], "scope": "memory_only"},
    "dongcha": {"allow": [], "deny": [], "scope": "perception_only"},
    "luling": {"allow": [], "deny": [], "scope": "rule_only"},
    "lingxi": {"allow": [], "deny": [], "scope": "dialogue_only"},
    "tiansuan": {"allow": ["yiku"], "deny": [], "scope": "analysis"},
    "kuangshi": {"allow": ["yiku"], "deny": [], "scope": "corpus"},
    "baiqiao": {"allow": ["yiku", "tianshu"], "deny": [], "scope": "skill_dispatch"},
    "shiguan": {"allow": ["yiku"], "deny": [], "scope": "archive"},
    "jinshu": {"allow": ["yiku"], "deny": [], "scope": "export"},
    "qianli": {"allow": ["yiku", "tiewei"], "deny": [], "scope": "ops"},
    "gongzao": {"allow": ["qianli", "yiku"], "deny": [], "scope": "devops"},
    "zhenshan": {"allow": ["yiku", "tiewei"], "deny": [], "scope": "security"},
    "zhuiguang": {"allow": ["yiku"], "deny": [], "scope": "performance"},
    "evolver": {"allow": ["yiku", "tianshu"], "deny": [], "scope": "evolution"},
    "graphbuilder": {"allow": ["yiku"], "deny": [], "scope": "graph"},
    "orchestrator": {"allow": ["*"], "deny": [], "scope": "system_control"},
    "multimodal": {"allow": ["yiku"], "deny": [], "scope": "multimodal"},
}


class AgentPermissionHook(SyncHook):
    """Agent权限检查钩子 — 与全局tvp_guard互补"""

    def __init__(self):
        super().__init__(name="agent_permission", phase=HookPhase.PRE, priority=HookPriority.P0_CRITICAL, enabled=True, fail_safe=False, tags=["agent", "permission", "P0"])

    def execute(self, context: HookContext) -> HookResult:
        if context.operation != "agent_switch":
            return HookResult(hook_id=self._hook_id, hook_name=self.name, verdict=HookVerdict.PASS, message="not_agent_switch")
        source = context.agent_id
        target = context.target_agent or context.payload.get("target_agent", "")
        if not source or not target:
            return HookResult(hook_id=self._hook_id, hook_name=self.name, verdict=HookVerdict.PASS, message="missing_agent_info_skip")
        if source == target:
            return HookResult(hook_id=self._hook_id, hook_name=self.name, verdict=HookVerdict.PASS, message="self_call_allowed")
        result = self._check_permission(source, target)
        if result["allowed"]:
            return HookResult(hook_id=self._hook_id, hook_name=self.name, verdict=HookVerdict.PASS, message="permission_granted", metadata={"scope": result.get("scope", ""), "reason": result.get("reason", "")})
        return HookResult(hook_id=self._hook_id, hook_name=self.name, verdict=HookVerdict.BLOCK, success=False, message=f"权限拒绝: @{source} → @{target}: {result.get('reason', '未授权')}", metadata={"source": source, "target": target, "reason": result.get("reason", "")})

    def _check_permission(self, source: str, target: str) -> dict:
        matrix = PERMISSION_MATRIX.get(source)
        if not matrix:
            return {"allowed": False, "reason": f"@{source} 不在权限矩阵中"}
        allow, deny, scope = matrix.get("allow", []), matrix.get("deny", []), matrix.get("scope", "")
        if target in deny:
            return {"allowed": False, "reason": "显式拒绝"}
        if "*" in allow:
            return {"allowed": True, "reason": "read_only_consultation" if scope == "read_only" else "wildcard_permission", "scope": scope}
        if target in allow:
            return {"allowed": True, "reason": "explicit_permission", "scope": scope}
        return {"allowed": False, "reason": f"未授权: @{source} 不可调用 @{target}"}
