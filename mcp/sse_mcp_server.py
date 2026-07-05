# -*- coding: utf-8-sig -*-
"""
独立SSE MCP Server — 常驻进程，托盘守护

端口: 8772 (与主服务8771分开)
SSE端点: http://127.0.0.1:8772/sse
消息端点: http://127.0.0.1:8772/messages

由托盘启动器启动并守护，挂了自动重启。
Trae的MCP客户端配置为SSE模式，直接连这个端口即可，
不需要Trae自己启动MCP进程。
"""

import asyncio
import json
import os
import sys
import uuid
from pathlib import Path
from typing import Any, Dict, Optional

TIANJI_ROOT = Path(__file__).resolve().parent.parent
if str(TIANJI_ROOT) not in sys.path:
    sys.path.insert(0, str(TIANJI_ROOT))
if str(TIANJI_ROOT / "mcp") not in sys.path:
    sys.path.insert(0, str(TIANJI_ROOT / "mcp"))

from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
import uvicorn

MCP_PORT = int(os.environ.get("TIANJI_MCP_PORT", "8772"))
TIANJI_API_URL = os.environ.get("TIANJI_API_URL", "http://127.0.0.1:8771")

app = FastAPI(title="天机v9.1 SSE MCP Server", version="9.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_sse_clients: Dict[str, asyncio.Queue] = {}
_mcp_server: Optional[Any] = None


def _get_mcp_server():
    """延迟初始化MCP Server"""
    global _mcp_server
    if _mcp_server is None:
        from mcp.tianji_mcp_server import TianjiMCPServer
        _mcp_server = TianjiMCPServer()
    return _mcp_server


async def sse_event_generator(session_id: str, request: Request):
    """SSE事件生成器"""
    queue: asyncio.Queue = asyncio.Queue()
    _sse_clients[session_id] = queue

    try:
        endpoint_url = f"/messages?session_id={session_id}"
        yield f"event: endpoint\ndata: {endpoint_url}\n\n"

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


@app.get("/sse")
async def mcp_sse(request: Request):
    """MCP SSE连接端点"""
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


@app.post("/messages")
async def mcp_messages(request: Request, session_id: Optional[str] = None):
    """MCP消息接收端点"""
    if not session_id:
        raise HTTPException(status_code=400, detail="session_id required")
    if session_id not in _sse_clients:
        raise HTTPException(status_code=404, detail="session not found")

    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="invalid JSON")

    server = _get_mcp_server()
    response = _handle_mcp_request(server, body)

    queue = _sse_clients.get(session_id)
    if queue and response:
        await queue.put(response)

    return {"status": "ok"}


def _handle_mcp_request(server, request: dict) -> Optional[dict]:
    """处理MCP请求"""
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


@app.get("/health")
async def health():
    """健康检查"""
    from mcp.tianji_mcp_server import ALL_TOOLS
    return {
        "status": "ok",
        "transport": "sse",
        "port": MCP_PORT,
        "tools_count": len(ALL_TOOLS),
        "connected_clients": len(_sse_clients),
        "tianji_api": TIANJI_API_URL,
    }


@app.get("/tools")
async def tools_list():
    """工具列表（调试用）"""
    from mcp.tianji_mcp_server import ALL_TOOLS, SYSTEM_NAME, SYSTEM_VERSION
    return {
        "server": SYSTEM_NAME,
        "version": SYSTEM_VERSION,
        "transport": "sse",
        "tools_count": len(ALL_TOOLS),
        "tools": [
            {"name": t["name"], "title": t.get("title", ""), "description": t.get("description", "")}
            for t in ALL_TOOLS
        ],
    }


def main():
    """启动SSE MCP Server"""
    print(f"[SSE-MCP] Starting on port {MCP_PORT}...", file=sys.stderr, flush=True)
    print(f"[SSE-MCP] Tianji API: {TIANJI_API_URL}", file=sys.stderr, flush=True)
    uvicorn.run(
        app,
        host="127.0.0.1",
        port=MCP_PORT,
        log_level="warning",
    )


if __name__ == "__main__":
    if sys.platform == "win32":
        try:
            sys.stdin = open("nul", "r", encoding="utf-8")
            sys.stdout = open("nul", "w", encoding="utf-8")
        except Exception:
            pass
    main()
