import { api } from './api'

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

export interface SearchMemoriesRequest {
  query: string
  layer?: MemoryEntry['layer'] | MemoryEntry['layer'][]
  tags?: string[]
  priority?: MemoryEntry['priority'] | MemoryEntry['priority'][]
  namespace?: string
  start_date?: string
  end_date?: string
  dateRange?: [string, string]
  conditions?: Array<{ field: string; operator: string; value: string }>
  limit?: number
  offset?: number
}

export interface SearchMemoriesResponse {
  memories: MemoryEntry[]
  total: number
  limit: number
  offset: number
}

export interface MemoryStats {
  total_memories: number
  by_layer: Record<string, number>
  by_priority: Record<string, number>
  recent_count: number
  storage_size_mb: number
}

export const memoryService = {
  create: async (data: CreateMemoryRequest): Promise<MemoryEntry> => {
    return api.post<MemoryEntry>('/api/memory/', data)
  },

  get: async (id: string): Promise<MemoryEntry> => {
    return api.get<MemoryEntry>(`/api/memory/${id}`)
  },

  update: async (id: string, data: UpdateMemoryRequest): Promise<MemoryEntry> => {
    return api.put<MemoryEntry>(`/api/memory/${id}`, data)
  },

  delete: async (id: string): Promise<void> => {
    return api.delete(`/api/memory/${id}`)
  },

  search: async (params: SearchMemoriesRequest): Promise<SearchMemoriesResponse> => {
    return api.post<SearchMemoriesResponse>('/api/search/', params)
  },

  list: async (params?: {
    layer?: MemoryEntry['layer']
    namespace?: string
    limit?: number
    offset?: number
  }): Promise<SearchMemoriesResponse> => {
    return api.get<SearchMemoriesResponse>('/api/memory/', { params })
  },

  batchDelete: async (ids: string[]): Promise<void> => {
    return api.post('/api/memory/batch-delete', { ids })
  },

  export: async (format: 'json' | 'csv' = 'json'): Promise<Blob> => {
    const response = await api.get(`/api/memory/export`, {
      params: { format },
      responseType: 'blob',
    })
    return response
  },

  import: async (file: File, format: 'json' | 'csv' = 'json'): Promise<{ imported: number }> => {
    const formData = new FormData()
    formData.append('file', file)
    formData.append('format', format)

    return api.post('/api/memory/import', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
  },

  getStats: async (): Promise<MemoryStats> => {
    return api.get<MemoryStats>('/api/memory/stats')
  },
}

export default memoryService
