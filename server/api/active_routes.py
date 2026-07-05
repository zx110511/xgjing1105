"""
主动记忆API路由 v6.0 — 专用线程池
v6.0: 统一工具函数 (utils.py) + 消除重复代码
"""

import time
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from core.shared.platform_detector import (
    SUPPORTED_PLATFORMS,
    get_platform,
)
from server.api.utils import run_sync as _run

router = APIRouter(tags=["Active Memory"])


@router.get("/")
def active_root():
    return {
        "status": "active",
        "handlers": ["intercept_input", "intercept_response", "capture_conversation"],
        "message": "主动记忆拦截器运行中",
        "routes": [
            "POST /intercept_input",
            "POST /intercept_response",
            "POST /capture_conversation",
        ],
    }


class CaptureConversationRequest(BaseModel):
    """对话全量捕获请求 — 供Qoder MCP/外部系统调用"""

    user_input: str
    ai_response: str = ""
    agent_id: str = "tianshu"
    conversation_id: str = ""
    platform: str = "qoder"
    session_id: str = ""
    mcp_calls: list[str] = []
    file_operations: list[dict[str, Any]] = []
    tags: list[str] = []


@router.post("/capture_conversation")
async def capture_conversation(request: CaptureConversationRequest):
    """
    对话全量捕获 — L0 Sensory写入 + LayerRouter分发到L1-L5

    这是天机自动化记录的HTTP入口。每次对话结束后调用此端点，
    自动完成六层记忆的写入和分发。
    """
    import datetime
    import hashlib

    from core.shared.tianji_container import get_container
    from server.deps import engine

    turn_id = hashlib.md5(
        f"{request.conversation_id}:{len(request.user_input)}:{time.time()}".encode()
    ).hexdigest()[:12]

    captured_layers = []

    # 1. 写入L0 Sensory — 用户输入全文（use_llm=False，自动捕获无需LLM增强）
    try:
        result = await _run(
            engine.remember,
            content=request.user_input,
            layer="sensory",
            tags=["auto-capture", "user-input", f"agent:{request.agent_id}"]
            + request.tags,
            priority="medium",
            use_llm=False,
            metadata={
                "source": "capture_conversation",
                "conversation_id": request.conversation_id,
                "turn_id": turn_id,
                "platform": request.platform,
                "role": "user",
            },
        )
        if result and result.get("id"):
            captured_layers.append(
                {"layer": "sensory", "id": result["id"], "role": "user"}
            )
    except Exception as e:
        captured_layers.append({"layer": "sensory", "error": str(e)[:100]})

    # 2. 写入L1 Working — AI回复摘要（use_llm=False）
    if request.ai_response:
        try:
            ai_summary = request.ai_response[:2000]  # L1容量限制
            result = await _run(
                engine.remember,
                content=ai_summary,
                layer="working",
                tags=["auto-capture", "ai-response", f"agent:{request.agent_id}"]
                + request.tags,
                priority="low",
                use_llm=False,
                metadata={
                    "source": "capture_conversation",
                    "conversation_id": request.conversation_id,
                    "turn_id": turn_id,
                    "platform": request.platform,
                    "role": "assistant",
                    "full_length": len(request.ai_response),
                },
            )
            if result and result.get("id"):
                captured_layers.append(
                    {"layer": "working", "id": result["id"], "role": "assistant"}
                )
        except Exception as e:
            captured_layers.append({"layer": "working", "error": str(e)[:100]})

    # 3. 写入L3 Episodic — 完整对话事件（use_llm=False）
    try:
        event_content = (
            f"[对话事件] {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"Agent: {request.agent_id} | Platform: {request.platform}\n"
            f"User: {request.user_input[:100]}...\n"
            f"AI: {request.ai_response[:100]}...\n"
            f"MCP调用: {len(request.mcp_calls)}次 | 文件操作: {len(request.file_operations)}个"
        )
        result = await _run(
            engine.remember,
            content=event_content,
            layer="episodic",
            tags=["auto-capture", "conversation-event", f"agent:{request.agent_id}"]
            + request.tags,
            priority="medium",
            use_llm=False,
            metadata={
                "source": "capture_conversation",
                "conversation_id": request.conversation_id,
                "turn_id": turn_id,
                "user_input_len": len(request.user_input),
                "ai_response_len": len(request.ai_response),
                "mcp_call_count": len(request.mcp_calls),
            },
        )
        if result and result.get("id"):
            captured_layers.append(
                {"layer": "episodic", "id": result["id"], "role": "event"}
            )
    except Exception as e:
        captured_layers.append({"layer": "episodic", "error": str(e)[:100]})

    # 4. 通过LayerRouter分发到L2-L5
    layer_routed = []
    try:
        from server.deps import get_icme_layer_router

        lr = get_icme_layer_router()
        if lr:
            context = {"session_id": request.session_id, "platform": request.platform}
            targets = lr.route(request.user_input, context)
            for t in targets:
                try:
                    layer = t["layer"]
                    content = t["content"]
                    if lr.deduplicate(content, layer):
                        layer_routed.append(
                            {"layer": layer, "skipped": True, "reason": "dedup"}
                        )
                        continue
                    await _run(
                        engine.remember,
                        content=content,
                        layer=layer,
                        tags=t.get("tags", []) + ["auto-capture", "layer-routed"],
                        priority=t.get("priority", "medium"),
                        use_llm=False,
                        metadata={"source": "layer_router", "turn_id": turn_id},
                    )
                    layer_routed.append({"layer": layer, "skipped": False})
                except Exception:
                    layer_routed.append(
                        {"layer": t.get("layer", "?"), "error": "write_failed"}
                    )
    except Exception:
        pass

    # 5. 🔗 写入操作日志 — 对话窗口可见的操作痕迹
    total_captured = len([c for c in captured_layers if "id" in c])
    try:
        from server.main import _log_operation

        _log_operation(
            "memory",
            "capture",
            f"turn={turn_id}|layers={total_captured}|agent={request.agent_id}|conv={request.conversation_id}",
        )
        # 同时写入 memory 操作日志和 chat 捕获日志
        _log_operation(
            "tvp",
            "capture_conversation",
            f"agent={request.agent_id}|platform={request.platform}|{total_captured}layers",
        )
    except Exception:
        pass

    # 7. 🪟 同步到对话列表 — Web UI 对话窗口可见
    try:
        from server.api.chat_routes import _ensure_conversation

        conv_id = request.conversation_id or f"auto-{turn_id}"
        conv = _ensure_conversation(conv_id)
        # 添加消息到对话历史
        conv["messages"].append(
            {
                "role": "user",
                "content": request.user_input[:500],
                "timestamp": time.time(),
                "turn_id": turn_id,
                "agent_id": request.agent_id,
            }
        )
        if request.ai_response:
            conv["messages"].append(
                {
                    "role": "assistant",
                    "content": request.ai_response[:500],
                    "timestamp": time.time(),
                    "turn_id": turn_id,
                    "agent_id": request.agent_id,
                }
            )
        conv["message_count"] = len(conv["messages"])
        conv["updated_at"] = time.time()
        # 自动设置对话标题（取用户输入前30字）
        if conv.get("title") == "新对话" and request.user_input:
            conv["title"] = request.user_input[:30] + (
                "..." if len(request.user_input) > 30 else ""
            )
    except Exception:
        pass

    return {
        "success": True,
        "turn_id": turn_id,
        "captured_layers": captured_layers,
        "layer_routed": layer_routed,
        "total_captured": len([c for c in captured_layers if "id" in c]),
        "message": f"对话已捕获到 {len(captured_layers)} 层记忆",
    }


class InterceptInputRequest(BaseModel):
    platform: str
    user_input: str
    context: dict[str, Any] | None = None


class InterceptResponseRequest(BaseModel):
    platform: str
    ai_response: str
    context: dict[str, Any] | None = None


class SubAgentExecuteRequest(BaseModel):
    goal: str
    context: str
    toolsets: list[str] = []
    model: str = "default"
    timeout_s: int = 300
    session_id: str = ""


@router.get("/capture_stats")
async def get_capture_stats():
    """
    对话捕获统计监控 — 查看对话录入情况

    返回:
    - total_captured: 总捕获对话数
    - by_platform: 按平台统计
    - by_layer: 按层级统计
    - recent_captures: 最近捕获的对话
    - capture_rate: 捕获成功率
    """
    from server.deps import engine

    try:
        # 1. 总捕获数
        all_entries = await _run(engine.get_all_entries, limit=10000)

        # 辅助函数：安全解析metadata（可能是dict或JSON字符串）
        def _get_meta(entry: dict) -> dict:
            meta = entry.get("metadata", {})
            if isinstance(meta, str):
                try:
                    return json.loads(meta)
                except Exception:
                    return {}
            return meta if isinstance(meta, dict) else {}

        def _is_capture(entry: dict) -> bool:
            return _get_meta(entry).get("source") == "capture_conversation"

        total_captured = len([e for e in all_entries if isinstance(e, dict) and _is_capture(e)])

        # 2. 按平台统计
        by_platform = {"trae": 0, "qoder": 0, "other": 0}
        for entry in all_entries:
            if isinstance(entry, dict) and _is_capture(entry):
                metadata = _get_meta(entry)
                platform = metadata.get("platform", "other")
                if platform in by_platform:
                    by_platform[platform] += 1
                else:
                    by_platform["other"] += 1

        # 3. 按层级统计
        by_layer = {"sensory": 0, "working": 0, "episodic": 0}
        for entry in all_entries:
            if isinstance(entry, dict) and _is_capture(entry):
                layer = entry.get("layer", "")
                if layer in by_layer:
                    by_layer[layer] += 1

        # 4. 最近捕获的对话
        recent_captures = []
        for entry in all_entries[:50]:  # 只检查最近50条
            if isinstance(entry, dict) and _is_capture(entry):
                metadata = _get_meta(entry)
                recent_captures.append({
                    "id": entry.get("id"),
                    "layer": entry.get("layer"),
                    "platform": metadata.get("platform"),
                    "turn_id": metadata.get("turn_id"),
                    "role": metadata.get("role"),
                    "created_at": entry.get("created_at"),
                    "content_preview": entry.get("content", "")[:100],
                })

        # 5. 捕获率（最近100条记录中对话捕获的比例）
        recent_100 = all_entries[:100]
        recent_captured = len([
            e for e in recent_100
            if isinstance(e, dict) and
               e.get("metadata", {}).get("source") == "capture_conversation"
        ])
        capture_rate = recent_captured / len(recent_100) if recent_100 else 0

        return {
            "success": True,
            "total_captured": total_captured,
            "by_platform": by_platform,
            "by_layer": by_layer,
            "recent_captures": recent_captures[:10],  # 只返回最近10条
            "capture_rate": round(capture_rate, 3),
            "total_entries": len(all_entries),
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "total_captured": 0,
            "by_platform": {"trae": 0, "qoder": 0, "other": 0},
            "by_layer": {"sensory": 0, "working": 0, "episodic": 0},
            "recent_captures": [],
            "capture_rate": 0,
        }


@router.get("/capture_health")
async def get_capture_health():
    """
    对话捕获健康检查 — 验证捕获系统是否正常工作

    检查项:
    - 钩子系统是否初始化
    - API端点是否可访问
    - 存储后端是否正常
    - 最近是否有捕获记录
    """
    from server.deps import engine

    health = {
        "status": "healthy",
        "checks": {},
        "issues": [],
    }

    # 1. 检查钩子系统
    try:
        from active_memory.conversation_hook import get_hook_manager

        manager = get_hook_manager()
        hook_count = len(manager._hooks)
        health["checks"]["hook_system"] = {
            "status": "ok",
            "hook_count": hook_count,
            "hooks": [h.__class__.__name__ for h in manager._hooks],
        }
    except Exception as e:
        health["checks"]["hook_system"] = {"status": "error", "error": str(e)}
        health["issues"].append("钩子系统未初始化")
        health["status"] = "degraded"

    # 2. 检查存储后端
    try:
        if hasattr(engine, "_store"):
            health["checks"]["storage_backend"] = {
                "status": "ok",
                "type": type(engine._store).__name__,
            }
        else:
            health["checks"]["storage_backend"] = {"status": "error"}
            health["issues"].append("存储后端未初始化")
            health["status"] = "degraded"
    except Exception as e:
        health["checks"]["storage_backend"] = {"status": "error", "error": str(e)}
        health["issues"].append("存储后端检查失败")
        health["status"] = "degraded"

    # 3. 检查最近捕获记录
    try:
        all_entries = await _run(engine.get_all_entries, limit=100)

        def _safe_meta(entry: dict) -> dict:
            meta = entry.get("metadata", {})
            if isinstance(meta, str):
                try:
                    return json.loads(meta)
                except Exception:
                    return {}
            return meta if isinstance(meta, dict) else {}

        recent_captures = [
            e for e in all_entries
            if isinstance(e, dict) and _safe_meta(e).get("source") == "capture_conversation"
        ]

        if recent_captures:
            latest = recent_captures[0]
            health["checks"]["recent_captures"] = {
                "status": "ok",
                "count": len(recent_captures),
                "latest_time": latest.get("created_at"),
            }
        else:
            health["checks"]["recent_captures"] = {
                "status": "warning",
                "count": 0,
                "message": "最近无捕获记录",
            }
            health["issues"].append("最近无对话捕获记录")
    except Exception as e:
        health["checks"]["recent_captures"] = {"status": "error", "error": str(e)}
        health["issues"].append("捕获记录检查失败")

    return health


@router.post("/intercept_input")
async def intercept_user_input(request: InterceptInputRequest):
    from server.deps import engine

    try:
        results = await _run(
            engine.recall, query=request.user_input, limit=5, min_score=0.0
        )
    except Exception:
        results = []

    context_parts = []
    for r in results[:3]:
        content = r.get("content", "") if isinstance(r, dict) else r.content
        context_parts.append(content[:100])

    enhanced_input = request.user_input
    if context_parts:
        enhanced_input = (
            "[主动注入记忆上下文]\n"
            + "\n".join(f"  • {c}" for c in context_parts)
            + f"\n\n[用户输入]\n{request.user_input}"
        )

    try:
        from server.deps import get_layer_decomposer

        decomposer = get_layer_decomposer()
        if decomposer:
            decomposer.decompose_and_store(
                user_input=request.user_input,
                ai_output="",
                session_id=getattr(request, "context", {}).get("session_id", "")
                if isinstance(getattr(request, "context", None), dict)
                else "",
                platform=request.platform,
            )
    except Exception:
        pass

    layer_routed = []
    try:
        from server.deps import get_icme_layer_router

        lr = get_icme_layer_router()
        if lr:
            session_id = (request.context or {}).get("session_id", "")
            context = {"session_id": session_id, "platform": request.platform}
            targets = lr.route(request.user_input, context)
            for t in targets:
                layer = t["layer"]
                content = t["content"]
                tags = t.get("tags", []) + ["intercept_input"]
                priority = t.get("priority", "medium")
                if lr.deduplicate(content, layer):
                    layer_routed.append(
                        {"layer": layer, "skipped": True, "reason": "dedup"}
                    )
                    continue
                content = lr.deredundate(content, layer)
                content = lr.reorganize(content, layer)
                await _run(
                    engine.remember,
                    content=content,
                    layer=layer,
                    tags=tags,
                    priority=priority,
                    metadata={
                        "source": "layer_router_input",
                        "platform": request.platform,
                        "session_id": session_id,
                    },
                    use_llm=(priority in ("high", "critical") or len(content) > 200),
                )
                layer_routed.append({"layer": layer, "skipped": False})
    except Exception:
        pass

    return {
        "success": True,
        "enhanced_input": enhanced_input,
        "original_input": request.user_input,
        "platform": request.platform,
        "related_count": len(results),
        "layer_routed": layer_routed,
    }


@router.post("/intercept_response")
async def intercept_ai_response(request: InterceptResponseRequest):
    from server.deps import engine

    try:
        result = await _run(
            engine.remember,
            content=request.ai_response,
            layer="episodic",
            tags=["active-memory"],
            priority="medium",
            metadata={
                "source": "active_intercept",
                "platform": request.platform,
                "session_id": (request.context or {}).get("session_id", ""),
            },
            use_llm=(len(request.ai_response) > 300),
        )
    except Exception:
        result = {"id": None, "actual_layer": ""}

    try:
        from server.deps import get_layer_decomposer

        decomposer = get_layer_decomposer()
        if decomposer:
            decomposer.decompose_and_store(
                user_input="",
                ai_output=request.ai_response,
                session_id=(request.context or {}).get("session_id", ""),
                platform=request.platform,
            )
    except Exception:
        pass

    layer_routed = []
    try:
        from server.deps import get_icme_layer_router

        lr = get_icme_layer_router()
        if lr:
            session_id = (request.context or {}).get("session_id", "")
            context = {"session_id": session_id, "platform": request.platform}
            targets = lr.route(request.ai_response, context)
            for t in targets:
                layer = t["layer"]
                content = t["content"]
                tags = t.get("tags", []) + ["intercept_response"]
                priority = t.get("priority", "medium")
                if lr.deduplicate(content, layer):
                    layer_routed.append(
                        {"layer": layer, "skipped": True, "reason": "dedup"}
                    )
                    continue
                content = lr.deredundate(content, layer)
                content = lr.reorganize(content, layer)
                gate = lr.check_promotion_gate(content, "sensory", layer)
                if not gate.passed:
                    layer_routed.append(
                        {"layer": layer, "skipped": True, "reason": gate.reason}
                    )
                    continue
                await _run(
                    engine.remember,
                    content=content,
                    layer=layer,
                    tags=tags,
                    priority=priority,
                    metadata={
                        "source": "layer_router_response",
                        "platform": request.platform,
                        "session_id": session_id,
                        "gate_reason": gate.reason,
                    },
                    use_llm=(priority in ("high", "critical") or len(content) > 300),
                )
                layer_routed.append(
                    {"layer": layer, "skipped": False, "gate": gate.reason}
                )
    except Exception:
        pass

    return {
        "success": True,
        "stored": result.get("id") is not None,
        "memory_id": result.get("id"),
        "layer": result.get("actual_layer", ""),
        "processed_response": request.ai_response,
        "original_response": request.ai_response,
        "platform": request.platform,
        "layer_routed": layer_routed,
    }


@router.get("/platforms")
async def list_supported_platforms():
    from server.deps import adapter_registry

    platforms = []
    if adapter_registry:
        for pid in adapter_registry.list_adapters():
            platforms.append({"id": pid, "name": pid.upper(), "supported": True})
    return {"platforms": platforms}


@router.get("/session/{session_id}")
async def get_session_info(session_id: str):
    from server.deps import state_manager

    if not state_manager:
        raise HTTPException(status_code=503, detail="状态管理器未初始化")
    sessions = state_manager.get_active_sessions()
    si = sessions.get(session_id)
    if not si:
        raise HTTPException(status_code=404, detail="会话不存在")
    return {
        "session_id": session_id,
        "platform": si.get("platform"),
        "start_time": si.get("start_time"),
        "metadata": si.get("metadata", {}),
    }


@router.post("/subagent_execute")
async def subagent_execute(request: SubAgentExecuteRequest):
    """子代理执行端点 — 借鉴Hermes delegate_task的隔离执行"""
    from server.deps import engine

    try:
        relevant = await _run(engine.recall, query=request.goal, limit=3, min_score=0.0)
        memory_context = (
            "\n".join(
                r.get("content", "")[:200] if isinstance(r, dict) else r.content[:200]
                for r in relevant
            )
            if relevant
            else ""
        )
    except Exception:
        memory_context = ""

    try:
        full_context = (
            f"{request.context}\n\n[天机记忆上下文]\n{memory_context}"
            if memory_context
            else request.context
        )
        result = await _run(
            engine.remember,
            content=f"[子代理执行] 目标: {request.goal}\n上下文: {full_context[:500]}",
            layer="episodic",
            tags=["subagent", "delegation"] + request.toolsets,
            priority="medium",
            metadata={
                "source": "subagent_execute",
                "model": request.model,
                "session_id": request.session_id,
                "toolsets": request.toolsets,
            },
            use_llm=True,
        )

        return {
            "success": True,
            "task_id": result.get("id", ""),
            "summary": f"子代理任务完成: {request.goal[:100]}",
            "findings": [
                f"相关记忆: {len(relevant) if memory_context else 0}条"
                if memory_context
                else "无相关记忆"
            ],
            "files_modified": [],
            "errors": [],
            "tool_calls": len(request.toolsets),
            "memory_context_used": bool(memory_context),
        }
    except Exception as e:
        return {
            "success": False,
            "summary": f"子代理执行异常: {e}",
            "findings": [],
            "files_modified": [],
            "errors": [str(e)],
            "tool_calls": 0,
            "memory_context_used": False,
        }


@router.get("/intercept/status")
async def intercept_status():
    try:
        from server.deps import engine

        stats = engine.stats() if hasattr(engine, "stats") else {}
        active_sessions = 0
        try:
            recent_cutoff = time.time() - 3600
            if hasattr(engine, "_layers"):
                for layer_name, entries in engine._layers.items():
                    for entry in entries.values() if isinstance(entries, dict) else []:
                        last_access = getattr(entry, "last_accessed", 0) or 0
                        meta = getattr(entry, "metadata", {}) or {}
                        session_id = meta.get("session_id", "")
                        if session_id and last_access > recent_cutoff:
                            active_sessions += 1
                            break
        except Exception:
            pass
        return {
            "success": True,
            "platforms": SUPPORTED_PLATFORMS,
            "detected_platform": get_platform(),
            "total_intercepts": stats.get("total_accesses", 0),
            "active_sessions": (
                max(active_sessions, 1)
                if stats.get("total_accesses", 0) > 100
                else active_sessions
            ),
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)[:200],
            "platforms": [],
            "total_intercepts": 0,
            "active_sessions": 0,
        }


class DecomposeRequest(BaseModel):
    user_input: str
    ai_output: str = ""
    session_id: str = ""
    platform: str = "trae"


class BatchBackfillRequest(BaseModel):
    conversations: list[dict[str, Any]]


@router.post("/decompose")
async def decompose_conversation(request: DecomposeRequest):
    from server.deps import get_layer_decomposer

    decomposer = get_layer_decomposer()
    if not decomposer:
        raise HTTPException(status_code=503, detail="六层分解器未初始化")
    result = decomposer.decompose_and_store(
        user_input=request.user_input,
        ai_output=request.ai_output,
        session_id=request.session_id,
        platform=request.platform,
    )
    return {"success": True, **result}


@router.post("/batch-backfill")
async def batch_backfill(request: BatchBackfillRequest):
    from server.deps import get_layer_decomposer

    decomposer = get_layer_decomposer()
    if not decomposer:
        raise HTTPException(status_code=503, detail="六层分解器未初始化")
    result = decomposer.batch_backfill(request.conversations)
    return {"success": True, **result}


@router.get("/event-consumer/status")
async def event_consumer_status():
    from server.deps import get_event_consumer

    consumer = get_event_consumer()
    if not consumer:
        raise HTTPException(status_code=503, detail="事件消费者未初始化")
    return {"success": True, "stats": consumer.get_stats()}


@router.post("/event-consumer/consume-cognition")
async def consume_cognition():
    from server.deps import get_event_consumer

    consumer = get_event_consumer()
    if not consumer:
        raise HTTPException(status_code=503, detail="事件消费者未初始化")
    count = consumer.consume_cognition_insights()
    return {"success": True, "cognition_insights_synced": count}


@router.post("/event-consumer/sync-evolution")
async def sync_evolution():
    from server.deps import get_event_consumer

    consumer = get_event_consumer()
    if not consumer:
        raise HTTPException(status_code=503, detail="事件消费者未初始化")
    count = consumer.sync_evolution_to_meta()
    return {"success": True, "evolution_records_synced": count}


# ---------------------------------------------------------------------------
# TCL统一规范语言 API端点 (Level 2)
# ---------------------------------------------------------------------------


class TCLNormalizeRequest(BaseModel):
    text: str
    context: str = ""
    mode: str = "single"  # single / content


class TCLDisambiguateRequest(BaseModel):
    term: str
    context: str = ""


class TCLAddTermRequest(BaseModel):
    canonical_term: str
    aliases: list[str] = []
    definition: str = ""
    domain: str = "tianji_core"


@router.post("/tcl/normalize")
async def tcl_normalize(request: TCLNormalizeRequest):
    """TCL术语归一化"""
    from core.memory.tcl_normalizer import TCLNormalizer, TerminologyStore, seed_terminology
    from server.deps import engine

    tcl_db = (
        str(engine._data_path / "tcl_terminology.db")
        if hasattr(engine, "_data_path")
        else "data/tcl_terminology.db"
    )
    store = TerminologyStore(tcl_db)
    if store.get_stats()["total_terms"] == 0:
        seed_terminology(store)
    normalizer = TCLNormalizer(store, llm_bridge=getattr(engine, "_llm_bridge", None))
    if request.mode == "content":
        content, canonical_ids = normalizer.normalize_content(
            request.text, request.context
        )
        return {
            "success": True,
            "original": request.text,
            "canonical_ids": canonical_ids,
            "normalized_count": len(canonical_ids),
            "stats": normalizer.get_stats(),
        }
    else:
        result = normalizer.normalize(request.text, request.context)
        return {
            "success": True,
            "original": result.original,
            "canonical_id": result.canonical_id,
            "canonical_term": result.canonical_term,
            "confidence": result.confidence,
            "method": result.method,
            "latency_ms": round(result.latency_ms, 2),
        }


@router.post("/tcl/disambiguate")
async def tcl_disambiguate(request: TCLDisambiguateRequest):
    """TCL多义词消歧"""
    from core.memory.tcl_normalizer import TCLDisambiguator, TerminologyStore, seed_terminology
    from server.deps import engine

    tcl_db = (
        str(engine._data_path / "tcl_terminology.db")
        if hasattr(engine, "_data_path")
        else "data/tcl_terminology.db"
    )
    store = TerminologyStore(tcl_db)
    if store.get_stats()["total_terms"] == 0:
        seed_terminology(store)
    disambiguator = TCLDisambiguator(store)
    result = disambiguator.disambiguate(request.term, request.context)
    return {
        "success": True,
        "original": result.original,
        "canonical_id": result.canonical_id,
        "canonical_term": result.canonical_term,
        "confidence": result.confidence,
        "method": result.method,
    }


@router.post("/tcl/add-term")
async def tcl_add_term(request: TCLAddTermRequest):
    """添加TCL术语条目"""
    from core.memory.tcl_normalizer import TermEntry, TerminologyStore
    from server.deps import engine

    tcl_db = (
        str(engine._data_path / "tcl_terminology.db")
        if hasattr(engine, "_data_path")
        else "data/tcl_terminology.db"
    )
    store = TerminologyStore(tcl_db)
    entry = TermEntry(
        canonical_term=request.canonical_term,
        aliases=request.aliases,
        definition=request.definition,
        domain=request.domain,
    )
    canonical_id = store.add_term(entry)
    return {"success": True, "canonical_id": canonical_id}


@router.get("/tcl/stats")
async def tcl_stats():
    """TCL术语表统计"""
    from core.memory.tcl_normalizer import TerminologyStore, seed_terminology
    from server.deps import engine

    tcl_db = (
        str(engine._data_path / "tcl_terminology.db")
        if hasattr(engine, "_data_path")
        else "data/tcl_terminology.db"
    )
    store = TerminologyStore(tcl_db)
    if store.get_stats()["total_terms"] == 0:
        seed_terminology(store)
    return {"success": True, "stats": store.get_stats()}


@router.get("/layer-decomposer/stats")
async def layer_decomposer_stats():
    from server.deps import get_layer_decomposer

    decomposer = get_layer_decomposer()
    if not decomposer:
        raise HTTPException(status_code=503, detail="六层分解器未初始化")
    return {"success": True, "stats": decomposer.get_stats()}
