import api, { endpoints } from './api'
import memoryService from './memory-service'
import searchService from './search-service'
import metricsService from './metrics-service'
import { apiCache, cachedApi } from './cache'

export type {
  MemoryEntry,
  CreateMemoryRequest,
  UpdateMemoryRequest,
  SearchMemoriesRequest,
  SearchMemoriesResponse,
  MemoryStats,
} from './memory-service'

export interface SystemHealth {
  status: string
  version: string
  uptime: number
  database: string
  llm: string
}

export interface SystemStats {
  total_memories: number
  total_tags: number
  total_namespaces: number
  memory_by_layer: Record<string, number>
  memory_by_priority: Record<string, number>
  storage_size: number
}

export interface LLMChatRequest {
  messages: Array<{ role: string; content: string }>
  model?: string
  temperature?: number
  max_tokens?: number
}

export interface LLMChatResponse {
  response: string
  model: string
  usage: {
    prompt_tokens: number
    completion_tokens: number
    total_tokens: number
  }
}

export const systemService = {
  // [FIX-TS-014] 修复 AxiosResponse 类型不匹配: 提取 .data 字段
  getHealth: async (): Promise<SystemHealth> => {
    const res = await api.get<SystemHealth>(endpoints.system.health)
    return (res as any).data ?? res
  },

  getStats: async (): Promise<SystemStats> => {
    const res = await api.get<SystemStats>(endpoints.system.stats)
    return (res as any).data ?? res
  },

  getConfig: async (): Promise<Record<string, any>> => {
    const res = await api.get<Record<string, any>>(endpoints.system.config)
    return (res as any).data ?? res
  },
}

export const llmService = {
  chat: async (request: LLMChatRequest): Promise<LLMChatResponse> => {
    const res = await api.post<LLMChatResponse>(endpoints.deepseek.classify, request)
    return (res as any).data ?? res
  },

  complete: async (prompt: string, options?: any): Promise<string> => {
    const res = await api.post<string>(endpoints.deepseek.summarize, { prompt, ...options })
    return (res as any).data ?? res
  },

  embed: async (text: string): Promise<number[]> => {
    const res = await api.post<number[]>(endpoints.deepseek.classify, { text })
    return (res as any).data ?? res
  },
}

export const apiService = {
  memory: memoryService,
  search: searchService,
  metrics: metricsService,
  system: systemService,
  llm: llmService,

  getMemories: memoryService.list,
  createMemory: memoryService.create,
  updateMemory: memoryService.update,
  deleteMemory: memoryService.delete,
  batchDeleteMemories: memoryService.batchDelete,

  searchMemories: searchService.search,
  semanticSearch: searchService.semanticSearch,

  getSystemHealth: systemService.getHealth,
  getSystemStats: systemService.getStats,

  chat: llmService.chat,
  embed: llmService.embed,
}

export { apiCache, cachedApi }
export type { CacheStats } from './cache'

export default apiService
