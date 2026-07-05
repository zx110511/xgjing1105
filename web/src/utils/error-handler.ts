import { AxiosError } from 'axios'
import { message } from 'antd'

export interface ApiError {
  code: string
  message: string
  details?: any
  status?: number
}

export class ErrorHandler {
  static handle(error: unknown, customMessage?: string): ApiError {
    if (error instanceof AxiosError) {
      return this.handleAxiosError(error, customMessage)
    }

    if (error instanceof Error) {
      return this.handleGenericError(error, customMessage)
    }

    return this.handleUnknownError(error, customMessage)
  }

  private static handleAxiosError(error: AxiosError, customMessage?: string): ApiError {
    const status = error.response?.status
    const data: any = error.response?.data

    const apiError: ApiError = {
      code: 'API_ERROR',
      message: customMessage || this.getErrorMessage(status, data),
      details: data,
      status,
    }

    this.logError(apiError, error)
    this.showUserMessage(apiError)

    return apiError
  }

  private static handleGenericError(error: Error, customMessage?: string): ApiError {
    const apiError: ApiError = {
      code: 'GENERIC_ERROR',
      message: customMessage || error.message || '发生未知错误',
      details: error.stack,
    }

    this.logError(apiError, error)

    return apiError
  }

  private static handleUnknownError(error: unknown, customMessage?: string): ApiError {
    const apiError: ApiError = {
      code: 'UNKNOWN_ERROR',
      message: customMessage || '发生未知错误',
      details: error,
    }

    this.logError(apiError, error)

    return apiError
  }

  private static getErrorMessage(status: number | undefined, data: any): string {
    if (data?.message) {
      return data.message
    }

    if (data?.error) {
      return data.error
    }

    switch (status) {
      case 400:
        return '请求参数错误'
      case 401:
        return '未授权，请先登录'
      case 403:
        return '权限不足，无法访问'
      case 404:
        return '请求的资源不存在'
      case 408:
        return '请求超时'
      case 409:
        return '资源冲突'
      case 422:
        return '验证错误'
      case 429:
        return '请求过于频繁，请稍后重试'
      case 500:
        return '服务器内部错误'
      case 502:
        return '网关错误'
      case 503:
        return '服务暂不可用'
      case 504:
        return '网关超时'
      default:
        return '网络请求失败'
    }
  }

  private static logError(apiError: ApiError, originalError: unknown): void {
    if (import.meta.env.DEV) {
      console.group(`[${apiError.code}] ${apiError.message}`)
      console.error('Error Details:', apiError)
      console.error('Original Error:', originalError)
      console.groupEnd()
    }
  }

  private static showUserMessage(apiError: ApiError): void {
    if (apiError.status === 401) {
      return
    }

    if (apiError.status === 403) {
      message.error(apiError.message)
      return
    }

    if (apiError.status && apiError.status >= 500) {
      message.error(apiError.message)
      return
    }

    message.warning(apiError.message)
  }
}

export const handleApiError = (error: unknown, customMessage?: string): ApiError => {
  return ErrorHandler.handle(error, customMessage)
}

export const isApiError = (error: unknown): error is ApiError => {
  return (
    typeof error === 'object' &&
    error !== null &&
    'code' in error &&
    'message' in error
  )
}

export const getErrorMessage = (error: unknown): string => {
  if (isApiError(error)) {
    return error.message
  }

  if (error instanceof Error) {
    return error.message
  }

  return '发生未知错误'
}

export default ErrorHandler
