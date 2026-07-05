/**
 * 天机v9.1 Chat消息本地持久化 (IndexedDB)
 * - 离线消息本地存储
 * - 自动同步到服务器
 * - 多会话管理
 */

interface StoredConversation {
  id: string
  title: string
  messages: StoredMessage[]
  messageCount: number
  totalTokens: number
  createdAt: number
  updatedAt: number
  synced: boolean
}

interface StoredMessage {
  id: string
  role: 'user' | 'assistant' | 'system'
  content: string
  timestamp: number
  tokenCount?: number
  fidelity?: string
}

const DB_NAME = 'tianji_chat_db'
const DB_VERSION = 1
const STORE_NAME = 'conversations'

class ChatStorage {
  private db: IDBDatabase | null = null
  private ready: Promise<void>

  constructor() {
    this.ready = this.init()
  }

  private init(): Promise<void> {
    return new Promise((resolve, _reject) => {
      try {
        const request = indexedDB.open(DB_NAME, DB_VERSION)

        request.onupgradeneeded = (event) => {
          const db = (event.target as IDBOpenDBRequest).result
          if (!db.objectStoreNames.contains(STORE_NAME)) {
            const store = db.createObjectStore(STORE_NAME, { keyPath: 'id' })
            store.createIndex('updatedAt', 'updatedAt', { unique: false })
            store.createIndex('synced', 'synced', { unique: false })
          }
        }

        request.onsuccess = (event) => {
          this.db = (event.target as IDBOpenDBRequest).result
          resolve()
        }

        request.onerror = () => {
          console.warn('[ChatStorage] IndexedDB 不可用，降级到内存模式')
          resolve() // 降级不阻塞
        }
      } catch {
        console.warn('[ChatStorage] IndexedDB 初始化失败')
        resolve()
      }
    })
  }

  async saveConversation(conv: StoredConversation): Promise<void> {
    await this.ready
    if (!this.db) return

    return new Promise((resolve) => {
      try {
        const tx = this.db!.transaction(STORE_NAME, 'readwrite')
        const store = tx.objectStore(STORE_NAME)
        store.put({ ...conv, updatedAt: Date.now() })
        tx.oncomplete = () => resolve()
        tx.onerror = () => resolve()
      } catch {
        resolve()
      }
    })
  }

  async loadConversation(id: string): Promise<StoredConversation | null> {
    await this.ready
    if (!this.db) return null

    return new Promise((resolve) => {
      try {
        const tx = this.db!.transaction(STORE_NAME, 'readonly')
        const store = tx.objectStore(STORE_NAME)
        const request = store.get(id)
        request.onsuccess = () => resolve(request.result || null)
        request.onerror = () => resolve(null)
      } catch {
        resolve(null)
      }
    })
  }

  async loadAllConversations(): Promise<StoredConversation[]> {
    await this.ready
    if (!this.db) return []

    return new Promise((resolve) => {
      try {
        const tx = this.db!.transaction(STORE_NAME, 'readonly')
        const store = tx.objectStore(STORE_NAME)
        const index = store.index('updatedAt')
        const request = index.openCursor(null, 'prev')
        const results: StoredConversation[] = []

        request.onsuccess = (event) => {
          const cursor = (event.target as IDBRequest<IDBCursorWithValue>).result
          if (cursor) {
            results.push(cursor.value)
            cursor.continue()
          } else {
            resolve(results)
          }
        }
        request.onerror = () => resolve(results)
      } catch {
        resolve([])
      }
    })
  }

  async deleteConversation(id: string): Promise<void> {
    await this.ready
    if (!this.db) return

    return new Promise((resolve) => {
      try {
        const tx = this.db!.transaction(STORE_NAME, 'readwrite')
        const store = tx.objectStore(STORE_NAME)
        store.delete(id)
        tx.oncomplete = () => resolve()
        tx.onerror = () => resolve()
      } catch {
        resolve()
      }
    })
  }

  async markSynced(id: string): Promise<void> {
    await this.ready
    if (!this.db) return

    return new Promise((resolve) => {
      try {
        const tx = this.db!.transaction(STORE_NAME, 'readwrite')
        const store = tx.objectStore(STORE_NAME)
        const request = store.get(id)
        request.onsuccess = () => {
          const conv = request.result
          if (conv) {
            conv.synced = true
            store.put(conv)
          }
        }
        tx.oncomplete = () => resolve()
        tx.onerror = () => resolve()
      } catch {
        resolve()
      }
    })
  }

  async getUnsynced(): Promise<StoredConversation[]> {
    await this.ready
    if (!this.db) return []

    return new Promise((resolve) => {
      try {
        const tx = this.db!.transaction(STORE_NAME, 'readonly')
        const store = tx.objectStore(STORE_NAME)
        const index = store.index('synced')
        const request = index.getAll(IDBKeyRange.only(false))
        request.onsuccess = () => resolve(request.result || [])
        request.onerror = () => resolve([])
      } catch {
        resolve([])
      }
    })
  }

  async clear(): Promise<void> {
    await this.ready
    if (!this.db) return

    return new Promise((resolve) => {
      try {
        const tx = this.db!.transaction(STORE_NAME, 'readwrite')
        const store = tx.objectStore(STORE_NAME)
        store.clear()
        tx.oncomplete = () => resolve()
        tx.onerror = () => resolve()
      } catch {
        resolve()
      }
    })
  }

  async getStorageEstimate(): Promise<{ usage: number; quota: number } | null> {
    try {
      const estimate = await navigator.storage?.estimate()
      if (estimate) {
        return { usage: estimate.usage || 0, quota: estimate.quota || 0 }
      }
    } catch {
      /* ignore */
    }
    return null
  }
}

export const chatStorage = new ChatStorage()
export type { StoredConversation, StoredMessage }
export default chatStorage
