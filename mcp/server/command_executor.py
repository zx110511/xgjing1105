r"""
天机-执行器 (Command Executor) - MCP Server
=============================================
进程管理 | 命令执行 + 进程监控 + 脚本运行

Tools (9 total):
  execute_command, check_command, stop_command,
  list_processes, get_process_info, kill_process,
  run_script, get_script_status, list_scripts
"""

import sys
import json
import os
import io
import subprocess
import http.client
import urllib.request
from pathlib import Path
from typing import Any

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
SYSTEM_NAME = "天机-执行器"
SYSTEM_VERSION = "9.1.0"

SERVER_TOOLS = [
    {
        "name": "execute_command",
        "title": "执行器·命令执行",
        "description": "执行系统命令并返回结果。支持超时设置和工作目录指定。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "要执行的命令"},
                "timeout": {"type": "integer", "description": "超时时间(秒)", "default": 30},
                "cwd": {"type": "string", "description": "工作目录"},
            },
            "required": ["command"],
        },
    },
    {
        "name": "check_command",
        "title": "执行器·命令状态",
        "description": "检查异步命令的执行状态和输出。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "command_id": {"type": "string", "description": "命令ID"},
            },
            "required": ["command_id"],
        },
    },
    {
        "name": "stop_command",
        "title": "执行器·停止命令",
        "description": "停止正在运行的异步命令。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "command_id": {"type": "string", "description": "命令ID"},
            },
            "required": ["command_id"],
        },
    },
    {
        "name": "list_processes",
        "title": "执行器·进程列表",
        "description": "列出当前运行的系统进程。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "filter": {"type": "string", "description": "进程名过滤"},
            },
        },
    },
    {
        "name": "get_process_info",
        "title": "执行器·进程详情",
        "description": "获取指定进程的详细信息。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "pid": {"type": "integer", "description": "进程ID"},
            },
            "required": ["pid"],
        },
    },
    {
        "name": "kill_process",
        "title": "执行器·终止进程",
        "description": "终止指定进程。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "pid": {"type": "integer", "description": "进程ID"},
                "force": {"type": "boolean", "description": "是否强制终止", "default": False},
            },
            "required": ["pid"],
        },
    },
    {
        "name": "run_script",
        "title": "执行器·脚本运行",
        "description": "运行项目中的脚本文件。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "script_path": {"type": "string", "description": "脚本路径"},
                "args": {"type": "array", "items": {"type": "string"}, "description": "脚本参数"},
            },
            "required": ["script_path"],
        },
    },
    {
        "name": "get_script_status",
        "title": "执行器·脚本状态",
        "description": "获取脚本运行状态。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "script_id": {"type": "string", "description": "脚本运行ID"},
            },
            "required": ["script_id"],
        },
    },
    {
        "name": "list_scripts",
        "title": "执行器·脚本列表",
        "description": "列出项目scripts目录中的可用脚本。",
        "inputSchema": {"type": "object", "properties": {}},
    },
]


class CommandExecutorServer:
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
        return self._make_response({
            "protocolVersion": "2024-11-05",
            "capabilities": {"tools": {"listChanged": True}},
            "serverInfo": {"name": "command-executor", "version": SYSTEM_VERSION, "system": SYSTEM_NAME, "api_available": self._api_available, "tool_count": len(SERVER_TOOLS)},
        }, req_id=req_id)

    def handle_tools_list(self, params, req_id):
        return self._make_response({"tools": SERVER_TOOLS}, req_id=req_id)

    def handle_tools_call(self, params, req_id):
        name = params.get("name", "")
        arguments = params.get("arguments", {})

        # [v9.1-fix] 进程管理工具本地直处理(不依赖后端API)
        _local_tools = {
            "execute_command": self._local_execute,
            "list_processes": self._local_list_processes,
            "get_process_info": self._local_get_process_info,
            "kill_process": self._local_kill_process,
            "run_script": self._local_run_script,
            "list_scripts": self._local_list_scripts,
            "check_command": self._local_check_command,
            "stop_command": self._local_stop_command,
            "get_script_status": self._local_get_script_status,
        }

        if name in _local_tools:
            try:
                result = _local_tools[name](arguments)
                return self._make_response(
                    {"content": [{"type": "text", "text": json.dumps(result, ensure_ascii=False, indent=2)}]},
                    req_id=req_id
                )
            except Exception as e:
                return self._make_response(error={"code": -32603, "message": str(e)}, req_id=req_id)

        # 非本地工具: 降级到API代理(兼容性保留)
        if not self._api_available:
            self._check_api()
        handler_map = {t["name"]: lambda a, n=name: self._api_post(f"/api/mcp/tools/{n}", a) for t in SERVER_TOOLS}
        handler = handler_map.get(name)
        if not handler:
            return self._make_response(error={"code": -32601, "message": f"Unknown tool: {name}"}, req_id=req_id)
        try:
            result = handler(arguments)
            return self._make_response({"content": [{"type": "text", "text": json.dumps(result, ensure_ascii=False, indent=2)}]}, req_id=req_id)
        except Exception as e:
            return self._make_response(error={"code": -32603, "message": str(e)}, req_id=req_id)

    # ====================================================================
    # 本地工具处理器 (v9.1-fix: 解决404问题)
    # ====================================================================

    def _local_execute(self, args: dict) -> dict:
        """执行Shell命令(本地)"""
        cmd = args.get("command", "")
        timeout = args.get("timeout", 30)
        cwd = args.get("cwd") or str(PROJECT_ROOT)
        try:
            result = subprocess.run(
                cmd, shell=True, capture_output=True, text=True,
                timeout=timeout, cwd=cwd, encoding="utf-8-sig", errors="replace"
            )
            return {
                "type": "text", "output": (result.stdout or "") + (result.stderr or ""),
                "returncode": result.returncode, "success": result.returncode == 0
            }
        except subprocess.TimeoutExpired:
            return {"type": "text", "output": f"[TIMEOUT] 命令超时({timeout}s)", "returncode": -1, "success": False}
        except Exception as e:
            return {"type": "text", "output": f"[ERROR] {e}", "returncode": -1, "success": False}

    def _local_list_processes(self, args: dict) -> dict:
        """列出系统进程"""
        filter_name = args.get("filter", "")
        try:
            cmd = ["tasklist", "/FO", "CSV", "/NH"]
            if filter_name:
                cmd.append(f"/FI")
                cmd.append(f"IMAGENAME eq {filter_name}*")
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10, encoding="utf-8-sig", errors="replace")
            lines = result.stdout.strip().split("\n")
            processes = []
            for line in lines:
                line = line.strip().strip('"')
                if not line:
                    continue
                parts = [p.strip().strip('"') for p in line.split('","')]
                if len(parts) >= 5:
                    processes.append({
                        "name": parts[0], "pid": int(parts[1]) if parts[1].isdigit() else 0,
                        "memory": parts[4] if len(parts) > 4 else ""
                    })
            return {"processes": processes[:50], "total": len(processes)}
        except Exception as e:
            return {"error": str(e), "processes": []}

    def _local_get_process_info(self, args: dict) -> dict:
        """获取进程详情"""
        # [FIX-MCP-PROCESS-INFO] 修复参数错误：支持process_id和pid两种参数名
        pid = args.get("process_id") or args.get("pid", 0)
        if not pid:
            return {"error": "参数缺失：需要提供 process_id 或 pid"}
        try:
            result = subprocess.run(
                ["wmic", "process", "where", f"ProcessId={pid}", "get", "Name,ProcessId,CommandLine,PageFileUsage", "/format:list"],
                capture_output=True, text=True, timeout=10, encoding="utf-8-sig", errors="replace"
            )
            info = {}
            for line in result.stdout.strip().split("\n"):
                if "=" in line:
                    k, v = line.split("=", 1)
                    info[k.strip()] = v.strip()
            return info or {"error": f"PID {pid} not found"}
        except Exception as e:
            return {"error": str(e)}

    def _local_kill_process(self, args: dict) -> dict:
        """终止进程"""
        pid = args.get("pid", 0)
        force = args.get("force", False)
        try:
            sig = "/F" if force else ""
            result = subprocess.run(["taskkill", sig, "/PID", str(pid)], capture_output=True, text=True, timeout=5)
            return {"pid": pid, "output": result.stdout.strip(), "success": result.returncode == 0}
        except Exception as e:
            return {"pid": pid, "error": str(e), "success": False}

    def _local_run_script(self, args: dict) -> dict:
        """运行项目脚本"""
        # [FIX-MCP-RUN-SCRIPT] 修复Win32错误：使用Python解释器执行脚本
        script_path = args.get("script_path", "")
        script_args = args.get("args", [])
        try:
            full_path = Path(script_path)
            if not full_path.is_absolute():
                full_path = PROJECT_ROOT / script_path
            # 使用Python解释器执行，避免Win32错误
            python_exe = sys.executable or "python"
            cmd = [python_exe, str(full_path)] + list(script_args)
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120, cwd=str(PROJECT_ROOT), encoding="utf-8-sig", errors="replace")
            return {"script": script_path, "output": (result.stdout or "") + (result.stderr or ""), "returncode": result.returncode, "success": result.returncode == 0}
        except Exception as e:
            return {"script": script_path, "error": str(e)}

    def _local_list_scripts(self, args: dict) -> dict:
        """列出可用脚本"""
        scripts_dir = PROJECT_ROOT / "scripts"
        scripts = []
        if scripts_dir.is_dir():
            for f in sorted(scripts_dir.glob("*.py")):
                scripts.append({"name": f.name, "path": str(f), "size": f.stat().st_size})
        return {"scripts": scripts, "directory": str(scripts_dir)}

    def _local_check_command(self, args: dict) -> dict:
        """检查异步命令状态(本地简化版)"""
        cid = args.get("command_id", "")
        return {"command_id": cid, "status": "unknown", "note": "本地模式不支持异步命令追踪"}

    def _local_stop_command(self, args: dict) -> dict:
        """停止运行中命令(本地简化版)"""
        cid = args.get("command_id", "")
        return {"command_id": cid, "status": "stopped", "note": "本地模式"}

    def _local_get_script_status(self, args: dict) -> dict:
        """获取脚本状态"""
        sid = args.get("script_id", "")
        return {"script_id": sid, "status": "unknown"}

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
    server = CommandExecutorServer()
    server.run()


if __name__ == "__main__":
    main()
