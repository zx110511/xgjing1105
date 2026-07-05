import { create } from 'zustand'
import { devtools, persist, createJSONStorage } from 'zustand/middleware'
import { api } from '../services/api'

interface LlmFeatures {
  classify: boolean
  auto_tag: boolean
  summarize: boolean
  extract_knowledge: boolean
}

interface LlmConfig {
  api_key?: string
  base_url?: string
  temperature: number
  max_tokens: number
  top_p: number
  features: LlmFeatures
}

interface ConfigState {
  configData: Record<string, any> | null
  llmConfig: LlmConfig | null
  llmStatus: {
    brain: string
    configured: boolean
    model: string | null
    bridge_injected: boolean
    bridge_stats: Record<string, unknown>
  } | null
  loading: boolean
  error: string | null
  lastFetched: number | null

  fetchConfig: () => Promise<void>
  fetchLlmStatus: () => Promise<void>
  saveConfig: (data: Record<string, any>) => Promise<void>
  toggleLlmFeature: (feature: keyof LlmFeatures, checked: boolean) => void
  testLlm: (input: string) => Promise<{ response: string; latency: number }>
  clearError: () => void
}

export const useConfigStore = create<ConfigState>()(
  devtools(
    persist(
      (set, get) => ({
        configData: null,
        llmConfig: {
          temperature: 0.7,
          max_tokens: 2000,
          top_p: 0.9,
          features: { classify: true, auto_tag: true, summarize: true, extract_knowledge: false },
        },
        llmStatus: null,
        loading: false,
        error: null,
        lastFetched: null,

        fetchConfig: async () => {
          set({ loading: true, error: null })
          try {
            const res = await api.get('/api/config')
            set({
              configData: res,
              llmConfig: res?.llm || get().llmConfig,
              loading: false,
              lastFetched: Date.now(),
            })
          } catch {
            set({ error: '配置加载失败，使用本地缓存', loading: false })
          }
        },

        fetchLlmStatus: async () => {
          try {
            const res = await api.get('/api/llm/status')
            set({ llmStatus: res })
          } catch {
            // 静默降级
          }
        },

        saveConfig: async (data) => {
          set({ loading: true, error: null })
          try {
            await api.post('/api/config', data)
            set({ configData: data, loading: false })
          } catch (err: any) {
            set({ error: err?.message || '保存失败', loading: false })
            throw err
          }
        },

        toggleLlmFeature: (feature, checked) => {
          const current = get().llmConfig
          if (!current) return
          set({
            llmConfig: {
              ...current,
              features: { ...current.features, [feature]: checked },
            },
          })
        },

        testLlm: async (input) => {
          const res = await api.post('/api/llm/classify', { content: input })
          return { response: JSON.stringify(res), latency: 0 }
        },

        clearError: () => set({ error: null }),
      }),
      {
        name: 'tianji-config-store',
        storage: createJSONStorage(() => sessionStorage),
        partialize: (state) => ({
          configData: state.configData,
          llmConfig: state.llmConfig,
          llmStatus: state.llmStatus,
          lastFetched: state.lastFetched,
        }),
      }
    ),
    { name: 'config-store' }
  )
)

export default useConfigStore
