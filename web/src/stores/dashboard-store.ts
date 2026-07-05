import { create } from 'zustand'
import { devtools, persist, createJSONStorage } from 'zustand/middleware'
import { api } from '../services/api'

interface DashboardMetrics {
  health: Record<string, any> | null
  memoryStats: Record<string, any> | null
  systemStats: Record<string, any> | null
  deepseekStatus: Record<string, any> | null
  chainScores: Array<{ key: string; name: string; composite: number; health: number }>
  standardScores: Array<{ key: string; name: string; score: number }>
  trends: Array<{ timestamp: number; value: number; label: string }>
}

interface DashboardState {
  metrics: DashboardMetrics
  loading: boolean
  error: string | null
  lastFetched: number | null
  autoRefresh: boolean

  fetchAllMetrics: () => Promise<void>
  fetchHealth: () => Promise<void>
  fetchChainScores: () => Promise<void>
  fetchStandardScores: () => Promise<void>
  setAutoRefresh: (enabled: boolean) => void
  clearError: () => void
}

const DEFAULT_METRICS: DashboardMetrics = {
  health: null,
  memoryStats: null,
  systemStats: null,
  deepseekStatus: null,
  chainScores: [],
  standardScores: [],
  trends: [],
}

export const useDashboardStore = create<DashboardState>()(
  devtools(
    persist(
      (set) => ({
        metrics: DEFAULT_METRICS,
        loading: false,
        error: null,
        lastFetched: null,
        autoRefresh: true,

        fetchAllMetrics: async () => {
          set({ loading: true, error: null })
          try {
            const [healthRes, memRes, statsRes, dsRes] = await Promise.allSettled([
              api.get('/api/health'),
              api.get('/api/memory/stats'),
              api.get('/api/system/stats'),
              api.get('/api/llm/status'),
            ])

            const health = healthRes.status === 'fulfilled' ? healthRes.value : null
            const memoryStats = memRes.status === 'fulfilled' ? memRes.value : null
            const systemStats = statsRes.status === 'fulfilled' ? statsRes.value : null
            const deepseekStatus = dsRes.status === 'fulfilled' ? dsRes.value : null

            set({
              metrics: {
                health,
                memoryStats,
                systemStats,
                deepseekStatus,
                chainScores: [],
                standardScores: [],
                trends: [],
              },
              loading: false,
              lastFetched: Date.now(),
            })
          } catch {
            set({ error: '指标加载失败', loading: false })
          }
        },

        fetchHealth: async () => {
          try {
            const health = await api.get('/api/health')
            set((state) => ({
              metrics: { ...state.metrics, health },
            }))
          } catch {
            // 静默降级
          }
        },

        fetchChainScores: async () => {
          try {
            const res = await api.get('/api/governance/status')
            if (res?.chains) {
              set((state) => ({
                metrics: {
                  ...state.metrics,
                  chainScores: res.chains.map((c: any) => ({
                    key: c.key || c.name,
                    name: c.name || c.key,
                    composite: c.composite || c.score || 0,
                    health: c.health || 0,
                  })),
                  standardScores: res.standards?.map((s: any) => ({
                    key: s.key || s.name,
                    name: s.name || s.key,
                    score: s.score || 0,
                  })) || [],
                },
              }))
            }
          } catch {
            // 静默降级 - 保留上次数据
          }
        },

        fetchStandardScores: async () => {
          try {
            const res = await api.get('/api/standards/report')
            if (res) {
              // Direct standard report, chain scores already handled in fetchChainScores
            }
          } catch {
            // 静默降级
          }
        },

        setAutoRefresh: (enabled) => set({ autoRefresh: enabled }),

        clearError: () => set({ error: null }),
      }),
      {
        name: 'tianji-dashboard-store',
        storage: createJSONStorage(() => sessionStorage),
        partialize: (state) => ({
          metrics: state.metrics,
          lastFetched: state.lastFetched,
        }),
      }
    ),
    { name: 'dashboard-store' }
  )
)

export default useDashboardStore
