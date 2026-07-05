# -*- coding: utf-8-sig -*-
"""文件操作追踪钩子 — P2高级, PRE+POST阶段

版本: 1.0.0
"""

from __future__ import annotations

import sys
import hashlib
import logging
import time
from pathlib import Path
from typing import Dict, Any

_GLOBAL_HOOKS_ROOT = str(Path(__file__).resolve().parent.parent.parent.parent.parent)
if _GLOBAL_HOOKS_ROOT not in sys.path:
    sys.path.insert(0, _GLOBAL_HOOKS_ROOT)

from hooks.base import SyncHook, HookPhase, HookPriority, HookResult, HookContext, HookVerdict

logger = logging.getLogger("tianji.hooks.file_operation")


class FileOperationHook(SyncHook):
    """文件操作追踪钩子"""

    CORE_FILES = [
        "core/engine.py", "core/config.py", "core/quality_gate.py",
        "core/enforcement_hook.py", "core/models.py",
        ".trae/rules/", ".trae/mcp.json",
    ]

    def __init__(self):
        super().__init__(name="file_operation", phase=HookPhase.PRE, priority=HookPriority.P2_HIGH, enabled=True, fail_safe=True, tags=["file", "tracking", "P2"])
        self._pending_ops: Dict[str, Dict] = {}

    def execute(self, context: HookContext) -> HookResult:
        operation = context.operation
        if not operation.startswith("file_"):
            return HookResult(hook_id=self._hook_id, hook_name=self.name, verdict=HookVerdict.PASS, message="not_file_operation")
        if context.phase == HookPhase.PRE:
            return self._handle_pre(context)
        elif context.phase == HookPhase.POST:
            return self._handle_post(context)
        return HookResult(hook_id=self._hook_id, hook_name=self.name, verdict=HookVerdict.PASS, message="phase_not_applicable")

    def _handle_pre(self, context: HookContext) -> HookResult:
        payload = context.payload
        file_path = payload.get("path", "")
        op_type = payload.get("operation", "unknown")
        if not file_path:
            return HookResult(hook_id=self._hook_id, hook_name=self.name, verdict=HookVerdict.PASS, message="no_file_path")
        pre_state = self._capture_file_state(file_path)
        self._pending_ops[context.trace_id] = {"path": file_path, "operation": op_type, "pre_state": pre_state, "timestamp": time.time()}
        is_core = any(pattern in file_path for pattern in self.CORE_FILES)
        return HookResult(hook_id=self._hook_id, hook_name=self.name, verdict=HookVerdict.MODIFY, message="file_op_tracked", modified_context={"payload": {**payload, "_file_pre_state": pre_state, "_is_core_file": is_core}}, metadata={"is_core_file": is_core, "op_type": op_type})

    def _handle_post(self, context: HookContext) -> HookResult:
        pending = self._pending_ops.pop(context.trace_id, None)
        payload = context.payload
        file_path = payload.get("path", "")
        if not file_path:
            return HookResult(hook_id=self._hook_id, hook_name=self.name, verdict=HookVerdict.PASS, message="no_file_path")
        post_state = self._capture_file_state(file_path)
        change_summary = self._compute_change_summary(pending.get("pre_state", {}) if pending else {}, post_state)
        return HookResult(hook_id=self._hook_id, hook_name=self.name, verdict=HookVerdict.PASS, message="file_op_completed", metadata={"path": file_path, "change_summary": change_summary, "duration_ms": (time.time() - pending["timestamp"]) * 1000 if pending else 0})

    def _capture_file_state(self, file_path: str) -> Dict[str, Any]:
        try:
            p = Path(file_path)
            if p.exists() and p.is_file():
                content = p.read_text(encoding="utf-8", errors="replace")
                stat = p.stat()
                return {"exists": True, "size": stat.st_size, "content_hash": hashlib.sha256(content.encode()).hexdigest()[:16], "line_count": content.count("\n") + 1, "modified_time": stat.st_mtime}
        except Exception:
            pass
        return {"exists": False}

    def _compute_change_summary(self, pre: Dict[str, Any], post: Dict[str, Any]) -> Dict[str, Any]:
        if not pre.get("exists") and not post.get("exists"):
            return {"type": "no_change"}
        if not pre.get("exists") and post.get("exists"):
            return {"type": "created", "size": post.get("size", 0)}
        if pre.get("exists") and not post.get("exists"):
            return {"type": "deleted", "original_size": pre.get("size", 0)}
        if pre.get("content_hash") != post.get("content_hash"):
            return {"type": "modified", "size_before": pre.get("size", 0), "size_after": post.get("size", 0), "lines_before": pre.get("line_count", 0), "lines_after": post.get("line_count", 0)}
        return {"type": "no_change"}
