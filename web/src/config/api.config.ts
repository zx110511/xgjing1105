export interface ApiConfig {
  baseURL: string
  timeout: number
  retryAttempts: number
  retryDelay: number
  headers: Record<string, string>
}

const isDevelopment = import.meta.env.DEV
const isProduction = import.meta.env.PROD

function resolveBaseURL(): string {
  const envURL = import.meta.env.VITE_API_BASE_URL

  if (envURL && envURL.trim() !== '') {
    return envURL.trim()
  }

  // Tauri桌面模式: 后端运行在本地端口
  if (window.__TAURI_INTERNALS__) {
    return 'http://127.0.0.1:8771'
  }

  if (isProduction) {
    return window.location.origin
  }

  return 'http://localhost:8771'
}

const resolvedBaseURL = resolveBaseURL()

const sharedConfig: Omit<ApiConfig, 'baseURL'> = {
  timeout: 30000,
  retryAttempts: 3,
  retryDelay: 1000,
  headers: {
    'Content-Type': 'application/json',
  },
}

const developmentConfig: ApiConfig = {
  baseURL: resolvedBaseURL,
  ...sharedConfig,
}

const productionConfig: ApiConfig = {
  baseURL: resolvedBaseURL,
  ...sharedConfig,
}

export const apiConfig: ApiConfig = isDevelopment ? developmentConfig : productionConfig

export const endpoints = {
  memories: {
    list: '/api/memory/',
    create: '/api/memory/',
    get: (id: string) => `/api/memory/${id}`,
    update: (id: string) => `/api/memory/${id}`,
    delete: (id: string) => `/api/memory/${id}`,
    batchDelete: '/api/memory/batch-delete',
    search: '/api/search/',
    semanticSearch: '/api/search/semantic',
    suggest: '/api/search/quick',
    related: (id: string) => `/api/memory/${id}`,
    stats: '/api/memory/stats',
    layersInfo: '/api/memory/layers/info',
  },
  search: {
    history: '/api/search/quick',
    clearHistory: '/api/search/quick',
    suggestions: '/api/search/quick',
    quick: '/api/search/quick',
    semantic: '/api/search/semantic',
    byTag: (tag: string) => `/api/search/by-tag/${tag}`,
    indexStatus: '/api/search/index/status',
  },
  system: {
    health: '/api/health',
    stats: '/api/stats',
    config: '/api/config',
  },
  orchestrator: {
    status: '/api/orchestrator/status',
    agents: '/api/orchestrator/agents',
    pipelines: '/api/orchestrator/pipelines',
    track: '/api/orchestrator/track',
    parallelDispatch: '/api/orchestrator/parallel/dispatch',
    pipelineCreate: '/api/orchestrator/pipeline/create',
    stageSwitch: '/api/orchestrator/pipeline/stage/switch',
    stageComplete: '/api/orchestrator/pipeline/stage/complete',
  },
  activeMemory: {
    interceptInput: '/api/active/intercept_input',
    interceptResponse: '/api/active/intercept_response',
    platforms: '/api/active/platforms',
    session: (sessionId: string) => `/api/active/session/${sessionId}`,
    subagentExecute: '/api/active/subagent_execute',
  },
  deepseek: {
    classify: '/api/llm/classify',
    analyzeValue: '/api/llm/analyze_value',
    decideStorage: '/api/llm/decide_storage',
    extractKnowledge: '/api/llm/extract_knowledge',
    expandQuery: '/api/llm/expand_query',
    autoTag: '/api/llm/auto_tag',
    summarize: '/api/llm/summarize',
    status: '/api/llm/status',
  },
  mcp: {
    storeMemory: '/api/mcp/tools/store_memory',
    searchMemories: '/api/mcp/tools/search_memories',
    getMemory: '/api/mcp/tools/get_memory',
    listMemories: '/api/mcp/tools/list_memories',
    deleteMemory: '/api/mcp/tools/delete_memory',
    listNamespaces: '/api/mcp/tools/list_namespaces',
    getStats: '/api/mcp/tools/get_stats',
    getSessionDigest: '/api/mcp/tools/get_session_digest',
    runReflectiveCycle: '/api/mcp/tools/run_reflective_cycle',
    explainLineage: '/api/mcp/tools/explain_memory_lineage',
    buildWorkingRep: '/api/mcp/tools/build_working_representation',
    searchPerspective: '/api/mcp/tools/search_perspective_memories',
    initializeNexus: '/api/mcp/tools/initialize_nexus_system',
    toolHelp: '/api/mcp/tools/tool_help',
    toolSchema: '/api/mcp/tools/tool_schema',
  },
  summary: {
    conversation: '/api/summary/conversation',
    recent: '/api/summary/recent',
  },
  platform: {
    event: '/api/platform/event',
    remember: '/api/platform/remember',
    recall: '/api/platform/recall',
    platformStats: '/api/platform/stats',
    health: '/api/platform/health',
  },
  knowledgeGraph: {
    nodes: '/api/kg/nodes',
    nodeDetail: (id: string) => `/api/kg/nodes/${encodeURIComponent(id)}`,
    createNode: '/api/kg/nodes',
    deleteNode: (id: string) => `/api/kg/nodes/${encodeURIComponent(id)}`,
    edges: '/api/kg/edges',
    createEdge: '/api/kg/edges',
    deleteEdge: '/api/kg/edges',
    topology: '/api/kg/topology',
    metrics: '/api/kg/metrics',
    community: '/api/kg/community',
    sssAudit: '/api/kg/sss-audit',
    search: '/api/kg/search',
    subgraph: (id: string) => `/api/kg/subgraph/${encodeURIComponent(id)}`,
    path: '/api/kg/path',
    rebuild: '/api/kg/rebuild',
    rebuildStatus: '/api/kg/rebuild/status',
    optimize: '/api/kg/optimize',
    syncStats: '/api/kg/sync/stats',
    tvpEvents: '/api/kg/tvp-events',
    stats: '/api/kg/stats',
  },
}

export const getApiUrl = (endpoint: string): string => {
  return `${apiConfig.baseURL}${endpoint}`
}

export default apiConfig
