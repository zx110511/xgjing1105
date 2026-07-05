import React, { useState } from 'react'
import { Form, Input, Select, DatePicker, Button, Space, Card, Collapse, Tag, message, Modal } from 'antd'
import { SearchOutlined, ReloadOutlined, SaveOutlined, DeleteOutlined, PlusOutlined } from '@ant-design/icons'
import type { SearchMemoriesRequest } from '../services'

const { RangePicker } = DatePicker
const { Option } = Select

interface AdvancedSearchProps {
  onSearch: (params: SearchMemoriesRequest) => void
  onReset: () => void
  loading?: boolean
}

interface SearchCondition {
  field: string
  operator: string
  value: string
}

const AdvancedSearch: React.FC<AdvancedSearchProps> = ({ onSearch, onReset, loading }) => {
  const [form] = Form.useForm()
  const [conditions, setConditions] = useState<SearchCondition[]>([])
  const [savedSearches, setSavedSearches] = useState<Array<{ name: string; params: SearchMemoriesRequest }>>([])

  const fieldOptions = [
    { label: '内容', value: 'content' },
    { label: '标签', value: 'tags' },
    { label: '命名空间', value: 'namespace' },
    { label: 'ID', value: 'id' },
  ]

  const operatorOptions = [
    { label: '包含', value: 'contains' },
    { label: '等于', value: 'equals' },
    { label: '开头为', value: 'startsWith' },
    { label: '结尾为', value: 'endsWith' },
    { label: '不包含', value: 'notContains' },
  ]

  const handleAddCondition = () => {
    setConditions([...conditions, { field: 'content', operator: 'contains', value: '' }])
  }

  const handleRemoveCondition = (index: number) => {
    const newConditions = conditions.filter((_, i) => i !== index)
    setConditions(newConditions)
  }

  const handleConditionChange = (index: number, key: string, value: string) => {
    const newConditions = [...conditions]
    newConditions[index] = { ...newConditions[index], [key]: value }
    setConditions(newConditions)
  }

  const handleSearch = () => {
    const values = form.getFieldsValue()
    const searchParams = {
      query: values.query || '',
      layer: values.layer,
      priority: values.priority,
      namespace: values.namespace,
      tags: values.tags,
      dateRange: values.dateRange,
      conditions: conditions,
      limit: 20,
      offset: 0,
    } as SearchMemoriesRequest
    onSearch(searchParams)
  }

  const handleReset = () => {
    form.resetFields()
    setConditions([])
    onReset()
  }

  const handleSaveSearch = () => {
    const values = form.getFieldsValue()
    const searchParams = {
      query: values.query || '',
      layer: values.layer,
      priority: values.priority,
      namespace: values.namespace,
      tags: values.tags,
      dateRange: values.dateRange,
      conditions: conditions,
      limit: 20,
      offset: 0,
    } as SearchMemoriesRequest

    Modal.confirm({
      title: '保存搜索条件',
      content: (
        <Input
          placeholder="请输入搜索名称"
          id="searchName"
        />
      ),
      onOk: () => {
        const name = (document.getElementById('searchName') as HTMLInputElement)?.value
        if (name) {
          setSavedSearches([...savedSearches, { name, params: searchParams }])
          message.success('搜索条件已保存')
        }
      },
    })
  }

  const handleLoadSearch = (index: number) => {
    const saved = savedSearches[index]
    form.setFieldsValue({
      query: saved.params.query,
      layer: saved.params.layer,
      priority: saved.params.priority,
      namespace: saved.params.namespace,
      tags: saved.params.tags,
      dateRange: saved.params.dateRange,
    })
    setConditions(saved.params.conditions || [])
    message.info('已加载搜索条件')
  }

  const handleDeleteSavedSearch = (index: number) => {
    const newSavedSearches = savedSearches.filter((_, i) => i !== index)
    setSavedSearches(newSavedSearches)
    message.success('已删除保存的搜索')
  }

  return (
    <Card className="advanced-search">
      <Form form={form} layout="vertical">
        <Form.Item name="query" label="关键词搜索">
          <Input.Search
            placeholder="输入关键词搜索..."
            allowClear
            enterButton={<SearchOutlined />}
            onSearch={handleSearch}
            loading={loading}
          />
        </Form.Item>

        <Collapse defaultActiveKey={['1']} style={{ marginBottom: 16 }} items={[{
          key: '1', label: '高级筛选', children: (
            <Space direction="vertical" style={{ width: '100%' }} size="middle">
              <Form.Item name="layer" label="记忆层级">
                <Select placeholder="选择层级" allowClear mode="multiple">
                  <Option value="sensory">Sensory - 感知层</Option>
                  <Option value="working">Working - 工作层</Option>
                  <Option value="short_term">Short Term - 短期层</Option>
                  <Option value="episodic">Episodic - 情景层</Option>
                  <Option value="semantic">Semantic - 语义层</Option>
                  <Option value="meta">Meta - 元数据层</Option>
                </Select>
              </Form.Item>

              <Form.Item name="priority" label="优先级">
                <Select placeholder="选择优先级" allowClear mode="multiple">
                  <Option value="low">Low - 低优先级</Option>
                  <Option value="medium">Medium - 中优先级</Option>
                  <Option value="high">High - 高优先级</Option>
                  <Option value="critical">Critical - 关键优先级</Option>
                </Select>
              </Form.Item>

              <Form.Item name="namespace" label="命名空间">
                <Input placeholder="输入命名空间" allowClear />
              </Form.Item>

              <Form.Item name="tags" label="标签">
                <Select
                  mode="tags"
                  placeholder="输入标签后按回车"
                  style={{ width: '100%' }}
                />
              </Form.Item>

              <Form.Item name="dateRange" label="创建时间">
                <RangePicker style={{ width: '100%' }} showTime />
              </Form.Item>
            </Space>
          )
        }]} />

        <Collapse style={{ marginBottom: 16 }} items={[{
          key: '1', label: '自定义条件', children: (
            <Space direction="vertical" style={{ width: '100%' }}>
              {conditions.map((condition, index) => (
                <Space key={index} style={{ width: '100%' }} align="start">
                  <Select
                    value={condition.field}
                    onChange={(value) => handleConditionChange(index, 'field', value)}
                    style={{ width: 120 }}
                  >
                    {fieldOptions.map((opt) => (
                      <Option key={opt.value} value={opt.value}>
                        {opt.label}
                      </Option>
                    ))}
                  </Select>

                  <Select
                    value={condition.operator}
                    onChange={(value) => handleConditionChange(index, 'operator', value)}
                    style={{ width: 120 }}
                  >
                    {operatorOptions.map((opt) => (
                      <Option key={opt.value} value={opt.value}>
                        {opt.label}
                      </Option>
                    ))}
                  </Select>

                  <Input
                    value={condition.value}
                    onChange={(e) => handleConditionChange(index, 'value', e.target.value)}
                    placeholder="输入值"
                    style={{ flex: 1 }}
                  />

                  <Button
                    danger
                    icon={<DeleteOutlined />}
                    onClick={() => handleRemoveCondition(index)}
                  />
                </Space>
              ))}

              <Button
                type="dashed"
                onClick={handleAddCondition}
                block
                icon={<PlusOutlined />}
              >
                添加条件
              </Button>
            </Space>
          )
        }]} />

        {savedSearches.length > 0 && (
          <Collapse style={{ marginBottom: 16 }} items={[{
            key: '1', label: '保存的搜索', children: (
              <Space direction="vertical" style={{ width: '100%' }}>
                {savedSearches.map((saved, index) => (
                  <div
                    key={index}
                    style={{
                      display: 'flex',
                      justifyContent: 'space-between',
                      alignItems: 'center',
                      padding: '8px 12px',
                      background: '#f5f5f5',
                      borderRadius: 4,
                    }}
                  >
                    <Tag color="blue">{saved.name}</Tag>
                    <Space>
                      <Button
                        size="small"
                        onClick={() => handleLoadSearch(index)}
                      >
                        加载
                      </Button>
                      <Button
                        size="small"
                        danger
                        icon={<DeleteOutlined />}
                        onClick={() => handleDeleteSavedSearch(index)}
                      />
                    </Space>
                  </div>
                ))}
              </Space>
            )
          }]} />
        )}

        <Form.Item>
          <Space>
            <Button
              type="primary"
              icon={<SearchOutlined />}
              onClick={handleSearch}
              loading={loading}
            >
              搜索
            </Button>
            <Button
              icon={<ReloadOutlined />}
              onClick={handleReset}
            >
              重置
            </Button>
            <Button
              icon={<SaveOutlined />}
              onClick={handleSaveSearch}
            >
              保存搜索
            </Button>
          </Space>
        </Form.Item>
      </Form>
    </Card>
  )
}

export default AdvancedSearch
