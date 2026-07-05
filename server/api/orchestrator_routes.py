"""
Agent调度API路由 — 暴露AgentPipeline+ToolCallTracker到HTTP API
==============================================================
SSS级调度引擎的对外接口，支持:
  - 创建/查询流水线
  - 切换阶段 + Agent声明
  - 追踪工具调用
  - 并行分发
  - 查询调度状态
"""

from core.orchestration.agent_orchestrator import AGENT_CAPABILITY_MATRIX, AgentPipeline
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from server.api.utils import run_sync as _run

router = APIRouter(tags=["Agent Orchestrator"])


def _tvp_log(action: str, detail: str, result: str = "ok"):
    try:
        from server.main import _log_operation

        _log_operation("tvp", action, detail, result)
    except Exception:
        pass


@router.get("/")
def orchestrator_root():
    return {
        "status": "active",
        "agents": 19,
        "pipelines": 3,
        "layers": ["L1-SubAgent", "L2-BuildAgent", "L3-Orchestrator"],
        "routes": [
            "POST /pipeline/create",
            "POST /pipeline/stage/switch",
            "POST /pipeline/stage/complete",
            "POST /pipeline/tool/track",
            "POST /dispatch",
            "POST /parallel/dispatch",
        ],
    }


class PipelineCreateRequest(BaseModel):
    pipeline_type: str = "development"
    task_goal: str = ""


class StageSwitchRequest(BaseModel):
    stage_index: int
    task_goal: str
    task_context: str = ""


class StageResultRequest(BaseModel):
    status: str = "completed"
    summary: str = ""
    duration_s: float = 0.0


class ToolTrackRequest(BaseModel):
    tool_name: str
    success: bool = True
    duration_ms: float = 0
    output_summary: str = ""


class DispatchRequest(BaseModel):
    """智能调度请求 — 单任务智能路由到最合适Agent"""

    task: str
    context: str = ""
    agent_id: str | None = None  # 指定Agent（可选，不指定则自动路由）
    pipeline_type: str = "development"
    mode: str = "auto"  # auto / single / pipeline
    priority: str = "medium"


class ParallelDispatchRequest(BaseModel):
    tasks: list[dict[str, str]]


@router.post("/pipeline/create")
async def create_pipeline(request: PipelineCreateRequest):
    from server.deps import get_agent_scheduler

    scheduler = get_agent_scheduler()
    if not scheduler:
        raise HTTPException(status_code=503, detail="Agent调度器未初始化")

    pipeline = await _run(scheduler.create_pipeline, request.pipeline_type)
    info = {
        "pipeline_id": pipeline._pipeline_id,
        "pipeline_type": pipeline.pipeline_type,
        "total_stages": pipeline.get_stage_count(),
        "stages": [
            {
                "index": i,
                "stage": s.value,
                "agent_id": a,
                "agent_name": AGENT_CAPABILITY_MATRIX.get(a, {}).get("name", a),
                "agent_emoji": AGENT_CAPABILITY_MATRIX.get(a, {}).get("emoji", ""),
                "description": d,
            }
            for i, (s, a, d) in enumerate(pipeline.stages)
        ],
    }
    _tvp_log(
        "pipeline_create",
        f"type={request.pipeline_type} stages={pipeline.get_stage_count()}",
    )
    return {"success": True, "pipeline": info}


@router.post("/pipeline/stage/switch")
async def switch_stage(request: StageSwitchRequest):
    from server.deps import get_agent_scheduler

    scheduler = get_agent_scheduler()
    if not scheduler:
        raise HTTPException(status_code=503, detail="Agent调度器未初始化")

    _tvp_log(
        "stage_switch", f"stage={request.stage_index} goal={request.task_goal[:60]}"
    )
    result = await _run(
        scheduler.switch_pipeline_stage,
        request.stage_index,
        request.task_goal,
        request.task_context,
    )
    return result


@router.post("/pipeline/stage/complete")
async def complete_stage(request: StageResultRequest):
    from server.deps import get_agent_scheduler

    scheduler = get_agent_scheduler()
    if not scheduler:
        raise HTTPException(status_code=503, detail="Agent调度器未初始化")

    result = await _run(
        scheduler.record_stage_done, request.status, request.summary, request.duration_s
    )
    _tvp_log(
        "stage_complete", f"status={request.status} duration={request.duration_s:.1f}s"
    )
    return {"success": True, "tvp": result}


@router.post("/track")
async def track_tool(request: ToolTrackRequest):
    from server.deps import get_agent_scheduler

    scheduler = get_agent_scheduler()
    if not scheduler:
        raise HTTPException(status_code=503, detail="Agent调度器未初始化")

    record = await _run(
        scheduler.track_tool,
        request.tool_name,
        request.success,
        request.duration_ms,
        request.output_summary,
    )
    _tvp_log("tool_track", f"tool={request.tool_name} success={request.success}")
    return {
        "success": True,
        "call_id": record.call_id,
        "tvp": record.to_tvp(),
        "agent_name": record.agent_name,
        "agent_emoji": record.agent_emoji,
        "stage": record.stage.value,
    }


@router.post("/parallel/dispatch")
async def dispatch_parallel(request: ParallelDispatchRequest):
    from server.deps import get_agent_scheduler

    scheduler = get_agent_scheduler()
    if not scheduler:
        raise HTTPException(status_code=503, detail="Agent调度器未初始化")

    results = await _run(scheduler.dispatch_parallel, request.tasks)
    _tvp_log("parallel_dispatch", f"tasks={len(request.tasks)}")
    return {"success": True, "tasks": results}


@router.get("/status")
async def get_orchestrator_status():
    from server.deps import get_agent_scheduler

    scheduler = get_agent_scheduler()
    if not scheduler:
        raise HTTPException(status_code=503, detail="Agent调度器未初始化")

    summary = await _run(scheduler.get_summary)
    tvp_view = await _run(scheduler.get_tvp_status)
    return {
        "success": True,
        "version": scheduler.VERSION,
        "summary": summary,
        "tvp_view": tvp_view,
    }


@router.get("/agents")
async def list_agents():
    agents = []
    for agent_id, info in AGENT_CAPABILITY_MATRIX.items():
        agents.append(
            {
                "agent_id": agent_id,
                "name": info["name"],
                "emoji": info["emoji"],
                "layer": info["layer"],
                "role": info["role"],
                "capabilities": info["capabilities"],
                "tools": info["tools"],
            }
        )
    return {"success": True, "count": len(agents), "agents": agents}


@router.get("/agent-stats")
async def get_agent_stats():
    """
    Agent真实运行统计 — 基于ToolCallTracker的实际调用记录

    为前端 Agent 拓扑图提供真实的 successRate / taskCount / avgDuration，
    替代任何伪随机/mock数据。无调度器或无调用记录时返回空统计(success_rate=None)，
    由前端回退到DAG基线，绝不返回伪造数值。

    Returns:
        dict: {
            "success": bool,
            "total_calls": int,
            "agents": {agent_id: {agent_id, agent_name, task_count,
                                  success_rate, avg_duration_s, tools}}
        }
    """
    from server.deps import get_agent_scheduler

    scheduler = get_agent_scheduler()
    if not scheduler or not getattr(scheduler, "tracker", None):
        return {"success": True, "total_calls": 0, "agents": {}}

    tracker = scheduler.tracker
    calls = list(getattr(tracker, "_calls", []))

    agents: dict[str, dict] = {}
    for agent_id in AGENT_CAPABILITY_MATRIX:
        agent_calls = [c for c in calls if c.agent_id == agent_id]
        task_count = len(agent_calls)
        if task_count == 0:
            continue
        success_count = sum(1 for c in agent_calls if c.success)
        total_duration_ms = sum(c.duration_ms for c in agent_calls)
        info = AGENT_CAPABILITY_MATRIX.get(agent_id, {})
        agents[agent_id] = {
            "agent_id": agent_id,
            "agent_name": info.get("name", agent_id),
            "task_count": task_count,
            "success_rate": round(success_count / task_count, 4),
            "avg_duration_s": round(total_duration_ms / task_count / 1000.0, 3),
            "tools": sorted({c.tool_name for c in agent_calls}),
        }

    return {"success": True, "total_calls": len(calls), "agents": agents}


@router.post("/dispatch")
async def dispatch_task(request: DispatchRequest):
    """
    智能调度端点 — 将任务路由到最合适的Agent

    三种模式:
      - auto: 自动分析任务并路由到最优Agent
      - single: 指定单个Agent执行
      - pipeline: 创建完整流水线
    """
    import time as _time

    from server.deps import get_agent_scheduler

    scheduler = get_agent_scheduler()
    if not scheduler:
        raise HTTPException(status_code=503, detail="Agent调度器未初始化")

    # 尝试连接容器中的Trae统一调度器进行实时调度
    container_scheduler = None
    try:
        from core.shared.tianji_container import get_container

        c = get_container()
        if c:
            mod = c._modules.get("trae_agent_scheduler")
            if mod and mod.instance:
                container_scheduler = mod.instance
    except Exception:
        pass

    task_goal = request.task
    selected_agent = request.agent_id
    routing_reason = "user_specified"

    # 自动路由: 分析任务并匹配最合适的Agent
    if request.mode == "auto" and not selected_agent:
        task_lower = task_goal.lower()
        # 基于任务关键词匹配Agent
        agent_keywords = {
            "dongcha": ["分析", "理解", "感知", "意图", "需求", "analyze"],
            "jingwei": ["架构", "设计", "系统", "结构", "architecture", "design"],
            "miaobi": ["写", "创建", "生成", "代码", "实现", "create", "write", "code", "修复", "bug", "fix", "创作", "content"],
            "tiewei": ["测试", "验证", "检查", "门禁", "test", "verify", "check"],
            "mingjing": ["审查", "审核", "review", "audit"],
            "yiku": ["记忆", "回忆", "存储", "检索", "memory", "recall", "search"],
            "qianli": ["部署", "运维", "监控", "deploy", "ops", "monitor"],
            "zhenshan": ["安全", "审计", "扫描", "security", "audit", "scan"],
            "zhuiguang": ["性能", "优化", "profile", "perf", "optimize"],
            "baiqiao": ["技能", "工具", "skill", "tool", "mcp"],
            "shiguan": ["版本", "归档", "历史", "version", "archive"],
        }

        best_score = 0
        for aid, keywords in agent_keywords.items():
            score = sum(1 for kw in keywords if kw in task_lower)
            if score > best_score:
                best_score = score
                selected_agent = aid

        if not selected_agent or best_score == 0:
            selected_agent = "tianshu"  # 天枢作为默认调度
            routing_reason = "default_tianshu"
        else:
            routing_reason = f"keyword_match(score={best_score})"

    agent_info = AGENT_CAPABILITY_MATRIX.get(selected_agent, {})

    result = {
        "success": True,
        "mode": request.mode,
        "task": task_goal,
        "assigned_agent": {
            "agent_id": selected_agent,
            "agent_name": agent_info.get("name", selected_agent),
            "agent_emoji": agent_info.get("emoji", "🤖"),
            "layer": agent_info.get("layer", "?"),
        },
        "routing_reason": routing_reason,
        "timestamp": _time.time(),
    }

    # 模式: pipeline — 创建完整流水线
    if request.mode == "pipeline":
        try:
            pipeline = await _run(scheduler.create_pipeline, request.pipeline_type)
            tvp_stage = await _run(
                scheduler.switch_pipeline_stage, 0, task_goal, request.context
            )
            result["pipeline"] = {
                "pipeline_id": pipeline._pipeline_id,
                "pipeline_type": pipeline.pipeline_type,
                "total_stages": pipeline.get_stage_count(),
                "current_stage": tvp_stage,
            }
        except Exception as e:
            result["pipeline_error"] = str(e)[:200]

    # 所有模式都追踪调度事件 — 确保计数器更新
    try:
        track_result = await _run(
            scheduler.track_tool,
            tool_name="agent_dispatch",
            success=True,
            duration_ms=0,
            output_summary=f"Dispatch to @{selected_agent}: {task_goal[:80]}",
        )
        result["track_result"] = {
            "call_id": track_result.call_id,
            "agent_name": track_result.agent_name,
        }
        # 递增 dispatches_run 计数器
        scheduler._stats["dispatches_run"] += 1
    except Exception as e:
        result["track_error"] = str(e)[:200]

    # 通过容器调度器执行实际调度
    if container_scheduler:
        try:
            dispatch_result = container_scheduler.dispatch(
                {
                    "task": task_goal,
                    "context": request.context,
                    "agent_id": selected_agent,
                    "mode": request.mode,
                    "priority": request.priority,
                }
            )
            result["container_dispatch"] = dispatch_result
        except Exception:
            pass

    # TVP日志
    _tvp_log(
        "dispatch", f"agent={selected_agent} mode={request.mode} task={task_goal[:60]}"
    )

    return result


@router.get("/pipelines")
async def list_pipelines():
    pipelines = {}
    for ptype, stages in AgentPipeline.STANDARD_PIPELINES.items():
        pipelines[ptype] = [
            {
                "stage": s.value,
                "agent_id": a,
                "agent_name": AGENT_CAPABILITY_MATRIX.get(a, {}).get("name", a),
                "agent_emoji": AGENT_CAPABILITY_MATRIX.get(a, {}).get("emoji", ""),
                "description": d,
            }
            for s, a, d in stages
        ]
    return {"success": True, "pipelines": pipelines}
