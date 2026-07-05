export class SearchCache {
  private cache: Map<string, { data: any; timestamp: number }>
  private maxSize: number
  private ttl: number

  constructor(maxSize: number = 50, ttl: number = 300000) {
    this.cache = new Map()
    this.maxSize = maxSize
    this.ttl = ttl
  }

  get<T>(key: string): T | null {
    const cached = this.cache.get(key)
    if (!cached) return null

    if (Date.now() - cached.timestamp > this.ttl) {
      this.cache.delete(key)
      return null
    }

    return cached.data as T
  }

  set<T>(key: string, data: T): void {
    if (this.cache.size >= this.maxSize) {
      const firstKey = this.cache.keys().next().value
      if (firstKey) {
        this.cache.delete(firstKey)
      }
    }

    this.cache.set(key, {
      data,
      timestamp: Date.now(),
    })
  }

  has(key: string): boolean {
    const cached = this.cache.get(key)
    if (!cached) return false

    if (Date.now() - cached.timestamp > this.ttl) {
      this.cache.delete(key)
      return false
    }

    return true
  }

  delete(key: string): boolean {
    return this.cache.delete(key)
  }

  clear(): void {
    this.cache.clear()
  }

  size(): number {
    return this.cache.size
  }
}

export const debounce = <T extends (...args: any[]) => any>(
  func: T,
  wait: number
): ((...args: Parameters<T>) => void) => {
  let timeoutId: ReturnType<typeof setTimeout> | null = null

  return (...args: Parameters<T>) => {
    if (timeoutId) {
      clearTimeout(timeoutId)
    }

    timeoutId = setTimeout(() => {
      func(...args)
      timeoutId = null
    }, wait)
  }
}

export const throttle = <T extends (...args: any[]) => any>(
  func: T,
  limit: number
): ((...args: Parameters<T>) => void) => {
  let inThrottle: boolean = false

  return (...args: Parameters<T>) => {
    if (!inThrottle) {
      func(...args)
      inThrottle = true
      setTimeout(() => (inThrottle = false), limit)
    }
  }
}

export const createSearchKey = (params: Record<string, any>): string => {
  const sortedKeys = Object.keys(params).sort()
  const keyValuePairs = sortedKeys.map((key) => {
    const value = params[key]
    if (Array.isArray(value)) {
      return `${key}=[${value.sort().join(',')}]`
    } else if (typeof value === 'object' && value !== null) {
      return `${key}=${JSON.stringify(value)}`
    } else {
      return `${key}=${value}`
    }
  })
  return keyValuePairs.join('&')
}

export const searchCache = new SearchCache()

export const lazyLoad = <T extends (...args: any[]) => Promise<any>>(
  func: T,
  delay: number = 100
): ((...args: Parameters<T>) => Promise<ReturnType<T>>) => {
  let promise: Promise<ReturnType<T>> | null = null

  return async (...args: Parameters<T>): Promise<ReturnType<T>> => {
    if (promise) {
      return promise
    }

    await new Promise((resolve) => setTimeout(resolve, delay))

    promise = func(...args)
    const result = await promise
    promise = null

    return result
  }
}

export const prefetchSearch = async (
  query: string,
  searchFn: (query: string) => Promise<any>
): Promise<void> => {
  const cacheKey = createSearchKey({ query })
  
  if (!searchCache.has(cacheKey)) {
    try {
      const result = await searchFn(query)
      searchCache.set(cacheKey, result)
    } catch (error) {
      console.error('Prefetch search failed:', error)
    }
  }
}
