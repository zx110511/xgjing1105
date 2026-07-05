# -*- coding: utf-8-sig -*-
"""tianji_mcp_server_tcl.py — TianjiMCPServerTclMixin (SSS-PhaseB)

从 tianji_mcp_server.py 拆分的方法组: tcl
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


class TianjiMCPServerTclMixin:
    """tcl方法组Mixin"""

    def _handle_classify(self, args: dict) -> dict:
        data = {"content": args.get("content", ""), "context": args.get("context")}
        result = self._api_post("/api/llm/classify", data)
        if result and not result.get("error"):
            classification = result.get("classification", result)
            return {
                "status": "success",
                "recommended_layer": classification.get("layer", "working"),
                "confidence": classification.get(
                    "confidence",
                    max(0.5, float(classification.get("value_score", 0.5))),
                ),
                "tags": classification.get("tags", []),
                "priority": classification.get("priority", "medium"),
                "value_score": classification.get("value_score", 0.5),
                "reason": classification.get("reason", ""),
                "related_concepts": classification.get("related_concepts", []),
                "classification": classification,
                "system": SYSTEM_NAME,
            }
        if isinstance(result, dict) and "HTTP 503" in str(result.get("error", "")):
            return {
                "status": "fallback",
                "recommended_layer": "working",
                "confidence": 0.3,
                "reason": "DeepSeek不可用，使用默认分层",
                "system": SYSTEM_NAME,
            }
        return {"status": "error", "detail": result}

    def _handle_auto_tag(self, args: dict) -> dict:
        data = {"content": args.get("content", "")}
        result = self._api_post("/api/llm/auto_tag", data)
        if result and not result.get("error"):
            return {
                "status": "success",
                "tags": result.get("tags", []),
                "system": SYSTEM_NAME,
            }
        if isinstance(result, dict) and "HTTP 503" in str(result.get("error", "")):
            content = args.get("content", "")
            words = [
                w.strip()
                for w in content.replace("，", ",").replace("。", ",").split(",")
                if len(w.strip()) >= 2
            ]
            return {
                "status": "fallback",
                "tags": words[:8],
                "reason": "DeepSeek不可用，使用关键词提取",
                "system": SYSTEM_NAME,
            }
        return {"status": "error", "detail": result}

    def _handle_summarize(self, args: dict) -> dict:
        data = {
            "content": args.get("content", ""),
            "max_length": args.get("max_length", 200),
        }
        result = self._api_post("/api/llm/summarize", data)
        if result and not result.get("error"):
            return {
                "status": "success",
                "summary": result.get("summary", ""),
                "system": SYSTEM_NAME,
            }
        if isinstance(result, dict) and "HTTP 503" in str(result.get("error", "")):
            content = args.get("content", "")
            max_len = args.get("max_length", 200)
            return {
                "status": "fallback",
                "summary": content[:max_len]
                + ("..." if len(content) > max_len else ""),
                "reason": "DeepSeek不可用，使用截断摘要",
                "system": SYSTEM_NAME,
            }
        return {"status": "error", "detail": result}

    def _handle_extract_knowledge(self, args: dict) -> dict:
        data = {"content": args.get("content", "")}
        result = self._api_post("/api/llm/extract_knowledge", data)
        if result and not result.get("error"):
            return {
                "status": "success",
                "triples": result.get("triples", []),
                "count": result.get("count", 0),
                "system": SYSTEM_NAME,
            }
        if isinstance(result, dict) and "HTTP 503" in str(result.get("error", "")):
            return {
                "status": "fallback",
                "triples": [],
                "count": 0,
                "reason": "DeepSeek不可用，知识提取跳过",
                "system": SYSTEM_NAME,
            }
        return {"status": "error", "detail": result}

    def _handle_expand_query(self, args: dict) -> dict:
        data = {"query": args.get("query", "")}
        result = self._api_post("/api/llm/expand_query", data)
        if result and not result.get("error"):
            return {
                "status": "success",
                "original": args.get("query"),
                "expansions": result.get("expansions", []),
                "system": SYSTEM_NAME,
            }
        if isinstance(result, dict) and "HTTP 503" in str(result.get("error", "")):
            return {
                "status": "fallback",
                "original": args.get("query"),
                "expansions": [args.get("query")],
                "reason": "DeepSeek不可用，查询不扩展",
                "system": SYSTEM_NAME,
            }
        return {"status": "error", "detail": result}

    def _handle_semantic_search(self, args: dict) -> dict:
        query = args.get("query", "")
        limit = args.get("limit", 20)
        params = {"q": query, "limit": limit}
        result = self._api_get("/api/search/semantic", params)
        if result:
            # API returns {"results": [...], "total": N, "query_time": 0}
            if isinstance(result, dict) and "results" in result:
                return {
                    "status": "success",
                    "results": result["results"],
                    "total": result.get("total", len(result["results"])),
                    "query_time": result.get("query_time", 0),
                    "system": SYSTEM_NAME,
                }
            if isinstance(result, list):
                return {
                    "status": "success",
                    "results": result,
                    "total": len(result),
                    "system": SYSTEM_NAME,
                }
        return {"status": "error", "detail": result}

    def _handle_normalize(self, args: dict) -> dict:
        """TCL术语归一化处理"""
        # [FIX-MCP-Bug4] 兼容schema的content参数名 (schema=content, 旧代码=text)
        text = args.get("content", args.get("text", ""))
        context = args.get("context", "")
        mode = args.get("mode", "single")
        if not text:
            return {"status": "error", "detail": "content参数不能为空"}
        try:
            from core.memory.tcl_normalizer import (
                TCLNormalizer,
                TerminologyStore,
                seed_terminology,
            )

            tcl_db = "data/.memory/tcl_terminology.db"
            if hasattr(self, "_engine") and self._engine is not None and hasattr(self._engine, "_data_path"):
                tcl_db = str(self._engine._data_path / "tcl_terminology.db")
            store = TerminologyStore(tcl_db)
            if store.get_stats()["total_terms"] == 0:
                seed_terminology(store)
            llm_bridge = None
            if hasattr(self, "_engine") and self._engine is not None:
                llm_bridge = getattr(self._engine, "_llm_bridge", None)
            normalizer = TCLNormalizer(
                store, llm_bridge=llm_bridge
            )
            if mode == "content":
                content, canonical_ids = normalizer.normalize_content(text, context)
                return {
                    "status": "success",
                    "original": text,
                    "canonical_ids": canonical_ids,
                    "normalized_count": len(canonical_ids),
                    "stats": normalizer.get_stats(),
                    "system": SYSTEM_NAME,
                }
            else:
                result = normalizer.normalize(text, context)
                return {
                    "status": "success",
                    "original": result.original,
                    "canonical_id": result.canonical_id,
                    "canonical_term": result.canonical_term,
                    "confidence": result.confidence,
                    "method": result.method,
                    "latency_ms": round(result.latency_ms, 2),
                    "system": SYSTEM_NAME,
                }
        except Exception as e:
            return {"status": "error", "detail": str(e)}

    def _handle_disambiguate(self, args: dict) -> dict:
        """TCL多义词消歧处理"""
        # [FIX-MCP-Bug5] 兼容schema的content参数名 (schema=content, 旧代码=term)
        term = args.get("content", args.get("term", ""))
        context = args.get("context", "")
        if not term:
            return {"status": "error", "detail": "content参数不能为空"}
        try:
            from core.memory.tcl_normalizer import (
                TCLDisambiguator,
                TerminologyStore,
                seed_terminology,
            )

            tcl_db = "data/.memory/tcl_terminology.db"
            if hasattr(self, "_engine") and self._engine is not None and hasattr(self._engine, "_data_path"):
                tcl_db = str(self._engine._data_path / "tcl_terminology.db")
            store = TerminologyStore(tcl_db)
            if store.get_stats()["total_terms"] == 0:
                seed_terminology(store)
            disambiguator = TCLDisambiguator(store)
            result = disambiguator.disambiguate(term, context)
            return {
                "status": "success",
                "original": result.original,
                "canonical_id": result.canonical_id,
                "canonical_term": result.canonical_term,
                "confidence": result.confidence,
                "method": result.method,
                "system": SYSTEM_NAME,
            }
        except Exception as e:
            return {"status": "error", "detail": str(e)}
