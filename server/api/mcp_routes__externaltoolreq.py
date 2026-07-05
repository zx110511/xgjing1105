# -*- coding: utf-8-sig -*-
"""mcp_routes__ExternalToolReq — 从 mcp_routes.py 拆分 (SSS-PhaseB)

源文件: mcp_routes.py
"""

import os
from pathlib import Path
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from server.api.utils import run_sync as _run
from server.deps import get_cognition, get_engine

# SSS-PhaseE: MCP路由器定义 (拆分时遗漏，与mcp_routes_searchperspectivememoriesrequest共享)
from .mcp_routes_searchperspectivememoriesrequest import router

_EXTERNAL_TOOL_NAMES = {
    "execute_command", "check_command", "stop_command", "list_processes",
    "get_process_info", "kill_process", "run_script", "get_script_status",
    "list_scripts", "deploy_service", "check_deployment", "rollback_deployment",
    "get_resource_usage", "scale_service", "list_services", "scan_vulnerabilities",
    "check_compliance", "get_security_report", "scan_dependencies",
    "check_permissions", "list_security_policies", "profile_function",
    "get_performance_metrics", "analyze_bottleneck", "get_memory_profile",
    "get_cpu_profile", "list_profiling_sessions",
}


class _ExternalToolReq(BaseModel):
    """外部MCP工具请求 (通用)"""

    # command-executor
    command: str | None = None
    timeout: int | None = 30
    cwd: str | None = None
    command_id: str | None = None
    pid: int | None = None
    force: bool | None = False
    script_path: str | None = None
    args: list | None = None
    script_id: str | None = None
    filter: str | None = None
    # ops-engine
    service_name: str | None = None
    environment: str | None = None
    config: dict | None = None
    version: str | None = None
    resource_type: str | None = None
    duration: str | None = None
    replicas: int | None = None
    # security-scanner
    target_path: str | None = None
    scan_type: str | None = None
    severity: str | None = None
    standard: str | None = None
    report_type: str | None = None
    format: str | None = None
    include_dev: bool | None = True
    check_type: str | None = None
    policy_type: str | None = None
    # performance-profiler
    module_path: str | None = None
    function_name: str | None = None
    time_range: str | None = None
    target: str | None = None
    threshold: float | None = 0.8
    top_n: int | None = 20


@router.post("/tools/{tool_name}")
async def mcp_external_tool(tool_name: str, req: _ExternalToolReq):
    """外部MCP工具转发: 将请求路由到对应的子进程MCP Server"""
    if tool_name not in _EXTERNAL_TOOL_NAMES:
        raise HTTPException(status_code=404, detail=f"工具 {tool_name} 不存在")

    import json as _json
    import subprocess

    # 确定要启动的MCP Server脚本
    _SERVER_SCRIPTS = {
        "execute_command": "command_executor.py",
        "check_command": "command_executor.py",
        "stop_command": "command_executor.py",
        "list_processes": "command_executor.py",
        "get_process_info": "command_executor.py",
        "kill_process": "command_executor.py",
        "run_script": "command_executor.py",
        "get_script_status": "command_executor.py",
        "list_scripts": "command_executor.py",
        "deploy_service": "ops_engine.py",
        "check_deployment": "ops_engine.py",
        "rollback_deployment": "ops_engine.py",
        "get_resource_usage": "ops_engine.py",
        "scale_service": "ops_engine.py",
        "list_services": "ops_engine.py",
        "scan_vulnerabilities": "security_scanner.py",
        "check_compliance": "security_scanner.py",
        "get_security_report": "security_scanner.py",
        "scan_dependencies": "security_scanner.py",
        "check_permissions": "security_scanner.py",
        "list_security_policies": "security_scanner.py",
        "profile_function": "performance_profiler.py",
        "get_performance_metrics": "performance_profiler.py",
        "analyze_bottleneck": "performance_profiler.py",
        "get_memory_profile": "performance_profiler.py",
        "get_cpu_profile": "performance_profiler.py",
        "list_profiling_sessions": "performance_profiler.py",
    }

    script = _SERVER_SCRIPTS.get(tool_name)
    if not script:
        raise HTTPException(
            status_code=404, detail=f"工具 {tool_name} 无对应MCP Server"
        )

    # 构建MCP JSON-RPC请求
    args_dict = {k: v for k, v in req.model_dump().items() if v is not None}
    mcp_request = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {
            "name": tool_name,
            "arguments": args_dict,
        },
    }

    # 通过子进程调用MCP Server
    script_path = str(
        Path(__file__).resolve().parent.parent.parent / "mcp" / "server" / script
    )
    python_exe = str(
        Path(__file__).resolve().parent.parent.parent / "python" / "python.exe"
    )

    try:
        proc = subprocess.run(
            [python_exe, script_path],
            input=_json.dumps(mcp_request) + "\n",
            capture_output=True,
            text=True,
            timeout=req.timeout or 30,
            encoding="utf-8",
            cwd=str(Path(__file__).resolve().parent.parent.parent),
            env={
                **os.environ,
                "PYTHONIOENCODING": "utf-8-sig",
                "PROJECT_ROOT": str(Path(__file__).resolve().parent.parent.parent),
            },
        )

        # 解析MCP JSON-RPC响应
        for line in proc.stdout.strip().split("\n"):
            line = line.strip()
            if not line:
                continue
            try:
                resp = _json.loads(line)
                if "result" in resp:
                    content = resp["result"].get("content", [])
                    if isinstance(content, list) and len(content) > 0:
                        text_parts = []
                        for item in content:
                            if isinstance(item, dict) and "text" in item:
                                text_parts.append(item["text"])
                        return {
                            "success": True,
                            "data": "\n".join(text_parts)
                            if text_parts
                            else resp["result"],
                            "tool_name": tool_name,
                        }
                    return {
                        "success": True,
                        "data": resp["result"],
                        "tool_name": tool_name,
                    }
                if "error" in resp:
                    return {
                        "success": False,
                        "error": resp["error"].get("message", str(resp["error"])),
                        "tool_name": tool_name,
                    }
            except _json.JSONDecodeError:
                continue

        return {
            "success": False,
            "error": f"MCP Server无有效响应: {proc.stderr[:500] if proc.stderr else 'empty'}",
            "tool_name": tool_name,
        }

    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "error": f"工具 {tool_name} 执行超时",
            "tool_name": tool_name,
        }
    except Exception as e:
        return {"success": False, "error": str(e), "tool_name": tool_name}


__all__ = ["_ExternalToolReq"]
