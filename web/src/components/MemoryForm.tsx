import React, { useEffect } from 'react'
import { Modal, Form, Input, Select, Button, Space, message } from 'antd'
import { PlusOutlined, MinusCircleOutlined } from '@ant-design/icons'
import { useMemoryStore } from '../stores/memory-store'
import { MemoryEntry, CreateMemoryRequest, UpdateMemoryRequest } from '../types'

const { TextArea } = Input
const { Option } = Select

interface MemoryFormProps {
  visible: boolean
  memory: MemoryEntry | null
  onClose: () => void
  onSuccess: () => void
}

const MemoryForm: React.FC<MemoryFormProps> = ({ visible, memory, onClose, onSuccess }) => {
  const [form] = Form.useForm()
  const { createMemory, updateMemory, loading } = useMemoryStore()

  const isEdit = !!memory

  useEffect(() => {
    if (visible) {
      if (memory) {
        form.setFieldsValue({
          content: memory.content,
          layer: memory.layer,
          priority: memory.priority,
          namespace: memory.namespace,
          tags: memory.tags || [],
        })
      } else {
        form.resetFields()
        form.setFieldsValue({
          layer: 'working',
          priority: 'medium',
          namespace: 'default',
          tags: [],
        })
      }
    }
  }, [visible, memory, form])

  const handleSubmit = async () => {
    try {
      const values = await form.validateFields()

      if (isEdit && memory) {
        const updateData: UpdateMemoryRequest = {
          content: values.content,
          layer: values.layer,
          priority: values.priority,
          tags: values.tags,
          metadata: values.metadata,
        }
        await updateMemory(memory.id, updateData)
        message.success('记忆更新成功')
      } else {
        const createData: CreateMemoryRequest = {
          content: values.content,
          layer: values.layer,
          priority: values.priority,
          namespace: values.namespace,
          tags: values.tags,
          metadata: values.metadata,
        }
        await createMemory(createData)
        message.success('记忆创建成功')
      }

      onSuccess()
    } catch (error) {
      console.error('Form validation failed:', error)
    }
  }

  const handleCancel = () => {
    form.resetFields()
    onClose()
  }

  return (
    <Modal
      title={isEdit ? '编辑记忆' : '创建记忆'}
      open={visible}
      onCancel={handleCancel}
      width={700}
      footer={[
        <Button key="cancel" onClick={handleCancel}>
          取消
        </Button>,
        <Button
          key="submit"
          type="primary"
          loading={loading}
          onClick={handleSubmit}
        >
          {isEdit ? '更新' : '创建'}
        </Button>,
      ]}
    >
      <Form
        form={form}
        layout="vertical"
        initialValues={{
          layer: 'working',
          priority: 'medium',
          namespace: 'default',
          tags: [],
        }}
      >
        <Form.Item
          name="content"
          label="记忆内容"
          rules={[
            { required: true, message: '请输入记忆内容' },
            { min: 1, message: '记忆内容至少1个字符' },
            { max: 10000, message: '记忆内容不能超过10000个字符' },
          ]}
        >
          <TextArea
            rows={6}
            placeholder="请输入记忆内容..."
            showCount
            maxLength={10000}
          />
        </Form.Item>

        <Form.Item
          name="layer"
          label="记忆层级"
          rules={[{ required: true, message: '请选择记忆层级' }]}
        >
          <Select placeholder="选择记忆层级">
            <Option value="sensory">
              <Space>
                <span style={{ color: '#1890ff' }}>●</span>
                Sensory - 感知层
              </Space>
            </Option>
            <Option value="working">
              <Space>
                <span style={{ color: '#13c2c2' }}>●</span>
                Working - 工作层
              </Space>
            </Option>
            <Option value="short_term">
              <Space>
                <span style={{ color: '#52c41a' }}>●</span>
                Short Term - 短期层
              </Space>
            </Option>
            <Option value="episodic">
              <Space>
                <span style={{ color: '#fa8c16' }}>●</span>
                Episodic - 情景层
              </Space>
            </Option>
            <Option value="semantic">
              <Space>
                <span style={{ color: '#722ed1' }}>●</span>
                Semantic - 语义层
              </Space>
            </Option>
            <Option value="meta">
              <Space>
                <span style={{ color: '#eb2f96' }}>●</span>
                Meta - 元数据层
              </Space>
            </Option>
          </Select>
        </Form.Item>

        <Form.Item
          name="priority"
          label="优先级"
          rules={[{ required: true, message: '请选择优先级' }]}
        >
          <Select placeholder="选择优先级">
            <Option value="low">
              <Space>
                <span style={{ color: '#8c8c8c' }}>●</span>
                Low - 低优先级
              </Space>
            </Option>
            <Option value="medium">
              <Space>
                <span style={{ color: '#1890ff' }}>●</span>
                Medium - 中优先级
              </Space>
            </Option>
            <Option value="high">
              <Space>
                <span style={{ color: '#fa8c16' }}>●</span>
                High - 高优先级
              </Space>
            </Option>
            <Option value="critical">
              <Space>
                <span style={{ color: '#f5222d' }}>●</span>
                Critical - 关键优先级
              </Space>
            </Option>
          </Select>
        </Form.Item>

        <Form.Item
          name="namespace"
          label="命名空间"
          rules={[
            { required: true, message: '请输入命名空间' },
            { pattern: /^[a-zA-Z0-9_-]+$/, message: '命名空间只能包含字母、数字、下划线和连字符' },
          ]}
        >
          <Input placeholder="例如: default, project1, user123" />
        </Form.Item>

        <Form.List name="tags">
          {(fields, { add, remove }) => (
            <div>
              <Form.Item label="标签">
                <Button
                  type="dashed"
                  onClick={() => add()}
                  block
                  icon={<PlusOutlined />}
                >
                  添加标签
                </Button>
              </Form.Item>
              {fields.map((field) => (
                <Space key={field.key} style={{ display: 'flex', marginBottom: 8 }} align="baseline">
                  <Form.Item
                    {...field}
                    rules={[
                      { required: true, message: '请输入标签' },
                      { pattern: /^[a-zA-Z0-9_\-\u4e00-\u9fa5]+$/, message: '标签只能包含字母、数字、下划线、连字符和中文' },
                    ]}
                  >
                    <Input placeholder="输入标签" style={{ width: 200 }} />
                  </Form.Item>
                  <MinusCircleOutlined
                    onClick={() => remove(field.name)}
                    style={{ color: '#ff4d4f' }}
                  />
                </Space>
              ))}
            </div>
          )}
        </Form.List>

        <Form.Item name="metadata" label="元数据 (JSON格式)">
          <TextArea
            rows={4}
            placeholder='{"key": "value"}'
            style={{ fontFamily: 'monospace' }}
          />
        </Form.Item>
      </Form>
    </Modal>
  )
}

export default MemoryForm
