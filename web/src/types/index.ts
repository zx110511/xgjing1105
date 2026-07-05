export interface MemoryEntry {
  id: string
  content: string
  layer: 'sensory' | 'working' | 'short_term' | 'episodic' | 'semantic' | 'meta'
  tags: string[]
  priority: 'low' | 'medium' | 'high' | 'critical'
  namespace: string
  created_at: string
  updated_at: string
  metadata?: Record<string, any>
}

// [FIX-TS-010] 补充缺失的 CreateMemoryRequest/UpdateMemoryRequest 导出
// (MemoryForm.tsx 从 '../types' 导入这些类型)
export interface CreateMemoryRequest {
  content: string
  layer: MemoryEntry['layer']
  tags?: string[]
  priority?: MemoryEntry['priority']
  namespace?: string
  metadata?: Record<string, any>
}

export interface UpdateMemoryRequest {
  content?: string
  layer?: MemoryEntry['layer']
  tags?: string[]
  priority?: MemoryEntry['priority']
  metadata?: Record<string, any>
}

export interface ApiResponse<T = any> {
  success: boolean
  data?: T
  error?: string
  message?: string
}

export interface PaginatedResponse<T = any> {
  items: T[]
  total: number
  limit: number
  offset: number
}

export type MemoryLayer = MemoryEntry['layer']
export type MemoryPriority = MemoryEntry['priority']

export const MEMORY_LAYERS: Record<MemoryLayer, { name: string; color: string }> = {
  sensory: { name: '感知记忆', color: '#722ed1' },
  working: { name: '工作记忆', color: '#1890ff' },
  short_term: { name: '短期记忆', color: '#13c2c2' },
  episodic: { name: '情景记忆', color: '#52c41a' },
  semantic: { name: '语义记忆', color: '#fa8c16' },
  meta: { name: '元记忆', color: '#eb2f96' },
}

export const MEMORY_PRIORITIES: Record<MemoryPriority, { name: string; color: string }> = {
  low: { name: '低', color: 'default' },
  medium: { name: '中', color: 'blue' },
  high: { name: '高', color: 'orange' },
  critical: { name: '关键', color: 'red' },
}

export interface SystemStatsResponse {
  timestamp: number
  version: string
  module_count: number
  modules: Record<string, ModuleStatus>
  coverage: { total: number; online: number; with_stats: number }
  memory_total: number
  memory_by_layer: Record<string, number>
  uptime_seconds: number
}

export interface ModuleStatus {
  status: 'pend_active' | 'offline' | 'error'
  last_update: number
  [key: string]: any
}

export interface OperationsHeader {
  header: string
  recent_count: number
  categories: string[]
}

export interface OperationsSummary {
  total_operations: number
  by_category: Record<string, { count: number; label: string }>
  recent?: Array<{
    time_str: string
    category: string
    action: string
    detail: string
    result: string
  }>
  tvp_declarations?: Array<{
    time_str: string
    action: string
    detail: string
  }>
  mcp_calls?: Array<{
    time_str: string
    action: string
    detail: string
  }>
  memory_ops?: Array<{
    time_str: string
    action: string
    detail: string
  }>
}

export interface OperationsLogEntry {
  id: string
  timestamp: number
  time_str: string
  category: 'tvp' | 'mcp' | 'memory' | 'llm'
  action: string
  detail: string
  result: 'ok' | 'fail'
  duration_ms?: number
  source?: string
}

export interface HealthCheckResponse {
  status: string
  version: string
  engine_ready: boolean
  embedding_ready: boolean
  layers: Record<string, number>
  uptime: number
  storage_backend?: string
  db_size_mb?: number
}

export interface MemoryStatsResponse {
  total_entries: number
  total_accesses: number
  uptime_seconds: number
  layers: Record<string, number>
  archive_entries: number
}

export interface LayerCapacityResponse {
  layer: string
  used_bytes: number
  max_bytes: number
  entry_count: number
  max_entries: number
  utilization_pct: number
}

export interface LLMClassifyRequest {
  content: string
}

export interface LLMClassifyResponse {
  predicted_layer: string
  confidence: number
  suggested_tags: string[]
  suggested_priority: string
}
