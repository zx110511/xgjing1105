import React, { useState } from 'react'
import { Modal, Space, Typography, message, Progress, List, Tag, Card } from 'antd'
import { DeleteOutlined, ExportOutlined, TagOutlined, FolderOutlined } from '@ant-design/icons'
import type { MemoryEntry } from '../types'

const { Text, Title } = Typography

interface BatchOperation {
  key: string
  name: string
  icon: React.ReactNode
  description: string
  confirmMessage: string
  action: (selectedIds: string[]) => Promise<void>
}

interface BatchOperationsProps {
  visible: boolean
  selectedMemories: MemoryEntry[]
  onClose: () => void
  onComplete: () => void
}

const BatchOperations: React.FC<BatchOperationsProps> = ({
  visible,
  selectedMemories,
  onClose,
  onComplete,
}) => {
  const [processing, setProcessing] = useState(false)
  const [progress, setProgress] = useState(0)
  const [currentOperation, setCurrentOperation] = useState<string | null>(null)

  const operations: BatchOperation[] = [
    {
      key: 'delete',
      name: '批量删除',
      icon: <DeleteOutlined />,
      description: '删除选中的记忆条目',
      confirmMessage: `确定要删除选中的 ${selectedMemories.length} 条记忆吗？此操作不可撤销。`,
      action: async (ids) => {
        const { default: apiService } = await import('../services')
        // [FIX-TS-015] 修复 batchDeleteMemories 不存在: 改用 deleteMemory 循环
        await Promise.all(ids.map((id) => apiService.memory.delete(id)))
      },
    },
    {
      key: 'export',
      name: '批量导出',
      icon: <ExportOutlined />,
      description: '导出选中的记忆到文件',
      confirmMessage: `确定要导出选中的 ${selectedMemories.length} 条记忆吗？`,
      action: async (ids) => {
        const memories = selectedMemories.filter((m) => ids.includes(m.id))
        const data = JSON.stringify(memories, null, 2)
        const blob = new Blob([data], { type: 'application/json' })
        const url = URL.createObjectURL(blob)
        const a = document.createElement('a')
        a.href = url
        a.download = `memories_export_${Date.now()}.json`
        a.click()
        URL.revokeObjectURL(url)
      },
    },
    {
      key: 'change-layer',
      name: '修改层级',
      icon: <FolderOutlined />,
      description: '批量修改记忆层级',
      confirmMessage: `确定要修改选中的 ${selectedMemories.length} 条记忆的层级吗？`,
      action: async (_ids) => {
        // [FIX-TS-015] _ids 参数未使用 (前缀下划线表示有意未用)
        message.info('层级修改功能开发中...')
      },
    },
    {
      key: 'add-tags',
      name: '添加标签',
      icon: <TagOutlined />,
      description: '批量为记忆添加标签',
      confirmMessage: `确定要为选中的 ${selectedMemories.length} 条记忆添加标签吗？`,
      action: async (_ids) => {
        // [FIX-TS-015] _ids 参数未使用 (前缀下划线表示有意未用)
        message.info('标签添加功能开发中...')
      },
    },
  ]

  const handleOperation = async (operation: BatchOperation) => {
    Modal.confirm({
      title: operation.name,
      content: operation.confirmMessage,
      okText: '确定',
      cancelText: '取消',
      okButtonProps: { danger: operation.key === 'delete' },
      onOk: async () => {
        setProcessing(true)
        setProgress(0)
        setCurrentOperation(operation.name)

        try {
          const ids = selectedMemories.map((m) => m.id)
          const batchSize = 10
          const totalBatches = Math.ceil(ids.length / batchSize)

          for (let i = 0; i < totalBatches; i++) {
            const batch = ids.slice(i * batchSize, (i + 1) * batchSize)
            await operation.action(batch)
            setProgress(((i + 1) / totalBatches) * 100)
          }

          message.success(`${operation.name}成功完成`)
          onComplete()
          onClose()
        } catch (error) {
          message.error(`${operation.name}失败`)
          console.error('Batch operation error:', error)
        } finally {
          setProcessing(false)
          setProgress(0)
          setCurrentOperation(null)
        }
      },
    })
  }

  return (
    <Modal
      open={visible}
      onCancel={onClose}
      title={`批量操作 (${selectedMemories.length} 条已选)`}
      footer={null}
      width={600}
    >
      {processing ? (
        <div style={{ padding: '24px 0' }}>
          <Title level={5}>{currentOperation} 进行中...</Title>
          <Progress percent={Math.round(progress)} status="active" />
          <Text type="secondary">请勿关闭此窗口</Text>
        </div>
      ) : (
        <>
          <div style={{ marginBottom: 16 }}>
            <Text type="secondary">
              已选择 <Text strong>{selectedMemories.length}</Text> 条记忆，请选择要执行的操作：
            </Text>
          </div>

          <List
            grid={{ gutter: 16, column: 2 }}
            dataSource={operations}
            renderItem={(operation) => (
              <List.Item>
                <Card
                  hoverable
                  onClick={() => handleOperation(operation)}
                  style={{ height: '100%' }}
                >
                  <Space direction="vertical" style={{ width: '100%' }}>
                    <Space>
                      {operation.icon}
                      <Text strong>{operation.name}</Text>
                    </Space>
                    <Text type="secondary" style={{ fontSize: 12 }}>
                      {operation.description}
                    </Text>
                  </Space>
                </Card>
              </List.Item>
            )}
          />

          {selectedMemories.length > 0 && (
            <div style={{ marginTop: 16 }}>
              <Text type="secondary">选中的记忆：</Text>
              <div style={{ maxHeight: 200, overflow: 'auto', marginTop: 8 }}>
                {selectedMemories.slice(0, 10).map((memory) => (
                  <Tag key={memory.id} style={{ marginBottom: 4 }}>
                    {memory.content.substring(0, 30)}...
                  </Tag>
                ))}
                {selectedMemories.length > 10 && (
                  <Text type="secondary"> 还有 {selectedMemories.length - 10} 条...</Text>
                )}
              </div>
            </div>
          )}
        </>
      )}
    </Modal>
  )
}

export default BatchOperations
