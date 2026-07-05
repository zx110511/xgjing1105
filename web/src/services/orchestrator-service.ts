import { api } from './api'
import type {
    PlanResponse,
    DAGBuildRequest,
    DAGExecuteRequest,
    DAGExecuteResponse,
    DAGPipelineData,
    WorkflowData,
    WorkflowEvent,
    OrchestratorStats,
    V10RootResponse,
} from '../types/orchestrator'

const BASE = '/api/orchestrator/v9.1'

export const orchestratorService = {
    /** 获取v10引擎根信息 */
    getRoot: () => api.get<V10RootResponse>(`${BASE}/`),

    /** LLM任务规划: 自然语言→DAG流水线 */
    plan: (task: string, context?: string, preferLlm?: boolean) =>
        api.post<PlanResponse>(`${BASE}/plan`, {
            task,
            context: context || '',
            prefer_llm: preferLlm ?? true,
        }),

    /** 手动构建DAG流水线 */
    buildDAG: (request: DAGBuildRequest) =>
        api.post<{ success: boolean; pipeline_id: string; dag: DAGPipelineData; has_cycle: boolean }>(
            `${BASE}/dag/build`,
            request
        ),

    /** 执行DAG流水线 */
    executeDAG: (request: DAGExecuteRequest) =>
        api.post<DAGExecuteResponse>(`${BASE}/dag/execute`, request),

    /** 查询DAG流水线状态 */
    getDAGStatus: (pipelineId: string) => api.get<DAGPipelineData>(`${BASE}/dag/${pipelineId}`),

    /** 获取DAG拓扑数据 (含自动布局) */
    getDAGTopology: (pipelineId: string) =>
        api.get<DAGPipelineData>(`${BASE}/dag/${pipelineId}/topology`),

    /** 创建持久化工作流 */
    createWorkflow: (
        workflowName: string,
        steps: Array<{ step_name: string; compensation_fn?: string }>
    ) =>
        api.post<{ success: boolean; workflow: WorkflowData }>(`${BASE}/workflow/create`, {
            workflow_name: workflowName,
            steps,
        }),

    /** 恢复工作流 */
    resumeWorkflow: (workflowId: string) =>
        api.post<{ success: boolean; workflow: WorkflowData }>(`${BASE}/workflow/resume`, {
            workflow_id: workflowId,
        }),

    /** 查询工作流状态 */
    getWorkflow: (workflowId: string) => api.get<WorkflowData>(`${BASE}/workflow/${workflowId}`),

    /** 获取工作流事件历史 */
    getWorkflowEvents: (workflowId: string, limit?: number) =>
        api.get<{ workflow_id: string; events: WorkflowEvent[]; count: number }>(
            `${BASE}/workflow/${workflowId}/events`,
            { params: { limit: limit || 100 } }
        ),

    /** 列出所有工作流 */
    listWorkflows: (status?: string, limit?: number) =>
        api.get<{ workflows: WorkflowData[]; count: number }>(`${BASE}/workflows`, {
            params: { status, limit: limit || 50 },
        }),

    /** 获取调度引擎统计 */
    getStats: () => api.get<OrchestratorStats>(`${BASE}/stats`),

    /** 获取 Agent 真实运行统计 (基于 ToolCallTracker 实际调用记录) */
    getAgentStats: () =>
        api.get<{
            success: boolean
            total_calls: number
            agents: Record<
                string,
                {
                    agent_id: string
                    agent_name: string
                    task_count: number
                    success_rate: number
                    avg_duration_s: number
                    tools: string[]
                }
            >
        }>('/api/orchestrator/agent-stats'),

    /** 获取A2A Agent卡片列表 */
    getAgentCards: () =>
        api.get<{
            agent_cards: Array<{
                name: string
                description: string
                url: string
                version: string
                capabilities: Record<string, boolean>
                skills: Array<{ id: string; name: string; description: string }>
            }>
            count: number
        }>(`${BASE}/a2a/agent-cards`),

    /** 获取A2A协作统计 */
    getA2AStats: () =>
        api.get<{
            version: string
            total_tasks: number
            tasks_by_state: Record<string, number>
            agent_cards: number
            sse_subscribers: number
        }>(`${BASE}/a2a/stats`),

    /** 创建WebSocket连接 */
    createPipelineSocket: (): WebSocket => {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
        const host = window.location.host || 'localhost:8771'
        return new WebSocket(`${protocol}//${host}${BASE}/ws/pipeline`)
    },
}
