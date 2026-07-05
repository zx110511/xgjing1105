import { useState, useCallback, useRef } from 'react'
import { message } from 'antd'

export interface HistoryState<T> {
  data: T
  timestamp: number
  description?: string
}

export interface UndoRedoConfig {
  maxHistorySize?: number
  enableNotifications?: boolean
}

export const useUndoRedo = <T>(
  initialState: T,
  config: UndoRedoConfig = {}
) => {
  const { maxHistorySize = 50, enableNotifications = false } = config

  const [currentState, setCurrentState] = useState<T>(initialState)
  const historyRef = useRef<HistoryState<T>[]>([
    { data: initialState, timestamp: Date.now(), description: '初始状态' },
  ])
  const currentIndexRef = useRef<number>(0)

  const canUndo = currentIndexRef.current > 0
  const canRedo = currentIndexRef.current < historyRef.current.length - 1

  const pushState = useCallback(
    (newState: T, description?: string) => {
      const newHistory = historyRef.current.slice(0, currentIndexRef.current + 1)

      newHistory.push({
        data: newState,
        timestamp: Date.now(),
        description,
      })

      if (newHistory.length > maxHistorySize) {
        newHistory.shift()
      } else {
        currentIndexRef.current++
      }

      historyRef.current = newHistory
      setCurrentState(newState)

      if (enableNotifications && description) {
        message.info(`已记录: ${description}`)
      }
    },
    [maxHistorySize, enableNotifications]
  )

  const undo = useCallback(() => {
    if (!canUndo) {
      if (enableNotifications) {
        message.warning('无法撤销')
      }
      return null
    }

    currentIndexRef.current--
    const previousState = historyRef.current[currentIndexRef.current]
    setCurrentState(previousState.data)

    if (enableNotifications && previousState.description) {
      message.success(`已撤销: ${previousState.description}`)
    }

    return previousState.data
  }, [canUndo, enableNotifications])

  const redo = useCallback(() => {
    if (!canRedo) {
      if (enableNotifications) {
        message.warning('无法重做')
      }
      return null
    }

    currentIndexRef.current++
    const nextState = historyRef.current[currentIndexRef.current]
    setCurrentState(nextState.data)

    if (enableNotifications && nextState.description) {
      message.success(`已重做: ${nextState.description}`)
    }

    return nextState.data
  }, [canRedo, enableNotifications])

  const clearHistory = useCallback(() => {
    historyRef.current = [
      { data: currentState, timestamp: Date.now(), description: '当前状态' },
    ]
    currentIndexRef.current = 0

    if (enableNotifications) {
      message.info('历史记录已清空')
    }
  }, [currentState, enableNotifications])

  const getHistory = useCallback(() => {
    return historyRef.current.map((state, index) => ({
      ...state,
      isCurrent: index === currentIndexRef.current,
    }))
  }, [])

  const jumpToState = useCallback(
    (index: number) => {
      if (index < 0 || index >= historyRef.current.length) {
        return null
      }

      currentIndexRef.current = index
      const targetState = historyRef.current[index]
      setCurrentState(targetState.data)

      if (enableNotifications && targetState.description) {
        message.success(`已跳转到: ${targetState.description}`)
      }

      return targetState.data
    },
    [enableNotifications]
  )

  return {
    currentState,
    pushState,
    undo,
    redo,
    canUndo,
    canRedo,
    clearHistory,
    getHistory,
    jumpToState,
    historyLength: historyRef.current.length,
    currentIndex: currentIndexRef.current,
  }
}

export class UndoRedoManager<T> {
  private history: HistoryState<T>[] = []
  private currentIndex: number = -1
  private maxHistorySize: number
  private enableNotifications: boolean

  constructor(config: UndoRedoConfig = {}) {
    this.maxHistorySize = config.maxHistorySize || 50
    this.enableNotifications = config.enableNotifications || false
  }

  initialize(initialState: T, description?: string) {
    this.history = [
      { data: initialState, timestamp: Date.now(), description: description || '初始状态' },
    ]
    this.currentIndex = 0
  }

  pushState(state: T, description?: string) {
    const newHistory = this.history.slice(0, this.currentIndex + 1)

    newHistory.push({
      data: state,
      timestamp: Date.now(),
      description,
    })

    if (newHistory.length > this.maxHistorySize) {
      newHistory.shift()
    } else {
      this.currentIndex++
    }

    this.history = newHistory

    if (this.enableNotifications && description) {
      message.info(`已记录: ${description}`)
    }
  }

  undo(): T | null {
    if (!this.canUndo()) {
      return null
    }

    this.currentIndex--
    const previousState = this.history[this.currentIndex]

    if (this.enableNotifications && previousState.description) {
      message.success(`已撤销: ${previousState.description}`)
    }

    return previousState.data
  }

  redo(): T | null {
    if (!this.canRedo()) {
      return null
    }

    this.currentIndex++
    const nextState = this.history[this.currentIndex]

    if (this.enableNotifications && nextState.description) {
      message.success(`已重做: ${nextState.description}`)
    }

    return nextState.data
  }

  canUndo(): boolean {
    return this.currentIndex > 0
  }

  canRedo(): boolean {
    return this.currentIndex < this.history.length - 1
  }

  getCurrentState(): T | null {
    if (this.currentIndex >= 0 && this.currentIndex < this.history.length) {
      return this.history[this.currentIndex].data
    }
    return null
  }

  getHistory(): Array<HistoryState<T> & { isCurrent: boolean }> {
    return this.history.map((state, index) => ({
      ...state,
      isCurrent: index === this.currentIndex,
    }))
  }

  clearHistory() {
    const currentState = this.getCurrentState()
    if (currentState) {
      this.history = [
        { data: currentState, timestamp: Date.now(), description: '当前状态' },
      ]
      this.currentIndex = 0
    }
  }

  jumpToState(index: number): T | null {
    if (index < 0 || index >= this.history.length) {
      return null
    }

    this.currentIndex = index
    const targetState = this.history[index]

    if (this.enableNotifications && targetState.description) {
      message.success(`已跳转到: ${targetState.description}`)
    }

    return targetState.data
  }
}

export default UndoRedoManager
