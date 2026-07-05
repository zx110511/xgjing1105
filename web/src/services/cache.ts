/**
 * 天机v9.1 API响应缓存层
 * 内存Map缓存 + sessionStorage降级
 * - TTL自动过期
 * - LRU淘汰策略 (max 200 entries)
 * - 离线降级到 sessionStorage
 */

interface CacheEntry<T = unknown> {
  data: T
  timestamp: number
  ttl: number
  hits: number
}

// [FIX-TS-007] export CacheStats: services/index.ts 需要
export interface CacheStats {
  size: number
  hits: number
  misses: number
  hitRate: number
  storageMode: 'memory' | 'sessionStorage' | 'degraded'
}

const DEFAULT_TTL = 30_000 // 30秒默认TTL
const DEFAULT_STALE_TTL = 300_000 // 5分钟离线过期
const MAX_ENTRIES = 200
const SESSION_STORAGE_PREFIX = 'tianji_cache_'

class ApiCache {
  private memoryCache = new Map<string, CacheEntry>()
  private hits = 0
  private misses = 0
  private sessionStorageAvailable: boolean

  constructor() {
    this.sessionStorageAvailable = this.checkSessionStorage()
  }

  private checkSessionStorage(): boolean {
    try {
      const key = `${SESSION_STORAGE_PREFIX}test`
      sessionStorage.setItem(key, '1')
      sessionStorage.removeItem(key)
      return true
    } catch {
      return false
    }
  }

  private buildKey(url: string, params?: Record<string, unknown>): string {
    if (!params || Object.keys(params).length === 0) return url
    const sorted = Object.keys(params).sort().reduce((acc, k) => {
      acc[k] = params[k]
      return acc
    }, {} as Record<string, unknown>)
    return `${url}?${JSON.stringify(sorted)}`
  }

  /** 从缓存获取 */
  get<T = unknown>(url: string, params?: Record<string, unknown>, ttl: number = DEFAULT_TTL): T | null {
    const key = this.buildKey(url, params)

    // 1. 检查内存缓存
    const memEntry = this.memoryCache.get(key)
    if (memEntry) {
      if (Date.now() - memEntry.timestamp < memEntry.ttl) {
        memEntry.hits++
        this.hits++
        return memEntry.data as T
      }
      // 过期移除
      this.memoryCache.delete(key)
    }

    // 2. 内存未命中，尝试 sessionStorage
    if (this.sessionStorageAvailable) {
      try {
        const raw = sessionStorage.getItem(`${SESSION_STORAGE_PREFIX}${key}`)
        if (raw) {
          const entry: CacheEntry = JSON.parse(raw)
          if (Date.now() - entry.timestamp < (ttl || entry.ttl)) {
            // 回填内存缓存
            this.memoryCache.set(key, { ...entry, hits: entry.hits + 1 })
            this.hits++
            return entry.data as T
          }
          // 过期清理
          sessionStorage.removeItem(`${SESSION_STORAGE_PREFIX}${key}`)
        }
      } catch {
        // sessionStorage 读取失败，降级
      }
    }

    this.misses++
    return null
  }

  /** 写入缓存 */
  set<T = unknown>(url: string, data: T, params?: Record<string, unknown>, ttl: number = DEFAULT_TTL): void {
    const key = this.buildKey(url, params)
    const entry: CacheEntry<T> = { data, timestamp: Date.now(), ttl, hits: 0 }

    // LRU 淘汰: 超出上限时移除访问次数最少的
    if (this.memoryCache.size >= MAX_ENTRIES) {
      let minHits = Infinity
      let minKey = ''
      for (const [k, v] of this.memoryCache) {
        if (v.hits < minHits) {
          minHits = v.hits
          minKey = k
        }
      }
      if (minKey) this.memoryCache.delete(minKey)
    }

    this.memoryCache.set(key, entry)

    // 同时持久化到 sessionStorage
    if (this.sessionStorageAvailable) {
      try {
        sessionStorage.setItem(`${SESSION_STORAGE_PREFIX}${key}`, JSON.stringify(entry))
      } catch {
        // storage 满时清理旧条目
        this.pruneSessionStorage()
        try {
          sessionStorage.setItem(`${SESSION_STORAGE_PREFIX}${key}`, JSON.stringify(entry))
        } catch {
          // 最终失败则放弃持久化
        }
      }
    }
  }

  /** 使指定缓存失效 */
  invalidate(url: string, params?: Record<string, unknown>): void {
    const key = this.buildKey(url, params)
    this.memoryCache.delete(key)
    if (this.sessionStorageAvailable) {
      sessionStorage.removeItem(`${SESSION_STORAGE_PREFIX}${key}`)
    }
  }

  /** 按前缀批量失效 */
  invalidatePrefix(prefix: string): void {
    for (const key of this.memoryCache.keys()) {
      if (key.startsWith(prefix)) this.memoryCache.delete(key)
    }
    if (this.sessionStorageAvailable) {
      const toRemove: string[] = []
      for (let i = 0; i < sessionStorage.length; i++) {
        const k = sessionStorage.key(i)
        if (k?.startsWith(`${SESSION_STORAGE_PREFIX}${prefix}`)) toRemove.push(k)
      }
      toRemove.forEach(k => sessionStorage.removeItem(k))
    }
  }

  /** 清空所有缓存 */
  clear(): void {
    this.memoryCache.clear()
    this.hits = 0
    this.misses = 0
    if (this.sessionStorageAvailable) {
      const toRemove: string[] = []
      for (let i = 0; i < sessionStorage.length; i++) {
        const k = sessionStorage.key(i)
        if (k?.startsWith(SESSION_STORAGE_PREFIX)) toRemove.push(k)
      }
      toRemove.forEach(k => sessionStorage.removeItem(k))
    }
  }

  /** 获取缓存统计 */
  getStats(): CacheStats {
    const total = this.hits + this.misses
    return {
      size: this.memoryCache.size,
      hits: this.hits,
      misses: this.misses,
      hitRate: total > 0 ? Math.round((this.hits / total) * 100) : 0,
      storageMode: this.sessionStorageAvailable ? 'sessionStorage' : 'memory',
    }
  }

  /** 离线模式获取（允许返回过期数据） */
  getStale<T = unknown>(url: string, params?: Record<string, unknown>): T | null {
    const key = this.buildKey(url, params)

    // 内存中过期数据也可用
    const memEntry = this.memoryCache.get(key)
    if (memEntry && Date.now() - memEntry.timestamp < DEFAULT_STALE_TTL) {
      return memEntry.data as T
    }

    // sessionStorage 中过期数据也可用
    if (this.sessionStorageAvailable) {
      try {
        const raw = sessionStorage.getItem(`${SESSION_STORAGE_PREFIX}${key}`)
        if (raw) {
          const entry: CacheEntry = JSON.parse(raw)
          if (Date.now() - entry.timestamp < DEFAULT_STALE_TTL) {
            return entry.data as T
          }
        }
      } catch { /* ignore */ }
    }

    return null
  }

  /** 带缓存装饰器的请求方法 */
  async fetchWithCache<T = unknown>(
    url: string,
    fetcher: () => Promise<T>,
    params?: Record<string, unknown>,
    ttl?: number,
  ): Promise<{ data: T; fromCache: boolean }> {
    // 先查缓存
    const cached = this.get<T>(url, params, ttl)
    if (cached !== null) {
      return { data: cached, fromCache: true }
    }

    // 缓存未命中，发起请求
    try {
      const data = await fetcher()
      this.set(url, data, params, ttl)
      return { data, fromCache: false }
    } catch {
      // 请求失败时尝试使用过期缓存
      const stale = this.getStale<T>(url, params)
      if (stale !== null) {
        return { data: stale, fromCache: true }
      }
      throw new Error('请求失败且无过期缓存可用')
    }
  }

  private pruneSessionStorage(): void {
    // 清理一半最旧的 sessionStorage 条目
    const entries: Array<{ key: string; ts: number }> = []
    for (let i = 0; i < sessionStorage.length; i++) {
      const k = sessionStorage.key(i)
      if (k?.startsWith(SESSION_STORAGE_PREFIX)) {
        try {
          const raw = sessionStorage.getItem(k)
          if (raw) {
            const entry = JSON.parse(raw)
            entries.push({ key: k, ts: entry.timestamp || 0 })
          }
        } catch { /* skip */ }
      }
    }
    entries.sort((a, b) => a.ts - b.ts)
    const toRemove = entries.slice(0, Math.ceil(entries.length / 2))
    toRemove.forEach(e => sessionStorage.removeItem(e.key))
  }
}

/** 全局单例 */
export const apiCache = new ApiCache()

/** 便捷方法 */
export const cachedApi = {
  get: <T = unknown>(url: string, params?: Record<string, unknown>, ttl?: number) =>
    apiCache.get<T>(url, params, ttl),
  set: <T = unknown>(url: string, data: T, params?: Record<string, unknown>, ttl?: number) =>
    apiCache.set(url, data, params, ttl),
  invalidate: (url: string, params?: Record<string, unknown>) =>
    apiCache.invalidate(url, params),
  invalidatePrefix: (prefix: string) => apiCache.invalidatePrefix(prefix),
  clear: () => apiCache.clear(),
  getStats: () => apiCache.getStats(),
  getStale: <T = unknown>(url: string, params?: Record<string, unknown>) =>
    apiCache.getStale<T>(url, params),
  fetchWithCache: <T = unknown>(
    url: string,
    fetcher: () => Promise<T>,
    params?: Record<string, unknown>,
    ttl?: number,
  ) => apiCache.fetchWithCache<T>(url, fetcher, params, ttl),
}

export default apiCache
