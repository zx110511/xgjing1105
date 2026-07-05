import { useMemo } from 'react'
import { Card, Typography, Space, Tag, Empty, Row, Col, Statistic, Tooltip } from 'antd'
import type { DAGPipelineData } from '../types/orchestrator'
import { NODE_STATUS_COLORS } from '../types/orchestrator'

const { Text } = Typography

interface ExecutionTimelineProps {
    dagData: DAGPipelineData | null
    maxBars?: number
}

/** 甘特图时间线 — 展示DAG流水线中各节点的执行时间线 */
function ExecutionTimeline({ dagData, maxBars = 20 }: ExecutionTimelineProps) {
    const timelineData = useMemo(() => {
        if (!dagData || !dagData?.nodes?.length) return null

        const allDurations = dagData.nodes
            .filter((n) => n.data.duration_s > 0)
            .map((n) => n.data.duration_s)
        const maxDuration = Math.max(...allDurations, 1)

        const sorted = [...dagData.nodes]
            .filter((n) => n.data.status !== 'pending')
            .sort((a, b) => {
                const order = ['failed', 'running', 'completed', 'skipped', 'cancelled', 'ready']
                return order.indexOf(a.data.status) - order.indexOf(b.data.status)
            })
            .slice(0, maxBars)

        const levels = dagData.levels || []
        const nodeLevelMap: Record<string, number> = {}
        levels.forEach((levelNodes, idx) => {
            levelNodes.forEach((nid) => {
                nodeLevelMap[nid] = idx
            })
        })

        return { nodes: sorted, maxDuration, nodeLevelMap }
    }, [dagData, maxBars])

    if (!dagData) {
        return <Empty description="暂无流水线数据" image={Empty.PRESENTED_IMAGE_SIMPLE} />
    }

    if (!timelineData) {
        return <Empty description="所有节点处于等待状态" image={Empty.PRESENTED_IMAGE_SIMPLE} />
    }

    const { nodes, maxDuration, nodeLevelMap } = timelineData

    return (
        <div style={{ overflowX: 'auto' }}>
            {nodes.map((node, idx) => {
                const pct = Math.max(2, (node.data.duration_s / maxDuration) * 100)
                const statusColor = NODE_STATUS_COLORS[node.data.status] || '#d9d9d9'
                const level = nodeLevelMap[node.id] ?? idx

                return (
                    <div
                        key={node.id}
                        style={{
                            display: 'flex',
                            alignItems: 'center',
                            marginBottom: 8,
                            gap: 12,
                        }}
                    >
                        {/* 标签区域 */}
                        <div style={{ minWidth: 200, maxWidth: 200 }}>
                            <Tooltip title={`Layer ${level} · ${node.data.agent_name}`}>
                                <Space size={4}>
                                    <span>{node.data.agent_emoji}</span>
                                    <Text
                                        ellipsis={{ tooltip: node.data.label }}
                                        style={{ fontSize: 12, maxWidth: 140 }}
                                    >
                                        {node.data.label}
                                    </Text>
                                </Space>
                            </Tooltip>
                        </div>

                        {/* 甘特条 */}
                        <div style={{ flex: 1, position: 'relative', height: 22 }}>
                            <div
                                style={{
                                    width: `${pct}%`,
                                    height: '100%',
                                    backgroundColor: statusColor,
                                    borderRadius: 4,
                                    minWidth: 4,
                                    display: 'flex',
                                    alignItems: 'center',
                                    paddingLeft: 8,
                                    transition: 'width 0.5s ease',
                                }}
                            >
                                {node.data.duration_s > 0 && (
                                    <Text
                                        style={{
                                            color: '#fff',
                                            fontSize: 11,
                                            fontWeight: 500,
                                            textShadow: '0 1px 2px rgba(0,0,0,0.3)',
                                        }}
                                    >
                                        {node.data.duration_s.toFixed(1)}s
                                    </Text>
                                )}
                            </div>
                        </div>

                        {/* 标签 */}
                        <Tag
                            color={
                                node.data.status === 'completed'
                                    ? 'green'
                                    : node.data.status === 'failed'
                                        ? 'red'
                                        : node.data.status === 'running'
                                            ? 'blue'
                                            : 'default'
                            }
                            style={{ minWidth: 56, textAlign: 'center' }}
                        >
                            {node.data.status}
                        </Tag>
                    </div>
                )
            })}
            {dagData.nodes.length > maxBars && (
                <Text type="secondary" style={{ fontSize: 12 }}>
                    显示 {maxBars}/{dagData.nodes.length} 个节点
                </Text>
            )}
        </div>
    )
}

/** 天机v9.1调度统计面板 */
interface StatsPanelProps {
    dagStats?: {
        pipelines_executed: number
        nodes_executed: number
        nodes_failed: number
        total_duration_s: number
        active_pipelines: number
    } | null
    checkpointStats?: {
        total_workflows: number
        completed: number
        failed: number
        running: number
    } | null
    plannerStats?: {
        plans_created: number
        llm_plans: number
        rule_plans: number
        avg_confidence: number
    } | null
    agentSchedulerStats?: Record<string, number> | null
}

function StatsPanel({
    dagStats,
    checkpointStats,
    plannerStats,
    agentSchedulerStats,
}: StatsPanelProps) {
    const successRate = dagStats
        ? dagStats.nodes_executed > 0
            ? (
                ((dagStats.nodes_executed - dagStats.nodes_failed) / dagStats.nodes_executed) *
                100
            ).toFixed(1)
            : '100'
        : '0'

    return (
        <div>
            <Row gutter={[16, 16]}>
                {/* DAG调度统计 */}
                <Col span={24}>
                    <Card size="small" title="🏗️ DAG调度引擎" style={{ marginBottom: 16 }}>
                        <Row gutter={16}>
                            <Col span={6}>
                                <Statistic
                                    title="流水线执行数"
                                    value={dagStats?.pipelines_executed || 0}
                                    suffix="次"
                                />
                            </Col>
                            <Col span={6}>
                                <Statistic title="节点执行数" value={dagStats?.nodes_executed || 0} suffix="个" />
                            </Col>
                            <Col span={6}>
                                <Statistic
                                    title="成功率"
                                    value={successRate}
                                    suffix="%"
                                    valueStyle={{
                                        color: parseFloat(successRate) >= 95 ? '#52c41a' : '#faad14',
                                    }}
                                />
                            </Col>
                            <Col span={6}>
                                <Statistic title="活跃流水线" value={dagStats?.active_pipelines || 0} suffix="个" />
                            </Col>
                        </Row>
                    </Card>
                </Col>

                {/* 持久化执行统计 */}
                <Col span={12}>
                    <Card size="small" title="💾 持久化执行引擎">
                        <Row gutter={16}>
                            <Col span={12}>
                                <Statistic title="总工作流" value={checkpointStats?.total_workflows || 0} />
                            </Col>
                            <Col span={12}>
                                <Statistic
                                    title="完成率"
                                    value={
                                        checkpointStats && checkpointStats.total_workflows > 0
                                            ? (
                                                (checkpointStats.completed / checkpointStats.total_workflows) *
                                                100
                                            ).toFixed(1)
                                            : '0'
                                    }
                                    suffix="%"
                                />
                            </Col>
                            <Col span={12}>
                                <Statistic
                                    title="运行中"
                                    value={checkpointStats?.running || 0}
                                    valueStyle={{ color: '#1890ff' }}
                                />
                            </Col>
                            <Col span={12}>
                                <Statistic
                                    title="失败数"
                                    value={checkpointStats?.failed || 0}
                                    valueStyle={{
                                        color: (checkpointStats?.failed || 0) > 0 ? '#ff4d4f' : undefined,
                                    }}
                                />
                            </Col>
                        </Row>
                    </Card>
                </Col>

                {/* LLM规划器统计 */}
                <Col span={12}>
                    <Card size="small" title="🧠 LLM任务规划器">
                        <Row gutter={16}>
                            <Col span={12}>
                                <Statistic title="总规划数" value={plannerStats?.plans_created || 0} />
                            </Col>
                            <Col span={12}>
                                <Statistic
                                    title="LLM规划占比"
                                    value={
                                        plannerStats && plannerStats.plans_created > 0
                                            ? (
                                                ((plannerStats.llm_plans || 0) / plannerStats.plans_created) *
                                                100
                                            ).toFixed(1)
                                            : '0'
                                    }
                                    suffix="%"
                                    valueStyle={{ color: '#1890ff' }}
                                />
                            </Col>
                            <Col span={12}>
                                <Statistic
                                    title="平均置信度"
                                    value={plannerStats?.avg_confidence?.toFixed(2) || '0'}
                                />
                            </Col>
                            <Col span={12}>
                                <Statistic title="规则降级数" value={plannerStats?.rule_plans || 0} />
                            </Col>
                        </Row>
                    </Card>
                </Col>

                {/* Agent调度统计 */}
                {agentSchedulerStats && (
                    <Col span={24}>
                        <Card size="small" title="🤖 Agent调度器 v3.0">
                            <Row gutter={16}>
                                <Col span={6}>
                                    <Statistic
                                        title="流水线创建"
                                        value={agentSchedulerStats.pipelines_created || 0}
                                    />
                                </Col>
                                <Col span={6}>
                                    <Statistic title="并行调度" value={agentSchedulerStats.dispatches_run || 0} />
                                </Col>
                                <Col span={6}>
                                    <Statistic title="工具追踪" value={agentSchedulerStats.tools_tracked || 0} />
                                </Col>
                                <Col span={6}>
                                    <Statistic
                                        title="DAG流水线"
                                        value={agentSchedulerStats.dag_pipelines_executed || 0}
                                        valueStyle={{ color: '#722ed1' }}
                                    />
                                </Col>
                            </Row>
                        </Card>
                    </Col>
                )}
            </Row>
        </div>
    )
}

export { ExecutionTimeline, StatsPanel }
export default ExecutionTimeline
