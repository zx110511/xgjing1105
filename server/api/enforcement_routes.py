r"""
强制执行钩子 API 路由 (EnforcementHook Routes) v1.0
===================================================
提供对话自动存储、合规检查、暂停/恢复等 API 端点。

端点:
  GET  /api/enforcement/status     — 强制执行状态+统计
  GET  /api/enforcement/stats      — 详细统计
  POST /api/enforcement/pause      — 暂停记录
  POST /api/enforcement/resume     — 恢复记录
  POST /api/enforcement/flush      — 同步缓存
  POST /api/enforcement/session/start    — 开始会话
  POST /api/enforcement/session/turn     — 注册轮次
  POST /api/enforcement/session/complete — 完成会话
  GET  /api/enforcement/health     — 健康检查
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List

from server.api.utils import run_sync

router = APIRouter(tags=["强制执行钩子"])


class SessionStartRequest(BaseModel):
    session_id: str
    platform: str = "trae"
    agent_id: str = ""


class TurnRegisterRequest(BaseModel):
    session_id: str
    user_input: str
    ai_response: str
    mcp_calls: Optional[List[str]] = None


class SessionCompleteRequest(BaseModel):
    session_id: str
    force_record: bool = True


def _get_hook():
    from server.deps import get_enforcement_hook_instance
    hook = get_enforcement_hook_instance()
    if hook is None:
        raise HTTPException(status_code=503, detail="强制执行钩子未初始化")
    return hook


@router.get("/status")
async def enforcement_status():
    hook = _get_hook()
    result = await run_sync(hook.get_stats)
    return {"success": True, **result}


@router.get("/stats")
async def enforcement_stats():
    hook = _get_hook()
    result = await run_sync(hook.get_stats)
    return {"success": True, **result}


@router.post("/pause")
async def enforcement_pause():
    hook = _get_hook()
    result = await run_sync(hook.pause)
    return {"success": True, **result}


@router.post("/resume")
async def enforcement_resume():
    hook = _get_hook()
    result = await run_sync(hook.resume)
    return {"success": True, **result}


@router.post("/flush")
async def enforcement_flush():
    hook = _get_hook()
    result = await run_sync(hook.flush_pending)
    return {"success": True, "flushed": result}


@router.get("/health")
async def enforcement_health():
    hook = _get_hook()
    result = await run_sync(hook.check_health)
    return {"success": True, **result}


@router.post("/enable")
async def enforcement_enable():
    hook = _get_hook()
    await run_sync(hook.enable)
    return {"success": True, "enabled": True}


@router.post("/disable")
async def enforcement_disable():
    hook = _get_hook()
    await run_sync(hook.disable)
    return {"success": True, "enabled": False}


@router.post("/session/start")
async def session_start(request: SessionStartRequest):
    hook = _get_hook()
    result = await run_sync(hook.start_session, request.session_id, request.platform, request.agent_id)
    return {"success": True, **result}


@router.post("/session/turn")
async def session_turn(request: TurnRegisterRequest):
    hook = _get_hook()
    result = await run_sync(hook.register_turn, request.session_id,
                            request.user_input, request.ai_response, request.mcp_calls)
    return {"success": True, **result}


@router.post("/session/complete")
async def session_complete(request: SessionCompleteRequest):
    hook = _get_hook()
    result = await run_sync(hook.complete_session, request.session_id, request.force_record)
    return {"success": True, **result}
