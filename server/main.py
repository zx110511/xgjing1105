"""main.py — 天机v9.1 FastAPI主入口 (SSS-PhaseB拆分+PhaseE修复)

核心变量(app/engine/_SHUTDOWN_EVENT等)在本文件定义，
各子模块通过 from server.main import app 引用。
启动方式:
    python -m server.main_ops
    uvicorn server.main:app --host 0.0.0.0 --port 8771
"""

import os
import sys
import threading
import time
from pathlib import Path

try:
    from dotenv import load_dotenv

    _dotenv_path = Path(__file__).resolve().parent.parent / ".env"
    if _dotenv_path.exists():
        load_dotenv(_dotenv_path, override=True)
except ImportError:
    pass

# Fix for console=False mode (Windows background service)
if sys.stdout is None:

    class NullWriter:
        def write(self, *args, **kwargs):
            pass

        def flush(self):
            pass

        def isatty(self):
            return False

    sys.stdout = NullWriter()
    sys.stderr = NullWriter()

_DEFAULT_ROOT = Path(__file__).resolve().parent.parent
AI_MEMORY_ROOT = Path(os.environ.get("AI_MEMORY_ROOT", str(_DEFAULT_ROOT)))
TIANJI_EDITION = os.environ.get("TIANJI_EDITION", "source-v9.1")

_EDITION_LABEL = {
    "compiled-exe": "编译版 (天机v9.1.exe)",
    "source-v8.0": "源码版 v8.0 (平台化研究)",
    "source-v9.0": "源码版 v9.0 (统一架构)",
    "source-v9.1": "源码版 v9.1 (SSS精炼)",
}.get(TIANJI_EDITION, TIANJI_EDITION)

if str(AI_MEMORY_ROOT) not in sys.path:
    sys.path.insert(0, str(AI_MEMORY_ROOT))


from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.gzip import GZipMiddleware

# ── 核心模块级变量 ──
_START_TIME = time.time()
_SHUTDOWN_EVENT = threading.Event()
_GRACEFUL_SHUTDOWN_TIMEOUT = 15

_PROTOCOL_MODE_ACTIVE: bool = False
_EVENT_WIRING_ACTIVE: bool = False

# ── FastAPI应用实例 ──
app = FastAPI(
    title=f"天机v9.1 元初系统 · 智能记忆平台 [{_EDITION_LABEL}]",
    description="ICME六层记忆引擎 | REST API + WebSocket | 语义搜索 | 多平台适配",
    version="9.1.0-sss",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(GZipMiddleware, minimum_size=1000)

# ── 引擎单例 (从deps导入) ──

# ── 导入子模块 (注册路由+事件) ──
import server.api.mcp_routes__externaltoolreq  # noqa: E402,F401 (注册外部工具类MCP路由)
import server.api.mcp_routes__llmqueryreq  # noqa: E402,F401 (注册LLM查询类MCP路由)
import server.api.mcp_routes__llmsummarizereq  # noqa: E402,F401 (注册LLM类MCP路由到共享router)
from server.api.active_routes import router as active_router  # noqa: E402
from server.api.audit_routes import router as audit_router  # noqa: E402
from server.api.chat_routes_conv_ops import (
    router as chat_router,  # noqa: E402 (SSS拆分修复)
)
from server.api.container_routes import router as container_router  # noqa: E402

# [v9.1-ARCHIVER] 完整对话归档路由(4要素全记录)
from server.api.conversation_archive_routes import (
    router as conversation_archive_router,
)  # noqa: E402

# [v9.1-ARCHIVER] 完整对话归档路由(4要素全记录)
from server.api.deepseek_system_prompt import (
    router as deepseek_prompt_router,  # noqa: E402 (V4双模式法则提示词)
)
from server.api.enforcement_routes import router as enforcement_router  # noqa: E402
from server.api.governance_routes import router as governance_router  # noqa: E402
from server.api.knowledge_graph_routes_endpoints import (
    router as kg_router,  # noqa: E402 (SSS拆分修复-端点重建)
)
from server.api.llm_routes import router as llm_router  # noqa: E402

# ── SSS-PhaseE: 注册APIRouter子模块 (拆分时遗漏 — 全量补齐) ──
# 已通过OpenAPI验证: 前端28个API调用中仅6个端点存在，其余全部404
# 根因: SSS拆分时48个路由文件中仅2个被注册到main.py
from server.api.mcp_routes_searchperspectivememoriesrequest import (
    router as mcp_router,  # noqa: E402
)
from server.api.memory_routes import router as memory_router  # noqa: E402
from server.api.metrics_routes import router as metrics_router  # noqa: E402
from server.api.module_manager_routes import router as module_router  # noqa: E402
from server.api.ops_routes import router as ops_router  # noqa: E402
from server.api.orchestrator_routes import router as orchestrator_router  # noqa: E402
from server.api.orchestrator_v10 import (
    router as orchestrator_v10_router,  # noqa: E402 (v9.1调度引擎)
)
from server.api.platform_routes import router as platform_router  # noqa: E402
from server.api.search_routes import create_search_router  # noqa: E402 (工厂函数)
from server.api.standards_routes import router as standards_router  # noqa: E402

# [FIX-API-404] 导入status_routes_module的router，解决 /api/status 404错误
from server.api.status_routes_module import router as status_router  # noqa: E402
from server.api.ws_routes import router as ws_router  # noqa: E402

from .main_config import *  # noqa: F401,F403
from .main_health import *  # noqa: F401,F403
from .main_ops import *  # noqa: F401,F403
from .main_static import *  # noqa: F401,F403
from .main_stats_helpers import *  # noqa: F401,F403
from .main_status import *  # noqa: F401,F403

# ════════════════════════════════════════════════════════
# [FIX-JIANHENG] 补充前端期望但后端缺失的API端点
# ════════════════════════════════════════════════════════


@app.get("/api/config/all")
def api_config_all():
    """获取系统全部配置 (前端P5系统配置页面使用)"""
    from server.main_config import api_config as get_base_config

    base = get_base_config()

    # 补充skills信息
    skills_info = []
    try:
        from server.api.module_manager_routes import get_module_manager

        mm = get_module_manager()
        if mm:
            for name, mod in mm._modules.items():
                skills_info.append(
                    {
                        "name": name,
                        "status": mod.state.value,
                        "enabled": mod.state.value == "running",
                    }
                )
    except:
        pass

    return {
        "config": base,
        "skills": skills_info,
        "timestamp": __import__("time").time(),
    }


@app.get("/api/config/skills")
def api_config_skills():
    """获取Skills配置列表 (前端P5系统配置页面使用)"""
    skills_info = []
    try:
        from server.api.module_manager_routes import get_module_manager

        mm = get_module_manager()
        if mm:
            for name, mod in mm._modules.items():
                skills_info.append(
                    {
                        "name": name,
                        "status": mod.state.value,
                        "enabled": mod.state.value == "running",
                        "description": getattr(mod, "description", ""),
                    }
                )
    except Exception as e:
        print(f"[WARN] get skills failed: {e}")

    return {"skills": skills_info}


@app.get("/api/mcp/servers")
def api_mcp_servers():
    """获取MCP服务器列表 (前端P7 MCP工具页面使用)

    [FIX-FAB-001] 修复硬编码假数据: tools_count 不再使用 random.randint
    真实数据源: 从 /api/mcp/tools 返回的工具清单按 category 分组统计
    """
    # MCP服务器与MCP工具category的映射关系 (架构定义)
    MCP_SERVER_CATEGORIES = {
        "memory-engine-global": {
            "description": "记忆引擎 (ICME六层+认知+搜索)",
            "categories": ["memory", "namespace", "session", "search", "system"],
        },
        "agent-framework-global": {
            "description": "智能体框架 (@tianshu协调+A2A)",
            "categories": [],  # Agent调度走 /api/orchestrator/* 与 /api/chat/fusion/*
        },
        "command-executor": {
            "description": "命令执行器 (进程+脚本)",
            "categories": ["command"],
        },
        "ops-engine": {
            "description": "DevOps运维引擎 (部署+服务)",
            "categories": ["ops"],
        },
        "performance-profiler": {
            "description": "性能剖析器 (CPU+内存+瓶颈)",
            "categories": ["profiler"],
        },
        "security-scanner": {
            "description": "安全扫描器 (漏洞+合规+权限)",
            "categories": ["security"],
        },
    }

    # 从真实MCP工具清单统计每个服务器的工具数
    tools_by_category: dict[str, int] = {}
    try:
        from server.api.mcp_routes_searchperspectivememoriesrequest import (
            mcp_tools_list,
        )

        tools_payload = mcp_tools_list()
        for tool in tools_payload.get("tools", []):
            cat = tool.get("category", "unknown")
            tools_by_category[cat] = tools_by_category.get(cat, 0) + 1
    except Exception as e:
        print(f"[WARN] /api/mcp/servers 统计工具数失败: {e}", flush=True)

    servers = []
    for name, info in MCP_SERVER_CATEGORIES.items():
        cats = info["categories"]
        tools_count = sum(tools_by_category.get(c, 0) for c in cats) if cats else 0
        # 真实状态: 有工具数则视为已连接 (工具清单能正常返回即代表MCP服务在线)
        connected = (
            bool(tools_by_category) if cats else True
        )  # agent-framework 走独立通道
        servers.append(
            {
                "name": name,
                "description": info["description"],
                "enabled": True,
                "status": "connected" if connected else "disconnected",
                "tools_count": tools_count,
                "categories": cats,
            }
        )

    return {"servers": servers, "total_tools": sum(tools_by_category.values())}


@app.get("/api/sss/run")
def api_sss_run():
    """触发SSS审计 (前端P8 SSS审计页面使用)

    [FIX-FAB-002] 修复降级模式硬编码分数: 不再返回伪造的75分
    异常时返回 success=false 让前端正确识别错误状态
    """
    import time

    try:
        # 尝试调用实际的SSS审计引擎
        from core.enforcement.audit_engine import AuditEngine

        engine = AuditEngine()
        result = engine.run_quick_audit()

        return {
            "success": True,
            "result_id": result.get("id", f"sss-{time.time()}"),
            "score": result.get("overall_score", 0),
            "grade": result.get("grade", "N/A"),
            "result": result,
            "timestamp": time.time(),
        }
    except Exception as e:
        # [FIX] 显式返回错误状态, 不再伪造75分让前端误以为审计成功
        return {
            "success": False,
            "degraded": True,
            "result_id": f"sss-degraded-{time.time()}",
            "score": None,
            "grade": None,
            "error": str(e),
            "issues": [f"SSS审计引擎异常: {e}"],
            "recommendations": [
                "建议重启服务以启用完整SSS审计",
                "检查 core/enforcement/audit_engine.py 模块",
            ],
            "timestamp": time.time(),
        }


@app.post("/api/deepseek/chat")
def api_deepseek_chat(body: dict):
    """DeepSeek对话接口 (前端P12 DeepSeek页面使用) - 别名到LLM路由"""
    try:
        from server.api.llm_routes import handle_chat_request

        return handle_chat_request(body)
    except Exception as e:
        return {
            "error": str(e),
            "response": "DeepSeek服务暂时不可用，请稍后重试。",
        }


@app.get("/api/deepseek/models")
def api_deepseek_models():
    """获取DeepSeek可用模型列表 (前端P12 DeepSeek页面使用)

    [FIX-FAB-003] 修复硬编码模型列表: 从 llm_layer.client.config 读取真实模型
    - llm_layer未就绪 → 返回空数组(明示未配置) 而非伪造deepseek-chat
    - 已就绪 → 返回真实配置的模型
    """
    try:
        from server.deps import llm_layer

        if not llm_layer or not llm_layer.is_ready:
            return {
                "models": [],
                "configured": False,
                "reason": "DeepSeek大脑未就绪, 请检查DEEPSEEK_API_KEY",
            }

        # 从 llm_layer 读取真实配置的模型
        model_id = None
        if hasattr(llm_layer, "client") and llm_layer.client is not None:
            model_id = getattr(llm_layer.client.config, "model", None)

        if not model_id:
            return {
                "models": [],
                "configured": True,
                "reason": "LLM已就绪但未读取到模型配置",
            }

        # 真实模型列表(基于实际配置)
        # context_length 为 DeepSeek 官方文档值, 仅为展示用途
        CONTEXT_MAP = {
            "deepseek-chat": 65536,
            "deepseek-coder": 65536,
            "deepseek-reasoner": 65536,
        }
        models = [
            {
                "id": model_id,
                "name": model_id.replace("-", " ").title(),
                "context_length": CONTEXT_MAP.get(model_id, 65536),
                "active": True,
            }
        ]
        return {"models": models, "configured": True}
    except Exception as e:
        return {
            "models": [],
            "configured": False,
            "error": str(e),
        }


app.include_router(mcp_router)  # /api/mcp/* (MCP工具)
app.include_router(memory_router, prefix="/api/memory")  # /api/memory/* (记忆CRUD+统计)
app.include_router(llm_router, prefix="/api/llm")  # /api/llm/* (DeepSeek大脑)
app.include_router(
    governance_router, prefix="/api/governance"
)  # /api/governance/* (治理)
app.include_router(
    orchestrator_router, prefix="/api/orchestrator"
)  # /api/orchestrator/* (调度)
app.include_router(
    orchestrator_v10_router
)  # /api/orchestrator/v9.1/* (v10调度引擎,自带prefix)
app.include_router(ops_router, prefix="/api/ops")  # /api/ops/* (运维报告)
app.include_router(
    standards_router, prefix="/api/standards"
)  # /api/standards/* (标准合规)
app.include_router(audit_router)  # /api/audit/* (鉴衡审计,自带prefix)
app.include_router(module_router, prefix="/api/skills")  # /api/skills/* (模块管理)
app.include_router(
    metrics_router, prefix="/api"
)  # /api/metrics/* (指标,路由自带/metrics前缀)
app.include_router(
    create_search_router(), prefix="/api/search"
)  # /api/search/* (搜索,工厂函数)
# app.include_router(chat_ops_router, prefix="/api/chat")         # 对话操作(父文件注册，见chat_routes.py)
app.include_router(platform_router, prefix="/api/platform")  # /api/platform/* (平台)
app.include_router(ws_router, prefix="/api/ws")  # /api/ws/* (WebSocket)
app.include_router(container_router, prefix="/api/container")  # /api/container/* (容器)
app.include_router(active_router, prefix="/api/active")  # /api/active/* (活跃记忆)
app.include_router(
    enforcement_router, prefix="/api/enforcement"
)  # /api/enforcement/* (强制执行)
app.include_router(kg_router, prefix="/api/kg")  # /api/kg/* (知识图谱)
app.include_router(chat_router, prefix="/api/chat")  # /api/chat/* (AI对话,SSS拆分修复)
app.include_router(
    deepseek_prompt_router
)  # /api/deepseek/* (V4双模式法则提示词,自带prefix)
# [FIX-API-404] 注册status_router，解决 /api/status 404错误
app.include_router(status_router, prefix="/api/status")  # /api/status/* (系统状态)
# [v9.1-ARCHIVER] 完整对话归档路由(4要素全记录)
app.include_router(
    conversation_archive_router, prefix="/api/conversation"
)  # /api/conversation/* (完整对话归档)
