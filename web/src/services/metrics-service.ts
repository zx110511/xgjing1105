import { api } from './api'
import {
  MetricsLatestResponse,
  MetricHistoryResponse,
  MetricVerifyResult,
  MetricVerifyAllResponse,
  CollectorStatus,
  MetricDefinitionsResponse,
} from '../types/metrics'

export const metricsService = {
  getLatest: async (category?: string): Promise<MetricsLatestResponse> => {
    const params = category ? { category } : {}
    return api.get('/api/metrics/latest', { params })
  },

  getHistory: async (
    name: string,
    windowSeconds: number = 600,
    limit: number = 200
  ): Promise<MetricHistoryResponse> => {
    return api.get(`/api/metrics/history/${encodeURIComponent(name)}`, {
      params: { window_seconds: windowSeconds, limit },
    })
  },

  verify: async (name: string): Promise<MetricVerifyResult> => {
    return api.post(`/api/metrics/verify/${encodeURIComponent(name)}`)
  },

  verifyAll: async (): Promise<MetricVerifyAllResponse> => {
    return api.post('/api/metrics/verify-all')
  },

  getStatus: async (): Promise<CollectorStatus> => {
    return api.get('/api/metrics/status')
  },

  getDefinitions: async (category?: string): Promise<MetricDefinitionsResponse> => {
    const params = category ? { category } : {}
    return api.get('/api/metrics/definitions', { params })
  },
}

export default metricsService
