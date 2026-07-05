import React, { useState, useEffect } from 'react'
import { Table, Button, Space, Tag, Modal, message, Popconfirm, Input, Select, Card } from 'antd'
import { PlusOutlined, EditOutlined, DeleteOutlined, SearchOutlined, ReloadOutlined, ExportOutlined } from '@ant-design/icons'
import type { ColumnsType, TablePaginationConfig } from 'antd/es/table'
import { useMemoryStore } from '../stores/memory-store'
import { MemoryEntry } from '../types'
import MemoryForm from './MemoryForm'
import MemoryDetail from './MemoryDetail'

const { Search } = Input
const { Option } = Select

const MemoryList: React.FC = () => {
  const {
    memories,
    loading,
    error,
    total,
    searchParams,
    fetchMemories,
    deleteMemory,
    batchDeleteMemories,
    setCurrentMemory,
    clearError,
  } = useMemoryStore()

  const [selectedRowKeys, setSelectedRowKeys] = useState<React.Key[]>([])
  const [formVisible, setFormVisible] = useState(false)
  const [detailVisible, setDetailVisible] = useState(false)
  const [editingMemory, setEditingMemory] = useState<MemoryEntry | null>(null)
  const [searchText, setSearchText] = useState('')
  const [layerFilter, setLayerFilter] = useState<string | undefined>(undefined)
  const [priorityFilter, setPriorityFilter] = useState<string | undefined>(undefined)

  useEffect(() => {
    loadMemories()
  }, [searchParams])

  useEffect(() => {
    if (error) {
      message.error(error)
      clearError()
    }
  }, [error, clearError])

  const loadMemories = async () => {
    await fetchMemories(searchParams)
  }

  const handleTableChange = (pagination: TablePaginationConfig) => {
    fetchMemories({
      ...searchParams,
      offset: ((pagination.current || 1) - 1) * (pagination.pageSize || 20),
      limit: pagination.pageSize || 20,
    })
  }

  const handleSearch = (value: string) => {
    setSearchText(value)
    fetchMemories({
      ...searchParams,
      query: value,
      offset: 0,
    })
  }

  const handleLayerFilter = (value: string | undefined) => {
    setLayerFilter(value)
    fetchMemories({
      ...searchParams,
      // [FIX-TS-011] 修复类型: value 是 string, 需要断言为 MemoryEntry['layer']
      layer: value as MemoryEntry['layer'] | undefined,
      offset: 0,
    })
  }

  const handlePriorityFilter = (value: string | undefined) => {
    setPriorityFilter(value)
    fetchMemories({
      ...searchParams,
      // [FIX-TS-011] 修复类型: value 是 string, 需要断言为 MemoryEntry['priority']
      priority: value as MemoryEntry['priority'] | undefined,
      offset: 0,
    })
  }

  const handleCreate = () => {
    setEditingMemory(null)
    setFormVisible(true)
  }

  const handleEdit = (record: MemoryEntry) => {
    setEditingMemory(record)
    setFormVisible(true)
  }

  const handleView = (record: MemoryEntry) => {
    setCurrentMemory(record)
    setDetailVisible(true)
  }

  const handleDelete = async (id: string) => {
    await deleteMemory(id)
    message.success('记忆删除成功')
    loadMemories()
  }

  const handleBatchDelete = async () => {
    if (selectedRowKeys.length === 0) {
      message.warning('请选择要删除的记忆')
      return
    }

    Modal.confirm({
      title: '批量删除确认',
      content: `确定要删除选中的 ${selectedRowKeys.length} 条记忆吗？此操作不可恢复。`,
      okText: '确定',
      cancelText: '取消',
      okType: 'danger',
      onOk: async () => {
        await batchDeleteMemories(selectedRowKeys as string[])
        message.success(`成功删除 ${selectedRowKeys.length} 条记忆`)
        setSelectedRowKeys([])
        loadMemories()
      },
    })
  }

  const handleExport = () => {
    message.info('导出功能开发中...')
  }

  const handleFormClose = () => {
    setFormVisible(false)
    setEditingMemory(null)
  }

  const handleFormSuccess = () => {
    setFormVisible(false)
    setEditingMemory(null)
    loadMemories()
  }

  const handleDetailClose = () => {
    setDetailVisible(false)
    setCurrentMemory(null)
  }

  const getLayerColor = (layer: string) => {
    const colors: Record<string, string> = {
      sensory: 'blue',
      working: 'cyan',
      short_term: 'green',
      episodic: 'orange',
      semantic: 'purple',
      meta: 'magenta',
    }
    return colors[layer] || 'default'
  }

  const getPriorityColor = (priority: string) => {
    const colors: Record<string, string> = {
      low: 'default',
      medium: 'blue',
      high: 'orange',
      critical: 'red',
    }
    return colors[priority] || 'default'
  }

  const columns: ColumnsType<MemoryEntry> = [
    {
      title: 'ID',
      dataIndex: 'id',
      key: 'id',
      width: 100,
      ellipsis: true,
    },
    {
      title: '内容',
      dataIndex: 'content',
      key: 'content',
      ellipsis: true,
      render: (text: string) => (
        <div style={{ maxWidth: 300 }} title={text}>
          {text.length > 50 ? `${text.substring(0, 50)}...` : text}
        </div>
      ),
    },
    {
      title: '层级',
      dataIndex: 'layer',
      key: 'layer',
      width: 100,
      filters: [
        { text: 'Sensory', value: 'sensory' },
        { text: 'Working', value: 'working' },
        { text: 'Short Term', value: 'short_term' },
        { text: 'Episodic', value: 'episodic' },
        { text: 'Semantic', value: 'semantic' },
        { text: 'Meta', value: 'meta' },
      ],
      render: (layer: string) => (
        <Tag color={getLayerColor(layer)}>{layer.toUpperCase()}</Tag>
      ),
    },
    {
      title: '优先级',
      dataIndex: 'priority',
      key: 'priority',
      width: 100,
      filters: [
        { text: 'Low', value: 'low' },
        { text: 'Medium', value: 'medium' },
        { text: 'High', value: 'high' },
        { text: 'Critical', value: 'critical' },
      ],
      render: (priority: string) => (
        <Tag color={getPriorityColor(priority)}>{priority.toUpperCase()}</Tag>
      ),
    },
    {
      title: '标签',
      dataIndex: 'tags',
      key: 'tags',
      width: 150,
      render: (tags: string[]) => (
        <>
          {tags && tags.slice(0, 3).map((tag) => (
            <Tag key={tag} style={{ marginBottom: 4 }}>
              {tag}
            </Tag>
          ))}
          {tags && tags.length > 3 && <Tag>+{tags.length - 3}</Tag>}
        </>
      ),
    },
    {
      title: '创建时间',
      dataIndex: 'created_at',
      key: 'created_at',
      width: 180,
      sorter: true,
      render: (date: string) => new Date(date).toLocaleString('zh-CN'),
    },
    {
      title: '操作',
      key: 'action',
      width: 200,
      fixed: 'right',
      render: (_, record) => (
        <Space size="small">
          <Button
            type="link"
            size="small"
            onClick={() => handleView(record)}
          >
            查看
          </Button>
          <Button
            type="link"
            size="small"
            icon={<EditOutlined />}
            onClick={() => handleEdit(record)}
          >
            编辑
          </Button>
          <Popconfirm
            title="确定要删除这条记忆吗？"
            onConfirm={() => handleDelete(record.id)}
            okText="确定"
            cancelText="取消"
          >
            <Button
              type="link"
              size="small"
              danger
              icon={<DeleteOutlined />}
            >
              删除
            </Button>
          </Popconfirm>
        </Space>
      ),
    },
  ]

  const rowSelection = {
    selectedRowKeys,
    onChange: (newSelectedRowKeys: React.Key[]) => {
      setSelectedRowKeys(newSelectedRowKeys)
    },
  }

  return (
    <div className="memory-list">
      <Card>
        <div style={{ marginBottom: 16 }}>
          <Space size="middle" wrap>
            <Search
              placeholder="搜索记忆内容..."
              allowClear
              enterButton={<SearchOutlined />}
              style={{ width: 300 }}
              onSearch={handleSearch}
              onChange={(e) => setSearchText(e.target.value)}
              value={searchText}
            />
            <Select
              placeholder="选择层级"
              allowClear
              style={{ width: 150 }}
              onChange={handleLayerFilter}
              value={layerFilter}
            >
              <Option value="sensory">Sensory</Option>
              <Option value="working">Working</Option>
              <Option value="short_term">Short Term</Option>
              <Option value="episodic">Episodic</Option>
              <Option value="semantic">Semantic</Option>
              <Option value="meta">Meta</Option>
            </Select>
            <Select
              placeholder="选择优先级"
              allowClear
              style={{ width: 150 }}
              onChange={handlePriorityFilter}
              value={priorityFilter}
            >
              <Option value="low">Low</Option>
              <Option value="medium">Medium</Option>
              <Option value="high">High</Option>
              <Option value="critical">Critical</Option>
            </Select>
          </Space>
        </div>

        <div style={{ marginBottom: 16 }}>
          <Space>
            <Button
              type="primary"
              icon={<PlusOutlined />}
              onClick={handleCreate}
            >
              创建记忆
            </Button>
            <Button
              icon={<DeleteOutlined />}
              danger
              disabled={selectedRowKeys.length === 0}
              onClick={handleBatchDelete}
            >
              批量删除 {selectedRowKeys.length > 0 && `(${selectedRowKeys.length})`}
            </Button>
            <Button
              icon={<ReloadOutlined />}
              onClick={loadMemories}
            >
              刷新
            </Button>
            <Button
              icon={<ExportOutlined />}
              onClick={handleExport}
            >
              导出
            </Button>
          </Space>
        </div>

        <Table
          columns={columns}
          dataSource={memories}
          rowKey="id"
          loading={loading}
          rowSelection={rowSelection}
          pagination={{
            // [FIX-TS-012] 修复 possibly undefined: 提供默认值 0/20
            current: Math.floor((searchParams.offset ?? 0) / (searchParams.limit ?? 20)) + 1,
            pageSize: searchParams.limit ?? 20,
            total,
            showSizeChanger: true,
            showQuickJumper: true,
            showTotal: (total) => `共 ${total} 条记录`,
            pageSizeOptions: ['10', '20', '50', '100'],
          }}
          onChange={handleTableChange}
          scroll={{ x: 1200 }}
          style={{ marginTop: 16 }}
        />
      </Card>

      <MemoryForm
        visible={formVisible}
        memory={editingMemory}
        onClose={handleFormClose}
        onSuccess={handleFormSuccess}
      />

      <MemoryDetail
        visible={detailVisible}
        onClose={handleDetailClose}
      />
    </div>
  )
}

export default MemoryList
