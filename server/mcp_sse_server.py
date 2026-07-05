# -*- coding: utf-8-sig -*-
"""
SSE MCP Server — 基于TianjiMCPServer的SSE传输实现

MCP SSE协议规范:
  - GET /mcp/sse → 服务端SSE流，发消息给客户端
  - POST /mcp/messages → 客户端发消息给服务端
  - SSE初始事件: endpoint (告诉客户端POST消息的URL)

集成到FastAPI主服务后，托盘启动即自动运行，永远在线。
"""

import asyncio
import json
import uuid
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import StreamingResponse

TIANJI_ROOT = Path(__file__).resolve().parent.parent
import sys
if str(TIANJI_ROOT) not in sys.path:
    sys.path.insert(0, str(TIANJI_ROOT))

router = APIRouter(prefix="/mcp", tags=["MCP SSE"])

_sse_clients: Dict[str, asyncio.Queue] = {}
_mcp_server: Optional[Any] = None
_ALL_TOOLS: Optional[list] = None
_SYSTEM_NAME: str = "天机-忆库"
_SYSTEM_VERSION: str = "9.1.0"


def _ensure_mcp_imported():
    """延迟导入MCP模块，避免启动时阻塞"""
    global _ALL_TOOLS, _SYSTEM_NAME, _SYSTEM_VERSION
    if _ALL_TOOLS is None:
        from mcp.tianji_mcp_server import (
            ALL_TOOLS,
            SYSTEM_NAME,
            SYSTEM_VERSION,
        )
        _ALL_TOOLS = ALL_TOOLS
        _SYSTEM_NAME = SYSTEM_NAME
        _SYSTEM_VERSION = SYSTEM_VERSION


def get_mcp_server():
    """获取单例MCP Server（延迟初始化）"""
    global _mcp_server
    if _mcp_server is None:
        _ensure_mcp_imported()
        from mcp.tianji_mcp_server import TianjiMCPServer
        _mcp_server = TianjiMCPServer()
    return _mcp_server


async def sse_event_generator(session_id: str, request: Request):
    """SSE事件生成器"""
    queue: asyncio.Queue = asyncio.Queue()
    _sse_clients[session_id] = queue

    try:
        # 1. 发送 endpoint 事件（告诉客户端消息发送URL）
        endpoint_url = f"/api/mcp/messages?session_id={session_id}"
        yield f"event: endpoint\ndata: {endpoint_url}\n\n"

        # 2. 持续从队列取消息发往客户端
        while True:
            if await request.is_disconnected():
                break

            try:
                message = await asyncio.wait_for(queue.get(), timeout=30)
                yield f"data: {json.dumps(message, ensure_ascii=False)}\n\n"
            except asyncio.TimeoutError:
                yield ": ping\n\n"

    finally:
        _sse_clients.pop(session_id, None)


@router.get("/sse")
async def mcp_sse(request: Request):
    """MCP SSE连接端点 — 客户端通过SSE接收服务端消息"""
    session_id = str(uuid.uuid4())
    return StreamingResponse(
        sse_event_generator(session_id, request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/messages")
async def mcp_messages(request: Request, session_id: Optional[str] = None):
    """MCP消息接收端点 — 客户端通过POST发消息给服务端"""
    if not session_id:
        raise HTTPException(status_code=400, detail="session_id required")

    if session_id not in _sse_clients:
        raise HTTPException(status_code=404, detail="session not found")

    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="invalid JSON")

    server = get_mcp_server()
    response = _handle_mcp_request(server, body)

    queue = _sse_clients.get(session_id)
    if queue and response:
        await queue.put(response)

    return {"status": "ok"}


def _handle_mcp_request(server, request: dict) -> Optional[dict]:
    """处理MCP请求（复用stdio模式的核心逻辑）"""
    method = request.get("method", "")
    params = request.get("params", {})
    req_id = request.get("id")

    if method == "initialize":
        return server.handle_initialize(params, req_id)
    elif method == "notifications/initialized":
        return None
    elif method == "tools/list":
        return server.handle_tools_list(params, req_id)
    elif method == "tools/call":
        return server.handle_tools_call(params, req_id)
    elif method == "ping":
        return server._make_response({"status": "ok"}, req_id=req_id)
    else:
        return server._make_response(
            error={"code": -32601, "message": f"Method not found: {method}"},
            req_id=req_id,
        )


@router.get("/tools")
async def mcp_tools_list():
    """列出所有MCP工具（方便调试）"""
    _ensure_mcp_imported()
    return {
        "server": _SYSTEM_NAME,
        "version": _SYSTEM_VERSION,
        "transport": "sse",
        "tools_count": len(_ALL_TOOLS) if _ALL_TOOLS else 0,
        "tools": [
            {"name": t["name"], "title": t.get("title", ""), "description": t.get("description", "")}
            for t in (_ALL_TOOLS or [])
        ],
    }


@router.get("/health")
async def mcp_health():
    """MCP SSE服务健康检查"""
    server = get_mcp_server()
    return {
        "status": "ok",
        "transport": "sse",
        "tools_count": len(_ALL_TOOLS) if _ALL_TOOLS else 0,
        "connected_clients": len(_sse_clients),
        "api_available": server._api_available if server else False,
    }
