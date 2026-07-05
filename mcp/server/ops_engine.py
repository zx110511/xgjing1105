r"""
天机-运维 (Ops Engine) - MCP Server
=============================================
DevOps运维 | 部署管理 + 资源调度 + 服务监控

Tools (6 total):
  deploy_service, check_deployment, rollback_deployment,
  get_resource_usage, scale_service, list_services
"""

import io
import json
import os
import sys
import urllib.request
from pathlib import Path

_SELF_DIR = Path(__file__).resolve().parent.parent.parent
if str(_SELF_DIR) not in sys.path:
    sys.path.insert(0, str(_SELF_DIR))

try:
    from config import PROJECT_ROOT, TIANJI_ROOT
except Exception:
    PROJECT_ROOT = _SELF_DIR
    TIANJI_ROOT = _SELF_DIR

if sys.platform == "win32":
    try:
        sys.stdin = io.TextIOWrapper(sys.stdin.buffer, encoding="utf-8-sig")
        sys.stdout = io.TextIOWrapper(
            sys.stdout.buffer, encoding="utf-8", line_buffering=True
        )
        sys.stderr = io.TextIOWrapper(
            sys.stderr.buffer, encoding="utf-8", line_buffering=True
        )
    except Exception:
        pass

_STDOUT = sys.stdout
_STDERR = sys.stderr

TIANJI_API_URL = os.environ.get("TIANJI_API_URL", "http://127.0.0.1:8771")
SYSTEM_NAME = "天机-运维"
SYSTEM_VERSION = "9.1.0"

SERVER_TOOLS = [
    {
        "name": "deploy_service",
        "title": "运维·服务部署",
        "description": "部署指定服务到目标环境。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "service_name": {"type": "string", "description": "服务名称"},
                "environment": {
                    "type": "string",
                    "description": "目标环境",
                    "enum": ["dev", "staging", "production"],
                },
                "config": {"type": "object", "description": "部署配置"},
            },
            "required": ["service_name"],
        },
    },
    {
        "name": "check_deployment",
        "title": "运维·部署检查",
        "description": "检查服务部署状态。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "service_name": {"type": "string", "description": "服务名称"}
            },
            "required": ["service_name"],
        },
    },
    {
        "name": "rollback_deployment",
        "title": "运维·部署回滚",
        "description": "回滚服务到上一版本。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "service_name": {"type": "string", "description": "服务名称"},
                "version": {"type": "string", "description": "目标版本"},
            },
            "required": ["service_name"],
        },
    },
    {
        "name": "get_resource_usage",
        "title": "运维·资源使用",
        "description": "获取系统资源使用情况。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "resource_type": {
                    "type": "string",
                    "description": "资源类型",
                    "enum": ["cpu", "memory", "disk", "network", "all"],
                },
                "duration": {
                    "type": "string",
                    "description": "统计周期",
                    "default": "1h",
                },
            },
        },
    },
    {
        "name": "scale_service",
        "title": "运维·服务扩缩",
        "description": "调整服务实例数量。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "service_name": {"type": "string", "description": "服务名称"},
                "replicas": {"type": "integer", "description": "目标实例数"},
            },
            "required": ["service_name", "replicas"],
        },
    },
    {
        "name": "list_services",
        "title": "运维·服务列表",
        "description": "列出所有已部署的服务及其状态。",
        "inputSchema": {
            "type": "object",
            "properties": {"filter": {"type": "string", "description": "服务名过滤"}},
        },
    },
]


class OpsEngineServer:
    def __init__(self):
        self.api_url = TIANJI_API_URL
        self._api_available = False
        self._check_api()

    def _check_api(self):
        # [FIX-v9.1-conn-leak] with语句确保连接关闭
        try:
            req = urllib.request.Request(f"{self.api_url}/api/health")
            with urllib.request.urlopen(req, timeout=3) as r:
                self._api_available = r.status == 200
        except Exception:
            self._api_available = False

    def _api_post(self, path, data):
        # [FIX-v9.1-conn-leak] with语句确保连接关闭
        # [FIX-MCP-CHECK-DEPLOYMENT] 增加超时时间：默认10秒→30秒，避免超时
        try:
            body = json.dumps(data, ensure_ascii=False).encode("utf-8")
            req = urllib.request.Request(
                f"{self.api_url}{path}",
                data=body,
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.loads(r.read().decode("utf-8-sig", errors="replace"))
        except Exception as e:
            return {"error": str(e)}

    def _api_get(self, path):
        # [FIX-MCP-405] GET方法调用，用于list类工具
        # [FIX-MCP-CHECK-DEPLOYMENT] 增加超时时间：默认10秒→30秒，避免超时
        try:
            req = urllib.request.Request(f"{self.api_url}{path}")
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.loads(r.read().decode("utf-8-sig", errors="replace"))
        except Exception as e:
            return {"error": str(e)}

    def _make_response(self, result=None, error=None, req_id=None):
        response = {"jsonrpc": "2.0"}
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

    def handle_initialize(self, params, req_id):
        return self._make_response(
            {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {"listChanged": True}},
                "serverInfo": {
                    "name": "ops-engine",
                    "version": SYSTEM_VERSION,
                    "system": SYSTEM_NAME,
                    "api_available": self._api_available,
                    "tool_count": len(SERVER_TOOLS),
                },
            },
            req_id=req_id,
        )

    def handle_tools_list(self, params, req_id):
        return self._make_response({"tools": SERVER_TOOLS}, req_id=req_id)

    def handle_tools_call(self, params, req_id):
        name = params.get("name", "")
        arguments = params.get("arguments", {})
        if not self._api_available:
            self._check_api()
        # [FIX-MCP-405] GET类工具用GET方法调用，避免405 Method Not Allowed
        GET_TOOLS = {
            "list_security_policies",
            "get_security_report",
            "list_processes",
            "list_scripts",
            "get_resource_usage",
            "list_services",
            "get_performance_metrics",
            "get_memory_profile",
            "get_cpu_profile",
            "list_profiling_sessions",
            "list_namespaces",
            "get_stats",
            "tool_help",
            "tool_schema",
        }
        if name in GET_TOOLS:
            handler = lambda a, n=name: self._api_get(f"/api/mcp/tools/{n}")
        else:
            handler = lambda a, n=name: self._api_post(f"/api/mcp/tools/{n}", a)
        try:
            result = handler(arguments)
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
            return self._make_response(
                error={"code": -32603, "message": str(e)}, req_id=req_id
            )

    def run(self):
        _STDERR.write(
            f"[{SYSTEM_NAME}] MCP Server v{SYSTEM_VERSION} starting (stdio)...\n"
        )
        _STDERR.write(
            f"[{SYSTEM_NAME}] API: {self.api_url} (available: {self._api_available})\n"
        )
        _STDERR.write(f"[{SYSTEM_NAME}] Tools: {len(SERVER_TOOLS)}\n")
        _STDERR.flush()
        for line in sys.stdin:
            line = line.strip()
            if not line:
                continue
            try:
                request = json.loads(line)
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
            _STDOUT.write(json.dumps(response, ensure_ascii=False) + "\n")
            _STDOUT.flush()


def main():
    server = OpsEngineServer()
    server.run()


if __name__ == "__main__":
    main()
