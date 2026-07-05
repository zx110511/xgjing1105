import React from 'react'
import { Modal, Descriptions, Tag, Space, Button, Divider, Typography } from 'antd'
import { EditOutlined, DeleteOutlined, CopyOutlined } from '@ant-design/icons'
import { useMemoryStore } from '../stores/memory-store'
import { message } from 'antd'

const { Paragraph } = Typography

interface MemoryDetailProps {
  visible: boolean
  onClose: () => void
  onEdit?: () => void
}

const MemoryDetail: React.FC<MemoryDetailProps> = ({ visible, onClose, onEdit }) => {
  const { currentMemory, deleteMemory } = useMemoryStore()

  if (!currentMemory) {
    return null
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

  const handleCopyContent = () => {
    navigator.clipboard.writeText(currentMemory.content)
    message.success('内容已复制到剪贴板')
  }

  const handleDelete = async () => {
    Modal.confirm({
      title: '删除确认',
      content: '确定要删除这条记忆吗？此操作不可恢复。',
      okText: '确定',
      cancelText: '取消',
      okType: 'danger',
      onOk: async () => {
        await deleteMemory(currentMemory.id)
        message.success('记忆删除成功')
        onClose()
      },
    })
  }

  const formatDateTime = (dateString: string) => {
    return new Date(dateString).toLocaleString('zh-CN', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    })
  }

  return (
    <Modal
      title="记忆详情"
      open={visible}
      onCancel={onClose}
      width={800}
      footer={[
        <Button key="close" onClick={onClose}>
          关闭
        </Button>,
        <Button
          key="edit"
          type="primary"
          icon={<EditOutlined />}
          onClick={onEdit}
        >
          编辑
        </Button>,
        <Button
          key="delete"
          danger
          icon={<DeleteOutlined />}
          onClick={handleDelete}
        >
          删除
        </Button>,
      ]}
    >
      <Descriptions bordered column={2}>
        <Descriptions.Item label="ID" span={2}>
          <Paragraph copyable style={{ marginBottom: 0 }}>
            {currentMemory.id}
          </Paragraph>
        </Descriptions.Item>

        <Descriptions.Item label="层级">
          <Tag color={getLayerColor(currentMemory.layer)}>
            {currentMemory.layer.toUpperCase()}
          </Tag>
        </Descriptions.Item>

        <Descriptions.Item label="优先级">
          <Tag color={getPriorityColor(currentMemory.priority)}>
            {currentMemory.priority.toUpperCase()}
          </Tag>
        </Descriptions.Item>

        <Descriptions.Item label="命名空间" span={2}>
          {currentMemory.namespace}
        </Descriptions.Item>

        <Descriptions.Item label="标签" span={2}>
          <Space wrap>
            {currentMemory.tags && currentMemory.tags.length > 0 ? (
              currentMemory.tags.map((tag) => (
                <Tag key={tag}>{tag}</Tag>
              ))
            ) : (
              <span style={{ color: '#999' }}>无标签</span>
            )}
          </Space>
        </Descriptions.Item>

        <Descriptions.Item label="创建时间">
          {formatDateTime(currentMemory.created_at)}
        </Descriptions.Item>

        <Descriptions.Item label="更新时间">
          {formatDateTime(currentMemory.updated_at)}
        </Descriptions.Item>
      </Descriptions>

      <Divider orientation="left">记忆内容</Divider>

      <div style={{ position: 'relative' }}>
        <Paragraph
          style={{
            whiteSpace: 'pre-wrap',
            wordBreak: 'break-word',
            backgroundColor: '#f5f5f5',
            padding: 16,
            borderRadius: 4,
            maxHeight: 300,
            overflowY: 'auto',
          }}
        >
          {currentMemory.content}
        </Paragraph>
        <Button
          type="text"
          icon={<CopyOutlined />}
          onClick={handleCopyContent}
          style={{ position: 'absolute', top: 8, right: 8 }}
        >
          复制
        </Button>
      </div>

      {currentMemory.metadata && Object.keys(currentMemory.metadata).length > 0 && (
        <>
          <Divider orientation="left">元数据</Divider>
          <Descriptions bordered column={1}>
            {Object.entries(currentMemory.metadata).map(([key, value]) => (
              <Descriptions.Item key={key} label={key}>
                {typeof value === 'object' ? JSON.stringify(value, null, 2) : String(value)}
              </Descriptions.Item>
            ))}
          </Descriptions>
        </>
      )}
    </Modal>
  )
}

export default MemoryDetail
