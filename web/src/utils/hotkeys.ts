import { useEffect } from 'react'
// [FIX-TS-013] 删除未使用的 useCallback/useRef/message

export interface HotkeyConfig {
  key: string
  ctrl?: boolean
  shift?: boolean
  alt?: boolean
  meta?: boolean
  description: string
  action: () => void
  preventDefault?: boolean
}

export interface HotkeyGroup {
  group: string
  hotkeys: HotkeyConfig[]
}

const defaultHotkeys: HotkeyGroup[] = [
  {
    group: '通用',
    hotkeys: [
      { key: 'n', ctrl: true, description: '新建记忆', action: () => {} },
      { key: 's', ctrl: true, description: '保存', action: () => {} },
      { key: 'f', ctrl: true, description: '搜索', action: () => {} },
      { key: 'z', ctrl: true, description: '撤销', action: () => {} },
      { key: 'z', ctrl: true, shift: true, description: '重做', action: () => {} },
      { key: '/', description: '快速搜索', action: () => {} },
      { key: 'Escape', description: '关闭弹窗', action: () => {} },
    ],
  },
  {
    group: '导航',
    hotkeys: [
      { key: '1', ctrl: true, description: '仪表盘', action: () => {} },
      { key: '2', ctrl: true, description: '记忆管理', action: () => {} },
      { key: '3', ctrl: true, description: '知识图谱', action: () => {} },
      { key: '4', ctrl: true, description: '系统配置', action: () => {} },
    ],
  },
  {
    group: '记忆操作',
    hotkeys: [
      { key: 'e', ctrl: true, description: '编辑选中记忆', action: () => {} },
      { key: 'd', ctrl: true, description: '删除选中记忆', action: () => {} },
      { key: 'c', ctrl: true, description: '复制选中记忆', action: () => {} },
      { key: 'a', ctrl: true, description: '全选', action: () => {} },
    ],
  },
]

class HotkeyManager {
  private hotkeys: Map<string, HotkeyConfig> = new Map()
  private enabled: boolean = true

  register(config: HotkeyConfig) {
    const key = this.generateKey(config)
    this.hotkeys.set(key, config)
  }

  unregister(config: HotkeyConfig) {
    const key = this.generateKey(config)
    this.hotkeys.delete(key)
  }

  registerGroup(group: HotkeyGroup) {
    group.hotkeys.forEach((hotkey) => this.register(hotkey))
  }

  unregisterGroup(group: HotkeyGroup) {
    group.hotkeys.forEach((hotkey) => this.unregister(hotkey))
  }

  enable() {
    this.enabled = true
  }

  disable() {
    this.enabled = false
  }

  handleKeyDown = (event: KeyboardEvent) => {
    if (!this.enabled) return

    const key = this.generateKeyFromEvent(event)
    const config = this.hotkeys.get(key)

    if (config) {
      if (config.preventDefault !== false) {
        event.preventDefault()
      }
      config.action()
    }
  }

  private generateKey(config: HotkeyConfig): string {
    const parts: string[] = []
    if (config.ctrl) parts.push('ctrl')
    if (config.shift) parts.push('shift')
    if (config.alt) parts.push('alt')
    if (config.meta) parts.push('meta')
    parts.push(config.key.toLowerCase())
    return parts.join('+')
  }

  private generateKeyFromEvent(event: KeyboardEvent): string {
    const parts: string[] = []
    if (event.ctrlKey) parts.push('ctrl')
    if (event.shiftKey) parts.push('shift')
    if (event.altKey) parts.push('alt')
    if (event.metaKey) parts.push('meta')
    parts.push(event.key.toLowerCase())
    return parts.join('+')
  }

  getHotkeyList(): HotkeyGroup[] {
    return defaultHotkeys
  }

  getHotkeyDescription(key: string, ctrl?: boolean, shift?: boolean, alt?: boolean): string | undefined {
    const configKey = this.generateKey({ key, ctrl, shift, alt, description: '', action: () => {} })
    const config = this.hotkeys.get(configKey)
    return config?.description
  }
}

export const hotkeyManager = new HotkeyManager()

export const useHotkey = (config: HotkeyConfig) => {
  useEffect(() => {
    hotkeyManager.register(config)
    return () => hotkeyManager.unregister(config)
  }, [config])
}

export const useHotkeyGroup = (group: HotkeyGroup) => {
  useEffect(() => {
    hotkeyManager.registerGroup(group)
    return () => hotkeyManager.unregisterGroup(group)
  }, [group])
}

export const useGlobalHotkeys = () => {
  useEffect(() => {
    window.addEventListener('keydown', hotkeyManager.handleKeyDown)
    return () => {
      window.removeEventListener('keydown', hotkeyManager.handleKeyDown)
    }
  }, [])
}

export const formatHotkey = (config: HotkeyConfig): string => {
  const parts: string[] = []
  if (config.ctrl) parts.push('Ctrl')
  if (config.shift) parts.push('Shift')
  if (config.alt) parts.push('Alt')
  if (config.meta) parts.push('⌘')
  parts.push(config.key.toUpperCase())
  return parts.join(' + ')
}

export default hotkeyManager
