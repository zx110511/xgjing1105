export interface KGNode {
  id: string
  type: string
  properties: Record<string, any>
  frequency: number
  first_seen?: string
  last_seen?: string
}

export interface KGEdge {
  source: string
  target: string
  relation: string
  weight: number
  timestamp?: string
}

export interface KGTopology {
  nodes: KGNode[]
  edges: KGEdge[]
  meta: {
    total_nodes: number
    total_edges: number
    returned_nodes: number
    returned_edges: number
    mode: string
    sample_rate: number
  }
  communities: Array<{ type: string; count: number; sample_ids: string[] }>
}

export interface KGMetrics {
  T1_scale: { nodes: number; edges: number; entity_types: number; relation_types: number; edge_node_ratio: number }
  T2_topology: { density: number; avg_degree: number; max_degree: number; iso_rate: number; gcc_pct: number; degree_cv: number }
  T3_small_world: { clustering_C: number; sigma: number; diameter: number; avg_path_length: number; C_over_Crand: number }
  T4_scale_free: { hubs: number; richest_ratio: number; entropy: number; power_law_r2: number }
  T5_community: { modularity_Q: number; communities: number; community_details: Array<{ type: string; count: number }>; max_community_pct: number }
  T6_semantic: { temporal_pct: number; causal_edges: number; layers: number; agents: number; concepts: number }
  T7_retrieval: { fts5: boolean; vector_index: boolean; subgraph_ms: number }
  T8_evolution: { incremental: boolean; timestamps: boolean; frequency_tracking: boolean }
  summary: { grade: string; score: number }
}

export interface SSSAuditResult {
  grade: string
  score: number
  total: number
  passed: number
  failed: number
  results: Array<{
    code: string
    name: string
    value: number | string
    threshold: string
    unit: string
    passed: boolean
    weight: number
  }>
  timestamp: number
  // [FIX-TS-004] KGMetricsPanel.tsx 使用的字段
  issues?: string[]
  recommendations?: string[]
}

export interface MemoryStats {
  total_entries: number
  layers: Record<string, number | { entry_count?: number; [key: string]: any }>
}

export interface SimNode {
  id: string
  type: string
  x: number
  y: number
  vx: number
  vy: number
  degree: number
  frequency: number
}

export const TYPE_COLORS: Record<string, string> = {
  layer: '#ffd666',
  module: '#91d5ff',
  agent: '#b7eb8f',
  concept: '#ffadd2',
  skill: '#d3adf7',
  function: '#ffc069',
  class: '#87e8de',
  config: '#ff9c6e',
  route: '#95de64',
  model: '#69c0ff',
  event: '#ff85c0',
  tool: '#bae637',
}

export const DEFAULT_COLOR = '#8c8c8c'

export const CANVAS_CONFIG = {
  WIDTH: 1100,
  HEIGHT: 650,
  NODE_RADIUS_BASE: 5,
  REPULSION: 4000,
  ATTRACTION: 0.003,
  DAMPING: 0.82,
  MAX_ITERATIONS: 300,
} as const

export function getLayerCount(val: number | { entry_count?: number } | undefined): number {
  if (typeof val === 'number') return val
  if (val && typeof val === 'object' && typeof val.entry_count === 'number') return val.entry_count
  return 0
}