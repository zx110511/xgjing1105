/** 天机v9.1 调度引擎 TypeScript 类型定义 */

export interface DAGNodeData {
  id: string
  type: string
  data: {
    label: string
    agent_id: string
    agent_name: string
    agent_emoji: string
    status: 'pending' | 'ready' | 'running' | 'completed' | 'failed' | 'skipped' | 'cancelled'
    duration_s: number
    error?: string | null
  }
  position: { x: number; y: number }
}

export interface DAGEdgeData {
  id: string
  source: string
  target: string
  type: string
  animated: boolean
  data: {
    type: string
    condition?: string
  }
}

export interface DAGPipelineData {
  pipeline_id: string
  pipeline_name: string
  status: string
  stats: {
    total: number
    pending: number
    ready: number
    running: number
    completed: number
    failed: number
    skipped: number
  }
  nodes: DAGNodeData[]
  edges: DAGEdgeData[]
  levels: string[][]
}

export interface SubTaskData {
  index: number
  goal: string
  agent_id: string
  agent_name: string
  agent_emoji: string
  depends_on: number[]
  can_parallel: boolean
  estimated_duration_s: number
}

export interface TaskPlanData {
  plan_id: string
  original_task: string
  complexity: 'low' | 'medium' | 'high' | 'very_high'
  strategy: 'single_agent' | 'serial_chain' | 'parallel_batch' | 'dag_pipeline'
  reasoning: string
  confidence: number
  suggested_agents: string[]
  warnings: string[]
  sub_tasks: SubTaskData[]
}

export interface PlanResponse {
  success: boolean
  plan: TaskPlanData
  dag: DAGPipelineData
}

export interface DAGBuildRequest {
  pipeline_name: string
  nodes: Array<{
    agent_id: string
    goal: string
    context?: string
    tools?: string[]
    priority?: string
    timeout_s?: number
  }>
  edges: Array<{
    source_index: number
    target_index: number
    type?: string
  }>
}

export interface DAGExecuteRequest {
  plan_id?: string
  dag_json?: DAGPipelineData
  parallel?: boolean
  node_executor_type?: string
}

export interface DAGExecuteResponse {
  success: boolean
  pipeline_id: string
  result: {
    success: boolean
    nodes_completed: number
    nodes_failed: number
    pipeline_id: string
    duration_s?: number
  }
  dag: DAGPipelineData
}

export interface WorkflowData {
  workflow_id: string
  workflow_name: string
  status: string
  steps: Array<{
    step_id: string
    step_name: string
    status: string
    duration_s: number
    error?: string | null
    retry_count: number
  }>
  current_step_index: number
  checkpoint_version: number
  error?: string | null
  duration_s: number
}

export interface WorkflowEvent {
  event_id: string
  workflow_id: string
  event_type: string
  step_id: string
  event_data_json: string
  timestamp: number
}

export interface OrchestratorStats {
  dag_scheduler: {
    version: string
    pipelines_executed: number
    nodes_executed: number
    nodes_failed: number
    total_duration_s: number
    active_pipelines: number
  }
  checkpoint: {
    total_workflows: number
    completed: number
    failed: number
    running: number
    db_path: string
    db_size_mb: number
  }
  planner: {
    version: string
    plans_created: number
    llm_plans: number
    rule_plans: number
    avg_confidence: number
  }
  timestamp: number
}

export interface V10RootResponse {
  version: string
  status: string
  modules: Record<string, string>
  endpoints: string[]
}

export type NodeStatusColor = Record<string, string>

export const NODE_STATUS_COLORS: NodeStatusColor = {
  pending: '#d9d9d9',
  ready: '#91d5ff',
  running: '#1890ff',
  completed: '#52c41a',
  failed: '#ff4d4f',
  skipped: '#faad14',
  cancelled: '#8c8c8c',
}
