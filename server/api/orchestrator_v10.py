"""
天机v9.1 智能调度 API路由 — DAG调度+持久化执行+LLM规划
==========================================================
暴露天枢级调度引擎的全部能力:
  - DAG流水线创建/执行/查询
  - 持久化工作流管理
  - LLM任务规划
  - 拓扑可视化数据
  - 流水线全景WebSocket推送
"""

import time as _time
import uuid

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

router = APIRouter(prefix="/api/orchestrator/v9.1", tags=["Orchestrator v9.1"])


# ═══════════════════════════════════════════════════════════════
# 请求模型
# ═══════════════════════════════════════════════════════════════


class PlanRequest(BaseModel):
    task: str
    context: str = ""
    prefer_llm: bool = True
    available_agents: list[str] | None = None


class DAGExecuteRequest(BaseModel):
    """执行DAG流水线请求"""

    plan_id: str | None = None  # 从规划结果执行
    dag_json: dict | None = None  # 或直接传入DAG JSON
    parallel: bool = True
    node_executor_type: str = "auto"  # auto / simulated


class DAGBuildRequest(BaseModel):
    """手动构建DAG请求"""

    pipeline_name: str = ""
    nodes: list[dict] = []  # [{agent_id, goal, context, ...}]
    edges: list[dict] = []  # [{source_index, target_index, type}]


class WorkflowRequest(BaseModel):
    workflow_name: str
    steps: list[dict] = []  # [{step_name, compensation_fn, ...}]


class WorkflowResumeRequest(BaseModel):
    workflow_id: str


# ═══════════════════════════════════════════════════════════════
# 依赖注入
# ═══════════════════════════════════════════════════════════════


def _get_dag_scheduler():
    from core.orchestration.dag_scheduler import get_dag_scheduler

    from server.deps import get_agent_scheduler

    agent_scheduler = get_agent_scheduler()
    return get_dag_scheduler(
        event_bus=agent_scheduler.event_bus if agent_scheduler else None,
        tracker=agent_scheduler.tracker if agent_scheduler else None,
    )


def _get_task_planner():
    from core.orchestration.task_planner import get_task_planner

    from server.deps import get_agent_scheduler, llm_layer

    agent_scheduler = get_agent_scheduler()
    return get_task_planner(
        decision_engine=llm_layer,
        event_bus=agent_scheduler.event_bus if agent_scheduler else None,
    )


def _get_checkpoint_manager():
    from core.shared.durable_executor import get_checkpoint_manager

    return get_checkpoint_manager()


def _get_workflow_runner():
    from core.shared.durable_executor import get_workflow_runner

    return get_workflow_runner()


def _tvp_log(action: str, detail: str, result: str = "ok"):
    try:
        from server.main import _log_operation

        _log_operation("tvp", action, detail, result)
    except Exception:
        pass


# ═══════════════════════════════════════════════════════════════
# API端点
# ═══════════════════════════════════════════════════════════════


@router.get("/")
def orchestrator_root():
    return {
        "version": "v9.1.0-天枢",
        "status": "active",
        "modules": {
            "dag_scheduler": "✅ DAG拓扑调度引擎",
            "durable_executor": "✅ 持久化执行+检查点+Saga",
            "task_planner": "✅ LLM动态任务规划器",
        },
        "endpoints": [
            "POST /plan                    — LLM任务规划",
            "POST /dag/build               — 手动构建DAG",
            "POST /dag/execute             — 执行DAG流水线",
            "GET  /dag/{pipeline_id}       — 查询DAG状态",
            "GET  /dag/{pipeline_id}/topology — DAG拓扑数据 (React Flow)",
            "POST /workflow/create         — 创建持久化工作流",
            "POST /workflow/run            — 运行工作流",
            "POST /workflow/resume         — 恢复工作流",
            "GET  /workflow/{id}           — 查询工作流状态",
            "GET  /workflow/{id}/events    — 工作流事件历史",
            "GET  /workflows               — 列出所有工作流",
            "GET  /stats                   — 调度统计",
            "WS   /ws/pipeline             — WebSocket流水线实时推送",
        ],
    }


# ── 任务规划 ──


@router.post("/plan")
async def plan_task(request: PlanRequest):
    """LLM驱动任务规划 — 自然语言→DAG流水线"""
    planner = _get_task_planner()
    plan = planner.plan(
        request.task,
        context=request.context,
        available_agents=request.available_agents,
        prefer_llm=request.prefer_llm,
    )

    # 转换为DAG
    dag_scheduler = _get_dag_scheduler()
    dag = planner.plan_to_dag(plan, event_bus=dag_scheduler.event_bus)

    _tvp_log(
        "v10_plan",
        f"task={request.task[:60]} complexity={plan.complexity.value} strategy={plan.strategy.value}",
    )

    return {
        "success": True,
        "plan": plan.to_dict(),
        "dag": dag.to_dict(),
    }


# ── DAG构建与执行 ──


@router.post("/dag/build")
async def build_dag(request: DAGBuildRequest):
    """手动构建DAG流水线"""
    from core.orchestration.dag_scheduler import DAGBuilder

    builder = DAGBuilder(request.pipeline_name)
    node_ids = []

    for node_data in request.nodes:
        builder.node(
            agent_id=node_data.get("agent_id", "tianshu"),
            goal=node_data.get("goal", ""),
            context=node_data.get("context", ""),
            tools=node_data.get("tools"),
            priority=node_data.get("priority", "medium"),
            timeout_s=node_data.get("timeout_s", 300),
        )
        node_ids.append(builder._last_node_id)

    for edge_data in request.edges:
        src_idx = edge_data.get("source_index", 0)
        tgt_idx = edge_data.get("target_index", 1)
        if src_idx < len(node_ids) and tgt_idx < len(node_ids):
            from core.orchestration.dag_scheduler import EdgeType

            edge_type = EdgeType(edge_data.get("type", "dependency"))
            builder.pipeline.add_edge(node_ids[src_idx], node_ids[tgt_idx], edge_type)

    dag = builder.build()
    _tvp_log(
        "v10_dag_build",
        f"name={request.pipeline_name} nodes={len(request.nodes)} edges={len(request.edges)}",
    )

    return {
        "success": True,
        "pipeline_id": dag.pipeline_id,
        "dag": dag.to_dict(),
        "has_cycle": dag.has_cycle(),
    }


@router.post("/dag/execute")
async def execute_dag(request: DAGExecuteRequest):
    """执行DAG流水线"""
    dag_scheduler = _get_dag_scheduler()

    if request.plan_id:
        # 从规划结果加载
        planner = _get_task_planner()
        # 简化: 直接用plan_id查询 (实际应持久化存储plan)
        raise HTTPException(
            status_code=501, detail="Plan persistence not yet implemented"
        )
    elif request.dag_json:
        # 从JSON重建DAG
        from core.orchestration.dag_scheduler import DAGNode, DAGPipeline

        dag = DAGPipeline(pipeline_id=f"dag-{uuid.uuid4().hex[:8]}")
        for nd in request.dag_json.get("nodes", []):
            node = DAGNode(
                node_id=nd.get("id", f"node-{uuid.uuid4().hex[:6]}"),
                agent_id=nd.get("data", {}).get("agent_id", "tianshu"),
                agent_name=nd.get("data", {}).get("agent_name", ""),
                agent_emoji=nd.get("data", {}).get("agent_emoji", "🤖"),
                goal=nd.get("data", {}).get("label", ""),
            )
            dag.add_node(node)
        for ed in request.dag_json.get("edges", []):
            dag.add_edge(ed["source"], ed["target"])
    else:
        raise HTTPException(
            status_code=400, detail="Either plan_id or dag_json required"
        )

    # 异步执行 (FastAPI BackgroundTasks)
    import asyncio

    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(
        None, lambda: dag_scheduler.execute(dag, parallel=request.parallel)
    )

    _tvp_log(
        "v10_dag_execute",
        f"pipeline={dag.pipeline_id} nodes_completed={result.get('nodes_completed', 0)}",
    )

    return {
        "success": result.get("success", False),
        "pipeline_id": dag.pipeline_id,
        "result": result,
        "dag": dag.to_dict(),
    }


@router.get("/dag/{pipeline_id}")
async def get_dag_status(pipeline_id: str):
    """查询DAG流水线状态"""
    dag_scheduler = _get_dag_scheduler()
    dag = dag_scheduler.get_pipeline(pipeline_id)
    if not dag:
        raise HTTPException(status_code=404, detail="Pipeline not found")
    return dag.to_dict()


@router.get("/dag/{pipeline_id}/topology")
async def get_dag_topology(pipeline_id: str):
    """获取DAG拓扑数据 — 供React Flow渲染"""
    dag_scheduler = _get_dag_scheduler()
    dag = dag_scheduler.get_pipeline(pipeline_id)
    if not dag:
        raise HTTPException(status_code=404, detail="Pipeline not found")

    # 自动布局: 按拓扑层级分配XY坐标
    levels = dag.topological_levels()
    node_positions = {}
    for level_idx, level_nodes in enumerate(levels):
        y = level_idx * 150 + 50
        x_step = 250
        x_start = -(len(level_nodes) - 1) * x_step / 2
        for node_idx, node_id in enumerate(level_nodes):
            node_positions[node_id] = {"x": x_start + node_idx * x_step, "y": y}

    # 更新节点位置
    for node_id, pos in node_positions.items():
        if node_id in dag.nodes:
            dag.nodes[node_id].metadata["position"] = pos

    return dag.to_dict()


# ── 持久化工作流 ──


@router.post("/workflow/create")
async def create_workflow(request: WorkflowRequest):
    """创建持久化工作流"""
    from core.shared.durable_executor import WorkflowContext

    ctx = WorkflowContext(
        workflow_id=f"wf-{uuid.uuid4().hex[:8]}",
        workflow_name=request.workflow_name,
    )
    for step in request.steps:
        ctx.add_step(
            name=step.get("step_name", ""),
            compensation_fn=step.get("compensation_fn"),
            compensation_args=step.get("compensation_args", {}),
        )

    mgr = _get_checkpoint_manager()
    mgr.save_checkpoint(ctx)

    _tvp_log(
        "v10_workflow_create",
        f"name={request.workflow_name} steps={len(request.steps)}",
    )

    return {
        "success": True,
        "workflow": ctx.to_dict(),
    }


@router.post("/workflow/resume")
async def resume_workflow(request: WorkflowResumeRequest):
    """恢复暂停/失败的工作流"""
    mgr = _get_checkpoint_manager()
    ctx = mgr.load_latest(request.workflow_id)
    if not ctx:
        raise HTTPException(status_code=404, detail="Workflow not found")

    runner = _get_workflow_runner()
    success, ctx = runner.run(ctx, {}, resume_from_checkpoint=True)

    _tvp_log("v10_workflow_resume", f"id={request.workflow_id} success={success}")

    return {
        "success": success,
        "workflow": ctx.to_dict(),
    }


@router.get("/workflow/{workflow_id}")
async def get_workflow(workflow_id: str):
    """查询工作流状态"""
    mgr = _get_checkpoint_manager()
    ctx = mgr.load_latest(workflow_id)
    if not ctx:
        raise HTTPException(status_code=404, detail="Workflow not found")
    return ctx.to_dict()


@router.get("/workflow/{workflow_id}/events")
async def get_workflow_events(workflow_id: str, limit: int = 100):
    """获取工作流事件历史"""
    mgr = _get_checkpoint_manager()
    events = mgr.get_events(workflow_id, limit)
    return {"workflow_id": workflow_id, "events": events, "count": len(events)}


@router.get("/workflows")
async def list_workflows(status: str = None, limit: int = 50):
    """列出所有工作流"""
    mgr = _get_checkpoint_manager()
    workflows = mgr.list_workflows(status, limit)
    return {"workflows": workflows, "count": len(workflows)}


# ── 统计 ──


@router.get("/stats")
async def get_orchestrator_stats():
    """获取调度引擎统计"""
    dag_scheduler = _get_dag_scheduler()
    mgr = _get_checkpoint_manager()
    planner = _get_task_planner()

    # 可观测性统计
    obs_stats = {}
    try:
        from core.shared.observability import get_tracer

        tracer = get_tracer()
        obs_stats = tracer.get_stats()
    except Exception:
        pass

    checkpoint_stats = mgr.get_stats()

    return {
        "dag_scheduler": dag_scheduler.get_stats(),
        # 前端 StatsPanel 读取 "checkpoint"；"checkpoint_manager" 为审计标准别名，二者同源
        "checkpoint": checkpoint_stats,
        "checkpoint_manager": checkpoint_stats,
        "planner": planner.get_stats(),
        "observability": obs_stats,
        "timestamp": _time.time(),
    }


# ── 可观测性 ──


@router.get("/metrics")
async def get_prometheus_metrics():
    """Prometheus格式指标暴露"""
    try:
        from core.shared.observability import get_metrics

        metrics = get_metrics()
        from fastapi.responses import PlainTextResponse

        return PlainTextResponse(metrics.to_prometheus(), media_type="text/plain")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/traces")
async def list_traces(limit: int = 50):
    """列出最近的追踪链"""
    try:
        from core.shared.observability import get_tracer

        tracer = get_tracer()
        return {
            "traces": tracer.list_traces(limit),
            "count": len(tracer.list_traces(limit)),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/traces/{trace_id}")
async def get_trace(trace_id: str):
    """获取指定追踪链详情"""
    try:
        from core.shared.observability import get_tracer

        tracer = get_tracer()
        trace = tracer.get_trace(trace_id)
        if not trace:
            raise HTTPException(status_code=404, detail="Trace not found")
        return {
            "trace_id": trace.trace_id,
            "root_span": trace.root_span.to_dict() if trace.root_span else None,
            "spans": [s.to_dict() for s in trace.spans.values()],
            "created_at": trace.created_at,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/latency")
async def get_latency_stats():
    """获取延迟统计 (P50/P90/P99)"""
    try:
        from core.shared.observability import get_metrics

        metrics = get_metrics()
        return {"latency": metrics.get_stats()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── A2A 互操作 ──


class A2ATaskRequest(BaseModel):
    description: str
    context_id: str | None = None
    metadata: dict | None = None


class A2AMessageRequest(BaseModel):
    task_id: str
    text: str
    role: str = "user"  # user / agent


@router.get("/a2a/agent-cards")
async def list_agent_cards():
    """列出所有Agent的A2A能力卡片"""
    try:
        from core.orchestration.a2a_gateway import get_a2a_gateway

        gateway = get_a2a_gateway()
        return {
            "agent_cards": gateway.list_agent_cards(),
            "count": len(gateway.list_agent_cards()),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/a2a/agent-card/{agent_id}")
async def get_agent_card(agent_id: str):
    """获取指定Agent的A2A能力卡片"""
    try:
        from core.orchestration.a2a_gateway import get_a2a_gateway

        gateway = get_a2a_gateway()
        card = gateway.get_agent_card(agent_id)
        if not card:
            raise HTTPException(status_code=404, detail=f"Agent not found: {agent_id}")
        return card.to_a2a_json()
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/a2a/task/create")
async def create_a2a_task(request: A2ATaskRequest):
    """创建A2A任务"""
    try:
        from core.orchestration.a2a_gateway import get_a2a_gateway

        gateway = get_a2a_gateway()
        task = gateway.create_task(
            request.description, request.context_id, request.metadata
        )
        return {"success": True, "task": task.to_dict()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/a2a/task/send")
async def send_a2a_message(request: A2AMessageRequest):
    """向A2A任务发送消息"""
    try:
        from core.orchestration.a2a_gateway import MessageRole, get_a2a_gateway

        gateway = get_a2a_gateway()
        role = MessageRole(request.role)
        msg = gateway.send_message(request.task_id, request.text, role)
        if not msg:
            raise HTTPException(status_code=404, detail="Task not found")
        return {"success": True, "message": msg.to_dict()}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/a2a/task/{task_id}")
async def get_a2a_task(task_id: str):
    """查询A2A任务状态"""
    try:
        from core.orchestration.a2a_gateway import get_a2a_gateway

        gateway = get_a2a_gateway()
        task = gateway.get_task(task_id)
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
        return task.to_dict()
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/a2a/tasks")
async def list_a2a_tasks(state: str = None, limit: int = 50):
    """列出A2A任务"""
    try:
        from core.orchestration.a2a_gateway import TaskState, get_a2a_gateway

        gateway = get_a2a_gateway()
        filter_state = TaskState(state) if state else None
        tasks = gateway.list_tasks(filter_state, limit)
        return {"tasks": [t.to_dict() for t in tasks], "count": len(tasks)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/a2a/stats")
async def get_a2a_stats():
    """获取A2A网关统计"""
    try:
        from core.orchestration.a2a_gateway import get_a2a_gateway

        gateway = get_a2a_gateway()
        return gateway.get_stats()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── 拓扑进化 ──


@router.get("/evolution/topology")
async def get_evolution_topology():
    """获取当前Agent协作拓扑"""
    try:
        from core.processors.evolving_topology import get_evolution_engine

        engine = get_evolution_engine()
        topology = engine.get_topology()
        return topology.to_dict() if topology else {"error": "No topology"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/evolution/collaboration")
async def record_collaboration(
    source_agent: str,
    target_agent: str,
    task_goal: str = "",
    success: bool = True,
    latency_ms: float = 0,
):
    """记录一次Agent协作 (用于进化学习)"""
    try:
        from core.processors.evolving_topology import get_evolution_engine

        engine = get_evolution_engine()
        engine.record_collaboration(
            source_agent, target_agent, task_goal, success, latency_ms
        )
        return {"success": True, "message": "Collaboration recorded"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/evolution/evolve")
async def trigger_evolution(level: str = "L1"):
    """手动触发进化 (L1/L2/L3)"""
    try:
        from core.processors.evolving_topology import get_evolution_engine

        engine = get_evolution_engine()
        if level == "L1":
            result = engine.evolve_l1_parameters()
        elif level == "L2":
            result = engine.evolve_l2_rules()
        elif level == "L3":
            result = engine.evolve_l3_topology()
        else:
            raise HTTPException(status_code=400, detail=f"Invalid level: {level}")
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/evolution/stats")
async def get_evolution_stats():
    """获取进化引擎统计"""
    try:
        from core.processors.evolving_topology import get_evolution_engine

        engine = get_evolution_engine()
        return engine.get_stats()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/evolution/rules")
async def get_routing_rules(limit: int = 50):
    """获取自动发现的路由规则"""
    try:
        from core.processors.evolving_topology import get_evolution_engine

        engine = get_evolution_engine()
        return {
            "rules": engine.get_routing_rules(limit),
            "count": len(engine.get_routing_rules(limit)),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── WebSocket 流水线全景实时推送 ──


@router.websocket("/ws/pipeline")
async def websocket_pipeline(websocket: WebSocket):
    """WebSocket端点 — 实时推送流水线状态到前端画布"""
    await websocket.accept()

    # 注册回调
    def on_node_change(node):
        try:
            import asyncio

            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.create_task(
                    _ws_send(
                        websocket,
                        {
                            "type": "node_update",
                            "data": node.to_dict(),
                        },
                    )
                )
        except Exception:
            pass

    dag_scheduler = _get_dag_scheduler()
    # 为所有活跃pipeline注册回调
    for pid, pipeline in dag_scheduler._active_pipelines.items():
        pipeline.on_status_change(on_node_change)

    try:
        while True:
            data = await websocket.receive_json()
            action = data.get("action", "")

            if action == "subscribe":
                pipeline_id = data.get("pipeline_id", "")
                pipeline = dag_scheduler.get_pipeline(pipeline_id)
                if pipeline:
                    pipeline.on_status_change(on_node_change)
                    await websocket.send_json(
                        {
                            "type": "subscribed",
                            "pipeline_id": pipeline_id,
                            "dag": pipeline.to_dict(),
                        }
                    )

            elif action == "cancel":
                pipeline_id = data.get("pipeline_id", "")
                cancelled = dag_scheduler.cancel_pipeline(pipeline_id)
                await websocket.send_json(
                    {
                        "type": "cancelled" if cancelled else "error",
                        "pipeline_id": pipeline_id,
                    }
                )

            elif action == "ping":
                await websocket.send_json({"type": "pong"})

    except WebSocketDisconnect:
        pass
    except Exception as e:
        try:
            await websocket.send_json({"type": "error", "message": str(e)})
        except Exception:
            pass


async def _ws_send(ws: WebSocket, data: dict):
    """安全发送WebSocket消息"""
    try:
        await ws.send_json(data)
    except Exception:
        pass
