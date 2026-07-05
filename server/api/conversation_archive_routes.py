# -*- coding: utf-8-sig -*-
"""
conversation_archive_routes.py — 对话归档HTTP端点 v1.0
=====================================================

提供REST API端点供Agent/Trae IDE调用，实现完整对话归档。

端点:
  POST /api/conversation/archive    - 归档单轮对话(4要素)
  POST /api/conversation/session    - 归档整个会话(多轮)
  GET  /api/conversation/recent     - 查看最近归档
  GET  /api/conversation/stats      - 归档器统计
  POST /api/conversation/sync_offline - 同步离线队列

集成路径:
  - 启动器: launcher/tianji_v91_launcher.py 启动时验证
  - 桌面快捷方式: start_tianji.bat → launcher → server → archiver
  - Agent调用: 对话结束时自动调用 POST /api/conversation/archive
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from core.memory.conversation_archiver import (
    ConversationArchive,
    Decision,
    FileChange,
    get_archiver,
)

logger = logging.getLogger("tianji.conversation_archive_routes")

router = APIRouter(tags=["conversation-archive"])


# ── Pydantic 模型 ──


class DecisionModel(BaseModel):
    step: str = Field(..., description="决策步骤")
    agent: str = Field(..., description="决策Agent")
    decision: str = Field(..., description="决策内容")
    reason: str = Field("", description="决策原因")
    evidence: str = Field("", description="证据/数据")


class FileChangeModel(BaseModel):
    file_path: str = Field(..., description="文件路径")
    change_type: str = Field(..., description="变更类型: create/modify/delete")
    summary: str = Field("", description="变更摘要")
    lines_added: int = Field(0, description="新增行数")
    lines_removed: int = Field(0, description="删除行数")
    diff_preview: str = Field("", description="变更预览")


class ArchiveRequest(BaseModel):
    """完整对话归档请求(4要素)"""

    session_id: str = Field(..., description="会话ID")
    turn_number: int = Field(1, description="轮次号")
    user_message: str = Field(..., description="要素1: 完整用户消息(全文)")
    agent_response: str = Field(..., description="要素2: Agent完整回复(全文)")
    decisions: list[DecisionModel] = Field(
        default_factory=list, description="要素3: 关键决策过程"
    )
    file_changes: list[FileChangeModel] = Field(
        default_factory=list, description="要素4: 所有文件变更"
    )
    agent_id: str = Field("tianji", description="Agent ID")
    complexity: str = Field("standard", description="复杂度: trivial/standard/critical")
    mcp_tools_used: list[str] = Field(default_factory=list, description="使用的MCP工具")
    tvp_declarations: list[str] = Field(default_factory=list, description="TVP声明列表")


class ArchiveResponse(BaseModel):
    l3_id: str | None = None
    l4_ids: list[str] = []
    l5_id: str | None = None
    offline_queued: int = 0
    content_hash: str = ""
    total_bytes: int = 0


class SessionArchiveRequest(BaseModel):
    """整个会话归档请求"""

    session_id: str
    turns: list[ArchiveRequest]
    agent_id: str = "tianji"


class SessionArchiveResponse(BaseModel):
    session_id: str
    total_turns: int
    archived_turns: int
    results: list[ArchiveResponse] = []
    offline_queued: int = 0


# ── 端点实现 ──


@router.post("/archive", response_model=ArchiveResponse)
async def archive_conversation(req: ArchiveRequest) -> ArchiveResponse:
    """归档单轮对话(4要素完整记录)

    集成入口:
    - Agent对话结束时调用此端点
    - 启动器自动调用(如配置)
    - Trae IDE hook调用(如支持)
    """
    try:
        # 转换为内部数据结构
        decisions = [
            Decision(
                step=d.step,
                agent=d.agent,
                decision=d.decision,
                reason=d.reason,
                evidence=d.evidence,
            )
            for d in req.decisions
        ]
        file_changes = [
            FileChange(
                file_path=fc.file_path,
                change_type=fc.change_type,
                summary=fc.summary,
                lines_added=fc.lines_added,
                lines_removed=fc.lines_removed,
                diff_preview=fc.diff_preview,
            )
            for fc in req.file_changes
        ]

        conv = ConversationArchive(
            session_id=req.session_id,
            turn_number=req.turn_number,
            user_message=req.user_message,
            agent_response=req.agent_response,
            decisions=decisions,
            file_changes=file_changes,
            agent_id=req.agent_id,
            complexity=req.complexity,
            mcp_tools_used=req.mcp_tools_used,
            tvp_declarations=req.tvp_declarations,
        )

        archiver = get_archiver()
        result = archiver.archive(conv)

        return ArchiveResponse(
            l3_id=result["l3_id"],
            l4_ids=result["l4_ids"],
            l5_id=result["l5_id"],
            offline_queued=result["offline_queued"],
            content_hash=conv.content_hash,
            total_bytes=conv.total_bytes,
        )
    except Exception as e:
        logger.error(f"归档失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"归档失败: {e}")


@router.post("/session", response_model=SessionArchiveResponse)
async def archive_session(req: SessionArchiveRequest) -> SessionArchiveResponse:
    """归档整个会话(多轮)"""
    try:
        archiver = get_archiver()
        results = []
        total_offline = 0

        for turn in req.turns:
            decisions = [
                Decision(
                    step=d.step,
                    agent=d.agent,
                    decision=d.decision,
                    reason=d.reason,
                    evidence=d.evidence,
                )
                for d in turn.decisions
            ]
            file_changes = [
                FileChange(
                    file_path=fc.file_path,
                    change_type=fc.change_type,
                    summary=fc.summary,
                    lines_added=fc.lines_added,
                    lines_removed=fc.lines_removed,
                    diff_preview=fc.diff_preview,
                )
                for fc in turn.file_changes
            ]

            conv = ConversationArchive(
                session_id=turn.session_id,
                turn_number=turn.turn_number,
                user_message=turn.user_message,
                agent_response=turn.agent_response,
                decisions=decisions,
                file_changes=file_changes,
                agent_id=turn.agent_id,
                complexity=turn.complexity,
                mcp_tools_used=turn.mcp_tools_used,
                tvp_declarations=turn.tvp_declarations,
            )

            result = archiver.archive(conv)
            results.append(
                ArchiveResponse(
                    l3_id=result["l3_id"],
                    l4_ids=result["l4_ids"],
                    l5_id=result["l5_id"],
                    offline_queued=result["offline_queued"],
                    content_hash=conv.content_hash,
                    total_bytes=conv.total_bytes,
                )
            )
            total_offline += result["offline_queued"]

        return SessionArchiveResponse(
            session_id=req.session_id,
            total_turns=len(req.turns),
            archived_turns=len(results),
            results=results,
            offline_queued=total_offline,
        )
    except Exception as e:
        logger.error(f"会话归档失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"会话归档失败: {e}")


@router.get("/stats")
async def get_stats() -> dict:
    """获取归档器统计"""
    archiver = get_archiver()
    stats = archiver.get_stats()

    # 检查离线队列
    offline_count = 0
    offline_path = Path(".tianji/offline_writes.json")
    if offline_path.exists():
        try:
            queue = json.loads(offline_path.read_text(encoding="utf-8"))
            offline_count = len(queue)
        except Exception:
            offline_count = 0

    return {
        "archiver_stats": stats,
        "offline_queue_size": offline_count,
        "api_url": archiver.api_url,
        "timestamp": time.time(),
    }


@router.get("/recent")
async def get_recent_archives(limit: int = 10) -> dict:
    """查看最近归档(通过memory_recall检索)"""
    try:
        import urllib.request
        from urllib.parse import quote

        query = quote("完整对话归档 L3")
        url = f"http://127.0.0.1:8771/api/platform/recall?query={query}&limit={limit}"
        req = urllib.request.Request(url)
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        r = opener.open(req, timeout=15)
        data = json.loads(r.read().decode("utf-8", errors="replace"))
        return {
            "count": len(data) if isinstance(data, list) else 0,
            "archives": data if isinstance(data, list) else [],
        }
    except Exception as e:
        return {"error": str(e), "count": 0, "archives": []}


@router.post("/sync_offline")
async def sync_offline_queue() -> dict:
    """同步离线队列到天机ICME"""
    offline_path = Path(".tianji/offline_writes.json")
    if not offline_path.exists():
        return {"synced": 0, "remaining": 0, "message": "无离线队列"}

    try:
        queue = json.loads(offline_path.read_text(encoding="utf-8"))
        if not queue:
            return {"synced": 0, "remaining": 0, "message": "离线队列为空"}

        import urllib.request

        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        synced = 0
        failed = 0

        for item in queue:
            try:
                data = json.dumps(item, ensure_ascii=False).encode("utf-8")
                req = urllib.request.Request(
                    "http://127.0.0.1:8771/api/memory/",
                    data=data,
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                r = opener.open(req, timeout=30)
                resp = json.loads(r.read().decode("utf-8", errors="replace"))
                if resp.get("id"):
                    synced += 1
                else:
                    failed += 1
            except Exception:
                failed += 1

        # 清空已同步的离线队列
        if failed == 0:
            offline_path.write_text("[]", encoding="utf-8")
        else:
            # 保留失败的项
            remaining = queue[synced:]
            offline_path.write_text(
                json.dumps(remaining, ensure_ascii=False, indent=2), encoding="utf-8"
            )

        return {
            "synced": synced,
            "failed": failed,
            "remaining": failed,
            "message": f"同步完成: {synced}成功, {failed}失败",
        }
    except Exception as e:
        return {"error": str(e), "synced": 0, "remaining": -1}


@router.get("/health")
async def archiver_health() -> dict:
    """归档器健康检查"""
    try:
        archiver = get_archiver()
        stats = archiver.get_stats()
        return {
            "status": "healthy",
            "archiver_initialized": archiver is not None,
            "total_archives": stats["total_archives"],
            "api_url": archiver.api_url,
            "timestamp": time.time(),
        }
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}
