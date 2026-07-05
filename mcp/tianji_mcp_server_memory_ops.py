# -*- coding: utf-8-sig -*-
"""tianji_mcp_server_memory_ops.py — TianjiMCPServerMemory_OpsMixin (SSS-PhaseB)

从 tianji_mcp_server.py 拆分的方法组: memory_ops
"""

import time
import urllib.error
import urllib.parse
import urllib.request

# ── 共享常量 (从core导入) ──────────────────────────────
try:
    from tianji_mcp_server_core import (  # type: ignore
        SYSTEM_NAME,
        TIANJI_API_URL,
        _encoding_safe_dict,
        _encoding_safe_text,
    )
except ImportError:
    try:
        from .tianji_mcp_server_core import (  # type: ignore
            SYSTEM_NAME,
            TIANJI_API_URL,
            _encoding_safe_dict,
            _encoding_safe_text,
        )
    except ImportError:
        SYSTEM_NAME = "天机-忆库"
        TIANJI_API_URL = "http://127.0.0.1:8771"

        def _encoding_safe_text(t, l=""):
            return str(t)  # noqa: E701

        def _encoding_safe_dict(d, l=""):
            return d if isinstance(d, dict) else {}  # noqa: E701


class TianjiMCPServerMemory_OpsMixin:
    """memory_ops方法组Mixin"""

    def _subprocess_post_fallback(self, path: str, data: dict) -> dict:
        """[FIX-MCP-SUBPROCESS-FALLBACK] 当MCP server进程内HTTP超时时，用subprocess绕过

        根因：MCP server长驻进程可能存在socket fd泄漏/线程竞争/GIL持有等问题，
        导致urllib.request.urlopen()在进程内超时，但直接运行python 0.07s成功。
        本方法通过subprocess启动独立python进程执行HTTP请求，绕过进程内问题。
        """
        import json as _json
        import subprocess as _sp
        import sys as _sys

        try:
            # 序列化请求数据
            payload = _json.dumps(data, ensure_ascii=False)
            # 构造独立python脚本
            script = (
                "import urllib.request, json, sys; "
                f"url='http://127.0.0.1:8771{path}'; "
                f"data=json.loads(sys.argv[1]).encode('utf-8'); "
                "req=urllib.request.Request(url, data=data, "
                "headers={'Content-Type':'application/json'}, method='POST'); "
                "r=urllib.request.urlopen(req, timeout=30); "
                "sys.stdout.write(r.read().decode('utf-8','replace'))"
            )
            # 使用MCP专用python
            py_exe = _sys.executable
            proc = _sp.run(
                [py_exe, "-c", script, payload],
                capture_output=True,
                text=True,
                timeout=35,
                encoding="utf-8",
                errors="replace",
            )
            if proc.returncode == 0 and proc.stdout.strip():
                result = _json.loads(proc.stdout)
                return result if isinstance(result, dict) else {"data": result}
            return {
                "error": f"subprocess失败 rc={proc.returncode} stderr={proc.stderr[:300]}"
            }
        except _sp.TimeoutExpired:
            return {"error": "subprocess也超时(35s)，后端服务可能真的不可用"}
        except Exception as e:
            return {"error": f"subprocess异常: {e}"}

    def _handle_remember(self, args: dict) -> dict:
        data = {
            "content": args.get("content", ""),
            "layer": args.get("layer", "working"),
            "tags": args.get("tags", []),
            "priority": args.get("priority", "medium"),
            # [FIX-TIMEOUT] 默认关闭LLM增强，避免classify+summarize+extract_knowledge三连调用超时
            # 客户端可通过 args["use_llm"]=True 显式启用
            "use_llm": args.get("use_llm", False),
        }
        # [FIX-MCP-WARMUP] 内容为空时立即返回，不发后端请求
        if not data["content"].strip():
            return {
                "status": "error",
                "detail": "content 不能为空",
                "hint": "提供要写入的内容(>=30字符推荐)",
            }
        # [FIX-MCP-SUBPROCESS-FALLBACK] 先尝试_api_post，超时则fallback到subprocess
        result = self._api_post("/api/memory/", data)
        # 检测超时，fallback到subprocess直接HTTP调用
        if isinstance(result, dict) and result.get("error"):
            err_str = str(result.get("error", ""))
            if "timed out" in err_str or "timeout" in err_str.lower():
                result = self._subprocess_post_fallback("/api/memory/", data)
        # [FIX-B1-REMEMBER] _api_post 可能返回 list 或 dict，统一类型检查
        if isinstance(result, list):
            return {
                "status": "error",
                "detail": f"API返回了list而非dict: {str(result)[:200]}",
            }
        if result and not result.get("error"):
            return {
                "status": "success",
                "memory_id": result.get("id"),
                "layer": result.get("layer", data["layer"]),
                "gate_verdict": "stored",
                "system": SYSTEM_NAME,
            }
        # [FIX-TIMEOUT] 超时时给出明确诊断提示
        err_str = str(result.get("error", "")) if isinstance(result, dict) else ""
        if "timed out" in err_str or "timeout" in err_str.lower():
            return {
                "status": "error",
                "detail": "写入超时：天机服务冷启动或LLM增强处理中",
                "hint": "1) 自动预热后重试 2) 显式传 use_llm=False 3) 检查天机8771服务是否healthy",
                "diagnostic": {
                    "api_url": getattr(self, "api_url", "unknown"),
                    "api_available": getattr(self, "_api_available", "unknown"),
                    "error_raw": err_str[:200],
                    "use_llm": data["use_llm"],
                },
            }
        # [FIX-MCP-UNAVAILABLE] API不可用时的降级提示
        if "connection refused" in err_str.lower() or "api不可用" in err_str:
            return {
                "status": "error",
                "detail": "天机API不可用，请检查8771端口服务是否运行",
                "hint": "启动天机v9.1: 运行 desktop快捷方式或 start_server.py",
                "offline_queue": "如天机持续不可用，写入 .tianji/offline_writes.json 暂存",
            }
        return {"status": "error", "detail": result}

    @staticmethod
    def _client_side_filter(results: list, query: str, limit: int) -> list:
        if not query or not results:
            return results[:limit]
        q_lower = query.lower()
        q_words = set(q_lower.split())
        scored = []
        for r in results:
            content = (r.get("content") or "").lower()
            tags_str = " ".join(r.get("tags") or []).lower()
            combined = content + " " + tags_str
            if q_lower in combined:
                scored.append((3.0, r))
            elif q_words & set(combined.split()):
                scored.append((1.5, r))
            else:
                overlap = sum(1 for w in q_words if w in combined)
                if overlap > 0:
                    scored.append((0.5 * overlap / len(q_words), r))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [r for _, r in scored[:limit]]

    def _handle_recall(self, args: dict) -> dict:
        query = args.get("query", "")
        limit = args.get("limit", 10)
        layers = args.get("layers")
        params = {"query": query, "limit": limit}
        if layers:
            params["layers"] = ",".join(layers)
        result = self._api_get("/api/platform/recall", params)
        results = (
            result
            if isinstance(result, list)
            else (
                result.get("results", [])
                if isinstance(result, dict) and not result.get("error")
                else []
            )
        )
        if not results and query:
            list_result = self._api_post(
                "/api/mcp/tools/list_memories", {"limit": 200, "offset": 0}
            )
            if list_result and not list_result.get("error"):
                all_items = list_result.get("results", [])
                if layers:
                    all_items = [m for m in all_items if m.get("layer") in layers]
                results = self._client_side_filter(all_items, query, limit)
        return {
            "status": "success",
            "count": len(results),
            "results": results,
            "system": SYSTEM_NAME,
        }

    def _handle_forget(self, args: dict) -> dict:
        # [FIX-MCP-Bug8] 兼容entry_id/memory_id参数名 + 增强错误处理
        entry_id = args.get("entry_id", args.get("memory_id", ""))
        if not entry_id:
            return {"status": "error", "detail": "entry_id参数不能为空"}
        result = self._api_post("/api/mcp/tools/delete_memory", {"memory_id": entry_id})
        if result and isinstance(result, dict):
            # 服务端成功返回 {"status":"success","message":"..."} 失败抛HTTPException
            if result.get("status") == "success" or "deleted" in str(result).lower():
                return {
                    "status": "success",
                    "memory_id": entry_id,
                    "system": SYSTEM_NAME,
                }
            # 404也算成功(幂等删除)
            if result.get("error") and "404" in str(result.get("error", "")):
                return {
                    "status": "success",
                    "memory_id": entry_id,
                    "system": SYSTEM_NAME,
                    "note": "already_deleted",
                }
        return {"status": "error", "detail": result, "memory_id": entry_id}

    def _handle_stats(self, args: dict) -> dict:
        result = self._api_get("/api/memory/stats")
        if result and not result.get("error"):
            return {"status": "success", "stats": result, "system": SYSTEM_NAME}
        return {"status": "error", "detail": result}

    def _handle_capacity(self, args: dict) -> dict:
        result = self._api_get("/api/health")
        if result and not result.get("error"):
            return {
                "status": "success",
                "capacity": result.get("layers", {}),
                "system": SYSTEM_NAME,
            }
        return {"status": "error", "detail": result}

    def _handle_consolidate(self, args: dict) -> dict:
        from_layer = args.get("from_layer", "working")
        # Use storage/manage endpoint which works with both SQLite and JSON backends
        result = self._api_post(
            "/api/memory/storage/manage",
            {
                "action": "consolidate",
                "layer": from_layer,
                "force": True,
            },
        )
        if result and isinstance(result, dict):
            actions = result.get("actions_performed", [])
            consolidate_action = None
            for a in actions:
                if a.get("action") in ("consolidate", "emergency_consolidate"):
                    consolidate_action = a
                    break
            if consolidate_action:
                return {
                    "status": "success",
                    "consolidated_from": from_layer,
                    "consolidated_count": consolidate_action.get("result", {}).get(
                        "consolidated", 0
                    ),
                    "total_accumulated": consolidate_action.get("result", {}).get(
                        "candidates", 0
                    ),
                    "to_layer": consolidate_action.get("result", {}).get(
                        "to_layer", ""
                    ),
                    "system": SYSTEM_NAME,
                }
            # Fallback: try consolidate_all endpoint
            result2 = self._api_post(
                "/api/memory/consolidate_all", {"from_layer": from_layer}
            )
            if result2 and not result2.get("error"):
                return {
                    "status": "success",
                    "consolidated_from": from_layer,
                    "consolidated_count": result2.get("consolidated_count", 0),
                    "total_accumulated": result2.get("total_accumulated", 0),
                    "to_layer": result2.get("to_layer", ""),
                    "system": SYSTEM_NAME,
                }
        return {"status": "error", "detail": result}

    def _handle_search(self, args: dict) -> dict:
        query = args.get("query", "")
        limit = args.get("limit", 10)
        threshold = args.get("threshold", 0.1)
        data = {"query": query, "limit": limit, "threshold": threshold}
        result = self._api_post("/api/mcp/tools/search_memories", data)
        results = (
            result.get("results", [])
            if isinstance(result, dict) and not result.get("error")
            else []
        )
        if not results and query:
            list_result = self._api_post(
                "/api/mcp/tools/list_memories", {"limit": 200, "offset": 0}
            )
            if list_result and not list_result.get("error"):
                all_items = list_result.get("results", [])
                results = self._client_side_filter(all_items, query, limit)
        return {"status": "success", "results": results, "system": SYSTEM_NAME}

    def _handle_get_memory(self, args: dict) -> dict:
        # [FIX-MCP-Bug6/9] 兼容schema的entry_id参数名 (schema=entry_id, 旧代码=memory_id)
        entry_id = args.get("entry_id", args.get("memory_id", ""))
        result = self._api_post("/api/mcp/tools/get_memory", {"memory_id": entry_id})
        if result and not result.get("error"):
            return {
                "status": "success",
                "memory": result.get("memory"),
                "system": SYSTEM_NAME,
            }
        return {"status": "error", "detail": result}

    def _handle_list_memories(self, args: dict) -> dict:
        data = {"limit": args.get("limit", 20), "offset": args.get("offset", 0)}
        result = self._api_post("/api/mcp/tools/list_memories", data)
        if result and not result.get("error"):
            return {
                "status": "success",
                "results": result.get("results", []),
                "system": SYSTEM_NAME,
            }
        return {"status": "error", "detail": result}

    def _handle_memory_update(self, args: dict) -> dict:
        """更新指定记忆条目 (对应 PUT /api/memories/{id})"""
        entry_id = args.get("entry_id", "")
        if not entry_id:
            return {"status": "error", "detail": "entry_id 为必填项"}

        data = {}
        if "content" in args:
            data["content"] = args["content"]
        if "tags" in args:
            data["tags"] = args["tags"]
        if "priority" in args:
            data["priority"] = args["priority"]

        if not data:
            return {
                "status": "error",
                "detail": "至少需要提供一个可更新字段(content/tags/priority)",
            }

        # [FIX-MCP-Bug10] 修正路径: /api/memories/{id} → /api/memory/{id} (服务端prefix是单数memory)
        result = self._api_put(f"/api/memory/{entry_id}", data)
        if result and not result.get("error"):
            return {
                "status": "success",
                "memory_id": entry_id,
                "updated_fields": list(data.keys()),
                "system": SYSTEM_NAME,
            }
        return {"status": "error", "detail": result}

    # ═══════════════════════════════════════════════════════════════
    # P1-2: Agent自管理记忆工具 (MemGPT模式) [v10-ready]
    # 借鉴Letta MemGPT架构, 让Agent主动编辑memory blocks
    # 参考文档: https://docs.letta.com/guides/agents/architectures/memgpt
    # ═══════════════════════════════════════════════════════════════

    def _handle_memory_insert(self, args: dict) -> dict:
        """memory_insert — Agent向指定layer插入新记忆块

        MemGPT模式工具: Agent主动决定什么内容应该被记住、放在哪一层。
        与memory_remember的区别: remember是被动写入, insert是Agent主动构建记忆结构。

        参数:
            content: 必填, 要插入的记忆内容
            layer: 必填, 目标层级 (sensory/working/short_term/episodic/semantic/meta)
            tags: 可选, 标签列表
            priority: 可选, 优先级 (low/medium/high/critical)
            metadata: 可选, 元数据字典
            agent_id: 可选, 执行插入的Agent身份 (默认"self")
            reason: 可选, Agent插入这条记忆的原因 (用于审计)

        返回:
            memory_id: 新记忆条目ID
            layer: 实际写入的层级
            agent_id: 执行Agent
            audit_trail: 审计信息
        """
        content = args.get("content", "").strip()
        if not content:
            return {"status": "error", "detail": "content 为必填项"}

        layer = args.get("layer", "working").lower()
        valid_layers = {
            "sensory",
            "working",
            "short_term",
            "episodic",
            "semantic",
            "meta",
        }
        if layer not in valid_layers:
            return {"status": "error", "detail": f"layer 必须是 {valid_layers} 之一"}

        agent_id = args.get("agent_id", "self")
        reason = args.get("reason", "")

        data = {
            "content": content,
            "layer": layer,
            "tags": args.get("tags", []) + [f"agent_inserted:{agent_id}"],
            "priority": args.get("priority", "medium"),
            "metadata": {
                **args.get("metadata", {}),
                "operation": "memory_insert",
                "agent_id": agent_id,
                "reason": reason,
                "tool_source": "memgpt_pattern",
            },
            # [FIX-TIMEOUT] 默认关闭LLM增强，避免三连LLM调用超时
            "use_llm": args.get("use_llm", False),
        }

        result = self._api_post("/api/memory/", data)
        # [FIX-B1-INSERT] _api_post 可能返回 list 或 dict，统一类型检查
        if isinstance(result, list):
            return {
                "status": "error",
                "detail": f"API返回了list而非dict: {str(result)[:200]}",
            }
        if result and not result.get("error"):
            return {
                "status": "success",
                "memory_id": result.get("id"),
                "layer": layer,
                "agent_id": agent_id,
                "audit_trail": {
                    "operation": "memory_insert",
                    "reason": reason,
                    "timestamp": time.time(),
                },
                "system": SYSTEM_NAME,
            }
        return {"status": "error", "detail": result}

    def _handle_memory_replace(self, args: dict) -> dict:
        """memory_replace — Agent替换指定记忆条目的内容

        MemGPT模式工具: Agent主动修正/更新已有记忆。
        使用supersede机制: 旧记忆被标记为superseded, 新记忆链接到旧记忆形成版本链。

        参数:
            entry_id: 必填, 要替换的记忆条目ID
            new_content: 必填, 新内容
            reason: 可选, 替换原因 (用于审计)
            agent_id: 可选, 执行替换的Agent身份
            invalidate_old: 可选, 是否软删除旧记忆 (默认True, 保留可追溯)

        返回:
            old_memory_id: 被替换的旧记忆ID
            new_memory_id: 新记忆ID
            supersede_chain: 版本链信息
        """
        entry_id = args.get("entry_id", "").strip()
        if not entry_id:
            return {"status": "error", "detail": "entry_id 为必填项"}

        new_content = args.get("new_content", "").strip()
        if not new_content:
            return {"status": "error", "detail": "new_content 为必填项"}

        agent_id = args.get("agent_id", "self")
        reason = args.get("reason", "")
        invalidate_old = args.get("invalidate_old", True)

        # Step 1: 获取旧记忆的layer和metadata
        old_result = self._api_get(f"/api/memory/{entry_id}")
        if not old_result or old_result.get("error"):
            return {"status": "error", "detail": f"找不到原记忆 {entry_id}"}

        old_layer = old_result.get("layer", "working")
        old_tags = old_result.get("tags", [])
        old_content = old_result.get("content", "")

        # Step 2: 创建新记忆, 标记为替代品
        data = {
            "content": new_content,
            "layer": old_layer,
            "tags": old_tags + [f"supersedes:{entry_id}", f"agent_replaced:{agent_id}"],
            "priority": old_result.get("priority", "medium"),
            "metadata": {
                "operation": "memory_replace",
                "agent_id": agent_id,
                "reason": reason,
                "supersedes": entry_id,
                "old_content_preview": old_content[:100] if old_content else "",
                "tool_source": "memgpt_pattern",
            },
        }

        new_result = self._api_post("/api/memory/", data)
        if not new_result or new_result.get("error"):
            return {"status": "error", "detail": f"创建新记忆失败: {new_result}"}

        new_id = new_result.get("id")

        # Step 3: 标记旧记忆为superseded (软删除, 保留可追溯)
        if invalidate_old:
            update_data = {
                "tags": old_tags + ["superseded"],
                "metadata": {
                    **old_result.get("metadata", {}),
                    "superseded_by": new_id,
                    "invalidation_reason": f"replaced_by:{agent_id}:{reason}",
                },
            }
            self._api_put(f"/api/memory/{entry_id}", update_data)

        return {
            "status": "success",
            "old_memory_id": entry_id,
            "new_memory_id": new_id,
            "supersede_chain": {
                "old_id": entry_id,
                "new_id": new_id,
                "reason": reason,
                "agent_id": agent_id,
                "old_invalidated": invalidate_old,
            },
            "system": SYSTEM_NAME,
        }

    def _handle_memory_rethink(self, args: dict) -> dict:
        """memory_rethink — Agent完全重写一个记忆块

        MemGPT模式工具: 当Agent认为某个记忆块的整体表述需要重构时使用。
        比memory_replace更激进: 不保留旧内容结构, 完全重新组织。

        参数:
            entry_id: 必填, 要重写的记忆条目ID
            rewritten_content: 必填, 完全重写后的新内容
            rethink_reason: 必填, 重写理由 (强制Agent反思)
            agent_id: 可选, 执行重写的Agent身份
            preserve_tags: 可选, 是否保留原标签 (默认True)

        返回:
            original_id: 原记忆ID
            rewritten_id: 重写后记忆ID
            rethink_summary: 重写摘要
        """
        entry_id = args.get("entry_id", "").strip()
        if not entry_id:
            return {"status": "error", "detail": "entry_id 为必填项"}

        rewritten_content = args.get("rewritten_content", "").strip()
        if not rewritten_content:
            return {"status": "error", "detail": "rewritten_content 为必填项"}

        rethink_reason = args.get("rethink_reason", "").strip()
        if not rethink_reason:
            return {
                "status": "error",
                "detail": "rethink_reason 为必填项 (强制Agent反思)",
            }

        agent_id = args.get("agent_id", "self")
        preserve_tags = args.get("preserve_tags", True)

        # Step 1: 获取旧记忆
        old_result = self._api_get(f"/api/memory/{entry_id}")
        if not old_result or old_result.get("error"):
            return {"status": "error", "detail": f"找不到原记忆 {entry_id}"}

        old_layer = old_result.get("layer", "working")
        old_tags = old_result.get("tags", []) if preserve_tags else []
        old_content = old_result.get("content", "")

        # Step 2: 创建重写后的新记忆
        data = {
            "content": rewritten_content,
            "layer": old_layer,
            "tags": old_tags
            + [
                f"rethink_of:{entry_id}",
                f"agent_rethought:{agent_id}",
                "operation:rethink",
            ],
            "priority": "high",  # rethink默认高优先级, 因为是Agent主动反思
            "metadata": {
                "operation": "memory_rethink",
                "agent_id": agent_id,
                "rethink_reason": rethink_reason,
                "rethink_of": entry_id,
                "original_content_preview": old_content[:200] if old_content else "",
                "original_content_length": len(old_content),
                "rewritten_content_length": len(rewritten_content),
                "tool_source": "memgpt_pattern",
            },
        }

        new_result = self._api_post("/api/memory/", data)
        if not new_result or new_result.get("error"):
            return {"status": "error", "detail": f"重写记忆失败: {new_result}"}

        new_id = new_result.get("id")

        # Step 3: 将旧记忆标记为rethought (软归档)
        update_data = {
            "tags": old_result.get("tags", [])
            + ["rethought", f"rethought_by:{new_id}"],
            "metadata": {
                **old_result.get("metadata", {}),
                "rethought_by": new_id,
                "rethink_reason": rethink_reason,
            },
        }
        self._api_put(f"/api/memory/{entry_id}", update_data)

        return {
            "status": "success",
            "original_id": entry_id,
            "rewritten_id": new_id,
            "rethink_summary": {
                "reason": rethink_reason,
                "agent_id": agent_id,
                "original_length": len(old_content),
                "rewritten_length": len(rewritten_content),
                "layer": old_layer,
            },
            "system": SYSTEM_NAME,
        }

    # ═══════════════════════════════════════════════════════════════
    # P1-3: 多Agent记忆共享层 [v10-ready]
    # 借鉴Mem0/Zep多用户多Agent架构, 实现跨Agent记忆共享
    # scope体系: private (默认) / shared / team / global
    # ═══════════════════════════════════════════════════════════════

    def _handle_memory_share(self, args: dict) -> dict:
        """memory_share — Agent将自己的记忆共享给其他Agent

        Mem0/Zep模式工具: 实现跨Agent记忆共享。
        共享后, 目标Agent可通过memory_recall_shared检索到该记忆。

        参数:
            entry_id: 必填, 要共享的记忆条目ID
            owner_agent: 必填, 共享方Agent身份
            target_agents: 可选, 目标Agent列表 (空=所有Agent可访问)
            share_scope: 可选, 共享范围 (team/global), 默认team
            share_reason: 可选, 共享原因 (审计用)
            ttl_seconds: 可选, 共享有效期 (秒), 默认永久

        返回:
            shared_entry_id: 共享条目ID
            share_scope: 共享范围
            target_agents: 目标Agent列表
        """
        entry_id = args.get("entry_id", "").strip()
        if not entry_id:
            return {"status": "error", "detail": "entry_id 为必填项"}

        owner_agent = args.get("owner_agent", "").strip()
        if not owner_agent:
            return {"status": "error", "detail": "owner_agent 为必填项"}

        target_agents = args.get("target_agents", [])  # 空=所有Agent
        share_scope = args.get("share_scope", "team").lower()
        if share_scope not in {"team", "global"}:
            return {"status": "error", "detail": "share_scope 必须是 team 或 global"}
        share_reason = args.get("share_reason", "")
        ttl_seconds = args.get("ttl_seconds", 0)  # 0=永久

        # Step 1: 获取原记忆
        old_result = self._api_get(f"/api/memory/{entry_id}")
        if not old_result or old_result.get("error"):
            return {"status": "error", "detail": f"找不到原记忆 {entry_id}"}

        old_content = old_result.get("content", "")
        old_layer = old_result.get("layer", "working")
        old_tags = old_result.get("tags", [])

        # Step 2: 创建共享副本 (在episodic层, 带shared标记)
        expires_at = time.time() + ttl_seconds if ttl_seconds > 0 else None
        data = {
            "content": old_content,
            "layer": "episodic",  # 共享记忆统一存episodic层
            "tags": old_tags
            + [
                f"shared_by:{owner_agent}",
                f"share_scope:{share_scope}",
                "operation:share",
            ]
            + (
                [f"shared_to:{a}" for a in target_agents]
                if target_agents
                else ["shared_to:*"]
            ),
            "priority": "high",  # 共享记忆默认高优先级
            "metadata": {
                "operation": "memory_share",
                "owner_agent": owner_agent,
                "target_agents": target_agents,
                "share_scope": share_scope,
                "share_reason": share_reason,
                "source_entry_id": entry_id,
                "source_layer": old_layer,
                "created_at": time.time(),
                "expires_at": expires_at,
                "ttl_seconds": ttl_seconds,
                "tool_source": "mem0_pattern",
            },
        }

        new_result = self._api_post("/api/memory/", data)
        if not new_result or new_result.get("error"):
            return {"status": "error", "detail": f"创建共享记忆失败: {new_result}"}

        shared_id = new_result.get("id")

        return {
            "status": "success",
            "shared_entry_id": shared_id,
            "source_entry_id": entry_id,
            "share_scope": share_scope,
            "target_agents": target_agents if target_agents else ["*"],
            "owner_agent": owner_agent,
            "expires_at": expires_at,
            "system": SYSTEM_NAME,
        }

    def _handle_memory_recall_shared(self, args: dict) -> dict:
        """memory_recall_shared — Agent检索其他Agent共享的记忆

        Mem0/Zep模式工具: 跨Agent记忆检索。
        自动按target_agents和share_scope过滤。

        参数:
            requesting_agent: 必填, 请求方Agent身份
            query: 可选, 检索查询 (空=列出所有可访问共享记忆)
            owner_agent_filter: 可选, 仅检索指定owner共享的记忆
            share_scope_filter: 可选, 范围过滤 (team/global)
            limit: 可选, 结果上限, 默认10

        返回:
            results: 共享记忆列表
            accessible_count: 可访问总数
        """
        requesting_agent = args.get("requesting_agent", "").strip()
        if not requesting_agent:
            return {"status": "error", "detail": "requesting_agent 为必填项"}

        query = args.get("query", "").strip()
        owner_filter = args.get("owner_agent_filter", "").strip()
        scope_filter = args.get("share_scope_filter", "").strip().lower()
        limit = min(int(args.get("limit", 10)), 50)

        # Step 1: 检索所有带shared标记的记忆
        # 使用search_memories底层API, 然后客户端过滤
        search_query = query if query else "shared_by"
        result = self._api_post(
            "/api/search/",
            {
                "query": search_query,
                "limit": 100,  # 多取一些用于客户端过滤
                "layer": "episodic",
            },
        )

        # [FIX-B1] _api_post 可能返回 list (API直接返回数组) 或 dict
        if result is None:
            return {"status": "error", "detail": "检索失败: API返回None"}
        if isinstance(result, list):
            candidates = result
        elif isinstance(result, dict):
            if result.get("error"):
                return {"status": "error", "detail": f"检索失败: {result.get('error')}"}
            candidates = result.get("results", [])
        else:
            return {
                "status": "error",
                "detail": f"检索失败: 未知返回类型 {type(result)}",
            }

        # Step 2: 客户端过滤 — 检查权限
        accessible = []
        for item in candidates:
            tags = item.get("tags", [])
            metadata = item.get("metadata", {})

            # 必须是shared记忆
            if "operation:share" not in tags:
                continue

            # 检查过期
            expires_at = metadata.get("expires_at")
            if expires_at and time.time() > expires_at:
                continue

            # 检查owner过滤
            if owner_filter and metadata.get("owner_agent") != owner_filter:
                continue

            # 检查scope过滤
            item_scope = metadata.get("share_scope", "team")
            if scope_filter and item_scope != scope_filter:
                continue

            # 检查target_agents权限
            target_agents = metadata.get("target_agents", [])
            if target_agents:  # 非空列表, 必须包含请求方
                if requesting_agent not in target_agents and "*" not in target_agents:
                    continue
            # 空target_agents + global scope = 任何Agent可访问
            elif item_scope != "global":
                continue

            accessible.append(item)

        # 截取limit
        accessible = accessible[:limit]

        return {
            "status": "success",
            "requesting_agent": requesting_agent,
            "query": query,
            "results": accessible,
            "accessible_count": len(accessible),
            "system": SYSTEM_NAME,
        }

    def _handle_memory_list_shared(self, args: dict) -> dict:
        """memory_list_shared — 列出当前Agent可访问的所有共享记忆

        参数:
            requesting_agent: 必填, 请求方Agent身份
            include_expired: 可选, 是否包含过期记忆 (默认False)
            limit: 可选, 结果上限, 默认20

        返回:
            shared_memories: 共享记忆列表
            total: 总数
        """
        requesting_agent = args.get("requesting_agent", "").strip()
        if not requesting_agent:
            return {"status": "error", "detail": "requesting_agent 为必填项"}

        include_expired = args.get("include_expired", False)
        limit = min(int(args.get("limit", 20)), 100)

        # 复用recall_shared逻辑 (空query=列出全部)
        recall_args = {
            "requesting_agent": requesting_agent,
            "query": "",
            "limit": limit,
        }
        if include_expired:
            # 不过滤过期, 这里直接走原始检索
            result = self._api_post(
                "/api/search/",
                {
                    "query": "operation:share",
                    "limit": limit,
                    "layer": "episodic",
                },
            )
            # [FIX-B1] _api_post 可能返回 list 或 dict
            if result is None:
                return {"status": "error", "detail": "检索失败: API返回None"}
            if isinstance(result, list):
                results_list = result[:limit]
                return {
                    "status": "success",
                    "shared_memories": results_list,
                    "total": len(results_list),
                    "include_expired": True,
                    "system": SYSTEM_NAME,
                }
            if isinstance(result, dict) and result.get("error"):
                return {"status": "error", "detail": result}
            results_list = (
                result.get("results", [])[:limit] if isinstance(result, dict) else []
            )
            return {
                "status": "success",
                "shared_memories": results_list,
                "total": len(results_list),
                "include_expired": True,
                "system": SYSTEM_NAME,
            }

        return self._handle_memory_recall_shared(recall_args)

    def _handle_search_quick(self, args: dict) -> dict:
        """快速关键词搜索 (对应 GET /api/search/quick)"""
        query = args.get("query", "")
        limit = args.get("limit", 10)
        if not query:
            return {"status": "error", "detail": "query 为必填项"}

        result = self._api_get(
            f"/api/search/quick?q={urllib.parse.quote(query)}&limit={limit}"
        )
        # 【修复】端点可能返回list或dict，统一处理
        if isinstance(result, list):
            return {
                "status": "success",
                "query": query,
                "count": len(result),
                "results": result[:limit],
                "system": SYSTEM_NAME,
            }
        if isinstance(result, dict) and not result.get("error"):
            results = result.get("results", [])
            return {
                "status": "success",
                "query": query,
                "count": len(results),
                "results": results,
                "system": SYSTEM_NAME,
            }
        return {"status": "error", "detail": result}
