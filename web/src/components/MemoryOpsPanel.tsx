import { useState, useEffect } from 'react'
import { Button, Modal, Input, Select, Tag, Space, Card, List, Typography, Spin, message, Tabs, Badge, Row, Col, Statistic, Progress, Empty } from 'antd'
import {
  DatabaseOutlined,
  RobotOutlined,
  ExportOutlined,
  SendOutlined,
  SaveOutlined,
  SearchOutlined,
  TeamOutlined,
  ThunderboltOutlined,
} from '@ant-design/icons'
import { api } from '../services/api'

const { TextArea } = Input
const { Option } = Select
const { Text, Paragraph } = Typography
const { TabPane } = Tabs

interface MemoryEntry {
  id: string
  content: string
  layer: string
  tags: string[]
  timestamp: number
  score?: number
}

interface AgentInfo {
  id: string
  name: string
  role: string
  status: 'active' | 'idle' | 'busy'
}

interface ExtractResult {
  knowledge: string[]
  entities: string[]
  actions: string[]
  confidence: number
}

export default function MemoryOpsPanel({ visible, onClose }: { visible: boolean; onClose: () => void }) {
  const [activeTab, setActiveTab] = useState('store')
  const [loading, setLoading] = useState(false)
  const [memoryContent, setMemoryContent] = useState('')
  const [memoryLayer, setMemoryLayer] = useState('working')
  const [memoryTags, setMemoryTags] = useState('')
  const [searchQuery, setSearchQuery] = useState('')
  const [searchLayer, setSearchLayer] = useState('all')
  const [memories, setMemories] = useState<MemoryEntry[]>([])
  const [agents, setAgents] = useState<AgentInfo[]>([])
  const [selectedAgent, setSelectedAgent] = useState('')
  const [extractText, setExtractText] = useState('')
  const [extractResult, setExtractResult] = useState<ExtractResult | null>(null)
  const [pushContent, setPushContent] = useState('')
  const [pushTarget, setPushTarget] = useState('current')
  const [stats, setStats] = useState<{ total: number; by_layer: Record<string, number> }>({ total: 0, by_layer: {} })

  useEffect(() => {
    if (visible) {
      fetchAgents()
      fetchMemoryStats()
    }
  }, [visible])

  const fetchAgents = async () => {
    try {
      // [FIX-C1-001] 修正智能体列表API路径: orchestrator/agents → chat/fusion/agents
      const data = await api.get('/api/chat/fusion/agents')
      const raw = data as any
      // fusion/agents 返回 { agents: [...], current_agent: {...} }
      setAgents((raw.agents || []).map((a: any) => ({
        id: a.id,
        name: a.name,
        role: a.role || a.layer,
        status: 'active' as const,
      })))
    } catch {
      // silent
    }
  }

  const fetchMemoryStats = async () => {
    try {
      const data = await api.get('/api/memory/stats')
      const raw = data as any
      // [FIX-C1-002] 修正统计字段映射: 后端返回 layers={episodic:130} 不是 layer_counts
      const layers = raw.layers || {}
      setStats({
        total: raw.total_entries || 0,
        by_layer: layers,
      })
    } catch {
      // silent
    }
  }

  const handleStoreMemory = async () => {
    if (!memoryContent.trim()) {
      message.warning('请输入记忆内容')
      return
    }

    setLoading(true)
    try {
      // [FIX-C1-003] 使用非流式平台API替代SSE的mcp/store_memory,避免HTTP客户端超时
      const result = await api.post('/api/platform/remember', {
        content: memoryContent.trim(),
        layer: memoryLayer,
        tags: memoryTags.split(',').map(t => t.trim()).filter(Boolean),
        priority: 'medium',
      })
      const r = result as any
      message.success(`✅ 记忆已存储到 ${memoryLayer} 层 (ID: ${(r.entry_id || r.id || '').slice(0, 12)}...)`)
      setMemoryContent('')
      setMemoryTags('')
      fetchMemoryStats()
    } catch (err) {
      message.error(`❌ 存储失败: ${(err as Error).message}`)
    } finally {
      setLoading(false)
    }
  }

  const handleSearchMemory = async () => {
    if (!searchQuery.trim()) {
      message.warning('请输入搜索查询')
      return
    }

    setLoading(true)
    try {
      const data = await api.post('/api/mcp/tools/search_memories', {
        query: searchQuery.trim(),
        limit: 20,
        ...(searchLayer !== 'all' && { layer: searchLayer }),
      })
      const resultData = data as any
      // [FIX-C1-007] 修正搜索结果映射: MCP返回 {results:[...]} 每项字段需适配MemoryEntry接口
      const results = (resultData.results || []).map((item: any) => ({
        id: item.id || item.entry_id || '',
        content: item.content || '',
        layer: item.layer || item.actual_layer || 'unknown',
        tags: item.tags || [],
        timestamp: item.created_at ? (typeof item.created_at === 'number' ? item.created_at : new Date(item.created_at).getTime() / 1000) : Date.now() / 1000,
        score: item.score || item.relevance_score || undefined,
      }))
      setMemories(results)
      message.success(`找到 ${results.length} 条相关记忆`)
    } catch (err) {
      message.error(`❌ 搜索失败: ${(err as Error).message}`)
    } finally {
      setLoading(false)
    }
  }

  const handleExtractKnowledge = async () => {
    if (!extractText.trim()) {
      message.warning('请输入要提取的内容')
      return
    }

    setLoading(true)
    try {
      const data = await api.post('/api/llm/extract_knowledge', {
        content: extractText.trim(),
        mode: 'full',
      })
      const raw = data as any
      // [FIX-C1-006] 修正知识提取响应映射: 后端返回 {triples:[...]} 不是 {knowledge,entities,actions}
      const triples = raw.triples || []
      // [FIX-FAB-006] 修复伪造的 confidence: 0.85
      // 真实数据源: 后端返回的 confidence 字段; 未提供时基于三元组数估算
      const realConfidence = typeof raw.confidence === 'number'
        ? raw.confidence
        : (triples.length > 0 ? Math.min(1, 0.5 + triples.length * 0.1) : 0)
      setExtractResult({
        knowledge: triples.map((t: any) => `${t.subject || ''} ${t.relation || ''} ${t.object || ''}`).filter(Boolean),
        entities: [...new Set(triples.flatMap((t: any) => [t.subject, t.object].filter(Boolean)))] as string[],
        actions: triples.filter((t: any) => t.relation?.includes('action') || t.relation?.includes('do')).map((t: any) => t.object || t.subject),
        confidence: realConfidence,
      })
      message.success(`✅ 知识提取完成 (${triples.length}个三元组)`)
    } catch (err) {
      message.error(`❌ 提取失败: ${(err as Error).message}`)
    } finally {
      setLoading(false)
    }
  }

  const handleAgentDispatch = async () => {
    if (!selectedAgent) {
      message.warning('请选择智能体')
      return
    }

    setLoading(true)
    try {
      // [FIX-C1-004] 修正智能体调度API: active/subagent_execute → chat/fusion/dispatch
      const result = await api.post('/api/chat/fusion/dispatch', {
        task_type: 'memory_remember',
        task_data: {
          content: pushContent.trim() || '执行默认任务',
          layer: 'episodic',
        },
        priority: 'high',
      })
      const r = result as any
      message.success(`✅ 智能体 ${r.agent_id || selectedAgent} 已启动 (${r.duration_ms || 0}ms)`)
      setPushContent('')
    } catch (err) {
      message.error(`❌ 调度失败: ${(err as Error).message}`)
    } finally {
      setLoading(false)
    }
  }

  const handlePushMemory = async () => {
    if (!pushContent.trim()) {
      message.warning('请输入要推送的内容')
      return
    }

    setLoading(true)
    try {
      // [FIX-C1-005] 推送也使用非流式平台API
      const targetLayer = pushTarget === 'global' ? 'semantic' : pushTarget === 'episodic' ? 'episodic' : 'sensory'
      await api.post('/api/platform/remember', {
        content: pushContent.trim(),
        layer: targetLayer,
        tags: ['auto_push', 'chat_generated'],
        priority: 'high',
        metadata: { source: 'chat_panel', target: pushTarget },
      })
      message.success('✅ 已推送到记忆系统')
      setPushContent('')
      fetchMemoryStats()
    } catch (err) {
      message.error(`❌ 推送失败: ${(err as Error).message}`)
    } finally {
      setLoading(false)
    }
  }

  return (
    <Modal
      title={
        <Space>
          <DatabaseOutlined style={{ color: '#8B5CF6' }} />
          <span>🧠 天机记忆操作中心</span>
          <Badge count={stats.total} style={{ backgroundColor: '#52c41a' }} />
        </Space>
      }
      open={visible}
      onCancel={onClose}
      width={900}
      footer={null}
      styles={{ body: { padding: '16px', maxHeight: '70vh', overflowY: 'auto' } }}
    >
      <Tabs activeKey={activeTab} onChange={setActiveTab} type="card" size="small">
        
        {/* Tab 1: 对话录入 + 智能存储 */}
        <TabPane tab={<span><SaveOutlined /> 对话录入 & 存储</span>} key="store">
          <Row gutter={[16, 16]}>
            <Col span={24}>
              <Card size="small" title="💾 录入对话到记忆系统" className="ops-card">
                <TextArea
                  rows={4}
                  placeholder="在此输入对话内容或重要信息，将自动结构化存储到天机记忆系统..."
                  value={memoryContent}
                  onChange={e => setMemoryContent(e.target.value)}
                  style={{ marginBottom: 12, background: 'rgba(30,41,59,0.5)', color: '#E2E8F0', border: '1px solid rgba(139,92,246,0.3)' }}
                />
                <Row gutter={12} align="middle">
                  <Col span={6}>
                    <Select value={memoryLayer} onChange={setMemoryLayer} style={{ width: '100%' }}>
                      <Option value="sensory">L0-Sensory (感知)</Option>
                      <Option value="working">L1-Working (工作)</Option>
                      <Option value="short_term">L2-Short-Term (短期)</Option>
                      <Option value="episodic">L3-Episodic (经历)</Option>
                      <Option value="semantic">L4-Semantic (语义)</Option>
                    </Select>
                  </Col>
                  <Col span={10}>
                    <Input placeholder="标签 (逗号分隔)" value={memoryTags} onChange={e => setMemoryTags(e.target.value)} />
                  </Col>
                  <Col span={8}>
                    <Button type="primary" icon={<SaveOutlined />} loading={loading} onClick={handleStoreMemory} block>
                      💾 存储到记忆
                    </Button>
                  </Col>
                </Row>
              </Card>
            </Col>

            <Col span={24}>
              <Card size="small" title="📊 当前记忆统计" className="ops-card">
                <Row gutter={16}>
                  <Col span={8}>
                    <Statistic title="总记忆数" value={stats.total} prefix={<DatabaseOutlined />} valueStyle={{ color: '#8B5CF6' }} />
                  </Col>
                  {Object.entries(stats.by_layer).slice(0, 4).map(([layer, count]) => (
                    <Col span={4} key={layer}>
                      <Progress type="circle" percent={Math.min((count / Math.max(stats.total, 1)) * 100, 100)} size={60} format={() => `${count}`} />
                    </Col>
                  ))}
                </Row>
              </Card>
            </Col>
          </Row>
        </TabPane>

        {/* Tab 2: 记忆提取 */}
        <TabPane tab={<span><ExportOutlined /> 记忆提取</span>} key="extract">
          <Row gutter={[16, 16]}>
            <Col span={24}>
              <Card size="small" title="🔍 从文本中提取知识" className="ops-card">
                <TextArea
                  rows={4}
                  placeholder="粘贴或输入文本，AI将自动提取：知识点、实体、行动项..."
                  value={extractText}
                  onChange={e => setExtractText(e.target.value)}
                  style={{ marginBottom: 12, background: 'rgba(30,41,59,0.5)', color: '#E2E8F0', border: '1px solid rgba(139,92,246,0.3)' }}
                />
                <Button type="primary" icon={<ExportOutlined />} loading={loading} onClick={handleExtractKnowledge} block>
                  ⚡ 开始知识提取
                </Button>
              </Card>
            </Col>

            {extractResult && (
              <>
                <Col span={8}>
                  <Card size="small" title={`📚 知识点 (${extractResult.knowledge.length})`} className="ops-card">
                    <List dataSource={extractResult.knowledge} renderItem={item => (
                      <List.Item><Tag color="purple">{item}</Tag></List.Item>
                    )} />
                  </Card>
                </Col>
                <Col span={8}>
                  <Card size="small" title={`🏷️ 实体 (${extractResult.entities.length})`} className="ops-card">
                    <List dataSource={extractResult.entities} renderItem={item => (
                      <List.Item><Tag color="blue">{item}</Tag></List.Item>
                    )} />
                  </Card>
                </Col>
                <Col span={8}>
                  <Card size="small" title={`✅ 行动项 (${extractResult.actions.length})`} className="ops-card">
                    <List dataSource={extractResult.actions} renderItem={item => (
                      <List.Item><Tag color="green">{item}</Tag></List.Item>
                    )} />
                  </Card>
                </Col>
              </>
            )}
          </Row>
        </TabPane>

        {/* Tab 3: 智能推送记忆 */}
        <TabPane tab={<span><SendOutlined /> 智能推送</span>} key="push">
          <Row gutter={[16, 16]}>
            <Col span={24}>
              <Card size="small" title="🚀 推送到记忆系统" className="ops-card">
                <TextArea
                  rows={3}
                  placeholder="输入需要记住的重要内容..."
                  value={pushContent}
                  onChange={e => setPushContent(e.target.value)}
                  style={{ marginBottom: 12, background: 'rgba(30,41,59,0.5)', color: '#E2E8F0', border: '1px solid rgba(139,92,246,0.3)' }}
                />
                <Row gutter={12} align="middle">
                  <Col span={8}>
                    <Select value={pushTarget} onChange={setPushTarget} style={{ width: '100%' }}>
                      <Option value="current">当前会话</Option>
                      <Option value="global">全局记忆</Option>
                      <Option value="episodic">经历层</Option>
                    </Select>
                  </Col>
                  <Col span={8}>
                    <Button type="primary" icon={<SendOutlined />} loading={loading} onClick={handlePushMemory} block>
                      📤 推送记忆
                    </Button>
                  </Col>
                </Row>
              </Card>
            </Col>

            <Col span={24}>
              <Card size="small" title="⚡ 快捷操作" className="ops-card">
                <Space wrap>
                  <Button icon={<SaveOutlined />} onClick={() => { setPushContent('用户偏好设置已更新'); setPushTarget('semantic'); }}>
                    💾 保存用户偏好
                  </Button>
                  <Button icon={<SaveOutlined />} onClick={() => { setPushContent('重要决策记录'); setPushTarget('episodic'); }}>
                    📝 记录决策
                  </Button>
                  <Button icon={<SaveOutlined />} onClick={() => { setPushContent('错误教训总结'); setPushTarget('semantic'); }}>
                    📚 提取教训
                  </Button>
                </Space>
              </Card>
            </Col>
          </Row>
        </TabPane>

        {/* Tab 4: 智能体调度 */}
        <TabPane tab={<span><TeamOutlined /> 智能体调度</span>} key="agent">
          <Row gutter={[16, 16]}>
            <Col span={24}>
              <Card size="small" title="🤖 调度专业智能体" className="ops-card">
                <Row gutter={12} align="middle" style={{ marginBottom: 12 }}>
                  <Col span={10}>
                    <Select 
                      showSearch
                      value={selectedAgent} 
                      onChange={setSelectedAgent} 
                      style={{ width: '100%' }}
                      placeholder="选择要调度的智能体"
                    >
                      {agents.map(agent => (
                        <Option key={agent.id} value={agent.id}>
                          <Space>
                            <Badge status={agent.status === 'active' ? 'success' : agent.status === 'busy' ? 'processing' : 'default'} />
                            {agent.name} ({agent.role})
                          </Space>
                        </Option>
                      ))}
                    </Select>
                  </Col>
                  <Col span={14}>
                    <Input placeholder="任务描述..." value={pushContent} onChange={e => setPushContent(e.target.value)} />
                  </Col>
                </Row>
                <Button type="primary" icon={<ThunderboltOutlined />} loading={loading} onClick={handleAgentDispatch} block>
                  ⚡ 启动智能体任务
                </Button>
              </Card>
            </Col>

            <Col span={24}>
              <Card size="small" title="👥 可用智能体列表" className="ops-card">
                <List grid={{ gutter: 16, xs: 1, sm: 2, md: 3, lg: 4 }} dataSource={agents} renderItem={agent => (
                  <List.Item>
                    <Card size="small" hoverable onClick={() => setSelectedAgent(agent.id)} style={{
                      borderColor: selectedAgent === agent.id ? '#8B5CF6' : 'transparent',
                      background: selectedAgent === agent.id ? 'rgba(139,92,246,0.08)' : 'transparent'
                    }}>
                      <Space direction="vertical" align="center" style={{ width: '100%' }}>
                        <RobotOutlined style={{ fontSize: 24, color: agent.status === 'active' ? '#52c41a' : '#64748B' }} />
                        <Text strong>{agent.name}</Text>
                        <Text type="secondary" style={{ fontSize: 11 }}>{agent.role}</Text>
                        <Badge status={agent.status === 'active' ? 'success' : agent.status === 'busy' ? 'processing' : 'default'} text={agent.status} />
                      </Space>
                    </Card>
                  </List.Item>
                )} />
              </Card>
            </Col>
          </Row>
        </TabPane>

        {/* Tab 5: 记忆搜索 */}
        <TabPane tab={<span><SearchOutlined /> 记忆搜索</span>} key="search">
          <Row gutter={[16, 16]}>
            <Col span={24}>
              <Card size="small" title="🔍 搜索记忆库" className="ops-card">
                <Input.Search
                  placeholder="输入关键词或自然语言查询..."
                  enterButton="搜索"
                  size="large"
                  value={searchQuery}
                  onChange={e => setSearchQuery(e.target.value)}
                  onSearch={handleSearchMemory}
                  loading={loading}
                  style={{ marginBottom: 12 }}
                />
                <Select value={searchLayer} onChange={setSearchLayer} style={{ width: 200, marginRight: 12 }}>
                  <Option value="all">全部层级</Option>
                  <Option value="sensory">L0-Sensory</Option>
                  <Option value="working">L1-Working</Option>
                  <Option value="episodic">L3-Episodic</Option>
                  <Option value="semantic">L4-Semantic</Option>
                </Select>
              </Card>
            </Col>

            <Col span={24}>
              <Card size="small" title={`📋 搜索结果 (${memories.length})`} className="ops-card">
                {loading ? (
                  <div style={{ textAlign: 'center', padding: 40 }}><Spin size="large" /></div>
                ) : memories.length > 0 ? (
                  <List dataSource={memories} renderItem={mem => (
                    <List.Item>
                      <Card size="small" style={{ width: '100%', background: 'rgba(30,41,59,0.3)' }}>
                        <Paragraph ellipsis={{ rows: 2 }}>{mem.content}</Paragraph>
                        <div style={{ marginTop: 8 }}>
                          <Tag color="purple">{mem.layer}</Tag>
                          <Text type="secondary" style={{ fontSize: 11 }}>{new Date(mem.timestamp * 1000).toLocaleString()}</Text>
                          {mem.score && <Tag color="blue" style={{ marginLeft: 8 }}>评分: {(mem.score * 100).toFixed(0)}%</Tag>}
                          {mem.tags?.map(tag => <Tag key={tag}>{tag}</Tag>)}
                        </div>
                      </Card>
                    </List.Item>
                  )} />
                ) : (
                  <Empty description="暂无搜索结果" />
                )}
              </Card>
            </Col>
          </Row>
        </TabPane>

      </Tabs>

      <style>{`
        .ops-card {
          background: rgba(15,23,42,0.6) !important;
          border: 1px solid rgba(148,163,184,0.1) !important;
          border-radius: 8px !important;
        }
        .ops-card .ant-card-head-title {
          color: #E2E8F0 !important;
        }
        .ant-tabs-tab {
          color: #94A3B8 !important;
        }
        .ant-tabs-tab-active .ant-tabs-tab-btn {
          color: #8B5CF6 !important;
        }
      `}</style>
    </Modal>
  )
}
