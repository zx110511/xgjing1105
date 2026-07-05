import React from 'react'
import { Card, List, Button, Space, Empty, Tag, Popconfirm, message } from 'antd'
import { ClockCircleOutlined, SearchOutlined, DeleteOutlined, ClearOutlined } from '@ant-design/icons'
import { useLocalStorage } from '../hooks/useLocalStorage'

interface SearchHistoryItem {
  query: string
  timestamp: string
  count: number
}

interface SearchHistoryProps {
  onSelect: (query: string) => void
  maxItems?: number
}

const SearchHistory: React.FC<SearchHistoryProps> = ({ onSelect, maxItems = 10 }) => {
  const [history, setHistory] = useLocalStorage<SearchHistoryItem[]>('search-history', [])

  const handleSelect = (query: string) => {
    onSelect(query)
  }

  const handleDelete = (index: number) => {
    const newHistory = history.filter((_, i) => i !== index)
    setHistory(newHistory)
    message.success('已删除搜索记录')
  }

  const handleClearAll = () => {
    setHistory([])
    message.success('已清空所有搜索记录')
  }

  const formatTime = (timestamp: string) => {
    const date = new Date(timestamp)
    const now = new Date()
    const diff = now.getTime() - date.getTime()

    if (diff < 60000) {
      return '刚刚'
    } else if (diff < 3600000) {
      return `${Math.floor(diff / 60000)}分钟前`
    } else if (diff < 86400000) {
      return `${Math.floor(diff / 3600000)}小时前`
    } else if (diff < 604800000) {
      return `${Math.floor(diff / 86400000)}天前`
    } else {
      return date.toLocaleDateString('zh-CN')
    }
  }

  if (history.length === 0) {
    return (
      <Card>
        <Empty
          image={Empty.PRESENTED_IMAGE_SIMPLE}
          description="暂无搜索历史"
        />
      </Card>
    )
  }

  return (
    <Card
      title={
        <Space>
          <ClockCircleOutlined />
          搜索历史
        </Space>
      }
      extra={
        <Popconfirm
          title="确定要清空所有搜索历史吗？"
          onConfirm={handleClearAll}
          okText="确定"
          cancelText="取消"
        >
          <Button
            type="text"
            danger
            icon={<ClearOutlined />}
            size="small"
          >
            清空
          </Button>
        </Popconfirm>
      }
    >
      <List
        dataSource={history.slice(0, maxItems)}
        renderItem={(item, index) => (
          <List.Item
            actions={[
              <Button
                key="search"
                type="link"
                size="small"
                icon={<SearchOutlined />}
                onClick={() => handleSelect(item.query)}
              >
                搜索
              </Button>,
              <Button
                key="delete"
                type="link"
                size="small"
                danger
                icon={<DeleteOutlined />}
                onClick={() => handleDelete(index)}
              />,
            ]}
          >
            <List.Item.Meta
              title={
                <Space>
                  <span>{item.query}</span>
                  {item.count > 1 && (
                    <Tag color="blue" style={{ marginLeft: 8 }}>
                      {item.count}次
                    </Tag>
                  )}
                </Space>
              }
              description={formatTime(item.timestamp)}
            />
          </List.Item>
        )}
      />
    </Card>
  )
}

export default SearchHistory

export const useSearchHistory = () => {
  const [history, setHistory] = useLocalStorage<SearchHistoryItem[]>('search-history', [])

  const addToHistory = (query: string) => {
    if (!query.trim()) return

    const existingIndex = history.findIndex((item) => item.query === query)
    const timestamp = new Date().toISOString()

    if (existingIndex >= 0) {
      const updated = [...history]
      updated[existingIndex] = {
        ...updated[existingIndex],
        timestamp,
        count: updated[existingIndex].count + 1,
      }
      setHistory(updated)
    } else {
      const newItem: SearchHistoryItem = {
        query,
        timestamp,
        count: 1,
      }
      setHistory([newItem, ...history].slice(0, 20))
    }
  }

  const clearHistory = () => {
    setHistory([])
  }

  return {
    history,
    addToHistory,
    clearHistory,
  }
}
