import { useState, useEffect, useCallback } from 'react'
import {
  Card,
  Row,
  Col,
  Tag,
  Button,
  Input,
  Select,
  Space,
  Typography,
  Collapse,
  Descriptions,
  Empty,
  message,
  Badge,
  Alert,
} from 'antd'
import {
  ApiOutlined,
  PlayCircleOutlined,
  ReloadOutlined,
  CloudServerOutlined,
  CheckCircleOutlined,
  QuestionCircleOutlined,
  ThunderboltOutlined,
  DatabaseOutlined,
  SearchOutlined,
  BulbOutlined,
  ExperimentOutlined,
  SafetyCertificateOutlined,
  BarChartOutlined,
} from '@ant-design/icons'
import { api } from '../services/api'

const { Text } = Typography
const { Panel } = Collapse
const { TextArea } = Input

interface MCPTool {
  name: string
  method: string
  path: string
  description: string
  category: string
  params: string[]
  icon: React.ReactNode
}

interface DynamicMcpServer {
  name: string
  tools: number
  status: string
  desc: string
}

const TOOL_ICONS: Record<string, React.ReactNode> = {
  memory_remember: <DatabaseOutlined />,
  memory_recall: <SearchOutlined />,
  get_memory: <DatabaseOutlined />,
  list_memories: <DatabaseOutlined />,
  memory_forget: <DatabaseOutlined />,
  memory_stats: <BarChartOutlined />,
  memory_capacity: <BarChartOutlined />,
  memory_consolidate: <ThunderboltOutlined />,
  search_memories: <SearchOutlined />,
  tianji_semantic_search: <SearchOutlined />,
  tianji_intercept: <SafetyCertificateOutlined />,
  tianji_expand_query: <SearchOutlined />,
  build_working_representation: <BulbOutlined />,
  run_reflective_cycle: <ExperimentOutlined />,
  explain_memory_lineage: <BulbOutlined />,
  get_session_digest: <BulbOutlined />,
  search_perspective_memories: <SearchOutlined />,
  tianji_classify: <SafetyCertificateOutlined />,
  tianji_auto_tag: <SafetyCertificateOutlined />,
  tianji_summarize: <BulbOutlined />,
  tianji_extract_knowledge: <BulbOutlined />,
  tianji_summarize_conversation: <BulbOutlined />,
  tianji_stream_capture: <ThunderboltOutlined />,
  tianji_monitor: <BarChartOutlined />,
  tianji_health: <CheckCircleOutlined />,
  tianji_help: <QuestionCircleOutlined />,
  tianji_consolidate_auto: <ThunderboltOutlined />,
}

const CATEGORY_COLORS: Record<string, string> = {
  核心: 'blue',
  搜索: 'green',
  高级: 'purple',
  监控: 'orange',
}

export default function MCPTools() {
  const [loading, setLoading] = useState(false)
  const [selectedTool, setSelectedTool] = useState<MCPTool | null>(null)
  const [paramValues, setParamValues] = useState<Record<string, string>>({})
  const [result, setResult] = useState<any>(null)
  const [resultError, setResultError] = useState<string | null>(null)
  const [executing, setExecuting] = useState(false)
  const [categoryFilter, setCategoryFilter] = useState<string>('all')
  const [searchQuery, setSearchQuery] = useState('')
  // [FIX-TS-013] 删除未使用的 serverStatus state (setter 调用保留)
  const [, setServerStatus] = useState<Record<string, any>>({})
  const [dynamicTools, setDynamicTools] = useState<MCPTool[]>([])
  const [dynamicServers, setDynamicServers] = useState<DynamicMcpServer[]>([])

  const fetchServerStatus = useCallback(async () => {
    setLoading(true)
    try {
      const [healthRes, mcpRes, mcpToolsRes] = await Promise.allSettled([
        api.get('/api/health'),
        api.get('/api/mcp/'),
        api.get('/api/mcp/tools'),
      ])

      const health = healthRes.status === 'fulfilled' ? healthRes.value : {}
      const mcpRoot = mcpRes.status === 'fulfilled' ? mcpRes.value : {}

      setServerStatus({ health, mcp: mcpRoot })

      // Parse MCP servers from response
      if (mcpRoot?.servers && Array.isArray(mcpRoot.servers)) {
        setDynamicServers(
          mcpRoot.servers.map((s: any) => ({
            name: s.name || s.key || '',
            tools: s.tools || s.tool_count || 0,
            status: s.status || s.enabled ? 'active' : 'standby',
            desc: s.description || s.role || '',
          }))
        )
      }

      // Parse MCP tools from response
      if (mcpToolsRes.status === 'fulfilled') {
        const toolsData = mcpToolsRes.value
        const tools = toolsData?.tools || toolsData || []
        if (Array.isArray(tools)) {
          setDynamicTools(
            tools.map((t: any) => ({
              name: t.name || t.id || '',
              method: t.method || 'POST',
              path: t.path || t.endpoint || '',
              description: t.description || t.desc || '',
              category: t.category || '其他',
              params: t.params || t.parameters || [],
              icon: TOOL_ICONS[t.name] || <ApiOutlined />,
            }))
          )
        }
      }
    } catch {
      setServerStatus({})
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchServerStatus()
  }, [fetchServerStatus])

  const handleExecute = async () => {
    if (!selectedTool) return
    setExecuting(true)
    setResult(null)
    setResultError(null)
    try {
      let res: any
      if (selectedTool.method === 'GET') {
        const params: Record<string, string> = {}
        for (const [k, v] of Object.entries(paramValues)) {
          if (v) params[k] = v
        }
        res = await api.get(selectedTool.path, { params })
      } else {
        const body: Record<string, any> = {}
        for (const [k, v] of Object.entries(paramValues)) {
          if (v) {
            try {
              body[k] = JSON.parse(v)
            } catch {
              body[k] = v
            }
          }
        }
        res = await api.post(selectedTool.path, body)
      }
      setResult(res)
      message.success('执行成功')
    } catch (err: any) {
      const errMsg = err?.response?.data?.detail || err?.message || '执行失败'
      setResultError(errMsg)
      message.error(`执行失败: ${errMsg}`)
    } finally {
      setExecuting(false)
    }
  }

  const handleToolSelect = (tool: MCPTool) => {
    setSelectedTool(tool)
    setParamValues({})
    setResult(null)
    setResultError(null)
  }

  const filteredTools = dynamicTools.filter((t) => {
    if (categoryFilter !== 'all' && t.category !== categoryFilter) return false
    if (
      searchQuery &&
      !t.name.toLowerCase().includes(searchQuery.toLowerCase()) &&
      !t.description.includes(searchQuery)
    )
      return false
    return true
  })

  const toolCategories = ['all', ...new Set(dynamicTools.map((t) => t.category))]

  return (
    <div style={{ padding: '0 0 24px' }}>
      <Row gutter={[16, 16]}>
        <Col span={24}>
          <Card
            size="small"
            title={
              <Space>
                <CloudServerOutlined style={{ color: '#722ed1' }} />
                <span>MCP Server 状态</span>
                <Tag color="blue">{dynamicServers.length} 服务器</Tag>
                <Tag color="green">{dynamicTools.length} 工具</Tag>
              </Space>
            }
            extra={
              <Button
                size="small"
                icon={<ReloadOutlined />}
                onClick={fetchServerStatus}
                loading={loading}
              >
                刷新
              </Button>
            }
          >
            <Row gutter={[12, 12]}>
              {dynamicServers.map((server) => (
                <Col key={server.name} xs={12} sm={8} md={6} lg={3}>
                  <Card
                    size="small"
                    style={{
                      textAlign: 'center',
                      borderColor: server.status === 'active' ? '#52c41a' : '#faad14',
                    }}
                  >
                    <Badge status={server.status === 'active' ? 'success' : 'warning'} />
                    <div style={{ fontSize: 12, fontWeight: 600, marginTop: 4 }}>{server.name}</div>
                    <div style={{ fontSize: 11, color: '#999' }}>{server.tools} 工具</div>
                    <div style={{ fontSize: 10, color: '#bbb', marginTop: 2 }}>{server.desc}</div>
                  </Card>
                </Col>
              ))}
            </Row>
          </Card>
        </Col>

        <Col xs={24} lg={14}>
          <Card
            size="small"
            title={
              <Space>
                <ApiOutlined style={{ color: '#1890ff' }} />
                <span>tianji-native 工具集 ({filteredTools.length})</span>
              </Space>
            }
            extra={
              <Space>
                <Input
                  placeholder="搜索工具..."
                  size="small"
                  style={{ width: 140 }}
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  prefix={<SearchOutlined />}
                  allowClear
                />
                <Select
                  size="small"
                  value={categoryFilter}
                  onChange={setCategoryFilter}
                  style={{ width: 90 }}
                >
                  {toolCategories.map((c) => (
                    <Select.Option key={c} value={c}>
                      {c === 'all' ? '全部分类' : c}
                    </Select.Option>
                  ))}
                </Select>
              </Space>
            }
            style={{ maxHeight: 'calc(100vh - 320px)', overflow: 'auto' }}
          >
            <Collapse
              accordion
              activeKey={selectedTool?.name}
              onChange={(key: string | string[]) => {
                const activeKey = Array.isArray(key) ? key[0] : (key as string)
                const tool = dynamicTools.find((t) => t.name === activeKey)
                if (tool) handleToolSelect(tool)
                else setSelectedTool(null)
              }}
            >
              {filteredTools.map((tool) => (
                <Panel
                  key={tool.name}
                  header={
                    <Space>
                      {tool.icon}
                      <Text strong style={{ fontSize: 13 }}>
                        {tool.name}
                      </Text>
                      <Tag color={CATEGORY_COLORS[tool.category]} style={{ fontSize: 10 }}>
                        {tool.category}
                      </Tag>
                      <Tag
                        color={tool.method === 'GET' ? 'cyan' : 'geekblue'}
                        style={{ fontSize: 10 }}
                      >
                        {tool.method}
                      </Tag>
                      <Text type="secondary" style={{ fontSize: 12 }}>
                        {tool.description}
                      </Text>
                    </Space>
                  }
                >
                  {selectedTool?.name === tool.name && (
                    <div style={{ padding: '8px 0' }}>
                      <Descriptions size="small" column={1} bordered>
                        <Descriptions.Item label="路径">{tool.path}</Descriptions.Item>
                        <Descriptions.Item label="方法">{tool.method}</Descriptions.Item>
                        <Descriptions.Item label="参数">
                          {tool.params.length > 0 ? tool.params.join(', ') : '无'}
                        </Descriptions.Item>
                      </Descriptions>
                      {tool.params.length > 0 && (
                        <div style={{ marginTop: 12 }}>
                          <Text strong style={{ fontSize: 12, marginBottom: 8, display: 'block' }}>
                            参数输入
                          </Text>
                          {tool.params.map((param) => (
                            <div key={param} style={{ marginBottom: 8 }}>
                              <Text
                                style={{
                                  fontSize: 12,
                                  color: '#666',
                                  marginBottom: 2,
                                  display: 'block',
                                }}
                              >
                                {param}
                              </Text>
                              <TextArea
                                rows={param === 'content' ? 3 : 1}
                                size="small"
                                placeholder={`输入 ${param}...`}
                                value={paramValues[param] || ''}
                                onChange={(e) =>
                                  setParamValues((prev) => ({ ...prev, [param]: e.target.value }))
                                }
                              />
                            </div>
                          ))}
                        </div>
                      )}
                      <div style={{ marginTop: 12, textAlign: 'right' }}>
                        <Button
                          type="primary"
                          icon={<PlayCircleOutlined />}
                          onClick={handleExecute}
                          loading={executing}
                          style={{ background: 'linear-gradient(135deg, #722ed1, #1890ff)' }}
                        >
                          执行
                        </Button>
                      </div>
                    </div>
                  )}
                </Panel>
              ))}
            </Collapse>
          </Card>
        </Col>

        <Col xs={24} lg={10}>
          <Card
            size="small"
            title={
              <Space>
                <ThunderboltOutlined style={{ color: '#52c41a' }} />
                <span>执行结果</span>
                {result && <Tag color="success">成功</Tag>}
                {resultError && <Tag color="error">失败</Tag>}
              </Space>
            }
            style={{ maxHeight: 'calc(100vh - 320px)', overflow: 'auto' }}
          >
            {result ? (
              <pre
                style={{
                  background: '#f6f8fa',
                  padding: 12,
                  borderRadius: 6,
                  fontSize: 12,
                  lineHeight: 1.6,
                  overflow: 'auto',
                  maxHeight: 'calc(100vh - 440px)',
                  whiteSpace: 'pre-wrap',
                  wordBreak: 'break-all',
                }}
              >
                {JSON.stringify(result, null, 2)}
              </pre>
            ) : resultError ? (
              <Alert type="error" message="执行失败" description={resultError} showIcon />
            ) : (
              <Empty description="选择工具并执行以查看结果" image={Empty.PRESENTED_IMAGE_SIMPLE} />
            )}
          </Card>
        </Col>
      </Row>
    </div>
  )
}
