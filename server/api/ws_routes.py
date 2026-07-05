r"""
WebSocket路由 - 实时推送
=========================
支持实时连接管理、记忆变更推送、平台事件广播
"""

import asyncio
import time
from typing import Dict

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter()

active_connections: Dict[str, WebSocket] = {}
connection_platforms: Dict[str, str] = {}


@router.websocket("/connect")
async def websocket_connect(websocket: WebSocket):
    await websocket.accept()
    client_id = f"ws-{int(time.time() * 1000)}-{len(active_connections)}"
    active_connections[client_id] = websocket

    await websocket.send_json(
        {
            "type": "connected",
            "data": {"client_id": client_id, "message": "已连接到天机v9.1 元初系统"},
            "timestamp": time.time(),
        }
    )

    try:
        while True:
            data = await websocket.receive_json()
            msg_type = data.get("type", "")
            payload = data.get("data", {})

            if msg_type == "ping":
                await websocket.send_json(
                    {
                        "type": "pong",
                        "data": {"server_time": time.time()},
                        "timestamp": time.time(),
                    }
                )

            elif msg_type == "subscribe":
                platform = payload.get("platform", "generic")
                connection_platforms[client_id] = platform
                await websocket.send_json(
                    {
                        "type": "subscribed",
                        "data": {"platform": platform},
                        "timestamp": time.time(),
                    }
                )

            elif msg_type == "memory_event":
                await broadcast(
                    "memory_update",
                    {"source": client_id, **payload},
                    exclude=client_id,
                )

            else:
                await websocket.send_json(
                    {
                        "type": "echo",
                        "data": payload,
                        "timestamp": time.time(),
                    }
                )

    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        active_connections.pop(client_id, None)
        connection_platforms.pop(client_id, None)


@router.websocket("/memory/stream")
async def memory_stream(websocket: WebSocket):
    from server.deps import engine

    await websocket.accept()
    client_id = f"mem-{int(time.time() * 1000)}"
    active_connections[client_id] = websocket

    last_entry_count = engine.stats()["total_entries"]

    try:
        while True:
            await asyncio.sleep(5)
            try:
                current_stats = engine.stats()
                current_count = current_stats["total_entries"]
                if current_count != last_entry_count:
                    await websocket.send_json(
                        {
                            "type": "memory_changed",
                            "data": {
                                "total_entries": current_count,
                                "delta": current_count - last_entry_count,
                                "stats": current_stats,
                            },
                            "timestamp": time.time(),
                        }
                    )
                    last_entry_count = current_count
            except Exception:
                pass

            try:
                recv = await asyncio.wait_for(websocket.receive_text(), timeout=0.5)
                if recv == "ping":
                    await websocket.send_json(
                        {"type": "pong", "timestamp": time.time()}
                    )
            except asyncio.TimeoutError:
                pass
            except WebSocketDisconnect:
                break
            except Exception:
                break
    finally:
        active_connections.pop(client_id, None)


async def broadcast(msg_type: str, data: dict, exclude: str = None):
    dead = []
    for cid, ws in active_connections.items():
        if cid == exclude:
            continue
        try:
            await ws.send_json(
                {
                    "type": msg_type,
                    "data": data,
                    "timestamp": time.time(),
                }
            )
        except Exception:
            dead.append(cid)
    for cid in dead:
        active_connections.pop(cid, None)
        connection_platforms.pop(cid, None)
