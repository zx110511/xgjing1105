import { api } from './api'
import type { MemoryEntry, SearchMemoriesRequest, SearchMemoriesResponse } from './memory-service'

export interface SemanticSearchRequest {
  query: string
  limit?: number
  threshold?: number
  layer?: string
  namespace?: string
}

export interface SemanticSearchResponse {
  results: Array<{
    memory: MemoryEntry
    score: number
    highlights: string[]
  }>
  total: number
  query_time: number
}

export const searchService = {
  search: async (params: SearchMemoriesRequest): Promise<SearchMemoriesResponse> => {
    return api.post<SearchMemoriesResponse>('/api/search/', params)
  },

  semanticSearch: async (params: SemanticSearchRequest): Promise<SemanticSearchResponse> => {
    return api.post<SemanticSearchResponse>('/api/search/semantic', params)
  },

  suggest: async (query: string, limit: number = 5): Promise<string[]> => {
    return api.get<string[]>('/api/search/quick', {
      params: { q: query, limit },
    })
  },

  getSearchHistory: async (
    limit: number = 10
  ): Promise<Array<{ query: string; timestamp: string }>> => {
    return api.get<Array<{ query: string; timestamp: string }>>('/api/search/history', {
      params: { limit },
    })
  },

  clearSearchHistory: async (): Promise<void> => {
    return api.delete('/api/search/history')
  },

  getRelatedMemories: async (memoryId: string, limit: number = 5): Promise<MemoryEntry[]> => {
    return api.get<MemoryEntry[]>(`/api/memory/${memoryId}/related`, {
      params: { limit },
    })
  },

  getSearchSuggestions: async (partialQuery: string): Promise<string[]> => {
    if (!partialQuery || partialQuery.length < 2) {
      return []
    }
    return api.get<string[]>('/api/search/quick', {
      params: { q: partialQuery },
    })
  },

  getIndexStatus: async (): Promise<any> => {
    return api.get<any>('/api/search/index/status')
  },
}

export default searchService
