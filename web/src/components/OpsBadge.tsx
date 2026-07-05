import { useEffect, useState, useCallback } from 'react'
import { Tag, Tooltip, Space } from 'antd'
import {
  ApartmentOutlined,
  ApiOutlined,
  DatabaseOutlined,
  ThunderboltOutlined,
} from '@ant-design/icons'
import { api } from '../services/api'

interface OpsSummary {
  total_operations: number
  by_category: Record<string, number | { count?: number; label?: string; color?: string; desc?: string }>
  category_config?: Record<string, { label?: string; color?: string; desc?: string }>
}

const CATEGORIES = [
  { key: 'tvp', icon: <ApartmentOutlined />, color: '#8B5CF6', label: 'TVP', tip: 'TVP透明调度声明' },
  { key: 'mcp', icon: <ApiOutlined />, color: '#F97316', label: 'MCP', tip: 'MCP工具调用' },
  { key: 'memory', icon: <DatabaseOutlined />, color: '#06B6D4', label: '记忆', tip: '记忆操作' },
  { key: 'llm', icon: <ThunderboltOutlined />, color: '#EC4899', label: 'LLM', tip: 'DeepSeek AI调用' },
] as const

const getCatCount = (val: number | { count?: number } | undefined): number => {
  if (typeof val === 'number') return val
  if (val && typeof val === 'object' && typeof val.count === 'number') return val.count
  return 0
}

const OpsBadge: React.FC = () => {
  const [ops, setOps] = useState<OpsSummary | null>(null)

  const fetchOps = useCallback(async () => {
    try {
      const res = await api.get<OpsSummary>('/api/operations/summary')
      setOps(res)
    } catch {
      setOps(null)
    }
  }, [])

  useEffect(() => {
    fetchOps()
    const timer = setInterval(fetchOps, 10000)
    return () => clearInterval(timer)
  }, [fetchOps])

  return (
    <Space size={4}>
      {CATEGORIES.map(({ key, icon, color, label, tip }) => {
        const count = getCatCount(ops?.by_category?.[key])
        return (
          <Tooltip key={key} title={`${tip}: ${count}次`}>
            <Tag
              icon={icon}
              style={{
                margin: 0,
                padding: '0 6px',
                fontSize: 11,
                lineHeight: '20px',
                borderRadius: 4,
                color,
                background: `${color}15`,
                borderColor: `${color}40`,
              }}
            >
              {label} {count}
            </Tag>
          </Tooltip>
        )
      })}
    </Space>
  )
}

export default OpsBadge
