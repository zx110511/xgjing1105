# -*- coding: utf-8-sig -*-
"""tianji_mcp_server_evo.py — TianjiMCPServerEvoMixin (SSS-PhaseB)

从 tianji_mcp_server.py 拆分的方法组: evo
"""

import io
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

# evo模块仅使用self属性，无需外部常量（保留结构一致性）


class TianjiMCPServerEvoMixin:
    """evo方法组Mixin"""


    def _calc_mcp_effectiveness(
        self, action: str, state_before: dict[str, Any], state_after: dict[str, Any]
    ) -> float:
        if action == "tool_call":
            if state_after.get("success"):
                return 0.8
            return 0.1
        elif action == "health_check":
            return 0.9 if state_after.get("api_available") else 0.2
        elif action == "handle_initialize":
            return 0.7
        return 0.0

    def _learn_from_mcp(
        self, causal_pairs: list[Any], effectiveness_summary: dict[str, Any]
    ) -> dict[str, Any]:
        return {
            "patterns_found": len(causal_pairs),
            "avg_effectiveness": effectiveness_summary.get("avg_effectiveness", 0.0),
            "total_tool_calls": self._tool_call_count,
            "total_tool_errors": self._tool_error_count,
            "api_available": self._api_available,
            "error_rate": (self._tool_error_count / max(self._tool_call_count, 1)),
        }

    def _evolve_mcp_config(
        self, learn_result: dict[str, Any], mutable_config: dict[str, Any]
    ) -> dict[str, Any]:
        changes = {}
        error_rate = learn_result.get("error_rate", 0.0)
        if error_rate > 0.2:
            changes["api_timeout"] = min(30, mutable_config.get("api_timeout", 10) + 5)
        elif error_rate < 0.05:
            changes["api_timeout"] = 10
        if not learn_result.get("api_available", True):
            changes["health_check_interval"] = min(
                30, max(10, mutable_config.get("health_check_interval", 60) // 2)
            )
        else:
            changes["health_check_interval"] = 60
        return {"rules_modified": changes, "skills_created": []}
