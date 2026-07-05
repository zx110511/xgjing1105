# -*- coding: utf-8-sig -*-
"""mcp_routes__LLMSummarizeReq — 从 mcp_routes.py 拆分 (SSS-PhaseB)

源文件: mcp_routes.py
"""

from fastapi import HTTPException
from pydantic import BaseModel

from server.api.utils import run_sync as _run

from .mcp_routes__llmcontentreq import _LLMContentReq
from .mcp_routes__llmqueryreq import _LLMQueryReq

# SSS-PhaseE: MCP路由器定义 (拆分时遗漏，与mcp_routes_searchperspectivememoriesrequest共享)
from .mcp_routes_searchperspectivememoriesrequest import router


class _LLMSummarizeReq(BaseModel):
    content: str
    max_length: int = 200


@router.post("/tools/classify")
async def mcp_classify(req: _LLMContentReq):
    """MCP工具: 内容智能分类 — 判定记忆层级"""
    from server.deps import llm_layer

    if not llm_layer or not llm_layer.is_ready:
        raise HTTPException(status_code=503, detail="LLM决策引擎不可用")
    try:
        result = await _run(llm_layer.classify_layer, req.content, req.context)
        return {"success": True, **result.to_dict()}
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"分类失败: {e}")


@router.post("/tools/auto_tag")
async def mcp_auto_tag(req: _LLMContentReq):
    """MCP工具: 自动标签生成"""
    from server.deps import llm_layer

    if not llm_layer or not llm_layer.is_ready:
        raise HTTPException(status_code=503, detail="LLM决策引擎不可用")
    try:
        tags = await _run(llm_layer.auto_tag, req.content)
        return {"success": True, "tags": tags}
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"自动标签失败: {e}")


@router.post("/tools/summarize")
async def mcp_summarize(req: _LLMSummarizeReq):
    """MCP工具: 智能摘要"""
    from server.deps import llm_layer

    if not llm_layer or not llm_layer.is_ready:
        raise HTTPException(status_code=503, detail="LLM决策引擎不可用")
    try:
        summary = await _run(llm_layer.summarize, req.content, req.max_length)
        return {"success": True, "summary": summary}
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"摘要失败: {e}")


@router.post("/tools/extract_knowledge")
async def mcp_extract_knowledge(req: _LLMContentReq):
    """MCP工具: 知识三元组抽取"""
    from server.deps import llm_layer

    if not llm_layer or not llm_layer.is_ready:
        raise HTTPException(status_code=503, detail="LLM决策引擎不可用")
    try:
        triples = await _run(llm_layer.extract_knowledge, req.content)
        return {"success": True, "triples": triples, "count": len(triples)}
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"知识提取失败: {e}")


@router.post("/tools/expand_query")
async def mcp_expand_query(req: _LLMQueryReq):
    """MCP工具: 查询语义扩展"""
    from server.deps import llm_layer

    if not llm_layer or not llm_layer.is_ready:
        raise HTTPException(status_code=503, detail="LLM决策引擎不可用")
    try:
        expansions = await _run(llm_layer.expand_query, req.query)
        return {"success": True, "original": req.query, "expansions": expansions}
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"查询扩展失败: {e}")


@router.post("/tools/assess_value")
async def mcp_assess_value(req: _LLMContentReq):
    """MCP工具: 内容价值评估"""
    from server.deps import llm_layer

    if not llm_layer or not llm_layer.is_ready:
        raise HTTPException(status_code=503, detail="LLM决策引擎不可用")
    try:
        result = await _run(llm_layer.assess_value, req.content, req.context)
        return {"success": True, **result}
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"价值评估失败: {e}")


@router.post("/tools/decide_storage")
async def mcp_decide_storage(req: _LLMContentReq):
    """MCP工具: 综合存储策略决策"""
    from server.deps import llm_layer

    if not llm_layer or not llm_layer.is_ready:
        raise HTTPException(status_code=503, detail="LLM决策引擎不可用")
    try:
        result = await _run(llm_layer.decide_storage, req.content, req.context)
        return {"success": True, **result.to_dict()}
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"存储决策失败: {e}")


@router.post("/tools/normalize")
async def mcp_normalize(req: _LLMContentReq):
    """MCP工具: 术语归一化"""
    from server.deps import llm_layer

    if not llm_layer or not llm_layer.is_ready:
        raise HTTPException(status_code=503, detail="LLM决策引擎不可用")
    try:
        # 归一化使用auto_tag作为底层实现
        tags = await _run(llm_layer.auto_tag, req.content)
        return {
            "success": True,
            "normalized": tags[0] if tags else req.content,
            "tags": tags,
        }
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"归一化失败: {e}")


@router.post("/tools/disambiguate")
async def mcp_disambiguate(req: _LLMContentReq):
    """MCP工具: 上下文消歧"""
    from server.deps import llm_layer

    if not llm_layer or not llm_layer.is_ready:
        raise HTTPException(status_code=503, detail="LLM决策引擎不可用")
    try:
        # 消歧使用classify作为底层实现
        result = await _run(llm_layer.classify_layer, req.content, req.context)
        return {"success": True, "layer": result.layer, "reason": result.reason}
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"消歧失败: {e}")


# === 外部MCP Server工具转发 ===
# command-executor / ops-engine / security-scanner / performance-profiler
# 这些工具通过子进程MCP Server执行，后端作为转发代理

_EXTERNAL_TOOL_NAMES = {
    "execute_command",
    "check_command",
    "stop_command",
    "list_processes",
    "get_process_info",
    "kill_process",
    "run_script",
    "get_script_status",
    "list_scripts",
    "deploy_service",
    "check_deployment",
    "rollback_deployment",
    "get_resource_usage",
    "scale_service",
    "list_services",
    "scan_vulnerabilities",
    "check_compliance",
    "get_security_report",
    "scan_dependencies",
    "check_permissions",
    "list_security_policies",
    "profile_function",
    "get_performance_metrics",
    "analyze_bottleneck",
    "get_memory_profile",
    "get_cpu_profile",
    "list_profiling_sessions",
}


__all__ = ["_LLMSummarizeReq"]
