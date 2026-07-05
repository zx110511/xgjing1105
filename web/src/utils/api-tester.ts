import { message } from 'antd'
import apiService from '../services'
import { handleApiError } from './error-handler'

export interface TestResult {
  name: string
  status: 'success' | 'error' | 'warning'
  message: string
  duration?: number
  details?: any
}

export interface ApiTestReport {
  timestamp: string
  totalTests: number
  passed: number
  failed: number
  warnings: number
  results: TestResult[]
}

export class ApiConnectionTester {
  private results: TestResult[] = []

  async runAllTests(): Promise<ApiTestReport> {
    this.results = []

    await this.testHealthCheck()
    await this.testMemoryAPI()
    await this.testSearchAPI()
    await this.testSystemStats()

    const report: ApiTestReport = {
      timestamp: new Date().toISOString(),
      totalTests: this.results.length,
      passed: this.results.filter((r) => r.status === 'success').length,
      failed: this.results.filter((r) => r.status === 'error').length,
      warnings: this.results.filter((r) => r.status === 'warning').length,
      results: this.results,
    }

    this.displayReport(report)

    return report
  }

  private async testHealthCheck(): Promise<void> {
    const startTime = Date.now()

    try {
      const health = await apiService.system.getHealth()
      const duration = Date.now() - startTime

      this.results.push({
        name: '健康检查',
        status: 'success',
        message: `系统状态: ${health.status}`,
        duration,
        details: health,
      })
    } catch (error) {
      const apiError = handleApiError(error)

      this.results.push({
        name: '健康检查',
        status: 'error',
        message: apiError.message,
        details: apiError,
      })
    }
  }

  private async testMemoryAPI(): Promise<void> {
    const startTime = Date.now()

    try {
      // [FIX-TS-022] 修复 getMemories 不存在: memory-service 使用 list 方法
      const response = await apiService.memory.list({ limit: 1 } as any)
      const duration = Date.now() - startTime

      this.results.push({
        name: '记忆API',
        status: 'success',
        message: `成功获取 ${response.total} 条记忆`,
        duration,
        details: { total: response.total },
      })
    } catch (error) {
      const apiError = handleApiError(error)

      this.results.push({
        name: '记忆API',
        status: 'error',
        message: apiError.message,
        details: apiError,
      })
    }
  }

  private async testSearchAPI(): Promise<void> {
    const startTime = Date.now()

    try {
      const response = await apiService.search.search({
        query: 'test',
        limit: 1,
        offset: 0,
      })
      const duration = Date.now() - startTime

      this.results.push({
        name: '搜索API',
        status: 'success',
        message: `搜索功能正常`,
        duration,
        details: { results: response.total },
      })
    } catch (error) {
      const apiError = handleApiError(error)

      this.results.push({
        name: '搜索API',
        status: 'warning',
        message: apiError.message,
        details: apiError,
      })
    }
  }

  private async testSystemStats(): Promise<void> {
    const startTime = Date.now()

    try {
      const stats = await apiService.system.getStats()
      const duration = Date.now() - startTime

      this.results.push({
        name: '系统统计',
        status: 'success',
        message: `总记忆数: ${stats.total_memories}`,
        duration,
        details: stats,
      })
    } catch (error) {
      const apiError = handleApiError(error)

      this.results.push({
        name: '系统统计',
        status: 'warning',
        message: apiError.message,
        details: apiError,
      })
    }
  }

  private displayReport(report: ApiTestReport): void {
    console.group('🔍 API连接测试报告')
    console.log('测试时间:', report.timestamp)
    console.log('总测试数:', report.totalTests)
    console.log('通过:', report.passed)
    console.log('失败:', report.failed)
    console.log('警告:', report.warnings)
    console.table(
      report.results.map((r) => ({
        测试项: r.name,
        状态: r.status,
        消息: r.message,
        耗时: r.duration ? `${r.duration}ms` : '-',
      }))
    )
    console.groupEnd()

    if (report.failed > 0) {
      message.error(`API测试失败: ${report.failed}/${report.totalTests} 项未通过`)
    } else if (report.warnings > 0) {
      message.warning(`API测试完成: ${report.warnings}/${report.totalTests} 项警告`)
    } else {
      message.success(`API测试全部通过 (${report.passed}/${report.totalTests})`)
    }
  }
}

export const testApiConnection = async (): Promise<ApiTestReport> => {
  const tester = new ApiConnectionTester()
  return tester.runAllTests()
}

export default ApiConnectionTester
