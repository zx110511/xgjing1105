# -*- coding: utf-8-sig -*-
"""tianji_mcp_server_core.py — TianjiMCPServerCoreMixin (SSS-PhaseB)

从 tianji_mcp_server.py 拆分的方法组: core
"""

import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

# ── 模块级常量 (SSS-PhaseB拆分后补全) ──────────────────

_STDOUT = sys.stdout
_STDERR = sys.stderr

TIANJI_API_URL = os.environ.get("TIANJI_API_URL", "http://127.0.0.1:8771")
TIANJI_HEALTH_URL = f"{TIANJI_API_URL}/api/health"
SYSTEM_NAME = os.environ.get("SYSTEM_NAME", "天机-忆库")
SYSTEM_VERSION = os.environ.get("SYSTEM_VERSION", "9.1.0")
SYSTEM_TAG = os.environ.get("SYSTEM_TAG", "MEM-ENGINE")

TOOL_AGENT_MAPPING: dict = {}
try:
    from core.memory.amim import TOOL_AGENT_MAPPING as _TAM  # type: ignore

    TOOL_AGENT_MAPPING = _TAM
except Exception:
    pass

# 工具列表 (由tianji_mcp_server.py定义完整版，此处为默认值)
# 直接运行时从__main__覆盖；包导入时从tianji_mcp_server模块获取
try:
    _main_mod = sys.modules.get("__main__")
    if _main_mod and hasattr(_main_mod, "ALL_TOOLS"):
        ALL_TOOLS = _main_mod.ALL_TOOLS
        BASIC_TOOLS = _main_mod.BASIC_TOOLS
        ADVANCED_TOOLS = _main_mod.ADVANCED_TOOLS
    else:
        ALL_TOOLS: list[dict] = []
        BASIC_TOOLS: list[dict] = []
        ADVANCED_TOOLS: list[dict] = []
except Exception:
    ALL_TOOLS: list[dict] = []
    BASIC_TOOLS: list[dict] = []
    ADVANCED_TOOLS: list[dict] = []


# 编码安全辅助
def _encoding_safe_text(text: str, _label: str = "") -> str:
    """确保文本不含BOM和非法字符"""
    if isinstance(text, bytes):
        text = text.decode("utf-8-sig", errors="replace")
    return text.replace("\ufeff", "").replace("\ufffd", "?")


def _encoding_safe_dict(d: dict, _label: str = "") -> dict:
    """递归清理字典中的编码问题"""
    if not isinstance(d, dict):
        return d
    return {
        k: (_encoding_safe_text(v, f"{_label}:{k}") if isinstance(v, str) else v)
        for k, v in d.items()
    }


# [FIX-MCP-PROXY] 禁用HTTP代理，避免MCP server继承Trae IDE代理设置导致超时
# Trae IDE可能设置HTTP_PROXY环境变量，urllib默认会使用代理，导致请求被路由到不存在的代理
_NO_PROXY_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))


class TianjiMCPServerCoreMixin:
    """core方法组Mixin"""

    def __init__(self, recorder: Any | None = None, learning_engine: Any | None = None):
        self.api_url = TIANJI_API_URL
        self._api_available = False
        self._recorder = recorder
        self._learning_engine = learning_engine
        self._errors = 0
        self._tool_call_count = 0
        self._tool_error_count = 0
        self._enforcement_hook = None
        self._current_session_id: str | None = None

        self._amim = None
        try:
            from core.memory.amim import TOOL_AGENT_MAPPING as _TOOL_AGENT_MAPPING
            from core.memory.amim import AgentMCPIntegrationManager

            global TOOL_AGENT_MAPPING
            TOOL_AGENT_MAPPING = _TOOL_AGENT_MAPPING
            self._amim = AgentMCPIntegrationManager()
        except Exception:
            pass

        self._evo_loop = None
        try:
            from core.processors.evolution_loop import EvolutionLoop

            self._evo_loop = EvolutionLoop(
                module_name="mcp_server",
                effectiveness_fn=self._calc_mcp_effectiveness,
                learn_fn=self._learn_from_mcp,
                evolve_fn=self._evolve_mcp_config,
                mutable_config={
                    "api_timeout": 10,
                    "health_check_interval": 60,
                },
                recorder=recorder,
                learning_engine=learning_engine,
            )
        except Exception:
            pass

        self._check_api()

    def _check_api(self):
        try:
            req = urllib.request.Request(TIANJI_HEALTH_URL)
            # [FIX-MCP-PROXY] 使用无代理opener，避免继承Trae IDE代理设置
            r = _NO_PROXY_OPENER.open(req, timeout=3)
            self._api_available = r.status == 200
        except Exception:
            self._api_available = False

        if self._evo_loop is not None:
            try:
                self._evo_loop.record_action(
                    action="health_check",
                    state_before={"api_available": not self._api_available},
                    state_after={
                        "api_available": self._api_available,
                        "api_url": self.api_url,
                    },
                )
            except Exception:
                pass

    def set_enforcement_hook(self, hook):
        self._enforcement_hook = hook

    def set_session_id(self, session_id: str):
        self._current_session_id = session_id

    def _api_post(self, path: str, data: dict) -> dict | None:
        import os as _os
        import time as _time

        _diag_log = "D:\\元初系统\\天机v9.1\\.tianji\\mcp_post_diag.log"
        _t0 = _time.time()
        try:
            # [DIAG] 记录入口时间和环境变量
            try:
                _os.makedirs(_os.path.dirname(_diag_log), exist_ok=True)
                with open(_diag_log, "a", encoding="utf-8") as _f:
                    _f.write(
                        f"[{_time.strftime('%H:%M:%S')}] POST {path} START pid={_os.getpid()}\n"
                    )
                    _f.write(
                        f"  HTTP_PROXY={_os.environ.get('HTTP_PROXY', '<unset>')}\n"
                    )
                    _f.write(
                        f"  HTTPS_PROXY={_os.environ.get('HTTPS_PROXY', '<unset>')}\n"
                    )
                    _f.write(f"  NO_PROXY={_os.environ.get('NO_PROXY', '<unset>')}\n")
                    _f.write(f"  api_url={self.api_url}\n")
                    _f.flush()
            except Exception:
                pass

            safe_data = _encoding_safe_dict(data, f"post:{path}")
            payload = json.dumps(safe_data, ensure_ascii=False).encode("utf-8-sig")
            req = urllib.request.Request(
                f"{self.api_url}{path}",
                data=payload,
                headers={"Content-Type": "application/json; charset=utf-8-sig"},
                method="POST",
            )
            # [FIX-MCP-PROXY] 使用无代理opener，避免Trae IDE代理设置导致超时
            _t1 = _time.time()
            r = _NO_PROXY_OPENER.open(req, timeout=60)
            _t2 = _time.time()
            raw = r.read()
            _t3 = _time.time()
            result = json.loads(raw.decode("utf-8-sig", errors="replace"))
            _t4 = _time.time()
            try:
                with open(_diag_log, "a", encoding="utf-8") as _f:
                    _f.write(
                        f"  urlopen={_t2 - _t1:.3f}s read={_t3 - _t2:.3f}s json={_t4 - _t3:.3f}s total={_t4 - _t0:.3f}s\n"
                    )
                    _f.write(
                        f"  STATUS=success result_id={result.get('id') if isinstance(result, dict) else 'N/A'}\n\n"
                    )
                    _f.flush()
            except Exception:
                pass
            return (
                _encoding_safe_dict(result, f"post_resp:{path}")
                if isinstance(result, dict)
                else result
            )
        except urllib.error.HTTPError as e:
            try:
                body = e.read().decode("utf-8-sig", errors="replace")
                return {
                    "error": f"HTTP {e.code}: {_encoding_safe_text(body[:500], 'http_error')}"
                }
            except Exception:
                return {"error": f"HTTP {e.code}: {e.reason}"}
        except Exception as e:
            _t_err = _time.time()
            try:
                with open(_diag_log, "a", encoding="utf-8") as _f:
                    _f.write(f"  EXCEPTION after {_t_err - _t0:.3f}s: {e}\n\n")
                    _f.flush()
            except Exception:
                pass
            return {"error": _encoding_safe_text(str(e), "api_post_exception")}

    def _api_put(self, path: str, data: dict) -> dict | None:
        """HTTP PUT 请求 (用于 memory_update 等更新操作)"""
        try:
            safe_data = _encoding_safe_dict(data, f"put:{path}")
            payload = json.dumps(safe_data, ensure_ascii=False).encode("utf-8-sig")
            req = urllib.request.Request(
                f"{self.api_url}{path}",
                data=payload,
                headers={"Content-Type": "application/json; charset=utf-8-sig"},
                method="PUT",
            )
            # [FIX-MCP-PROXY] 使用无代理opener
            r = _NO_PROXY_OPENER.open(req, timeout=30)
            raw = r.read()
            result = json.loads(raw.decode("utf-8-sig", errors="replace"))
            return (
                _encoding_safe_dict(result, f"put_resp:{path}")
                if isinstance(result, dict)
                else result
            )
        except urllib.error.HTTPError as e:
            try:
                body = e.read().decode("utf-8-sig", errors="replace")
                return {
                    "error": f"HTTP {e.code}: {_encoding_safe_text(body[:500], 'http_error')}"
                }
            except Exception:
                return {"error": f"HTTP {e.code}: {e.reason}"}
        except Exception as e:
            return {"error": _encoding_safe_text(str(e), "api_put_exception")}

    def _api_get(self, path: str, params: dict | None = None) -> dict | None:
        try:
            url = f"{self.api_url}{path}"
            if params and isinstance(params, dict):
                safe_params = {
                    k: _encoding_safe_text(v, f"get:{path}.{k}")
                    if isinstance(v, str)
                    else v
                    for k, v in params.items()
                    if v is not None
                }
                qs = urllib.parse.urlencode(safe_params)
                url = f"{url}?{qs}"
            req = urllib.request.Request(url)
            # [FIX-MCP-PROXY] 使用无代理opener
            r = _NO_PROXY_OPENER.open(req, timeout=10)
            raw = r.read()
            result = json.loads(raw.decode("utf-8-sig", errors="replace"))
            return (
                _encoding_safe_dict(result, f"get_resp:{path}")
                if isinstance(result, dict)
                else result
            )
        except urllib.error.HTTPError as e:
            try:
                body = e.read().decode("utf-8-sig", errors="replace")
                return {
                    "error": f"HTTP {e.code}: {_encoding_safe_text(body[:500], 'http_error')}"
                }
            except Exception:
                return {"error": f"HTTP {e.code}: {e.reason}"}
        except Exception as e:
            return {"error": _encoding_safe_text(str(e), "api_get_exception")}

    def _make_response(
        self, result: Any = None, error: Any = None, req_id: Any = None
    ) -> dict:
        response: dict[str, Any] = {"jsonrpc": "2.0"}
        if req_id is not None:
            response["id"] = req_id
        if error:
            response["error"] = (
                error
                if isinstance(error, dict)
                else {"code": -32603, "message": str(error)}
            )
        elif result is not None:
            response["result"] = result
        return response

    def handle_initialize(self, params: dict, req_id: Any) -> dict:
        result = {
            "protocolVersion": "2024-11-05",
            "capabilities": {"tools": {"listChanged": True}, "logging": {}},
            "serverInfo": {
                "name": "tianji-memory-engine",
                "version": SYSTEM_VERSION,
                "system": SYSTEM_NAME,
                "tag": SYSTEM_TAG,
                "api_url": self.api_url,
                "api_available": self._api_available,
                "tool_count": len(ALL_TOOLS),
            },
        }

        if self._evo_loop is not None:
            try:
                self._evo_loop.record_action(
                    action="handle_initialize",
                    state_before={},
                    state_after={
                        "api_available": self._api_available,
                        "tool_count": len(ALL_TOOLS),
                        "version": SYSTEM_VERSION,
                    },
                )
            except Exception:
                pass

        return self._make_response(result, req_id=req_id)

    def handle_tools_list(self, params: dict, req_id: Any) -> dict:
        enhanced_tools = []
        for tool in ALL_TOOLS:
            tool_info = dict(tool)
            tool_name = tool["name"]
            if self._amim is not None and tool_name in TOOL_AGENT_MAPPING:
                mapping = TOOL_AGENT_MAPPING[tool_name]
                tool_info["owner_agent"] = mapping.get("owner", "unknown")
                tool_info["delegate_agents"] = mapping.get("delegates", [])
                tool_info["description_full"] = mapping.get(
                    "description", tool.get("description", "")
                )
                owner_agent = self._amim.get_agent(mapping.get("owner", ""))
                if owner_agent:
                    tool_info["mcp_server"] = owner_agent.mcp_server
                    tool_info["owner_layer"] = f"L{owner_agent.layer.value}"
                    tool_info["owner_name"] = owner_agent.name
            else:
                tool_info["owner_agent"] = "system"
                tool_info["delegate_agents"] = ["*"]
                tool_info["mcp_server"] = "memory-engine-global"
            enhanced_tools.append(tool_info)
        return self._make_response(
            {"tools": enhanced_tools, "amim_available": self._amim is not None},
            req_id=req_id,
        )

    def handle_tools_call(self, params: dict, req_id: Any) -> dict:
        name = params.get("name", "")
        arguments = params.get("arguments", {})

        if not self._api_available:
            self._check_api()
            if not self._api_available:
                return self._make_response(
                    error={
                        "code": -32603,
                        "message": f"天机API不可用 ({self.api_url})",
                    },
                    req_id=req_id,
                )

        handler_map = {
            "memory_remember": self._handle_remember,
            "memory_recall": self._handle_recall,
            "memory_forget": self._handle_forget,
            "memory_stats": self._handle_stats,
            "memory_capacity": self._handle_capacity,
            "memory_consolidate": self._handle_consolidate,
            "memory_update": self._handle_memory_update,
            "memory_insert": self._handle_memory_insert,
            "memory_replace": self._handle_memory_replace,
            "memory_rethink": self._handle_memory_rethink,
            "memory_share": self._handle_memory_share,
            "memory_recall_shared": self._handle_memory_recall_shared,
            "memory_list_shared": self._handle_memory_list_shared,
            "search_memories": self._handle_search,
            "get_memory": self._handle_get_memory,
            "list_memories": self._handle_list_memories,
            "build_working_representation": self._handle_build_repr,
            "run_reflective_cycle": self._handle_reflective,
            "get_session_digest": self._handle_session_digest,
            "explain_memory_lineage": self._handle_lineage,
            "tianji_health": self._handle_health,
            "tianji_help": self._handle_help,
            "tianji_classify": self._handle_classify,
            "tianji_auto_tag": self._handle_auto_tag,
            "tianji_summarize": self._handle_summarize,
            "tianji_extract_knowledge": self._handle_extract_knowledge,
            "tianji_expand_query": self._handle_expand_query,
            "tianji_semantic_search": self._handle_semantic_search,
            "tianji_intercept": self._handle_intercept,
            "tianji_normalize": self._handle_normalize,
            "tianji_disambiguate": self._handle_disambiguate,
            "tianji_export": self._handle_export,
            "tianji_summarize_conversation": self._handle_summarize_conv,
            "tianji_tool_owner": self._handle_tool_owner,
            "tianji_amim_status": self._handle_amim_status,
            "tianji_operation_header": self._handle_operation_header,
            "trae_stream_capture": self._handle_trae_stream_capture,
            "trae_stream_snapshot": self._handle_trae_stream_snapshot,
            "trae_monitoring_stats": self._handle_trae_monitoring_stats,
            "memory_build_graph": self._handle_memory_build_graph,
            "memory_query_graph": self._handle_memory_query_graph,
            "memory_evolve_self": self._handle_memory_evolve_self,
            "memory_learn_skill": self._handle_memory_learn_skill,
            "memory_capture_multimodal": self._handle_memory_capture_multimodal,
            # 以下4个工具已迁移至 agent-framework-global MCP Server (去重)
            # "context_extract", "agent_dispatch", "system_status", "rule_evaluate"
            # 新增2个工具 (填补API端点覆盖缺口)
            "memory_update": self._handle_memory_update,
            "search_quick": self._handle_search_quick,
        }

        handler = handler_map.get(name)
        if not handler:
            return self._make_response(
                error={"code": -32601, "message": f"Unknown tool: {name}"},
                req_id=req_id,
            )

        try:
            start_time = time.time()
            result = handler(arguments)
            call_duration = (time.time() - start_time) * 1000
            self._tool_call_count += 1

            params_text = str(arguments)[:300] if arguments else ""
            result_text = str(result)[:300] if result else ""

            if self._enforcement_hook and self._current_session_id:
                try:
                    self._enforcement_hook.register_mcp_call(
                        session_id=self._current_session_id,
                        tool_name=name,
                        params_summary=params_text,
                        result_summary=result_text,
                        duration_ms=call_duration,
                        status="success",
                    )
                except Exception:
                    pass

            tool_owner_info = {}
            if self._amim is not None and name in TOOL_AGENT_MAPPING:
                mapping = TOOL_AGENT_MAPPING[name]
                tool_owner_info = {
                    "owner_agent": mapping.get("owner", "unknown"),
                    "mcp_server": self._amim.get_agent(
                        mapping.get("owner", "")
                    ).mcp_server
                    if self._amim.get_agent(mapping.get("owner", ""))
                    else "unknown",
                }

            if self._evo_loop is not None:
                try:
                    self._evo_loop.record_action(
                        action="tool_call",
                        state_before={"tool": name},
                        state_after={
                            "tool": name,
                            "success": True,
                            "total_calls": self._tool_call_count,
                            "total_errors": self._tool_error_count,
                            **tool_owner_info,
                        },
                    )
                except Exception:
                    pass

            return self._make_response(
                {
                    "content": [
                        {
                            "type": "text",
                            "text": json.dumps(result, ensure_ascii=False, indent=2),
                        }
                    ]
                },
                req_id=req_id,
            )
        except Exception as e:
            self._tool_error_count += 1

            if self._enforcement_hook and self._current_session_id:
                try:
                    self._enforcement_hook.register_mcp_call(
                        session_id=self._current_session_id,
                        tool_name=name,
                        params_summary=str(arguments)[:300],
                        result_summary=str(e)[:300],
                        duration_ms=0.0,
                        status="error",
                    )
                except Exception:
                    pass

            if self._evo_loop is not None:
                try:
                    self._evo_loop.record_action(
                        action="tool_call",
                        state_before={"tool": name},
                        state_after={
                            "tool": name,
                            "success": False,
                            "error": str(e)[:100],
                            "total_calls": self._tool_call_count,
                            "total_errors": self._tool_error_count,
                        },
                    )
                except Exception:
                    pass

            return self._make_response(
                error={"code": -32603, "message": f"Tool execution error: {e}"},
                req_id=req_id,
            )

    def run(self):
        def _log(msg: str):
            try:
                _STDERR.write(msg + "\n")
                _STDERR.flush()
            except Exception:
                pass

        _log(f"[{SYSTEM_TAG}] MCP Server v{SYSTEM_VERSION} starting (stdio)...")
        _log(f"[{SYSTEM_TAG}] API: {self.api_url} (available: {self._api_available})")
        _log(
            f"[{SYSTEM_TAG}] Tools: {len(ALL_TOOLS)} ({len(BASIC_TOOLS)} basic + {len(ADVANCED_TOOLS)} advanced)"
        )
        _log(
            f"[{SYSTEM_TAG}] Encoding: stdin=utf-8-sig | stdout/stderr=utf-8 (BOM-free for MCP protocol)"
        )
        _log(
            f"[{SYSTEM_TAG}] AMIM M37: {'available' if self._amim else 'unavailable'} (agents: {self._amim.agent_count if self._amim else 0})"
        )

        for line in sys.stdin:
            line = line.strip()
            if not line:
                continue

            try:
                raw_line = _encoding_safe_text(line, "stdin_request")
                request = json.loads(raw_line)
                if isinstance(request.get("params"), dict):
                    request["params"] = _encoding_safe_dict(
                        request["params"], f"req_params:{request.get('method', '?')}"
                    )
            except json.JSONDecodeError:
                continue

            method = request.get("method", "")
            params = request.get("params", {})
            req_id = request.get("id")

            if method == "initialize":
                response = self.handle_initialize(params, req_id)
            elif method == "notifications/initialized":
                continue
            elif method == "tools/list":
                response = self.handle_tools_list(params, req_id)
            elif method == "tools/call":
                response = self.handle_tools_call(params, req_id)
            elif method == "ping":
                response = self._make_response({"status": "ok"}, req_id=req_id)
            else:
                response = self._make_response(
                    error={"code": -32601, "message": f"Method not found: {method}"},
                    req_id=req_id,
                )

            safe_output = json.dumps(response, ensure_ascii=False)
            _STDOUT.write(_encoding_safe_text(safe_output + "\n", "stdout_response"))
            _STDOUT.flush()

    def tick(self):
        if self._evo_loop is not None:
            try:
                self._evo_loop.tick()
            except Exception:
                pass

    def get_stats(self) -> dict:
        return {
            "health": self.health(),
            "version": "8.1",
            "api_available": self._api_available,
            "tool_call_count": self._tool_call_count,
            "tool_error_count": self._tool_error_count,
            "evo_loop": self._evo_loop.get_stats() if self._evo_loop else {},
        }

    def health(self) -> dict[str, Any]:
        return {
            "status": "ready" if self._api_available else "degraded",
            "version": "8.1",
            "api_available": self._api_available,
            "api_url": self.api_url,
            "tool_call_count": self._tool_call_count,
            "tool_error_count": self._tool_error_count,
            "tools_total": len(ALL_TOOLS),
            "errors": self._errors,
            "evo_loop_active": self._evo_loop is not None,
            "recorder_attached": self._recorder is not None,
            "amim_available": self._amim is not None,
            "amim_agents": self._amim.agent_count if self._amim else 0,
        }
