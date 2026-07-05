import { create } from 'zustand'
import { devtools, persist, createJSONStorage } from 'zustand/middleware'
import {
  MemoryEntry,
  CreateMemoryRequest,
  UpdateMemoryRequest,
  SearchMemoriesRequest,
} from '../services/memory-service'
import memoryService from '../services/memory-service'

interface MemoryState {
  memories: MemoryEntry[]
  currentMemory: MemoryEntry | null
  loading: boolean
  error: string | null
  total: number
  searchParams: SearchMemoriesRequest
  lastSyncTime: number | null

  fetchMemories: (params?: SearchMemoriesRequest) => Promise<void>
  fetchMemory: (id: string) => Promise<void>
  createMemory: (data: CreateMemoryRequest) => Promise<void>
  updateMemory: (id: string, data: UpdateMemoryRequest) => Promise<void>
  deleteMemory: (id: string) => Promise<void>
  batchDeleteMemories: (ids: string[]) => Promise<void>
  searchMemories: (params: SearchMemoriesRequest) => Promise<void>
  clearError: () => void
  setCurrentMemory: (memory: MemoryEntry | null) => void
}

export const useMemoryStore = create<MemoryState>()(
  devtools(
    persist(
      (set, get) => ({
        memories: [],
        currentMemory: null,
        loading: false,
        error: null,
        total: 0,
        lastSyncTime: null,
        searchParams: {
          query: '',
          limit: 20,
          offset: 0,
        },

        fetchMemories: async (params) => {
          set({ loading: true, error: null })
          try {
            const searchParams = { ...get().searchParams, ...params }
            const response = await memoryService.list(searchParams as any)
            set({
              memories: response.memories,
              total: response.total,
              searchParams,
              lastSyncTime: Date.now(),
              loading: false,
            })
          } catch (error: any) {
            set({ error: error.message || '获取记忆列表失败', loading: false })
          }
        },

        fetchMemory: async (id) => {
          set({ loading: true, error: null })
          try {
            const memory = await memoryService.get(id)
            set({ currentMemory: memory, loading: false })
          } catch (error: any) {
            set({ error: error.message || '获取记忆详情失败', loading: false })
          }
        },

        createMemory: async (data) => {
          set({ loading: true, error: null })
          try {
            const memory = await memoryService.create(data)
            set((state) => ({
              memories: [memory, ...state.memories],
              total: state.total + 1,
              loading: false,
            }))
          } catch (error: any) {
            set({ error: error.message || '创建记忆失败', loading: false })
            throw error
          }
        },

        updateMemory: async (id, data) => {
          set({ loading: true, error: null })
          try {
            const memory = await memoryService.update(id, data)
            set((state) => ({
              memories: state.memories.map((m) => (m.id === id ? memory : m)),
              currentMemory: state.currentMemory?.id === id ? memory : state.currentMemory,
              loading: false,
            }))
          } catch (error: any) {
            set({ error: error.message || '更新记忆失败', loading: false })
            throw error
          }
        },

        deleteMemory: async (id) => {
          set({ loading: true, error: null })
          try {
            await memoryService.delete(id)
            set((state) => ({
              memories: state.memories.filter((m) => m.id !== id),
              total: state.total - 1,
              currentMemory: state.currentMemory?.id === id ? null : state.currentMemory,
              loading: false,
            }))
          } catch (error: any) {
            set({ error: error.message || '删除记忆失败', loading: false })
            throw error
          }
        },

        batchDeleteMemories: async (ids) => {
          set({ loading: true, error: null })
          try {
            await memoryService.batchDelete(ids)
            set((state) => ({
              memories: state.memories.filter((m) => !ids.includes(m.id)),
              total: state.total - ids.length,
              loading: false,
            }))
          } catch (error: any) {
            set({ error: error.message || '批量删除失败', loading: false })
            throw error
          }
        },

        searchMemories: async (params) => {
          set({ loading: true, error: null })
          try {
            const searchParams = { ...get().searchParams, ...params }
            const response = await memoryService.search(searchParams)
            set({
              memories: response.memories,
              total: response.total,
              searchParams,
              loading: false,
            })
          } catch (error: any) {
            set({ error: error.message || '搜索记忆失败', loading: false })
          }
        },

        clearError: () => set({ error: null }),

        setCurrentMemory: (memory) => set({ currentMemory: memory }),
      }),
      {
        name: 'tianji-memory-store',
        storage: createJSONStorage(() => sessionStorage),
        partialize: (state) => ({
          memories: state.memories.slice(0, 50),
          searchParams: state.searchParams,
          lastSyncTime: state.lastSyncTime,
        }),
      }
    ),
    { name: 'memory-store' }
  )
)

export default useMemoryStore
