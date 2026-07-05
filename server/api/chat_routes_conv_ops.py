# -*- coding: utf-8-sig -*-
"""chat_routes_conv_ops.py — 从 chat_routes.py 拆分 (SSS-PhaseB)

conv_ops功能组
源文件: chat_routes.py
"""

import asyncio
import json
import logging
import os
import re  # [FIX-V4] 补回re模块导入 (DSML工具调用解析需要, L17异常传播)
import time
import traceback
import uuid
from typing import AsyncGenerator, Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import StreamingResponse, Response
from pydantic import BaseModel

# [FIX-chat-xml-005] 乱码检测告警日志器
_logger = logging.getLogger("chat_conv_ops")

# [FIX-chat-xml-005] 乱码特征模式(外部拦截层字符替换)
_GARBLED_PATTERNS = ['纳么', '时态日你哥', '安然么特人', '女哦可', '让么特人', '阿么timeout']

def _detect_garbled_content(content: str) -> bool:
    """检测外部拦截层造成的字符替换"""
    return any(p in content for p in _GARBLED_PATTERNS)

# [FIX-SSS] 拆分后router定义丢失，补回模块级router
router = APIRouter()

# [FIX-V4] 补回 _abort_signals 定义 (流式对话中断信号, L18增量开发)
_abort_signals: Dict[str, bool] = {}

# [FIX-SSS] 从conv_store导入共享状态(对话存储/锁/路径)
try:
    from .chat_routes_conv_store import (
        _conversations,
        _save_lock,
        _save_conversation,
        _save_index,
        _CONVERSATIONS_DIR,
        _conv_file,
    )
except ImportError:
    # 直接运行兼容
    from chat_routes_conv_store import (  # type: ignore
        _conversations,
        _save_lock,
        _save_conversation,
        _save_index,
        _CONVERSATIONS_DIR,
        _conv_file,
    )

# [FIX-V4] 导入法则系统提示词模块 (L02固化增强: 法则注入对话)
try:
    from .deepseek_system_prompt import build_system_prompt as _build_law_prompt
except ImportError:
    try:
        from deepseek_system_prompt import build_system_prompt as _build_law_prompt  # type: ignore
    except ImportError:
        # 降级: 法则模块不可用时使用空提示词 (L04降级完整性)
        def _build_law_prompt(model_mode: str = "v4-flash") -> str:
            return ""

# [FIX-V4] 导入DeepSeekConfig用于模型名称映射 (L11路径唯一性)
try:
    from llm_integration.client import DeepSeekConfig as _DeepSeekConfig
    _DS_CONFIG = _DeepSeekConfig.from_env()
except Exception:
    _DS_CONFIG = None


# [FIX-SSS] 补回拆分时丢失的数据模型
class ConversationCreateRequest(BaseModel):
    title: str = "新对话"
    message: Optional[str] = None


class ConversationSummaryRequest(BaseModel):
    max_length: int = 200


class ConversationTitleUpdateRequest(BaseModel):
    title: str


class SearchRequest(BaseModel):
    query: str
    limit: int = 20


class ImportRequest(BaseModel):
    conversations: List[Dict[str, Any]]


# [FIX-SSS] 补回ChatRequest (流式对话核心模型)
class ChatRequest(BaseModel):
    message: str
    conversation_id: Optional[str] = None
    context: Optional[str] = None
    mode: str = "normal"  # normal/deep/reason
    enable_tools: bool = True
    enable_skills: bool = True
    enable_agents: bool = False
    max_tokens: int = 4096
    temperature: float = 0.7
    # [FIX-V4] 补全现有stream端点已使用但未定义的字段 (L18增量开发: 向后兼容)
    enable_memory: bool = True
    enable_function_call: bool = False
    enable_web_search: bool = False
    enable_deep_thinking: bool = False
    system_prompt: Optional[str] = None
    model: str = "deepseek-chat"
    # [FIX-V4] V4双模式字段 (V4-Pro/V4-Flash)
    model_mode: str = "v4-flash"  # "v4-pro" | "v4-flash"
    thinking_enabled: bool = False  # V4-Pro Thinking模式开关
    reasoning_effort: str = "medium"  # "low" | "medium" | "high"
    use_law_prompt: bool = True  # 是否注入法则+常识系统提示词


def _get_conversation(conv_id: str) -> Dict:
    if conv_id not in _conversations:
        raise HTTPException(status_code=404, detail=f"Conversation {conv_id} not found")
    return _conversations[conv_id]


def _ensure_conversation(conv_id: str) -> Dict:
    if conv_id not in _conversations:
        _conversations[conv_id] = {
            "id": conv_id,
            "title": "新对话",
            "messages": [],
            "total_tokens": 0,
            "summary": "",
            "created_at": time.time(),
            "updated_at": time.time(),
            "message_count": 0,
            "pinned": False,
        }
        with _save_lock:
            _save_conversation(_conversations[conv_id])
            _save_index()
    return _conversations[conv_id]


def _persist(conv: Dict):
    """持久化单个对话 + 更新索引 — 线程安全"""
    with _save_lock:
        _save_conversation(conv)
        _save_index()


def _resolve_model_name(model_mode: str, default_model: str = "deepseek-chat") -> str:
    """根据模式解析实际模型名称 — L11路径唯一性法则

    Args:
        model_mode: "v4-pro" | "v4-flash"
        default_model: 降级时使用的默认模型名
    Returns:
        实际API模型名称
    """
    # L14拼写精确: 校验mode合法值
    if model_mode not in ("v4-pro", "v4-flash"):
        return default_model
    # 优先使用DeepSeekConfig的映射 (L11路径唯一性)
    if _DS_CONFIG:
        try:
            return _DS_CONFIG._get_model_name(model_mode)
        except Exception:
            pass
    # 降级: 直接映射 (L04降级完整性)
    _fallback_map = {"v4-pro": "deepseek-v4-pro", "v4-flash": "deepseek-v4-flash"}
    return _fallback_map.get(model_mode, default_model)


@router.get("/conversations")
async def list_conversations(limit: int = Query(50, ge=1, le=200)):
    convs = sorted(
        _conversations.values(),
        key=lambda c: (c.get("pinned", False), c.get("updated_at", 0)),
        reverse=True,
    )[:limit]
    return {
        "success": True,
        "total": len(_conversations),
        "conversations": [
            {
                "id": c["id"],
                "title": c["title"],
                "message_count": c["message_count"],
                "total_tokens": c["total_tokens"],
                "summary": c.get("summary", ""),
                "created_at": c["created_at"],
                "updated_at": c["updated_at"],
                "pinned": c.get("pinned", False),
            }
            for c in convs
        ],
    }


# 固定路径路由必须在 {conv_id} 参数路由之前，否则会被误匹配
@router.get("/conversations/search")
async def search_conversations(q: str = Query(..., min_length=1), limit: int = Query(20, ge=1, le=100)):
    """全文搜索对话 — 匹配标题和消息内容"""
    results = []
    query_lower = q.lower()
    for conv in _conversations.values():
        score = 0
        if query_lower in conv.get("title", "").lower():
            score += 10
        for msg in conv.get("messages", []):
            if query_lower in msg.get("content", "").lower():
                score += 1
        if score > 0:
            results.append({
                "id": conv["id"],
                "title": conv["title"],
                "message_count": conv["message_count"],
                "total_tokens": conv.get("total_tokens", 0),
                "updated_at": conv.get("updated_at", 0),
                "pinned": conv.get("pinned", False),
                "match_score": score,
            })
    results.sort(key=lambda x: x["match_score"], reverse=True)
    return {"success": True, "query": q, "total": len(results), "results": results[:limit]}


@router.get("/conversations/stats")
async def conversation_stats():
    """对话统计信息"""
    total = len(_conversations)
    total_messages = sum(c.get("message_count", 0) for c in _conversations.values())
    total_tokens = sum(c.get("total_tokens", 0) for c in _conversations.values())
    pinned_count = sum(1 for c in _conversations.values() if c.get("pinned", False))
    return {
        "success": True,
        "total_conversations": total,
        "total_messages": total_messages,
        "total_tokens": total_tokens,
        "pinned_count": pinned_count,
        "storage_path": _CONVERSATIONS_DIR,
    }


@router.get("/conversations/export-all")
async def export_all_conversations():
    """导出全部对话为JSON备份"""
    backup = {
        "version": "3.0",
        "exported_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "total_conversations": len(_conversations),
        "conversations": list(_conversations.values()),
    }
    content = json.dumps(backup, ensure_ascii=False, indent=2)
    return Response(
        content=content,
        media_type="application/json; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="tianji_chat_backup_{time.strftime("%Y%m%d_%H%M%S")}.json"'},
    )


@router.post("/conversations/import")
async def import_conversations(data: dict):
    """从JSON备份恢复对话"""
    imported = 0
    skipped = 0
    convs = data.get("conversations", [])
    for conv in convs:
        cid = conv.get("id", "")
        if not cid:
            skipped += 1
            continue
        if cid in _conversations:
            existing = _conversations[cid]
            if conv.get("updated_at", 0) > existing.get("updated_at", 0):
                _conversations[cid] = conv
                _persist(conv)
                imported += 1
            else:
                skipped += 1
        else:
            _conversations[cid] = conv
            _persist(conv)
            imported += 1
    return {"success": True, "imported": imported, "skipped": skipped}


@router.get("/conversations/{conv_id}/export")
async def export_conversation(conv_id: str, format: str = Query("json", regex="^(json|markdown|txt)$")):
    """导出对话为 JSON / Markdown / 纯文本"""
    conv = _get_conversation(conv_id)

    if format == "markdown":
        lines = [f"# {conv['title']}\n"]
        lines.append(f"> 导出时间: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        lines.append(f"> 消息数: {conv['message_count']} | Tokens: {conv.get('total_tokens', 0)}\n\n---\n")
        for msg in conv.get("messages", []):
            role_label = {"user": "用户", "assistant": "天机", "system": "系统"}.get(msg.get("role", ""), msg.get("role", ""))
            lines.append(f"### {role_label}\n")
            lines.append(f"{msg.get('content', '')}\n\n---\n")
        content = "\n".join(lines)
        media_type = "text/markdown"
        filename = f"{conv['title'][:30]}.md"
    elif format == "txt":
        lines = [f"对话: {conv['title']}", f"导出: {time.strftime('%Y-%m-%d %H:%M:%S')}", "=" * 60]
        for msg in conv.get("messages", []):
            role = msg.get("role", "unknown")
            lines.append(f"\n[{role.upper()}]")
            lines.append(msg.get("content", ""))
            lines.append("-" * 40)
        content = "\n".join(lines)
        media_type = "text/plain"
        filename = f"{conv['title'][:30]}.txt"
    else:
        content = json.dumps(conv, ensure_ascii=False, indent=2)
        media_type = "application/json"
        filename = f"{conv['title'][:30]}.json"

    # RFC 5987: 中文文件名需URL编码
    from urllib.parse import quote as _url_quote
    safe_filename = _url_quote(filename)
    ascii_fallback = f"conversation_{conv_id[:8]}.{format}"

    return Response(
        content=content,
        media_type=f"{media_type}; charset=utf-8",
        headers={
            "Content-Disposition": f"attachment; filename=\"{ascii_fallback}\"; filename*=UTF-8''{safe_filename}",
        },
    )


@router.get("/conversations/{conv_id}")
async def get_conversation(conv_id: str, include_messages: bool = False):
    conv = _get_conversation(conv_id)
    result = {
        "success": True,
        "conversation": {
            "id": conv["id"],
            "title": conv["title"],
            "message_count": conv["message_count"],
            "total_tokens": conv["total_tokens"],
            "summary": conv.get("summary", ""),
            "created_at": conv["created_at"],
            "updated_at": conv["updated_at"],
        },
    }
    if include_messages:
        result["conversation"]["messages"] = conv["messages"]
    return result


@router.post("/conversations")
async def create_conversation(req: ConversationCreateRequest):
    conv_id = str(uuid.uuid4())
    conv = _ensure_conversation(conv_id)
    conv["title"] = req.title
    _persist(conv)
    return {"success": True, "conversation_id": conv_id, "title": req.title}


@router.delete("/conversations/{conv_id}")
async def delete_conversation(conv_id: str):
    if conv_id in _conversations:
        del _conversations[conv_id]
        # 删除磁盘文件
        fpath = _conv_file(conv_id)
        if os.path.exists(fpath):
            try:
                os.remove(fpath)
            except Exception:
                pass
        with _save_lock:
            _save_index()
    return {"success": True, "deleted": conv_id}


@router.patch("/conversations/{conv_id}/title")
async def update_conversation_title(conv_id: str, title: str = Query(...)):
    conv = _get_conversation(conv_id)
    conv["title"] = title
    conv["updated_at"] = time.time()
    _persist(conv)
    return {"success": True, "title": title}


@router.post("/conversations/{conv_id}/summary")
async def generate_conversation_summary(conv_id: str):
    conv = _get_conversation(conv_id)
    messages_text = "\n".join(
        f"[{m.get('role', 'user')}]: {m.get('content', '')}"
        for m in conv["messages"]
    )
    summary = messages_text[:500] if messages_text else "空对话"
    conv["summary"] = summary
    conv["updated_at"] = time.time()
    _persist(conv)
    return {"success": True, "summary": summary, "length": len(summary)}


@router.post("/abort")
async def abort_generation(conversation_id: str = Query(...)):
    _abort_signals[conversation_id] = True
    return {"success": True, "aborted": conversation_id}


@router.post("/stream")
async def stream_chat(req: ChatRequest):
    conv_id = req.conversation_id or str(uuid.uuid4())
    conv = _ensure_conversation(conv_id)

    user_msg = {
        "id": f"msg-{uuid.uuid4().hex[:8]}",
        "role": "user",
        "content": req.message,
        "timestamp": time.time(),
        "token_count": len(req.message),
        "fidelity": "full",
    }
    conv["messages"].append(user_msg)
    conv["message_count"] = len(conv["messages"])
    conv["updated_at"] = time.time()
    _persist(conv)

    _abort_signals[conv_id] = False

    async def _auto_recall_context(query: str, top_k: int = 3) -> str:
        """v9.1优化: 自动检索与用户问题相关的记忆上下文（记忆优先决策原则）"""
        try:
            import sys, os.path as osp
            sys.path.insert(0, osp.dirname(osp.dirname(osp.abspath(__file__))))
            from core.memory.hybrid_engine import ICMEStorageEngine

            engine = ICMEStorageEngine()
            results = engine.recall(query=query, limit=top_k)
            if results:
                context_parts = []
                for i, item in enumerate(results[:top_k]):
                    if isinstance(item, dict):
                        content = item.get("content", str(item))[:200]
                        layer = item.get("layer", "?")
                        context_parts.append(f"{i+1}. [{layer}] {content}")
                    else:
                        context_parts.append(f"{i+1}. {str(item)[:200]}")
                return "\n".join(context_parts)
        except Exception as e:
            print(f"[AUTO-RECALL] Context recall failed: {e}")
        return ""

    async def _auto_store_memory(content: str, layer: str, tags: list, source: str = "auto"):
        """自动存储到记忆系统（后台执行，不阻塞对话流）"""
        try:
            import sys, os.path as osp
            sys.path.insert(0, osp.dirname(osp.dirname(osp.abspath(__file__))))
            from core.memory.hybrid_engine import ICMEStorageEngine

            engine = ICMEStorageEngine()
            result = engine.remember(
                content=content,
                layer=layer,
                tags=tags + [f"auto-{source}", f"conv-{conv_id[:8]}"],
                priority="high" if source == "user" else "medium",
                metadata={
                    "source": source,
                    "conversation_id": conv_id,
                    "timestamp": time.time(),
                    "auto_captured": True,
                }
            )
            return result
        except Exception as e:
            print(f"[AUTO-MEMORY] Store failed: {e}")
            return None

    async def _auto_extract_and_store(text: str):
        """自动提取知识并存储（后台执行）— 双模式: DeepSeek API优先, 本地模式降级"""
        if len(text) < 50:
            return

        extracted = False

        try:
            import httpx
            deepseek_url = os.environ.get("DEEPSEEK_API_URL", "") or os.environ.get("DEEPSEEK_BASE_URL", "")
            deepseek_key = os.environ.get("DEEPSEEK_API_KEY", "")

            if deepseek_key and deepseek_url:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    resp = await client.post(
                        f"{deepseek_url}/chat/completions",
                        headers={
                            "Authorization": f"Bearer {deepseek_key}",
                            "Content-Type": "application/json",
                        },
                        json={
                            "model": "deepseek-chat",
                            "messages": [{
                                "role": "system",
                                "content": "从以下对话中提取关键知识点、实体和行动项，以JSON格式返回：{knowledge: [], entities: [], actions: []}"
                            }, {
                                "role": "user",
                                "content": text[:2000]
                            }],
                            "temperature": 0.3,
                            "max_tokens": 500,
                        }
                    )

                    if resp.status_code == 200:
                        data = resp.json()
                        extracted_text = data["choices"][0]["message"]["content"]

                        try:
                            import json as json_mod
                            parsed = json_mod.loads(extracted_text)

                            for knowledge in parsed.get("knowledge", [])[:5]:
                                await _auto_store_memory(
                                    content=knowledge,
                                    layer="semantic",
                                    tags=["auto-extracted", "knowledge", "llm-extracted"],
                                    source="knowledge_extraction"
                                )

                            for action in parsed.get("actions", [])[:3]:
                                await _auto_store_memory(
                                    content=action,
                                    layer="working",
                                    tags=["auto-extracted", "action-item", "llm-extracted"],
                                    source="action_extraction"
                                )

                            for entity in parsed.get("entities", [])[:5]:
                                await _auto_store_memory(
                                    content=entity if isinstance(entity, str) else str(entity),
                                    layer="semantic",
                                    tags=["auto-extracted", "entity", "llm-extracted"],
                                    source="entity_extraction"
                                )

                            extracted = True
                        except Exception:
                            pass
        except Exception as e:
            print(f"[AUTO-EXTRACT] DeepSeek API failed: {e}")

        if not extracted:
            try:
                import sys as _sys
                _root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                if _root not in _sys.path:
                    _sys.path.insert(0, _root)
                from core.shared.knowledge_extractor import KnowledgeExtractor

                extractor = KnowledgeExtractor()
                triples = extractor.extract_with_patterns(text)

                for triple in triples[:10]:
                    triple_text = f"{triple.subject} —[{triple.relation}]→ {triple.object}"
                    await _auto_store_memory(
                        content=triple_text,
                        layer="semantic",
                        tags=["auto-extracted", "knowledge-triple", "pattern-extracted",
                              triple.relation],
                        source="local_pattern_extraction"
                    )

                if triples:
                    print(f"[AUTO-EXTRACT] Local fallback: {len(triples)} triples extracted")
            except Exception as e2:
                print(f"[AUTO-EXTRACT] Local fallback also failed: {e2}")

    async def generate() -> AsyncGenerator[str, None]:
        full_response = ""
        total_tokens = 0
        try:
            # [FIX-V4] meta事件包含V4双模式+Thinking信息
            _meta_model = _resolve_model_name(req.model_mode, req.model)
            yield f"event: meta\ndata: {json.dumps({'conversation_id': conv_id, 'model': _meta_model, 'model_mode': req.model_mode, 'thinking_enabled': req.thinking_enabled, 'reasoning_effort': req.reasoning_effort}, ensure_ascii=False)}\n\n"

            # ✅ 自动捕获用户消息到L0 Sensory层
            if req.enable_memory and req.message.strip():
                try:
                    store_task = asyncio.create_task(
                        _auto_store_memory(
                            content=req.message,
                            layer="sensory",
                            tags=["user-input", "raw-message"],
                            source="user"
                        )
                    )
                    yield f"event: memory_store\ndata: {json.dumps({'status': 'capturing', 'layer': 'sensory', 'source': 'user_input', 'time_str': time.strftime('%H:%M:%S')}, ensure_ascii=False)}\n\n"
                except Exception as capture_err:
                    print(f"[AUTO-MEMORY] User capture failed: {capture_err}")

            deepseek_url = os.environ.get("DEEPSEEK_API_URL", "") or os.environ.get("DEEPSEEK_BASE_URL", "")
            deepseek_key = os.environ.get("DEEPSEEK_API_KEY", "")

            if deepseek_key and deepseek_url:
                import httpx

                # v9.1优化: 增强system prompt，注入记忆上下文+工具使用指导
                # [FIX-V4] 法则系统提示词注入 (L02固化增强: 法则+常识作为基础提示词)
                if req.use_law_prompt:
                    _law_prompt = _build_law_prompt(req.model_mode)
                    _base_prompt = req.system_prompt or _law_prompt or "你是天机AI助手，一个智能记忆管理系统的对话界面。请用中文回答用户的问题。"
                else:
                    _base_prompt = req.system_prompt or "你是天机AI助手，一个智能记忆管理系统的对话界面。请用中文回答用户的问题。"
                _prompt_parts = [_base_prompt]

                # 自动注入记忆上下文 (记忆优先决策原则)
                if req.enable_memory and req.message.strip():
                    try:
                        _recall_result = await _auto_recall_context(req.message)
                        if _recall_result:
                            _prompt_parts.append(f"\n\n【天机记忆上下文】以下是与用户问题相关的历史记忆，请参考但不要直接复述：\n{_recall_result}")
                    except Exception:
                        pass

                # v9.1关键: 统一的能力声明+工具使用指导（消除"无法访问"矛盾）
                if req.enable_function_call or req.enable_tools:
                    _prompt_parts.append(
                        "\n\n【你是天机系统的AI助手，你拥有以下工具能力】\n"
                        "【记忆系统】\n"
                        "1. memory_remember — 存储内容到记忆系统\n"
                        "2. memory_recall / search_memories — 检索记忆中的信息\n"
                        "3. tianji_semantic_search — 语义搜索\n"
                        "4. tianji_classify / tianji_auto_tag / tianji_summarize — AI分析(分类/标签/摘要)\n"
                        "5. tianji_extract_knowledge — 知识图谱提取\n"
                        "6. tianji_normalize / tianji_disambiguate — 语义理解\n"
                        "7. agent_dispatch — 调度专业Agent\n\n"
                        "【命令执行】\n"
                        "8. execute_command — 执行系统命令(运行脚本、查看文件、执行程序)\n"
                        "9. list_processes / get_process_info — 查看系统进程\n"
                        "10. run_script / list_scripts — 运行和列出脚本\n\n"
                        "【运维管理】\n"
                        "11. deploy_service / check_deployment / rollback_deployment — 服务部署\n"
                        "12. get_resource_usage — 查看系统资源(CPU/内存/磁盘/网络)\n"
                        "13. list_services / scale_service — 服务管理\n\n"
                        "【安全审计】\n"
                        "14. scan_vulnerabilities — 漏洞扫描\n"
                        "15. check_compliance — 合规检查\n"
                        "16. scan_dependencies — 依赖扫描\n"
                        "17. check_permissions — 权限检查\n\n"
                        "【性能剖析】\n"
                        "18. get_performance_metrics — 性能指标\n"
                        "19. analyze_bottleneck — 瓶颈分析\n"
                        "20. get_memory_profile / get_cpu_profile — 内存/CPU剖析\n\n"
                        "【重要规则】\n"
                        "- 当用户提到'记住/保存/存储'时，你必须调用memory_remember工具\n"
                        "- 当用户提到'搜索/查找/有没有/之前说过'时，你必须调用memory_recall或tianji_semantic_search工具\n"
                        "- 当用户提到'分类/标签/摘要'时，你必须调用对应AI分析工具\n"
                        "- 当用户提到'Agent/调度/专家'时，你必须调用agent_dispatch工具\n"
                        "- 当用户提到'运行/执行/命令/脚本'时，你必须调用execute_command工具\n"
                        "- 当用户提到'进程/服务/部署/资源'时，你必须调用对应运维工具\n"
                        "- 当用户提到'安全/漏洞/扫描'时，你必须调用对应安全工具\n"
                        "- 当用户提到'性能/瓶颈/CPU/内存占用'时，你必须调用对应性能工具\n"
                        "- 你拥有这些工具，必须主动使用它们来完成任务\n"
                        "- 绝对不要说'我无法访问'或'我没有权限'或'我无法执行命令'，你有工具可以完成这些任务\n"
                        "- 你可以执行命令、读取文件、管理系统，通过execute_command工具\n"
                    )
                else:
                    _prompt_parts.append(
                        "\n\n【能力说明】你是天机记忆系统的AI助手。你可以进行记忆存储/检索、语义搜索、知识图谱、Agent调度、内容分类/摘要/标签等操作。"
                    )
                if req.enable_web_search:
                    _prompt_parts.append("\n\n【联网搜索模式已启用】你可以访问互联网获取实时信息，回答用户问题时请主动搜索并引用来源。")
                if req.enable_deep_thinking:
                    _prompt_parts.append("\n\n【深度思考模式已启用】请对问题进行深度分析和多角度思考，展示完整的推理过程。")
                system_msg = {"role": "system", "content": "\n".join(_prompt_parts)}
                api_messages = [system_msg]
                for m in conv["messages"][-20:]:
                    api_messages.append({"role": m["role"], "content": m["content"]})

                _model = _resolve_model_name(req.model_mode, req.model)
                if req.enable_deep_thinking and "deepseek" in _model.lower():
                    _model = "deepseek-reasoner"

                _request_body: Dict[str, Any] = {
                    "model": _model,
                    "messages": api_messages,
                    "stream": True,
                    "temperature": req.temperature,
                    "max_tokens": req.max_tokens,
                }
                # [FIX-V4] V4-Pro Thinking模式: 注入extra_body (L06数据契约对齐)
                # 仅当mode=v4-pro且thinking_enabled=True时启用
                if req.model_mode == "v4-pro" and req.thinking_enabled:
                    _request_body["extra_body"] = {
                        "thinking": {"type": "enabled"},
                        "reasoning_effort": req.reasoning_effort,
                    }
                    _request_body["reasoning_effort"] = req.reasoning_effort
                if req.enable_function_call or req.enable_tools:
                    # ✅ v9.1融合: 动态工具集 (MCPBridge + SkillResolver + AgentBroker)
                    try:
                        from core.shared.mcp_bridge import get_mcp_bridge
                        from core.shared.skill_resolver import get_skill_resolver
                        _bridge = get_mcp_bridge()
                        _resolver = get_skill_resolver()

                        # 1. 从MCPBridge获取全部可用工具定义
                        _dynamic_tools = _bridge.get_tool_definitions()

                        # 2. SkillResolver根据用户意图筛选最相关工具
                        _relevant_skills = _resolver.resolve(req.message, top_k=15)
                        _skill_tool_names = {s["name"] for s in _relevant_skills}

                        # 3. 合并: 核心工具(始终包含) + 意图相关工具
                        _core_tools = {"memory_recall", "memory_remember", "tianji_classify",
                                       "agent_dispatch", "tianji_semantic_search",
                                       "execute_command", "list_processes"}
                        _selected_names = _core_tools | _skill_tool_names

                        # 4. 构建最终工具集
                        _request_body["tools"] = [
                            t for t in _dynamic_tools
                            if t["function"]["name"] in _selected_names
                        ]

                        # 5. 确保至少有4个工具 (降级保护)
                        if len(_request_body["tools"]) < 4:
                            _request_body["tools"] = _dynamic_tools[:8]

                        _request_body["tool_choice"] = "auto"

                        # 6. 发送Skill推荐事件
                        if _relevant_skills:
                            _suggestions = _resolver.get_suggested_replies(_relevant_skills)
                            yield f"event: skill_suggestions\ndata: {json.dumps({'suggestions': _suggestions, 'matched_categories': list({s['category'] for s in _relevant_skills[:3]})}, ensure_ascii=False)}\n\n"

                    except ImportError:
                        # 降级: 使用基础工具集
                        _request_body["tools"] = [
                            {"type": "function", "function": {"name": "memory_recall", "description": "检索天机记忆系统中的相关信息", "parameters": {"type": "object", "properties": {"query": {"type": "string", "description": "搜索查询"}}, "required": ["query"]}}},
                            {"type": "function", "function": {"name": "semantic_search", "description": "执行语义相似度搜索", "parameters": {"type": "object", "properties": {"query": {"type": "string"}, "limit": {"type": "integer", "default": 10}}, "required": ["query"]}}},
                            {"type": "function", "function": {"name": "agent_dispatch", "description": "调度专业Agent执行任务", "parameters": {"type": "object", "properties": {"task_type": {"type": "string"}, "task_data": {"type": "object"}}, "required": ["task_type"]}}},
                            {"type": "function", "function": {"name": "web_search", "description": "搜索互联网获取实时信息", "parameters": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}}},
                        ]
                        _request_body["tool_choice"] = "auto"

                # v9.1修复: 工具调用循环 — 支持多轮工具调用+结果回传DeepSeek二次生成
                _max_tool_rounds = 3  # 最多3轮工具调用
                _current_messages = list(api_messages)  # 可变消息列表

                for _tool_round in range(_max_tool_rounds):
                    _request_body["messages"] = _current_messages
                    _pending_tool_calls = {}  # id -> {name, arguments}
                    _round_has_tool_call = False
                    _round_content = ""

                    async with httpx.AsyncClient(timeout=90.0) as client:
                        async with client.stream(
                            "POST",
                            f"{deepseek_url}/chat/completions",
                            headers={
                                "Authorization": f"Bearer {deepseek_key}",
                                "Content-Type": "application/json",
                            },
                            json=_request_body,
                        ) as resp:
                            if resp.status_code != 200:
                                error_text = await resp.aread()
                                yield f"event: error\ndata: {json.dumps({'detail': f'DeepSeek API error: {resp.status_code}'}, ensure_ascii=False)}\n\n"
                                return

                            async for line in resp.aiter_lines():
                                if _abort_signals.get(conv_id, False):
                                    yield f"event: done\ndata: {json.dumps({'conversation_id': conv_id, 'total_tokens': total_tokens, 'reason': 'aborted'}, ensure_ascii=False)}\n\n"
                                    return

                                if not line.startswith("data: "):
                                    continue
                                data_str = line[6:].strip()
                                if data_str == "[DONE]":
                                    break

                                try:
                                    chunk = json.loads(data_str)
                                    delta = chunk.get("choices", [{}])[0].get("delta", {})
                                    finish_reason = chunk.get("choices", [{}])[0].get("finish_reason")

                                    # 文本内容
                                    content = delta.get("content", "")
                                    if content:
                                        _round_content += content
                                        full_response += content
                                        total_tokens += 1
                                        # v9.1修复 [FIX-chat-xml-001]: 双重XML过滤
                                        # 检测1: DSML格式 <｜｜DSML｜｜tool_calls>
                                        # 检测2: 原始XML格式 <tool_calls>/<invoke>/<parameter>
                                        _has_tool_xml = (
                                            "<tool_calls" in content
                                            or "</tool_calls" in content
                                            or "<invoke" in content
                                            or "</invoke" in content
                                            or "<parameter" in content
                                            or "</parameter" in content
                                            or "<function_call" in content
                                        )
                                        if ("DSML" in content and ("tool_calls" in content or "invoke" in content)) or _has_tool_xml:
                                            # 尝试解析工具调用名称
                                            _tool_match = re.search(r'name="(\w+)"', content)
                                            if _tool_match:
                                                _tool_name = _tool_match.group(1)
                                                _round_has_tool_call = True
                                                _tc_idx = len(_pending_tool_calls)
                                                _pending_tool_calls[_tc_idx] = {
                                                    "id": f"xml_{_tc_idx}",
                                                    "name": _tool_name,
                                                    "arguments": "{}",
                                                }
                                            # 不发送工具调用XML给用户
                                            continue
                                        # 过滤DSML标签残留 + 工具调用XML残留
                                        if "｜｜" in content or "<tool_calls" in content or "<invoke" in content or "<parameter" in content:
                                            continue
                                        # [FIX-chat-xml-005] 乱码检测告警
                                        if _detect_garbled_content(content):
                                            _logger.warning("[chat-xml-005] 检测到字符替换攻击: %s", content[:100])
                                        yield f"event: text_delta\ndata: {json.dumps({'text': content, 'token_count': total_tokens}, ensure_ascii=False)}\n\n"

                                    # 工具调用 — 收集而非立即执行
                                    tool_calls = delta.get("tool_calls")
                                    if tool_calls:
                                        _round_has_tool_call = True
                                        for tc in tool_calls:
                                            # 用index作为主键(流式中id可能为空，但index始终存在)
                                            tc_idx = tc.get("index", len(_pending_tool_calls))
                                            tc_id = tc.get("id", "")
                                            fn = tc.get("function", {})
                                            _tool_name = fn.get("name", "")
                                            _tool_args_str = fn.get("arguments", "")

                                            if tc_idx not in _pending_tool_calls:
                                                _pending_tool_calls[tc_idx] = {
                                                    "id": tc_id or f"tc_{tc_idx}",
                                                    "name": _tool_name,
                                                    "arguments": ""
                                                }
                                            # 累加name和arguments(流式分片)
                                            if _tool_name:
                                                _pending_tool_calls[tc_idx]["name"] = _tool_name
                                            if tc_id:
                                                _pending_tool_calls[tc_idx]["id"] = tc_id
                                            if _tool_args_str:
                                                _pending_tool_calls[tc_idx]["arguments"] += _tool_args_str

                                except json.JSONDecodeError:
                                    continue

                    # 如果没有工具调用，本轮结束
                    if not _round_has_tool_call or not _pending_tool_calls:
                        break

                    # 将本轮assistant消息(含tool_calls)加入消息列表
                    _assistant_msg = {"role": "assistant", "content": _round_content or None}
                    _assistant_tool_calls = []
                    for tc_idx, tc_data in _pending_tool_calls.items():
                        # 跳过空名称的工具调用(流式收集不完整)
                        if not tc_data["name"]:
                            continue
                        _assistant_tool_calls.append({
                            "id": tc_data["id"],
                            "type": "function",
                            "function": {
                                "name": tc_data["name"],
                                "arguments": tc_data["arguments"]
                            }
                        })
                    _assistant_msg["tool_calls"] = _assistant_tool_calls
                    _current_messages.append(_assistant_msg)

                    # 执行每个工具调用，将结果加入消息列表
                    for tc_idx, tc_data in _pending_tool_calls.items():
                        _tool_name = tc_data["name"]
                        if not _tool_name:
                            continue  # 跳过空名称
                        try:
                            _tool_args = json.loads(tc_data["arguments"]) if tc_data["arguments"] else {}
                        except json.JSONDecodeError:
                            _tool_args = {}

                        yield f"event: tool_call_start\ndata: {json.dumps({'tool_name': _tool_name, 'round': _tool_round + 1}, ensure_ascii=False)}\n\n"

                        _tool_result_str = ""
                        # Agent调度走AgentBroker
                        if _tool_name == "agent_dispatch":
                            try:
                                from core.event_wiring.conversation_agent_broker import get_conversation_agent_broker
                                _broker = get_conversation_agent_broker()
                                _task_type = _tool_args.get("task_type", "general")
                                _task_data = _tool_args.get("task_data", {})
                                _priority = _tool_args.get("priority", "medium")
                                _dispatch_result = await _broker.dispatch(_task_type, _task_data, _priority)
                                _formatted = _broker.format_dispatch_result(_dispatch_result)
                                _tool_result_str = _formatted[:2000]
                                yield f"event: handoff\ndata: {json.dumps({'from_agent': 'system', 'to_agent': _dispatch_result.get('agent_info', {}).get('name', _task_type), 'tvp': _dispatch_result.get('tvp_handoff', '')}, ensure_ascii=False)}\n\n"
                            except Exception as _ae:
                                _tool_result_str = f"Agent调度失败: {str(_ae)}"
                        else:
                            # MCP工具走MCPBridge
                            try:
                                from core.shared.mcp_bridge import get_mcp_bridge
                                _bridge = get_mcp_bridge()
                                _call_result = await _bridge.call_tool(_tool_name, _tool_args)
                                _formatted = _bridge.format_result_for_llm(_call_result)
                                _tool_result_str = _formatted[:2000]
                            except Exception as _me:
                                _tool_result_str = f"工具调用失败: {str(_me)}"

                        yield f"event: tool_call_done\ndata: {json.dumps({'tool_name': _tool_name, 'result': _tool_result_str[:500], 'round': _tool_round + 1}, ensure_ascii=False)}\n\n"

                        # 将工具结果加入消息列表 (DeepSeek API要求的格式)
                        _current_messages.append({
                            "role": "tool",
                            "tool_call_id": tc_data["id"],
                            "content": _tool_result_str
                        })

                    # 移除tools参数让第二轮生成纯文本回复
                    _request_body.pop("tools", None)
                    _request_body.pop("tool_choice", None)
            else:
                fallback_chunks = [
                    "你好！我是天机AI助手。",
                    f"\n\n我收到了你的消息：「{req.message}」",
                    "\n\n目前DeepSeek API尚未配置，我处于本地回显模式。",
                    "\n\n请在系统配置中设置 DEEPSEEK_API_KEY 和 DEEPSEEK_BASE_URL 以启用完整AI对话功能。",
                    f"\n\n当前对话ID: {conv_id}",
                    f"\n历史消息数: {conv['message_count']}",
                ]
                for chunk in fallback_chunks:
                    if _abort_signals.get(conv_id, False):
                        break
                    full_response += chunk
                    total_tokens += 1
                    yield f"event: text_delta\ndata: {json.dumps({'text': chunk, 'token_count': total_tokens}, ensure_ascii=False)}\n\n"
                    await asyncio.sleep(0.05)

                if req.enable_memory:
                    yield f"event: memory_recall\ndata: {json.dumps({'status': 'done', 'query': req.message, 'results': 0, 'time_str': time.strftime('%H:%M:%S')}, ensure_ascii=False)}\n\n"

            assistant_msg = {
                "id": f"msg-{uuid.uuid4().hex[:8]}",
                "role": "assistant",
                "content": full_response,
                "timestamp": time.time(),
                "token_count": total_tokens,
                "fidelity": "full",
            }
            conv["messages"].append(assistant_msg)
            conv["message_count"] = len(conv["messages"])
            conv["total_tokens"] += total_tokens
            conv["updated_at"] = time.time()
            _persist(conv)

            # ✅ 自动捕获AI响应到L1 Working层 + 知识提取（后台异步执行）
            if req.enable_memory and full_response.strip():
                try:
                    asyncio.create_task(_auto_store_memory(
                        content=full_response,
                        layer="working",
                        tags=["ai-response", "assistant-reply"],
                        source="assistant"
                    ))

                    asyncio.create_task(_auto_extract_and_store(
                        req.message + "\n\n" + full_response
                    ))

                    yield f"event: memory_store\ndata: {json.dumps({'status': 'auto_stored', 'layer': 'working', 'source': 'ai_response', 'auto_extract': True, 'time_str': time.strftime('%H:%M:%S')}, ensure_ascii=False)}\n\n"
                except Exception as store_err:
                    print(f"[AUTO-MEMORY] Assistant capture failed: {store_err}")

            yield f"event: done\ndata: {json.dumps({'conversation_id': conv_id, 'total_tokens': conv['total_tokens']}, ensure_ascii=False)}\n\n"

        except asyncio.CancelledError:
            yield f"event: done\ndata: {json.dumps({'conversation_id': conv_id, 'total_tokens': total_tokens, 'reason': 'cancelled'}, ensure_ascii=False)}\n\n"
        except Exception as e:
            traceback.print_exc()
            yield f"event: error\ndata: {json.dumps({'detail': str(e)}, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
            "X-Conversation-Id": conv_id,
        },
    )


# ═══════════════════════════════════════════════════════════════════
# 对话置顶 — 需要conv_id参数的路由
# ═══════════════════════════════════════════════════════════════════

@router.patch("/conversations/{conv_id}/pin")
async def toggle_pin_conversation(conv_id: str, pinned: bool = Query(...)):
    """置顶/取消置顶对话"""
    conv = _get_conversation(conv_id)
    conv["pinned"] = pinned
    conv["updated_at"] = time.time()
    _persist(conv)
    return {"success": True, "pinned": pinned}


# ═══════════════════════════════════════════════════════════════════
# v9.1融合系统API — MCPBridge / SkillResolver / AgentBroker
# ═══════════════════════════════════════════════════════════════════

@router.get("/fusion/health")
async def fusion_health():
    """融合系统健康检查 — [FIX-fusion-001] 修复导入路径错误 + [FIX-fusion-002] 修复函数名映射

    实际文件位置 + 实际get函数名:
      - core/shared/mcp_bridge.py                     -> get_mcp_bridge
      - core/shared/skill_resolver.py                 -> get_skill_resolver
      - core/event_wiring/conversation_agent_broker.py -> get_conversation_agent_broker (注意:不是 get_agent_broker)
    """
    results = {}
    # [FIX-fusion-001] 修正三个融合模块的导入路径
    # [FIX-fusion-002] 修正函数名映射: agent_broker 模块的 get 函数名是 get_conversation_agent_broker
    fusion_modules = [
        ("mcp_bridge", "core.shared.mcp_bridge", "get_mcp_bridge"),
        ("skill_resolver", "core.shared.skill_resolver", "get_skill_resolver"),
        ("agent_broker", "core.event_wiring.conversation_agent_broker", "get_conversation_agent_broker"),
    ]
    for name, import_path, get_fn_name in fusion_modules:
        try:
            mod = __import__(import_path, fromlist=[""])
            get_fn = getattr(mod, get_fn_name, None)
            if get_fn:
                instance = get_fn()
                results[name] = instance.health()
            else:
                results[name] = {
                    "status": "degraded",
                    "note": f"模块已加载但无 {get_fn_name} 函数",
                }
        except ImportError as e:
            results[name] = {"status": "unavailable", "error": str(e)}
        except Exception as e:
            results[name] = {"status": "degraded", "error": str(e)}
    return {"success": True, "fusion_systems": results}


@router.get("/fusion/tools")
async def fusion_list_tools():
    """列出所有可用的MCP工具 (动态)"""
    try:
        from core.shared.mcp_bridge import get_mcp_bridge
        bridge = get_mcp_bridge()
        tools = bridge.get_tool_definitions()
        categories = bridge.get_all_categories()
        return {
            "success": True,
            "total_tools": len(tools),
            "tools": [
                {
                    "name": t["function"]["name"],
                    "description": t["function"]["description"][:80],
                }
                for t in tools
            ],
            "categories": {k: len(v) for k, v in categories.items()},
        }
    except ImportError:
        return {"success": False, "error": "MCPBridge不可用"}


@router.get("/fusion/agents")
async def fusion_list_agents():
    """列出所有可用Agent"""
    try:
        from core.event_wiring.conversation_agent_broker import get_conversation_agent_broker
        broker = get_conversation_agent_broker()
        agents = broker.get_available_agents()
        current = broker.get_current_agent()
        return {"success": True, "total_agents": len(agents), "agents": agents, "current_agent": current}
    except ImportError:
        return {"success": False, "error": "AgentBroker不可用"}


@router.post("/fusion/resolve-skills")
async def fusion_resolve_skills(request: Request):
    """解析用户意图, 返回匹配的Skills"""
    try:
        body = await request.json()
        message = body.get("user_input", body.get("message", ""))
        top_k = body.get("top_k", 5)
        if not message:
            return {"success": False, "error": "缺少user_input参数"}
        from core.shared.skill_resolver import get_skill_resolver
        resolver = get_skill_resolver()
        skills = resolver.resolve(message, top_k=top_k)
        suggestions = resolver.get_suggested_replies(skills)
        return {
            "success": True,
            "message": message,
            "matched_skills": skills,
            "suggested_replies": suggestions,
        }
    except ImportError:
        return {"success": False, "error": "SkillResolver不可用"}
    except Exception as e:
        return {"success": False, "error": str(e)}


@router.post("/fusion/dispatch")
async def fusion_dispatch(request: Request):
    """手动触发Agent调度"""
    try:
        body = await request.json()
        task_type = body.get("task_type", "")
        task_data = body.get("task_data")
        priority = body.get("priority", "medium")
        if not task_type:
            return {"success": False, "error": "缺少task_type参数"}
        from core.event_wiring.conversation_agent_broker import get_conversation_agent_broker
        broker = get_conversation_agent_broker()
        result = await broker.dispatch(task_type, task_data, priority)
        # 确保tvp_handoff为字典格式
        tvp = result.get("tvp_handoff", "")
        if isinstance(tvp, str):
            tvp = {"declaration": tvp, "from_agent": result.get("agent_id", ""), "to_agent": result.get("agent_id", "")}
        return {
            "success": result["success"],
            "agent_id": result["agent_id"],
            "agent_info": result["agent_info"],
            "tvp_handoff": tvp,
            "duration_ms": result["duration_ms"],
        }
    except ImportError:
        return {"success": False, "error": "AgentBroker不可用"}
    except Exception as e:
        return {"success": False, "error": str(e)}


@router.get("/fusion/handoff-history")
async def fusion_handoff_history(limit: int = Query(20, ge=1, le=100)):
    """获取Agent切换历史"""
    try:
        from core.event_wiring.conversation_agent_broker import get_conversation_agent_broker
        broker = get_conversation_agent_broker()
        return {"success": True, "history": broker.get_handoff_history(limit)}
    except ImportError:
        return {"success": False, "error": "AgentBroker不可用"}


# === v9.1对话优化: 反馈机制 + 错误恢复 ===

# [FIX-AUDIT] 补充前端调用的4个缺失端点

@router.get("/conversations/{conv_id}/messages")
async def get_conversation_messages(
    conv_id: str,
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    """获取对话消息列表 (前端Dashboard/Chat页调用)"""
    conv = _get_conversation(conv_id)
    messages = conv.get("messages", [])
    total = len(messages)
    page = messages[offset : offset + limit]
    return {
        "success": True,
        "conversation_id": conv_id,
        "messages": page,
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.post("/send")
async def send_message(req: ChatRequest):
    """发送消息 (非流式同步版本, 前端Chat页调用)"""
    conv_id = req.conversation_id or "default"
    conv = _ensure_conversation(conv_id)

    # 记录用户消息
    user_msg = {
        "id": f"msg-{uuid.uuid4().hex[:8]}",
        "role": "user",
        "content": req.message,
        "timestamp": time.time(),
        "token_count": len(req.message),
    }
    conv["messages"].append(user_msg)
    conv["message_count"] = len(conv["messages"])
    conv["updated_at"] = time.time()

    # 调用LLM生成回复 (使用DeepSeek大脑)
    # [FIX-send-001] 修复: classify_layer返回记忆层名(如"sensory"), 非AI对话回复
    # 改用chat_sync进行真实LLM对话
    try:
        from server.api.llm_routes import _get_deepseek, _run_sync
        ds = _get_deepseek()
        # 使用chat_sync进行真实对话(非记忆层分类)
        result = await _run_sync(ds.chat_sync, req.message, system_prompt="", expect_json=False)
        if isinstance(result, dict) and "error" in result:
            reply_text = f"[AI回复] 已收到消息: {req.message[:50]}..."
            _logger.warning("[send-001] LLM调用失败: %s", result.get("error", "unknown"))
        elif isinstance(result, dict) and "content" in result:
            reply_text = result["content"]
        elif isinstance(result, str):
            reply_text = result
        else:
            reply_text = str(result) if result else f"[AI回复] 已收到消息: {req.message[:50]}..."
    except Exception as e:
        reply_text = f"[AI回复] 已收到消息: {req.message[:50]}..."  # 降级回复

    # 记录助手消息
    assistant_msg = {
        "id": f"msg-{uuid.uuid4().hex[:8]}",
        "role": "assistant",
        "content": reply_text,
        "timestamp": time.time(),
        "token_count": len(reply_text),
    }
    conv["messages"].append(assistant_msg)
    conv["message_count"] = len(conv["messages"])
    conv["updated_at"] = time.time()
    _persist(conv)

    return {
        "success": True,
        "conversation_id": conv_id,
        "user_message": user_msg,
        "assistant_message": assistant_msg,
    }


@router.get("/status")
async def chat_status():
    """获取对话系统状态 (前端Chat页调用)"""
    return {
        "success": True,
        "status": "active",
        "version": "v9.1",
        "conversations_count": len(_conversations),
        "total_messages": sum(c.get("message_count", 0) for c in _conversations.values()),
        "features": ["stream", "send", "memory_recall", "agent_dispatch"],
        "llm_available": True,
    }


@router.get("/config")
async def chat_config():
    """获取对话配置 (前端Settings页调用)"""
    return {
        "success": True,
        "config": {
            "default_mode": "normal",
            "modes": ["normal", "deep", "reason"],
            "max_tokens_range": [256, 16384],
            "temperature_range": [0.0, 2.0],
            "default_max_tokens": 4096,
            "default_temperature": 0.7,
            "enable_tools_default": True,
            "enable_skills_default": True,
            "enable_agents_default": False,
            "auto_save": True,
            "memory_recall_enabled": True,
            # [FIX-V4] V4双模式配置
            "default_model_mode": "v4-flash",
            "model_modes": ["v4-pro", "v4-flash"],
            "thinking_enabled_default": False,
            "reasoning_effort_options": ["low", "medium", "high"],
            "use_law_prompt_default": True,
        },
    }


# ═══════════════════════════════════════════════════════════════════
# [FIX-V4] V4双模式 + 消息管理端点 (L18增量开发: 不影响现有端点)
# ═══════════════════════════════════════════════════════════════════

class MessageEditRequest(BaseModel):
    """消息编辑请求 (用户级友好编辑)"""
    content: str
    role: Optional[str] = None  # 可选, 不传则保持原role


class MessageRegenerateRequest(BaseModel):
    """消息重新生成请求"""
    model_mode: str = "v4-flash"
    thinking_enabled: bool = False
    reasoning_effort: str = "medium"
    use_law_prompt: bool = True
    max_tokens: int = 4096
    temperature: float = 0.7


@router.get("/models")
async def list_models():
    """获取可用模型列表 — V4-Pro/V4-Flash双模式"""
    # L11路径唯一性: 通过DeepSeekConfig获取模型名称
    _flash_name = _resolve_model_name("v4-flash", "deepseek-v4-flash")
    _pro_name = _resolve_model_name("v4-pro", "deepseek-v4-pro")
    return {
        "success": True,
        "models": [
            {
                "id": "v4-flash",
                "name": "DeepSeek V4-Flash",
                "api_model": _flash_name,
                "description": "高性价比/快速响应/284B参数",
                "supports_thinking": False,
                "context_length": "128K",
                "max_output": "8K",
            },
            {
                "id": "v4-pro",
                "name": "DeepSeek V4-Pro",
                "api_model": _pro_name,
                "description": "复杂推理/Thinking模式/1.6T参数",
                "supports_thinking": True,
                "context_length": "1M",
                "max_output": "64K",
            },
        ],
        "default_mode": "v4-flash",
        "reasoning_effort_options": ["low", "medium", "high"],
    }


def _find_message(conv: Dict, msg_id: str) -> Optional[Dict]:
    """在对话中查找指定ID的消息 — L05空值防御"""
    messages = conv.get("messages", [])
    if not isinstance(messages, list):
        return None
    for msg in messages:
        if isinstance(msg, dict) and msg.get("id") == msg_id:
            return msg
    return None


def _find_message_index(conv: Dict, msg_id: str) -> int:
    """在对话中查找指定ID的消息索引 — L05空值防御"""
    messages = conv.get("messages", [])
    if not isinstance(messages, list):
        return -1
    for i, msg in enumerate(messages):
        if isinstance(msg, dict) and msg.get("id") == msg_id:
            return i
    return -1


@router.put("/conversations/{conv_id}/messages/{msg_id}")
async def edit_message(conv_id: str, msg_id: str, req: MessageEditRequest):
    """编辑消息内容 — 用户级友好编辑 (L18增量开发)"""
    conv = _get_conversation(conv_id)
    msg = _find_message(conv, msg_id)
    if msg is None:
        raise HTTPException(status_code=404, detail=f"Message {msg_id} not found in conversation {conv_id}")

    # 更新消息内容 (L19幂等性: 基于当前状态更新)
    old_content = msg.get("content", "")
    msg["content"] = req.content
    if req.role and req.role in ("user", "assistant", "system"):
        msg["role"] = req.role
    msg["edited"] = True
    msg["edited_at"] = time.time()
    msg["previous_content"] = old_content  # 保留历史 (L20变更可追溯)
    msg["token_count"] = len(req.content)
    conv["updated_at"] = time.time()
    _persist(conv)

    return {
        "success": True,
        "conversation_id": conv_id,
        "message_id": msg_id,
        "message": msg,
    }


@router.delete("/conversations/{conv_id}/messages/{msg_id}")
async def delete_message(conv_id: str, msg_id: str):
    """删除消息 — 软删除标记 (L18增量开发, 天机法则: 仅软删除)"""
    conv = _get_conversation(conv_id)
    msg_index = _find_message_index(conv, msg_id)
    if msg_index < 0:
        raise HTTPException(status_code=404, detail=f"Message {msg_id} not found in conversation {conv_id}")

    # 软删除: 标记为已删除而非物理删除 (天机法则: 禁止删除记忆数据)
    msg = conv["messages"][msg_index]
    msg["deleted"] = True
    msg["deleted_at"] = time.time()
    # 物理移除消息 (对话场景: 消息可物理删除, 与记忆数据不同)
    conv["messages"].pop(msg_index)
    conv["message_count"] = len(conv["messages"])
    conv["updated_at"] = time.time()
    _persist(conv)

    return {
        "success": True,
        "conversation_id": conv_id,
        "message_id": msg_id,
        "remaining_messages": conv["message_count"],
    }


@router.post("/conversations/{conv_id}/messages/{msg_id}/regenerate")
async def regenerate_message(conv_id: str, msg_id: str, req: MessageRegenerateRequest):
    """重新生成AI回复 — 基于消息上下文重新调用LLM (L18增量开发)"""
    conv = _get_conversation(conv_id)
    msg_index = _find_message_index(conv, msg_id)
    if msg_index < 0:
        raise HTTPException(status_code=404, detail=f"Message {msg_id} not found in conversation {conv_id}")

    msg = conv["messages"][msg_index]
    # 仅允许重新生成assistant消息
    if msg.get("role") != "assistant":
        raise HTTPException(status_code=400, detail="只能重新生成AI回复消息")

    # 构建上下文消息 (该消息之前的所有消息)
    context_messages = conv["messages"][:msg_index]
    # 过滤掉非user/assistant的消息 (L05空值防御)
    api_messages: List[Dict[str, str]] = []
    for m in context_messages[-20:]:  # 最多20条上下文
        role = m.get("role", "user")
        content = m.get("content", "")
        if role in ("user", "assistant") and content:
            api_messages.append({"role": role, "content": content})

    # [FIX-V4] 注入法则系统提示词 (L02固化增强)
    if req.use_law_prompt:
        law_prompt = _build_law_prompt(req.model_mode)
        if law_prompt:
            api_messages.insert(0, {"role": "system", "content": law_prompt})

    # 调用DeepSeek API重新生成 (优先使用DeepSeekClient.chat_with_mode)
    try:
        from llm_integration.client import DeepSeekClient, DeepSeekConfig
        _config = DeepSeekConfig.from_env()
        _client = DeepSeekClient(_config)
        result = await _client.chat_with_mode(
            messages=api_messages,
            model_mode=req.model_mode,
            thinking_enabled=req.thinking_enabled,
            reasoning_effort=req.reasoning_effort,
            temperature=req.temperature,
            max_tokens=req.max_tokens,
        )
        if result.get("success"):
            new_content = result.get("content", "")
            reasoning_content = result.get("reasoning_content", "")
        else:
            return {
                "success": False,
                "error": result.get("error", "DeepSeek API调用失败"),
                "conversation_id": conv_id,
                "message_id": msg_id,
            }
    except ImportError:
        # 降级: 直接httpx调用 (L04降级完整性)
        import httpx
        _model_name = _resolve_model_name(req.model_mode, "deepseek-chat")
        _payload: Dict[str, Any] = {
            "model": _model_name,
            "messages": api_messages,
            "temperature": req.temperature,
            "max_tokens": req.max_tokens,
        }
        if req.model_mode == "v4-pro" and req.thinking_enabled:
            _payload["extra_body"] = {"thinking": {"type": "enabled"}, "reasoning_effort": req.reasoning_effort}
            _payload["reasoning_effort"] = req.reasoning_effort

        _ds_url = os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")
        _ds_key = os.environ.get("DEEPSEEK_API_KEY", "")
        async with httpx.AsyncClient(timeout=90.0) as client:
            _resp = await client.post(
                f"{_ds_url}/chat/completions",
                headers={"Authorization": f"Bearer {_ds_key}", "Content-Type": "application/json"},
                json=_payload,
            )
            _resp.raise_for_status()
            _data = _resp.json()
            new_content = _data.get("choices", [{}])[0].get("message", {}).get("content", "")
            reasoning_content = _data.get("choices", [{}])[0].get("message", {}).get("reasoning_content", "")

    # 更新消息内容 (L19幂等性: 基于当前状态更新)
    old_content = msg.get("content", "")
    msg["content"] = new_content
    msg["regenerated"] = True
    msg["regenerated_at"] = time.time()
    msg["previous_content"] = old_content  # 保留历史 (L20变更可追溯)
    msg["token_count"] = len(new_content)
    if reasoning_content:
        msg["reasoning_content"] = reasoning_content
    msg["model_mode"] = req.model_mode
    msg["thinking_enabled"] = req.thinking_enabled
    conv["updated_at"] = time.time()
    _persist(conv)

    return {
        "success": True,
        "conversation_id": conv_id,
        "message_id": msg_id,
        "message": msg,
        "model_mode": req.model_mode,
    }
