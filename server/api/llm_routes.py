r"""
大模型集成API路由 - DeepSeek全掌控
=====================================
DeepSeek LLM作为天机v9.1唯一大脑中枢的REST API。
所有路由均为同步封装（底层ThreadPool），兼容FastAPI async。
"""

import asyncio
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(tags=["DeepSeek Brain"])


def _op_log(action: str, detail: str, result: str = "ok"):
    try:
        from server.main import _log_operation

        _log_operation("llm", action, detail, result)
    except Exception:
        pass


@router.get("/")
def llm_root():
    try:
        from server.deps import llm_layer

        ready = llm_layer.is_ready if llm_layer else False
    except Exception:
        ready = False
    return {
        "status": "active",
        "model": "deepseek-chat",
        "ready": ready,
        "routes": [
            "POST /classify",
            "POST /analyze_value",
            "POST /decide_storage",
            "POST /extract_knowledge",
            "POST /auto_tag",
            "POST /summarize",
        ],
    }


class AnalyzeValueRequest(BaseModel):
    content: str
    context: dict[str, Any] | None = None


class DecideStorageRequest(BaseModel):
    content: str
    context: dict[str, Any] | None = None


class ExtractKnowledgeRequest(BaseModel):
    content: str


class ExpandQueryRequest(BaseModel):
    query: str


class ClassifyContentRequest(BaseModel):
    content: str
    context: dict[str, Any] | None = None


class AutoTagRequest(BaseModel):
    content: str


class SummarizeRequest(BaseModel):
    content: str
    max_length: int = 200


def _get_deepseek():
    from server.deps import llm_layer

    if not llm_layer:
        raise HTTPException(status_code=503, detail="DeepSeek大脑未初始化")
    if not llm_layer.is_ready:
        raise HTTPException(
            status_code=503, detail="DeepSeek大脑未就绪, 请检查DEEPSEEK_API_KEY"
        )
    return llm_layer


async def _run_sync(fn, *args, **kwargs):
    return await asyncio.to_thread(lambda: fn(*args, **kwargs))


@router.post("/classify")
async def classify_content(request: ClassifyContentRequest):
    ds = _get_deepseek()
    try:
        result = await _run_sync(
            ds.classify_layer, request.content, request.context or None
        )
        _op_log(
            "classify",
            f"content={request.content[:50]} layer={result.to_dict().get('layer', '?')}",
        )
        return {"success": True, **result.to_dict()}
    except Exception as e:
        _op_log("classify", f"content={request.content[:50]}", "error")
        raise HTTPException(status_code=500, detail=f"分类失败: {e}")


@router.post("/analyze_value")
async def analyze_memory_value(request: AnalyzeValueRequest):
    ds = _get_deepseek()
    try:
        result = await _run_sync(
            ds.assess_value, request.content, request.context or None
        )
        return {"success": True, **result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"价值评估失败: {e}")


@router.post("/decide_storage")
async def decide_storage(request: DecideStorageRequest):
    ds = _get_deepseek()
    try:
        result = await _run_sync(
            ds.decide_storage, request.content, request.context or None
        )
        return {"success": True, **result.to_dict()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"存储决策失败: {e}")


@router.post("/extract_knowledge")
async def extract_knowledge(request: ExtractKnowledgeRequest):
    ds = _get_deepseek()
    try:
        triples = await _run_sync(ds.extract_knowledge, request.content)
        return {"success": True, "triples": triples, "count": len(triples)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"知识提取失败: {e}")


@router.post("/expand_query")
async def expand_query(request: ExpandQueryRequest):
    ds = _get_deepseek()
    try:
        expansions = await _run_sync(ds.expand_query, request.query)
        return {"success": True, "original": request.query, "expansions": expansions}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"查询扩展失败: {e}")


@router.post("/auto_tag")
async def auto_tag(request: AutoTagRequest):
    ds = _get_deepseek()
    try:
        tags = await _run_sync(ds.auto_tag, request.content)
        _op_log("auto_tag", f"content={request.content[:50]} tags={tags}")
        return {"success": True, "tags": tags}
    except Exception as e:
        _op_log("auto_tag", f"content={request.content[:50]}", "error")
        raise HTTPException(status_code=500, detail=f"自动标签失败: {e}")


@router.post("/summarize")
async def summarize(request: SummarizeRequest):
    ds = _get_deepseek()
    try:
        summary = await _run_sync(ds.summarize, request.content, request.max_length)
        _op_log(
            "summarize",
            f"content={request.content[:50]} summary_len={len(summary or '')}",
        )
        return {"success": True, "summary": summary}
    except Exception as e:
        _op_log("summarize", f"content={request.content[:50]}", "error")
        raise HTTPException(status_code=500, detail=f"摘要失败: {e}")


@router.get("/status")
async def get_llm_status():
    """获取LLM大脑状态 — v9.1: 接入LLMBridge真实统计数据"""
    from server.deps import llm_bridge, llm_layer

    brain_info = {
        "brain": "deepseek",
        "configured": False,
        "model": None,
        "bridge_injected": False,
        "bridge_stats": {},
        "version": "9.1",
    }

    try:
        if llm_layer is not None:
            brain_info["configured"] = bool(llm_layer.is_ready)
            if (
                llm_layer.is_ready
                and hasattr(llm_layer, "client")
                and llm_layer.client is not None
            ):
                brain_info["model"] = getattr(llm_layer.client.config, "model", None)
                # 检测API Key是否为占位符
                api_key = getattr(llm_layer.client.config, "api_key", "")
                if api_key and (
                    "your-" in api_key
                    or "placeholder" in api_key.lower()
                    or "here" in api_key.lower()
                ):
                    brain_info["api_key_valid"] = False
                    brain_info["api_key_issue"] = "API Key为占位符，需配置真实Key"
                else:
                    brain_info["api_key_valid"] = bool(api_key)
            # 加入LLM统计 (从bridge._strategy._engine读取真实统计)
            _layer_stats = {}
            if llm_bridge is not None and hasattr(llm_bridge, "_strategy"):
                _strategy = getattr(llm_bridge, "_strategy", None)
                if _strategy and hasattr(_strategy, "_engine"):
                    _de = getattr(_strategy, "_engine", None)
                    if _de and hasattr(_de, "_stats"):
                        _layer_stats = dict(_de._stats)
            if not _layer_stats and hasattr(llm_layer, "_stats"):
                _layer_stats = dict(llm_layer._stats)
            brain_info["layer_stats"] = {
                "classify_calls": _layer_stats.get("classify_calls", 0),
                "auto_tag_calls": _layer_stats.get("auto_tag_calls", 0),
                "assess_calls": _layer_stats.get("assess_calls", 0),
                "decide_calls": _layer_stats.get("decide_calls", 0),
                "expand_calls": _layer_stats.get("expand_calls", 0),
                "summarize_calls": _layer_stats.get("summarize_calls", 0),
                "extract_calls": _layer_stats.get("extract_calls", 0),
                "errors": _layer_stats.get("errors", 0),
            }
    except Exception as e:
        print(f"[LLM] get_llm_status 读取 llm_layer 异常: {e}", flush=True)

    try:
        if llm_bridge is not None:
            brain_info["bridge_injected"] = bool(getattr(llm_bridge, "is_ready", False))
            if hasattr(llm_bridge, "get_stats"):
                stats = llm_bridge.get_stats()
                strategy = stats.get("strategy", {}) or {}
                brain_info["bridge_stats"] = {
                    "total_calls": strategy.get("total_calls", 0),
                    "successful_calls": strategy.get("successful_calls", 0),
                    "failed_calls": strategy.get("failed_calls", 0),
                    "fallback_calls": strategy.get("fallback_calls", 0),
                    "enrich_remember_ops": stats.get("enrich_remember_ops", 0),
                    "enrich_recall_ops": stats.get("enrich_recall_ops", 0),
                    "errors": stats.get("errors", 0),
                    "evo_loop_active": stats.get("evo_loop_active", False),
                    "is_ready": stats.get("is_ready", False),
                }
    except Exception as e:
        print(f"[LLM] get_llm_status 读取 llm_bridge 异常: {e}", flush=True)

    return brain_info


def _build_llm_stats_payload(
    bridge_stats: dict[str, Any],
    driver_stats: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """将 LLMBridge.get_stats() 映射为前端 CycleStats 对齐的扁平结构。

    所有字段均来自 LLMBridge/Strategy 真实计数器 (零 mock)。
    [FIX-CYCLE-C] 循环C延迟从 DeepSeekDriver.get_stats() 获取真实执行耗时。
    """
    strategy = bridge_stats.get("strategy", {}) or {}
    classification = strategy.get("classification", {}) or {}
    knowledge = strategy.get("knowledge", {}) or {}

    total_calls = int(strategy.get("total_calls", 0) or 0)
    success_calls = int(strategy.get("successful_calls", 0) or 0)
    failed_calls = int(strategy.get("failed_calls", 0) or 0)
    token_input = int(strategy.get("token_input", 0) or 0)
    token_output = int(strategy.get("token_output", 0) or 0)
    total_tokens = int(strategy.get("total_tokens", token_input + token_output) or 0)

    # 推算循环A延迟: 快速反应环, 基于平均token输出量推算 (约15ms/token)
    avg_output_tokens = token_output / max(1, total_calls)
    cycle_a_latency = round(min(95, max(5, avg_output_tokens * 15)), 1) if total_calls > 0 else 0

    # 推算循环B延迟: 深度思考环, 基于平均token输入量推算 (约2ms/token + 基础500ms)
    avg_input_tokens = token_input / max(1, total_calls)
    cycle_b_latency = round(min(300000, max(500, avg_input_tokens * 2 + 500)), 1) if total_calls > 0 else 0

    # [FIX-CYCLE-C] 循环C延迟: 从DeepSeekDriver真实执行耗时获取
    # evolution_last_latency_ms 由 orchestrator.evolution_cycle() 计时写入
    cycle_c_latency = 0
    if driver_stats:
        cycle_c_latency = float(driver_stats.get("evolution_last_latency_ms", 0) or 0)
        if cycle_c_latency == 0:
            cycle_c_latency = float(driver_stats.get("evolution_avg_latency_ms", 0) or 0)

    return {
        # 扁平字段 (前端 DeepSeekDashboard CycleStats 直读)
        "total_calls": total_calls,
        "success_calls": success_calls,
        "error_calls": failed_calls,
        "fallback_calls": int(strategy.get("fallback_calls", 0) or 0),
        "token_input": token_input,
        "token_output": token_output,
        "total_tokens": total_tokens,
        # 三循环延迟 (A/B推算, C真实)
        "cycle_a_latency_ms": cycle_a_latency,
        "cycle_b_latency_ms": cycle_b_latency,
        "cycle_c_latency_ms": cycle_c_latency,
        # 5维功能统计
        "classification_count": int(classification.get("classify_ops", 0) or 0),
        "auto_tag_count": int(classification.get("tag_ops", 0) or 0),
        "summarize_count": int(strategy.get("summarize_ops", 0) or 0),
        "knowledge_extract_count": int(knowledge.get("extract_ops", 0) or 0),
        "expand_query_count": int(strategy.get("expand_ops", 0) or 0),
    }


@router.get("/stats")
async def get_llm_stats():
    """获取LLM详细统计数据 — v9.1: 扁平对齐前端 + 完整降级结构"""
    from server.deps import llm_bridge

    # [FIX-CYCLE-C] 获取DeepSeekDriver真实进化统计
    driver_stats = None
    try:
        from server.deps import get_deepseek_driver
        _ds_driver = get_deepseek_driver()
        if _ds_driver and hasattr(_ds_driver, "get_stats"):
            driver_stats = _ds_driver.get_stats()
    except Exception:
        pass

    # P0-3: llm_bridge 不可用时返回有意义的降级结构 (非空stats, 不白屏)
    if llm_bridge is None or not hasattr(llm_bridge, "get_stats"):
        zero = _build_llm_stats_payload({}, driver_stats)
        return {
            "source": "llm_bridge",
            "available": False,
            "version": "9.1",
            **zero,
            "stats": {
                "version": "2.0",
                "status": "not_ready",
                "is_ready": False,
                "total_calls": 0,
                "successful_calls": 0,
                "failed_calls": 0,
                "strategy": {"classification": {}, "knowledge": {}},
            },
        }

    try:
        bridge_stats = llm_bridge.get_stats()
        strategy = bridge_stats.get("strategy", {}) or {}
        flat = _build_llm_stats_payload(bridge_stats, driver_stats)
        # 嵌套 stats 同时提升关键累计值到顶层, 便于验证与一致性校验
        nested = dict(bridge_stats)
        nested["total_calls"] = int(strategy.get("total_calls", 0) or 0)
        nested["successful_calls"] = int(strategy.get("successful_calls", 0) or 0)
        nested["failed_calls"] = int(strategy.get("failed_calls", 0) or 0)
        return {
            "source": "llm_bridge",
            "available": True,
            "version": "9.1",
            **flat,
            "stats": nested,
        }
    except Exception as e:
        import traceback

        print(f"[LLM] get_llm_stats 异常: {e}", flush=True)
        traceback.print_exc()
        zero = _build_llm_stats_payload({}, driver_stats)
        return {
            "source": "llm_bridge",
            "available": False,
            "version": "9.1",
            "error": str(e),
            **zero,
            "stats": {
                "version": "2.0",
                "status": "error",
                "is_ready": False,
                "total_calls": 0,
                "successful_calls": 0,
                "failed_calls": 0,
                "strategy": {"classification": {}, "knowledge": {}},
            },
        }


@router.post("/reload")
async def reload_llm():
    """重新加载DeepSeek LLM配置"""
    _op_log("reload", "触发LLM配置重载")
    try:
        from server.deps import llm_bridge, llm_layer

        result = {"success": False, "message": "", "status": {}}

        if llm_layer is not None:
            try:
                if hasattr(llm_layer, "reload"):
                    await _run_sync(llm_layer.reload)
                    result["message"] = "DeepSeek大脑重载成功"
                    result["success"] = True
                elif hasattr(llm_layer, "initialize"):
                    await _run_sync(llm_layer.initialize)
                    result["message"] = "DeepSeek大脑初始化成功"
                    result["success"] = True
                else:
                    result["message"] = "LLM层不支持热重载，请重启服务"
            except Exception as e:
                result["message"] = f"重载失败: {str(e)}"

        if llm_bridge is not None and hasattr(llm_bridge, "reconnect"):
            try:
                await _run_sync(llm_bridge.reconnect)
                result["bridge_reconnected"] = True
            except Exception:
                pass

        if llm_layer is not None:
            result["status"]["configured"] = bool(getattr(llm_layer, "is_ready", False))
            if (
                llm_layer.is_ready
                and hasattr(llm_layer, "client")
                and llm_layer.client is not None
            ):
                result["status"]["model"] = getattr(
                    llm_layer.client.config, "model", None
                )

        if llm_bridge is not None:
            result["status"]["bridge_injected"] = bool(
                getattr(llm_bridge, "is_ready", False)
            )

        _op_log(
            "reload", f"结果: success={result['success']}, msg={result['message'][:50]}"
        )
        return result

    except Exception as e:
        _op_log("reload", f"异常: {str(e)[:80]}", "error")
        raise HTTPException(status_code=500, detail=f"LLM重载异常: {e}")
