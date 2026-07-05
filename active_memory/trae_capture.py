r"""
Trae对话全量捕获模块 v1.0
=========================
Trae IDE 每轮对话结束时自动触发，实现全量对话内容捕获。

核心设计:
  1. L0 全文快照: 对话窗口全量内容（不限长）+ 文件内容摘要（保留≥40%）
  2. 分级分发: 通过 LayerRouter 自动路由到 L1-L5
  3. 去重去冗余: 写入前语义去重，层内去冗余
  4. 重组新知识: 高层知识重组（事件链/三元组/策略规则）

触发链路:
  Trae IDE 对话结束 → trae_stream_capture MCP → capture_conversation_turn()
    ├──→ L0 Sensory (全文快照)
    ├──→ LayerRouter.route() → L1-L5 分级分发
    └──→ engine.remember() → QualityGate → 写入
"""

import time
import json
import hashlib
import threading
import logging
from typing import Any, Optional, Dict, List, Tuple
from dataclasses import dataclass, field
from pathlib import Path
from enum import Enum

logger = logging.getLogger("tianji.trae_capture")


class CaptureMode(str, Enum):
    FULL = "full"
    INCREMENTAL = "incremental"
    SNAPSHOT_ONLY = "snapshot_only"


@dataclass
class FileSummary:
    file_path: str
    original_size: int
    summary_size: int
    retention_ratio: float
    content: str
    language: str = ""

    def to_dict(self) -> dict:
        return {
            "file_path": self.file_path,
            "original_size": self.original_size,
            "summary_size": self.summary_size,
            "retention_ratio": round(self.retention_ratio, 2),
            "language": self.language,
        }


@dataclass
class ConversationTurn:
    session_id: str
    turn_number: int
    user_input: str
    ai_response: str
    agent_id: str = "tianshu"
    timestamp: float = field(default_factory=time.time)
    platform: str = "trae"
    mcp_calls: List[str] = field(default_factory=list)
    file_operations: List[Dict] = field(default_factory=list)
    file_summaries: List[FileSummary] = field(default_factory=list)
    content_hash: str = ""
    total_bytes: int = 0

    def __post_init__(self):
        if not self.content_hash:
            raw = f"{self.session_id}:{self.turn_number}:{len(self.user_input)}:{len(self.ai_response)}"
            self.content_hash = hashlib.md5(raw.encode()).hexdigest()[:12]
        self.total_bytes = len(self.user_input.encode("utf-8")) + len(self.ai_response.encode("utf-8"))


class TraeConversationCapture:
    """
    Trae对话全量捕获器

    职责:
    1. 捕获完整对话内容（不限长度）
    2. 提取涉及文件的摘要（保留≥40%内容）
    3. 写入L0 Sensory层（原始快照）
    4. 通过LayerRouter分发到L1-L5
    """

    MIN_FILE_SUMMARY_RATIO = 0.4

    def __init__(self, engine=None, data_path: Optional[Path] = None,
                 capture_mode: CaptureMode = CaptureMode.FULL):
        self._engine = engine
        self._data_path = data_path or Path("./data")
        self._capture_mode = capture_mode
        self._lock = threading.Lock()
        self._stats = {
            "total_captures": 0,
            "total_bytes_captured": 0,
            "l0_writes": 0,
            "layer_routed_writes": 0,
            "dedup_skips": 0,
            "file_summaries_created": 0,
            "errors": 0,
        }
        self._session_turns: Dict[str, int] = {}
        self._layer_router = None

    def set_engine(self, engine):
        self._engine = engine

    def set_layer_router(self, router):
        self._layer_router = router

    def capture_conversation_turn(
        self,
        user_input: str,
        ai_response: str,
        session_id: str,
        agent_id: str = "tianshu",
        platform: str = "trae",
        mcp_calls: Optional[List[str]] = None,
        file_operations: Optional[List[Dict]] = None,
        file_contents: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """
        捕获一轮对话 — 核心入口

        参数:
            user_input: 用户输入全文（不限长）
            ai_response: AI响应全文（不限长）
            session_id: 会话ID
            agent_id: Agent标识
            platform: 平台标识
            mcp_calls: 本轮MCP调用列表
            file_operations: 本轮文件操作列表
            file_contents: 涉及文件内容映射 {path: content}

        返回:
            捕获结果字典，包含L0 memory_id和各层分发结果
        """
        with self._lock:
            self._stats["total_captures"] += 1
            turn_number = self._session_turns.get(session_id, 0) + 1
            self._session_turns[session_id] = turn_number

        file_summaries = []
        if file_contents:
            for fpath, fcontent in file_contents.items():
                summary = self._create_file_summary(fpath, fcontent)
                file_summaries.append(summary)

        turn = ConversationTurn(
            session_id=session_id,
            turn_number=turn_number,
            user_input=user_input,
            ai_response=ai_response,
            agent_id=agent_id,
            platform=platform,
            mcp_calls=mcp_calls or [],
            file_operations=file_operations or [],
            file_summaries=file_summaries,
        )

        self._stats["total_bytes_captured"] += turn.total_bytes

        l0_result = self._store_to_l0(turn)

        routed_results = self._route_to_layers(turn)

        return {
            "status": "success",
            "turn_number": turn_number,
            "content_hash": turn.content_hash,
            "total_bytes": turn.total_bytes,
            "l0_memory_id": l0_result.get("memory_id"),
            "l0_layer": l0_result.get("layer", "sensory"),
            "routed_layers": routed_results,
            "file_summaries": len(file_summaries),
            "dedup_skips": sum(1 for r in routed_results if r.get("skipped")),
        }

    def _store_to_l0(self, turn: ConversationTurn) -> Dict:
        """
        L0 Sensory 全文快照 — 不截断、不摘要、不丢字段
        """
        content = json.dumps({
            "type": "conversation_full_capture",
            "session_id": turn.session_id,
            "turn_number": turn.turn_number,
            "agent_id": turn.agent_id,
            "platform": turn.platform,
            "user_input": turn.user_input,
            "ai_response": turn.ai_response,
            "mcp_calls": turn.mcp_calls,
            "file_operations": turn.file_operations,
            "file_summaries": [fs.to_dict() for fs in turn.file_summaries],
            "content_hash": turn.content_hash,
            "total_bytes": turn.total_bytes,
            "timestamp": turn.timestamp,
        }, ensure_ascii=False)

        result = self._engine_remember(
            content=content,
            layer="sensory",
            tags=["trae_capture", "full_capture", turn.session_id[:20]],
            priority="low",
            metadata={
                "source": "trae_capture",
                "session_id": turn.session_id,
                "turn_number": turn.turn_number,
                "agent_id": turn.agent_id,
                "content_hash": turn.content_hash,
                "total_bytes": turn.total_bytes,
            },
        )

        self._stats["l0_writes"] += 1
        return result

    def _route_to_layers(self, turn: ConversationTurn) -> List[Dict]:
        """
        通过LayerRouter分级分发到L1-L5
        """
        if not self._layer_router:
            return self._fallback_route(turn)

        combined = f"{turn.user_input}\n{turn.ai_response}"
        context = {
            "session_id": turn.session_id,
            "turn_number": turn.turn_number,
            "agent_id": turn.agent_id,
            "mcp_calls": turn.mcp_calls,
            "file_operations": turn.file_operations,
            "platform": turn.platform,
        }

        try:
            targets = self._layer_router.route(combined, context)
        except Exception as e:
            logger.error(f"LayerRouter.route 失败: {e}")
            return self._fallback_route(turn)

        results = []
        for target in targets:
            layer = target["layer"]
            content = target.get("content", combined)
            tags = target.get("tags", []) + ["layer_routed", turn.session_id[:20]]
            priority = target.get("priority", "medium")

            if self._layer_router:
                try:
                    should_skip = self._layer_router.deduplicate(content, layer)
                    if should_skip:
                        self._stats["dedup_skips"] += 1
                        results.append({"layer": layer, "skipped": True, "reason": "dedup"})
                        continue
                except Exception:
                    pass

            result = self._engine_remember(
                content=content,
                layer=layer,
                tags=tags,
                priority=priority,
                metadata={
                    "source": "layer_router",
                    "session_id": turn.session_id,
                    "turn_number": turn.turn_number,
                    "agent_id": turn.agent_id,
                    "content_hash": turn.content_hash,
                },
            )

            self._stats["layer_routed_writes"] += 1
            results.append({
                "layer": layer,
                "memory_id": result.get("memory_id"),
                "gate_verdict": result.get("gate_verdict"),
                "skipped": False,
            })

        return results

    def _fallback_route(self, turn: ConversationTurn) -> List[Dict]:
        """
        降级路由 — LayerRouter不可用时使用关键词匹配
        """
        combined = f"{turn.user_input}\n{turn.ai_response}"
        results = []

        architecture_kw = ["架构", "设计", "重构", "改造", "architecture", "design", "refactor"]
        decision_kw = ["决策", "错误", "修复", "bug", "error", "fix", "决定"]
        strategy_kw = ["策略", "规则", "变更", "strategy", "policy", "rule", "config"]

        if any(kw in combined.lower() for kw in strategy_kw):
            result = self._engine_remember(
                content=combined, layer="meta",
                tags=["layer_routed", "strategy", turn.session_id[:20]],
                priority="high",
                metadata={"source": "fallback_route", "session_id": turn.session_id},
            )
            results.append({"layer": "meta", "memory_id": result.get("memory_id"), "skipped": False})

        if any(kw in combined.lower() for kw in architecture_kw):
            result = self._engine_remember(
                content=combined, layer="semantic",
                tags=["layer_routed", "architecture", turn.session_id[:20]],
                priority="high",
                metadata={"source": "fallback_route", "session_id": turn.session_id},
            )
            results.append({"layer": "semantic", "memory_id": result.get("memory_id"), "skipped": False})

        if any(kw in combined.lower() for kw in decision_kw):
            result = self._engine_remember(
                content=combined, layer="episodic",
                tags=["layer_routed", "decision", turn.session_id[:20]],
                priority="high",
                metadata={"source": "fallback_route", "session_id": turn.session_id},
            )
            results.append({"layer": "episodic", "memory_id": result.get("memory_id"), "skipped": False})

        if turn.turn_number >= 3:
            result = self._engine_remember(
                content=combined, layer="short_term",
                tags=["layer_routed", "multi_turn", turn.session_id[:20]],
                priority="medium",
                metadata={"source": "fallback_route", "session_id": turn.session_id},
            )
            results.append({"layer": "short_term", "memory_id": result.get("memory_id"), "skipped": False})

        result = self._engine_remember(
            content=combined, layer="working",
            tags=["layer_routed", "context", turn.session_id[:20]],
            priority="medium",
            metadata={"source": "fallback_route", "session_id": turn.session_id},
        )
        results.append({"layer": "working", "memory_id": result.get("memory_id"), "skipped": False})

        return results

    def _create_file_summary(self, file_path: str, content: str) -> FileSummary:
        """
        创建文件摘要 — 保留至少40%内容
        """
        original_size = len(content.encode("utf-8"))
        min_retain = int(original_size * self.MIN_FILE_SUMMARY_RATIO)

        if original_size <= 2000:
            summary = content
        else:
            lines = content.split("\n")
            total_lines = len(lines)
            keep_lines = max(int(total_lines * self.MIN_FILE_SUMMARY_RATIO), 10)

            head_lines = keep_lines // 2
            tail_lines = keep_lines - head_lines

            head = lines[:head_lines]
            tail = lines[-tail_lines:] if tail_lines > 0 else []

            if len(head) + len(tail) < total_lines:
                middle_marker = f"\n... [{total_lines - head_lines - tail_lines} lines omitted] ...\n"
            else:
                middle_marker = ""

            summary = "\n".join(head) + middle_marker + "\n".join(tail)

        summary_size = len(summary.encode("utf-8"))
        retention_ratio = summary_size / original_size if original_size > 0 else 1.0

        ext = Path(file_path).suffix.lower()
        lang_map = {".py": "python", ".js": "javascript", ".ts": "typescript",
                    ".md": "markdown", ".json": "json", ".yaml": "yaml", ".yml": "yaml"}
        language = lang_map.get(ext, "")

        self._stats["file_summaries_created"] += 1

        return FileSummary(
            file_path=file_path,
            original_size=original_size,
            summary_size=summary_size,
            retention_ratio=retention_ratio,
            content=summary,
            language=language,
        )

    def _engine_remember(self, content: str, layer: str, tags: List[str],
                         priority: str, metadata: Dict) -> Dict:
        """
        调用引擎写入记忆 — 支持多种引擎后端
        """
        if self._engine is None:
            try:
                import urllib.request
                data = json.dumps({
                    "content": content, "layer": layer,
                    "tags": tags, "priority": priority,
                    "metadata": metadata,
                }, ensure_ascii=False).encode("utf-8")
                req = urllib.request.Request(
                    "http://127.0.0.1:8771/api/memory/",
                    data=data,
                    headers={"Content-Type": "application/json; charset=utf-8"},
                    method="POST",
                )
                r = urllib.request.urlopen(req, timeout=10)
                if r.status in (200, 201):
                    result = json.loads(r.read())
                    return {"memory_id": result.get("id"), "layer": result.get("layer", layer),
                            "gate_verdict": "stored"}
            except Exception as e:
                self._stats["errors"] += 1
                logger.error(f"HTTP写入失败: {e}")
                return {"memory_id": None, "layer": layer, "gate_verdict": "error"}

        try:
            result = self._engine.remember(
                content=content, layer=layer, tags=tags,
                priority=priority, metadata=metadata,
                use_llm=(priority in ("high", "critical") or len(content) > 300),
            )
            if isinstance(result, dict):
                return {"memory_id": result.get("id"), "layer": result.get("actual_layer", layer),
                        "gate_verdict": result.get("status", "stored")}
            return {"memory_id": None, "layer": layer, "gate_verdict": "unknown"}
        except Exception as e:
            self._stats["errors"] += 1
            logger.error(f"引擎写入失败: {e}")
            return {"memory_id": None, "layer": layer, "gate_verdict": "error"}

    def get_stats(self) -> Dict:
        return {
            **self._stats,
            "active_sessions": len(self._session_turns),
            "capture_mode": self._capture_mode.value,
            "engine_connected": self._engine is not None,
            "layer_router_connected": self._layer_router is not None,
        }
