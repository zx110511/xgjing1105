export interface MetricDefinition {
  name: string
  display_name: string
  metric_type: 'counter' | 'gauge' | 'histogram' | 'summary'
  source_type: 'engine_api' | 'container_module' | 'file' | 'derived' | 'memory'
  anchor_policy: 'full' | 'sample' | 'none'
  interval_seconds: number
  unit: string
  category: string
  description: string
  tags: Record<string, string>
}

export interface MetricSnapshot {
  name: string
  timestamp: number
  value: any
  metric_type: string
  unit: string
  anchor_id: string | null
}

export interface MetricEntry {
  definition: MetricDefinition
  snapshot: MetricSnapshot | null
  stale: boolean
}

export interface MetricsLatestResponse {
  status: string
  timestamp: number
  total_metrics: number
  with_snapshots: number
  by_category: Record<string, MetricEntry[]>
  snapshots: Record<string, MetricEntry>
}

export interface MetricHistoryPoint {
  name: string
  timestamp: number
  value: any
  metric_type: string
  unit: string
  anchor_id: string | null
}

export interface MetricHistoryResponse {
  status: string
  metric: string
  display_name: string
  unit: string
  category: string
  window_seconds: number
  total_points: number
  points: MetricHistoryPoint[]
}

export interface MetricVerifyResult {
  status: string
  metric: string
  original?: any
  replayed?: any
  match?: boolean
  timestamp?: number
  anchor_id?: string
  detail?: string
}

export interface MetricVerifyAllResponse {
  status: string
  timestamp: number
  total: number
  verified: number
  mismatched: number
  results: Record<string, MetricVerifyResult>
}

export interface CollectorStatus {
  status: string
  running: boolean
  registry_stats: {
    total_metrics: number
    total_snapshots: number
    metrics_by_category: Record<string, number>
    latest_timestamps: Record<string, number>
  }
  uptime_seconds: number
  anchor_db_size: number
  adapters: string[]
}

export interface MetricDefinitionsResponse {
  status: string
  total: number
  categories: string[]
  definitions: MetricDefinition[]
}

export const METRIC_CATEGORY_COLORS: Record<string, string> = {
  memory: '#1890ff',
  system: '#52c41a',
  module: '#722ed1',
  search: '#fa8c16',
  llm: '#eb2f96',
  evolution: '#13c2c2',
}

export const METRIC_CATEGORY_NAMES: Record<string, string> = {
  memory: '记忆系统',
  system: '系统状态',
  module: '模块管理',
  search: '语义搜索',
  llm: '大模型',
  evolution: '进化引擎',
}
