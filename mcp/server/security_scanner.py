r"""
天机-铁卫 (Security Scanner) - MCP Server
=============================================
安全审计 | 漏洞扫描 + 合规检查 + 安全报告

Tools (6 total):
  scan_vulnerabilities, check_compliance, get_security_report,
  scan_dependencies, check_permissions, list_security_policies
"""

import sys
import json
import os
import io
import http.client
import urllib.request
from typing import Any
from pathlib import Path

_SELF_DIR = Path(__file__).resolve().parent.parent.parent
if str(_SELF_DIR) not in sys.path:
    sys.path.insert(0, str(_SELF_DIR))

try:
    from config import TIANJI_ROOT, PROJECT_ROOT
except Exception:
    PROJECT_ROOT = _SELF_DIR
    TIANJI_ROOT = _SELF_DIR

if sys.platform == "win32":
    try:
        sys.stdin = io.TextIOWrapper(sys.stdin.buffer, encoding="utf-8-sig")
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", line_buffering=True)
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", line_buffering=True)
    except Exception:
        pass

_STDOUT = sys.stdout
_STDERR = sys.stderr

TIANJI_API_URL = os.environ.get("TIANJI_API_URL", "http://127.0.0.1:8771")
SYSTEM_NAME = "天机-铁卫"
SYSTEM_VERSION = "9.1.0"

SERVER_TOOLS = [
    {"name": "scan_vulnerabilities", "title": "铁卫·漏洞扫描", "description": "扫描代码库中的安全漏洞，包括OWASP Top 10和CWE常见漏洞。", "inputSchema": {"type": "object", "properties": {"target_path": {"type": "string", "description": "扫描目标路径"}, "scan_type": {"type": "string", "description": "扫描类型", "enum": ["full", "quick", "dependency", "code"], "default": "quick"}, "severity": {"type": "string", "description": "最低严重级别", "enum": ["low", "medium", "high", "critical"], "default": "medium"}}, "required": ["target_path"]}},
    {"name": "check_compliance", "title": "铁卫·合规检查", "description": "检查代码是否符合安全合规标准(OWASP AOS/ISO/SOC2等)。", "inputSchema": {"type": "object", "properties": {"standard": {"type": "string", "description": "合规标准", "enum": ["owasp", "iso27001", "soc2", "gdpr", "all"]}, "target_path": {"type": "string", "description": "检查目标路径"}}, "required": ["standard"]}},
    {"name": "get_security_report", "title": "铁卫·安全报告", "description": "生成安全扫描报告，包含漏洞摘要和修复建议。", "inputSchema": {"type": "object", "properties": {"report_type": {"type": "string", "description": "报告类型", "enum": ["summary", "detailed", "executive"], "default": "summary"}, "format": {"type": "string", "description": "输出格式", "enum": ["json", "markdown", "html"], "default": "json"}}}},
    {"name": "scan_dependencies", "title": "铁卫·依赖扫描", "description": "扫描项目依赖中的已知漏洞。", "inputSchema": {"type": "object", "properties": {"target_path": {"type": "string", "description": "项目路径"}, "include_dev": {"type": "boolean", "description": "包含开发依赖", "default": True}}}},
    {"name": "check_permissions", "title": "铁卫·权限检查", "description": "检查文件和目录的权限配置是否安全。", "inputSchema": {"type": "object", "properties": {"target_path": {"type": "string", "description": "检查目标路径"}, "check_type": {"type": "string", "description": "检查类型", "enum": ["file", "directory", "all"], "default": "all"}}}},
    {"name": "list_security_policies", "title": "铁卫·安全策略", "description": "列出当前生效的安全策略和规则。", "inputSchema": {"type": "object", "properties": {"policy_type": {"type": "string", "description": "策略类型", "enum": ["all", "enforcement", "monitoring", "alerting"]}}}},
]


class SecurityScannerServer:
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
        try:
            body = json.dumps(data, ensure_ascii=False).encode("utf-8")
            req = urllib.request.Request(f"{self.api_url}{path}", data=body, headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=10) as r:
                return json.loads(r.read().decode("utf-8-sig", errors="replace"))
        except Exception as e:
            return {"error": str(e)}

    def _api_get(self, path):
        # [FIX-MCP-405] GET方法调用，用于list类工具
        try:
            req = urllib.request.Request(f"{self.api_url}{path}")
            with urllib.request.urlopen(req, timeout=10) as r:
                return json.loads(r.read().decode("utf-8-sig", errors="replace"))
        except Exception as e:
            return {"error": str(e)}

    def _make_response(self, result=None, error=None, req_id=None):
        response = {"jsonrpc": "2.0"}
        if req_id is not None:
            response["id"] = req_id
        if error:
            response["error"] = error if isinstance(error, dict) else {"code": -32603, "message": str(error)}
        elif result is not None:
            response["result"] = result
        return response

    def handle_initialize(self, params, req_id):
        return self._make_response({"protocolVersion": "2024-11-05", "capabilities": {"tools": {"listChanged": True}}, "serverInfo": {"name": "security-scanner", "version": SYSTEM_VERSION, "system": SYSTEM_NAME, "api_available": self._api_available, "tool_count": len(SERVER_TOOLS)}}, req_id=req_id)

    def handle_tools_list(self, params, req_id):
        return self._make_response({"tools": SERVER_TOOLS}, req_id=req_id)

    def handle_tools_call(self, params, req_id):
        name = params.get("name", "")
        arguments = params.get("arguments", {})
        if not self._api_available:
            self._check_api()
        # [FIX-MCP-405] GET类工具用GET方法调用，避免405 Method Not Allowed
        GET_TOOLS = {"list_security_policies", "get_security_report", "list_processes", "list_scripts",
                     "get_resource_usage", "list_services", "get_performance_metrics", "get_memory_profile",
                     "get_cpu_profile", "list_profiling_sessions", "list_namespaces", "get_stats",
                     "tool_help", "tool_schema"}
        if name in GET_TOOLS:
            handler = lambda a, n=name: self._api_get(f"/api/mcp/tools/{n}")
        else:
            handler = lambda a, n=name: self._api_post(f"/api/mcp/tools/{n}", a)
        try:
            result = handler(arguments)
            return self._make_response({"content": [{"type": "text", "text": json.dumps(result, ensure_ascii=False, indent=2)}]}, req_id=req_id)
        except Exception as e:
            return self._make_response(error={"code": -32603, "message": str(e)}, req_id=req_id)

    def run(self):
        _STDERR.write(f"[{SYSTEM_NAME}] MCP Server v{SYSTEM_VERSION} starting (stdio)...\n")
        _STDERR.write(f"[{SYSTEM_NAME}] API: {self.api_url} (available: {self._api_available})\n")
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
                response = self._make_response(error={"code": -32601, "message": f"Method not found: {method}"}, req_id=req_id)
            _STDOUT.write(json.dumps(response, ensure_ascii=False) + "\n")
            _STDOUT.flush()


def main():
    server = SecurityScannerServer()
    server.run()


if __name__ == "__main__":
    main()
