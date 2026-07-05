import axios, { AxiosInstance, AxiosRequestConfig, AxiosResponse, AxiosError } from 'axios'
import { message } from 'antd'
import { apiConfig, endpoints } from '../config/api.config'

declare module 'axios' {
    interface AxiosRequestConfig {
        metadata?: { requestId: string; startTime: number }
        retryCount?: number
    }
}

interface RetryConfig {
    retries: number
    retryDelay: number
    retryCondition?: (error: AxiosError) => boolean
}

const isNetworkError = (error: AxiosError): boolean => {
    return !error.response && error.code !== 'ECONNABORTED'
}

const isRetryableError = (error: AxiosError): boolean => {
    if (!error.response) return true

    const retryableStatusCodes = [408, 429, 500, 502, 503, 504]
    return retryableStatusCodes.includes(error.response.status)
}

const sleep = (ms: number): Promise<void> => {
    return new Promise((resolve) => setTimeout(resolve, ms))
}

const apiClient: AxiosInstance = axios.create({
    baseURL: apiConfig.baseURL,
    timeout: apiConfig.timeout,
    headers: apiConfig.headers,
})

let isRefreshing = false
let refreshSubscribers: Array<(token: string) => void> = []

const subscribeTokenRefresh = (cb: (token: string) => void) => {
    refreshSubscribers.push(cb)
}

const onTokenRefreshed = (token: string) => {
    refreshSubscribers.forEach((cb) => cb(token))
    refreshSubscribers = []
}

apiClient.interceptors.request.use(
    (config) => {
        const token = localStorage.getItem('auth_token')
        if (token) {
            config.headers.Authorization = `Bearer ${token}`
        }

        const requestId = `req_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`
        config.metadata = { requestId, startTime: Date.now() }

        if (import.meta.env.DEV) {
            console.log(`[API Request] ${config.method?.toUpperCase()} ${config.url}`, {
                requestId,
                params: config.params,
                data: config.data,
            })
        }

        return config
    },
    (error) => {
        console.error('[API Request Error]', error)
        return Promise.reject(error)
    }
)

apiClient.interceptors.response.use(
    (response: AxiosResponse) => {
        const { config } = response
        const duration = Date.now() - (config.metadata?.startTime || 0)

        if (import.meta.env.DEV) {
            console.log(`[API Response] ${config.method?.toUpperCase()} ${config.url}`, {
                requestId: config.metadata?.requestId,
                status: response.status,
                duration: `${duration}ms`,
                data: response.data,
            })
        }

        return response
    },
    async (error: AxiosError) => {
        const { config, response } = error

        if (!config) {
            return Promise.reject(error)
        }

        const duration = Date.now() - (config.metadata?.startTime || 0)

        if (import.meta.env.DEV) {
            console.error(`[API Error] ${config.method?.toUpperCase()} ${config.url}`, {
                requestId: config.metadata?.requestId,
                status: response?.status,
                duration: `${duration}ms`,
                error: error.message,
            })
        }

        if (response?.status === 401) {
            const refreshToken = localStorage.getItem('refresh_token')

            if (refreshToken && !isRefreshing) {
                isRefreshing = true

                try {
                    const { data } = await axios.post(`${apiConfig.baseURL}/api/auth/refresh`, {
                        refresh_token: refreshToken,
                    })

                    const newToken = data.access_token
                    localStorage.setItem('auth_token', newToken)

                    onTokenRefreshed(newToken)
                    isRefreshing = false

                    if (config.headers) {
                        config.headers.Authorization = `Bearer ${newToken}`
                    }

                    return apiClient(config)
                } catch (refreshError) {
                    localStorage.removeItem('auth_token')
                    localStorage.removeItem('refresh_token')
                    message.warning('认证已过期，请刷新页面重新连接')
                    return Promise.reject(refreshError)
                }
            } else if (isRefreshing) {
                return new Promise((resolve) => {
                    subscribeTokenRefresh((token: string) => {
                        if (config.headers) {
                            config.headers.Authorization = `Bearer ${token}`
                        }
                        resolve(apiClient(config))
                    })
                })
            } else {
                localStorage.removeItem('auth_token')
                localStorage.removeItem('refresh_token')
                message.warning('认证已过期，请刷新页面重新连接')
                return Promise.reject(error)
            }
        }

        if (response?.status === 403) {
            message.error('权限不足，无法访问该资源')
            return Promise.reject(error)
        }

        if (response?.status === 404) {
            message.error('请求的资源不存在')
            return Promise.reject(error)
        }

        if (response?.status === 500) {
            message.error('服务器内部错误，请稍后重试')
            return Promise.reject(error)
        }

        if (isNetworkError(error)) {
            message.error('网络连接失败，请检查网络设置')
            return Promise.reject(error)
        }

        if (error.code === 'ECONNABORTED') {
            message.error('请求超时，请稍后重试')
            return Promise.reject(error)
        }

        const retryConfig: RetryConfig = {
            retries: apiConfig.retryAttempts,
            retryDelay: apiConfig.retryDelay,
            retryCondition: isRetryableError,
        }

        const retryCount = config.retryCount || 0

        if (retryCount < retryConfig.retries && retryConfig.retryCondition?.(error)) {
            config.retryCount = retryCount + 1

            if (import.meta.env.DEV) {
                console.log(`[API Retry] ${config.method?.toUpperCase()} ${config.url}`, {
                    attempt: config.retryCount,
                    maxRetries: retryConfig.retries,
                })
            }

            await sleep(retryConfig.retryDelay * config.retryCount)
            return apiClient(config)
        }

        return Promise.reject(error)
    }
)

export const api = {
    get: <T = any>(url: string, config?: AxiosRequestConfig): Promise<T> =>
        apiClient.get(url, config).then((res) => res.data),

    post: <T = any>(url: string, data?: any, config?: AxiosRequestConfig): Promise<T> =>
        apiClient.post(url, data, config).then((res) => res.data),

    put: <T = any>(url: string, data?: any, config?: AxiosRequestConfig): Promise<T> =>
        apiClient.put(url, data, config).then((res) => res.data),

    patch: <T = any>(url: string, data?: any, config?: AxiosRequestConfig): Promise<T> =>
        apiClient.patch(url, data, config).then((res) => res.data),

    delete: <T = any>(url: string, config?: AxiosRequestConfig): Promise<T> =>
        apiClient.delete(url, config).then((res) => res.data),

    request: <T = any>(config: AxiosRequestConfig): Promise<T> =>
        apiClient.request(config).then((res) => res.data),
}

export const systemApi = {
    getStats: () => api.get('/api/system/stats'),
}

export const operationsApi = {
    getHeader: () => api.get('/api/operations/header'),
    getSummary: () => api.get('/api/operations/summary'),
    getLog: (params?: { limit?: number; category?: string }) =>
        api.get('/api/operations/log', { params }),
}

export const healthApi = {
    check: () => api.get('/api/health'),
}

export const memoryApi = {
    getStats: () => api.get('/api/memory/stats'),
}

export const llmApi = {
    classify: (content: string) =>
        api.post('/api/llm/classify', { content }),
    getStatus: () => api.get('/api/llm/status'),
}

export const cancelRequest = (_requestId: string) => {
    // [FIX-TS-013] _requestId 参数未使用 (前缀下划线表示有意未用)
    const controller = new AbortController()
    controller.abort()
}

export const createCancelToken = () => {
    return axios.CancelToken.source()
}

export { endpoints }

export default apiClient
