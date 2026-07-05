# -*- coding: utf-8-sig -*-
"""tianji_mcp_server_build_repr.py — TianjiMCPServerBuild_ReprMixin (SSS-PhaseB)

从 tianji_mcp_server.py 拆分的方法组: build_repr
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

# ── 共享常量 (从core导入) ──────────────────────────────
try:
    from tianji_mcp_server_core import (  # type: ignore
        SYSTEM_NAME, TIANJI_API_URL, _encoding_safe_dict, _encoding_safe_text
    )
except ImportError:
    try:
        from .tianji_mcp_server_core import (  # type: ignore
            SYSTEM_NAME, TIANJI_API_URL, _encoding_safe_dict, _encoding_safe_text
        )
    except ImportError:
        SYSTEM_NAME = "天机-忆库"
        TIANJI_API_URL = "http://127.0.0.1:8771"
        def _encoding_safe_text(t, l=""): return str(t)  # noqa: E701
        def _encoding_safe_dict(d, l=""): return d if isinstance(d, dict) else {}  # noqa: E701


class TianjiMCPServerBuild_ReprMixin:
    """build_repr方法组Mixin"""


    def _handle_build_repr(self, args: dict) -> dict:
        data = {"query": args.get("query", ""), "max_items": args.get("max_items", 24)}
        result = self._api_post("/api/mcp/tools/build_working_representation", data)
        repr_data = (
            result.get("representation", {})
            if isinstance(result, dict) and not result.get("error")
            else {}
        )
        if repr_data and repr_data.get("total_items", 0) > 0:
            return {
                "status": "success",
                "representation": repr_data,
                "system": SYSTEM_NAME,
            }
        query = args.get("query", "")
        max_items = args.get("max_items", 24)
        list_result = self._api_post(
            "/api/mcp/tools/list_memories", {"limit": max_items, "offset": 0}
        )
        if list_result and not list_result.get("error"):
            all_items = list_result.get("results", [])
            if query:
                all_items = self._client_side_filter(all_items, query, max_items)
            return {
                "status": "success",
                "representation": {
                    "query": query,
                    "total_items": len(all_items),
                    "semantic_matches": all_items,
                    "derived_insights": [],
                    "contradictions": [],
                    "digests": [],
                },
                "system": SYSTEM_NAME,
            }
        return {"status": "error", "detail": result}

    def _handle_reflective(self, args: dict) -> dict:
        result = self._api_post("/api/mcp/tools/run_reflective_cycle", {})
        if result and not result.get("error"):
            return {
                "status": "success",
                "dream_stats": result.get("dream_stats"),
                "system": SYSTEM_NAME,
            }
        return {"status": "error", "detail": result}

    def _handle_session_digest(self, args: dict) -> dict:
        data = {
            "session_key": args.get("session_key", ""),
            "digest_kind": args.get("digest_kind", "both"),
        }
        result = self._api_post("/api/mcp/tools/get_session_digest", data)
        if result and not result.get("error"):
            return {
                "status": "success",
                "digests": result.get("digests", []),
                "system": SYSTEM_NAME,
            }
        return {"status": "error", "detail": result}

    def _handle_lineage(self, args: dict) -> dict:
        data = {"memory_id": args.get("memory_id", "")}
        result = self._api_post("/api/mcp/tools/explain_memory_lineage", data)
        if result and not result.get("error"):
            return {
                "status": "success",
                "lineage": result.get("lineage"),
                "system": SYSTEM_NAME,
            }
        return {"status": "error", "detail": result}
