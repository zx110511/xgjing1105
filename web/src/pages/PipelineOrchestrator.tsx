import { useState, useEffect, useCallback } from 'react'
import {
  Card,
  Tabs,
  Input,
  Button,
  Space,
  Typography,
  Tag,
  message,
  Spin,
  Alert,
  Descriptions,
  List,
  Select,
} from 'antd'
import {
  SendOutlined,
  ReloadOutlined,
  PlayCircleOutlined,
  NodeIndexOutlined,
  ApartmentOutlined,
  BarChartOutlined,
  HistoryOutlined,
  ThunderboltOutlined,
} from '@ant-design/icons'
import PipelineCanvas from '../components/PipelineCanvas'
import AgentTopology from '../components/AgentTopology'
import { ExecutionTimeline, StatsPanel } from '../components/ExecutionTimeline'
import { orchestratorService } from '../services/orchestrator-service'
import type {
  DAGPipelineData,
  PlanResponse,
  OrchestratorStats,
  WorkflowData,
} from '../types/orchestrator'

const { Text, Title } = Typography
const { TextArea } = Input

function PipelineOrchestrator() {
  const [taskInput, setTaskInput] = useState('')
  const [planning, setPlanning] = useState(false)
  const [executing, setExecuting] = useState(false)
  const [currentPlan, setCurrentPlan] = useState<PlanResponse | null>(null)
  const [currentDAG, setCurrentDAG] = useState<DAGPipelineData | null>(null)
  const [activePipelineId, setActivePipelineId] = useState<string | null>(null)
  const [stats, setStats] = useState<OrchestratorStats | null>(null)
  const [workflows, setWorkflows] = useState<WorkflowData[]>([])
  const [v10Info, setV10Info] = useState<Record<string, any> | null>(null)
  const [loading, setLoading] = useState(true)

  // 加载初始数据
  const loadData = useCallback(async () => {
    try {
      const [rootInfo, orchStats, wfList] = await Promise.all([
        orchestratorService.getRoot().catch(() => null),
        orchestratorService.getStats().catch(() => null),
        orchestratorService.listWorkflows(undefined, 20).catch(() => ({ workflows: [], count: 0 })),
      ])
      setV10Info(rootInfo)
      setStats(orchStats)
      setWorkflows(wfList.workflows || [])
    } catch {
      // 天机未启动时静默
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    loadData()
    const timer = setInterval(loadData, 10000)
    return () => clearInterval(timer)
  }, [loadData])

  // LLM任务规划
  const handlePlan = async () => {
    if (!taskInput.trim()) {
      message.warning('请输入任务描述')
      return
    }
    setPlanning(true)
    try {
      const result = await orchestratorService.plan(taskInput)
      setCurrentPlan(result)
      setCurrentDAG(result.dag)
      message.success(
        `规划完成: ${result.plan.complexity} 复杂度 · ${result.plan.strategy} 策略 · ${result.plan.sub_tasks.length} 个子任务`
      )
    } catch (e: any) {
      message.error(`规划失败: ${e?.message || '未知错误'}`)
    } finally {
      setPlanning(false)
    }
  }

  // 执行DAG
  const handleExecute = async () => {
    if (!currentDAG) {
      message.warning('请先规划任务或加载DAG')
      return
    }
    setExecuting(true)
    try {
      const result = await orchestratorService.executeDAG({
        dag_json: currentDAG,
        parallel: true,
      })
      setActivePipelineId(result.pipeline_id)
      setCurrentDAG(result.dag)
      message.success(
        `执行完成: ${result.result.nodes_completed} 节点成功, ${result.result.nodes_failed} 失败`
      )
      loadData()
    } catch (e: any) {
      message.error(`执行失败: ${e?.message || '未知错误'}`)
    } finally {
      setExecuting(false)
    }
  }

  // 快速模板
  const quickTemplates = [
    {
      label: '🔒 安全审计',
      task: '对天机系统进行全面安全审计，包括漏洞扫描、合规检查和性能基线分析',
    },
    { label: '📊 数据分析', task: '分析天机记忆系统的容量趋势、质量分布和检索性能，生成综合报告' },
    { label: '🏗️ 架构审查', task: '审查天机v9.1核心架构，评估模块耦合度、扩展性和技术债务' },
  ]

  if (loading) {
    return (
      <div style={{ textAlign: 'center', padding: 100 }}>
        <Spin size="large" tip="连接天机调度引擎..." />
      </div>
    )
  }

  return (
    <div>
      {/* 页面标题 */}
      <div style={{ marginBottom: 24 }}>
        <Title level={3} style={{ margin: 0 }}>
          <ThunderboltOutlined style={{ marginRight: 12, color: '#722ed1' }} />
          天枢级调度引擎
          {v10Info && (
            <Tag color="purple" style={{ marginLeft: 12 }}>
              {v10Info.version}
            </Tag>
          )}
        </Title>
        <Text type="secondary">
          DAG拓扑调度 · 持久化执行 · LLM任务规划 · 全景可视化 · Agent拓扑
        </Text>
      </div>

      {/* 未连接状态 */}
      {!v10Info && (
        <Alert
          type="warning"
          message="天机v9.1调度引擎未连接"
          description="请确保天机服务已启动 (python server/main.py)，然后刷新页面。"
          showIcon
          style={{ marginBottom: 16 }}
          action={
            <Button size="small" onClick={loadData} icon={<ReloadOutlined />}>
              重试
            </Button>
          }
        />
      )}

      {/* 任务规划输入 */}
      <Card style={{ marginBottom: 16 }}>
        <Text strong style={{ display: 'block', marginBottom: 8 }}>
          🧠 LLM任务规划 — 输入自然语言任务，自动拆解为DAG流水线
        </Text>
        <Space direction="vertical" style={{ width: '100%' }}>
          <TextArea
            value={taskInput}
            onChange={(e) => setTaskInput(e.target.value)}
            placeholder="例如: 对天机系统进行全面安全审计，包括漏洞扫描、合规检查和性能基线分析..."
            rows={3}
            maxLength={500}
            showCount
          />
          <Space>
            <Button type="primary" icon={<SendOutlined />} onClick={handlePlan} loading={planning}>
              规划任务
            </Button>
            <Button
              icon={<PlayCircleOutlined />}
              onClick={handleExecute}
              loading={executing}
              disabled={!currentDAG}
              type={currentDAG ? 'primary' : 'default'}
              danger
            >
              执行DAG
            </Button>
            <Select
              placeholder="快速模板"
              style={{ width: 160 }}
              onChange={(val) => setTaskInput(val)}
              options={quickTemplates.map((t) => ({
                value: t.task,
                label: t.label,
              }))}
            />
          </Space>
        </Space>
      </Card>

      {/* 规划结果概览 */}
      {currentPlan && (
        <Card size="small" style={{ marginBottom: 16 }}>
          <Descriptions column={4} size="small">
            <Descriptions.Item label="复杂度">
              <Tag color={currentPlan.plan.complexity === 'very_high' ? 'red' : 'blue'}>
                {currentPlan.plan.complexity}
              </Tag>
            </Descriptions.Item>
            <Descriptions.Item label="策略">
              <Tag>{currentPlan.plan.strategy}</Tag>
            </Descriptions.Item>
            <Descriptions.Item label="置信度">
              {(currentPlan.plan.confidence * 100).toFixed(0)}%
            </Descriptions.Item>
            <Descriptions.Item label="子任务">
              {currentPlan.plan.sub_tasks.length} 个
            </Descriptions.Item>
            <Descriptions.Item label="推理" span={4}>
              <Text type="secondary" style={{ fontSize: 12 }}>
                {currentPlan.plan.reasoning}
              </Text>
            </Descriptions.Item>
          </Descriptions>

          {/* 子任务列表 */}
          <List
            size="small"
            header={<Text strong>子任务分解</Text>}
            dataSource={currentPlan.plan.sub_tasks}
            renderItem={(st) => (
              <List.Item>
                <Space>
                  <Tag>{st.index}</Tag>
                  <span>{st.agent_emoji}</span>
                  <Text>@{st.agent_name}</Text>
                  <Text type="secondary">— {st.goal}</Text>
                  {st.can_parallel && <Tag color="green">可并行</Tag>}
                  {st.depends_on?.length > 0 && <Tag>依赖: [{st.depends_on.join(', ')}]</Tag>}
                </Space>
              </List.Item>
            )}
          />
        </Card>
      )}

      {/* 主Tabs */}
      <Tabs
        defaultActiveKey="dag"
        items={[
          {
            key: 'dag',
            label: (
              <span>
                <NodeIndexOutlined /> DAG流水线
              </span>
            ),
            children: (
              <Card>
                <PipelineCanvas
                  pipelineId={activePipelineId}
                  dagData={currentDAG}
                  onNodeClick={(node) => {
                    message.info(
                      `${node.data.agent_emoji} @${node.data.agent_name}: ${node.data.label}`
                    )
                  }}
                />
              </Card>
            ),
          },
          {
            key: 'topology',
            label: (
              <span>
                <ApartmentOutlined /> Agent拓扑
              </span>
            ),
            children: (
              <Card>
                <AgentTopology />
              </Card>
            ),
          },
          {
            key: 'timeline',
            label: (
              <span>
                <HistoryOutlined /> 执行时间线
              </span>
            ),
            children: (
              <Card title="⏱️ 节点执行甘特图">
                <ExecutionTimeline dagData={currentDAG} />
              </Card>
            ),
          },
          {
            key: 'stats',
            label: (
              <span>
                <BarChartOutlined /> 统计面板
              </span>
            ),
            children: (
              <StatsPanel
                dagStats={stats?.dag_scheduler || null}
                checkpointStats={stats?.checkpoint || null}
                plannerStats={stats?.planner || null}
              />
            ),
          },
          {
            key: 'workflows',
            label: (
              <span>
                <HistoryOutlined /> 工作流 ({workflows.length})
              </span>
            ),
            children: (
              <Card title="💾 持久化工作流历史">
                {workflows.length === 0 ? (
                  <Alert
                    type="info"
                    message="暂无工作流记录"
                    description="执行DAG流水线后将自动创建工作流记录"
                  />
                ) : (
                  <List
                    dataSource={workflows}
                    renderItem={(wf) => (
                      <List.Item
                        actions={[
                          <Button
                            key="resume"
                            size="small"
                            onClick={async () => {
                              try {
                                await orchestratorService.resumeWorkflow(wf.workflow_id)
                                message.success('工作流已恢复')
                                loadData()
                              } catch (e: any) {
                                message.error(`恢复失败: ${e?.message}`)
                              }
                            }}
                          >
                            恢复
                          </Button>,
                        ]}
                      >
                        <List.Item.Meta
                          title={
                            <Space>
                              {wf.workflow_name}
                              <Tag
                                color={
                                  wf.status === 'completed'
                                    ? 'green'
                                    : wf.status === 'failed'
                                      ? 'red'
                                      : wf.status === 'running'
                                        ? 'blue'
                                        : 'default'
                                }
                              >
                                {wf.status}
                              </Tag>
                            </Space>
                          }
                          description={
                            <Space>
                              <Text type="secondary">{wf.workflow_id}</Text>
                              <Text type="secondary">{wf.steps?.length ?? 0} 步骤</Text>
                              <Text type="secondary">v{wf.checkpoint_version}</Text>
                            </Space>
                          }
                        />
                      </List.Item>
                    )}
                  />
                )}
              </Card>
            ),
          },
        ]}
      />
    </div>
  )
}

export default PipelineOrchestrator
