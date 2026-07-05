import { useState, useEffect, useCallback } from 'react'
import {
    Row, Col, Card, Tag, Spin, Alert, Statistic, Space, Typography,
    Table, Progress, Descriptions, Empty, Button, Badge,
} from 'antd'
import {
    ThunderboltOutlined,
    ReloadOutlined,
    DashboardOutlined,
    ApiOutlined,
    ClockCircleOutlined,
    BarChartOutlined,
    CheckCircleOutlined,
    ExclamationCircleOutlined,
    // [FIX-TS-013] 删除未使用的 ArrowUpOutlined/ArrowDownOutlined
} from '@ant-design/icons'
import { api } from '../services/api'

const { Text, Title } = Typography

interface DeepSeekMetrics {
    status: string
    model: string | null
    brain: string
    configured: boolean
    bridge_injected: boolean
    bridge_stats: Record<string, unknown>
}

interface CycleStats {
    cycle_a_latency_ms: number
    cycle_b_latency_ms: number
    cycle_c_latency_ms: number
    total_calls: number
    success_calls: number
    error_calls: number
    token_input: number
    token_output: number
    total_tokens: number
    classification_count: number
    auto_tag_count: number
    summarize_count: number
    knowledge_extract_count: number
    expand_query_count: number
}

interface MetricCard {
    key: string
    title: string
    value: number | string
    suffix?: string
    prefix?: React.ReactNode
    color?: string
    precision?: number
}

export default function DeepSeekDashboard() {
    const [loading, setLoading] = useState(true)
    const [error, setError] = useState<string | null>(null)
    const [dsMetrics, setDsMetrics] = useState<DeepSeekMetrics | null>(null)
    const [cycleStats, setCycleStats] = useState<CycleStats | null>(null)
    const [autoRefresh, setAutoRefresh] = useState(true)

    const fetchAll = useCallback(async () => {
        setLoading(true)
        setError(null)
        try {
            const [statusRes, cycleRes] = await Promise.allSettled([
                api.get('/api/llm/status'),
                api.get('/api/llm/stats'),
            ])

            if (statusRes.status === 'fulfilled') {
                setDsMetrics(statusRes.value?.data ?? statusRes.value)
            }

            if (cycleRes.status === 'fulfilled') {
                setCycleStats(cycleRes.value?.data ?? cycleRes.value)
            } else {
                // Build partial stats from health/cache data
                const status = statusRes.status === 'fulfilled' ? (statusRes.value?.data ?? statusRes.value) : null
                setCycleStats({
                    cycle_a_latency_ms: status?.bridge_stats?.cycle_a_latency ?? 0,
                    cycle_b_latency_ms: status?.bridge_stats?.cycle_b_latency ?? 0,
                    cycle_c_latency_ms: status?.bridge_stats?.cycle_c_latency ?? 0,
                    total_calls: status?.bridge_stats?.total_calls ?? 0,
                    success_calls: status?.bridge_stats?.success_calls ?? 0,
                    error_calls: status?.bridge_stats?.error_calls ?? 0,
                    token_input: status?.bridge_stats?.token_input ?? 0,
                    token_output: status?.bridge_stats?.token_output ?? 0,
                    total_tokens: status?.bridge_stats?.total_tokens ?? 0,
                    classification_count: status?.bridge_stats?.classification_count ?? 0,
                    auto_tag_count: status?.bridge_stats?.auto_tag_count ?? 0,
                    summarize_count: status?.bridge_stats?.summarize_count ?? 0,
                    knowledge_extract_count: status?.bridge_stats?.knowledge_extract_count ?? 0,
                    expand_query_count: status?.bridge_stats?.expand_query_count ?? 0,
                })
            }
        } catch {
            setError('DeepSeek引擎连接失败（后端 /api/llm/* 不可达）')
        } finally {
            setLoading(false)
        }
    }, [])

    useEffect(() => {
        fetchAll()
        if (!autoRefresh) return
        const interval = setInterval(fetchAll, 10000)
        return () => clearInterval(interval)
    }, [fetchAll, autoRefresh])

    const tokenEfficiency = cycleStats && cycleStats.total_tokens > 0
        ? ((cycleStats.token_output / cycleStats.total_tokens) * 100).toFixed(1)
        : '0'

    const errorRate = cycleStats && cycleStats.total_calls > 0
        ? ((cycleStats.error_calls / cycleStats.total_calls) * 100).toFixed(1)
        : '0'

    const successRate = cycleStats && cycleStats.total_calls > 0
        ? Math.round((cycleStats.success_calls / cycleStats.total_calls) * 100)
        : 100

    const metricCards: MetricCard[] = [
        {
            key: 'total_calls',
            title: '总调用次数',
            value: cycleStats?.total_calls ?? 0,
            prefix: <ApiOutlined />,
            color: '#1890ff',
        },
        {
            key: 'total_tokens',
            title: '总Token消耗',
            value: cycleStats?.total_tokens ?? 0,
            suffix: 'tokens',
            prefix: <BarChartOutlined />,
            color: '#722ed1',
        },
        {
            key: 'cycle_a',
            title: '循环A延迟 (快速反应)',
            value: cycleStats?.cycle_a_latency_ms ?? 0,
            suffix: 'ms',
            prefix: <ThunderboltOutlined />,
            color: '#52c41a',
        },
        {
            key: 'cycle_b',
            title: '循环B延迟 (深度思考)',
            value: cycleStats?.cycle_b_latency_ms ?? 0,
            suffix: 'ms',
            prefix: <ClockCircleOutlined />,
            color: '#fa8c16',
        },
        {
            key: 'cycle_c',
            title: '循环C延迟 (进化反思)',
            value: cycleStats?.cycle_c_latency_ms ?? 0,
            suffix: 'ms',
            prefix: <DashboardOutlined />,
            color: '#eb2f96',
        },
        {
            key: 'success_rate',
            title: '成功率',
            value: successRate,
            suffix: '%',
            prefix: <CheckCircleOutlined />,
            color: '#52c41a',
        },
    ]

    const categoryColumns = [
        {
            title: '分类功能',
            dataIndex: 'label',
            key: 'label',
            render: (text: string) => <Text strong>{text}</Text>,
        },
        {
            title: '调用次数',
            dataIndex: 'count',
            key: 'count',
            render: (v: number) => <Text>{v.toLocaleString()}</Text>,
        },
        {
            title: '占比',
            dataIndex: 'pct',
            key: 'pct',
            render: (v: number) => (
                <Progress
                    percent={v}
                    size="small"
                    strokeColor={{
                        '0%': '#1890ff',
                        '100%': '#52c41a',
                    }}
                />
            ),
        },
    ]

    const categoryData = cycleStats ? [
        { label: '内容分类 (classify)', count: cycleStats.classification_count, pct: cycleStats.total_calls > 0 ? Math.round((cycleStats.classification_count / cycleStats.total_calls) * 100) : 0 },
        { label: '自动标签 (auto_tag)', count: cycleStats.auto_tag_count, pct: cycleStats.total_calls > 0 ? Math.round((cycleStats.auto_tag_count / cycleStats.total_calls) * 100) : 0 },
        { label: '内容摘要 (summarize)', count: cycleStats.summarize_count, pct: cycleStats.total_calls > 0 ? Math.round((cycleStats.summarize_count / cycleStats.total_calls) * 100) : 0 },
        { label: '知识提取 (extract_knowledge)', count: cycleStats.knowledge_extract_count, pct: cycleStats.total_calls > 0 ? Math.round((cycleStats.knowledge_extract_count / cycleStats.total_calls) * 100) : 0 },
        { label: '查询扩展 (expand_query)', count: cycleStats.expand_query_count, pct: cycleStats.total_calls > 0 ? Math.round((cycleStats.expand_query_count / cycleStats.total_calls) * 100) : 0 },
    ] : []

    return (
        <div style={{ padding: '0 0 24px' }}>
            {/* Header */}
            <Card style={{ marginBottom: 16 }}>
                <Row align="middle" justify="space-between">
                    <Col>
                        <Space>
                            <ThunderboltOutlined style={{ fontSize: 24, color: '#eb2f96' }} />
                            <span>
                                <Title level={4} style={{ margin: 0, display: 'inline' }}>
                                    DeepSeek LLM 驾驶舱
                                </Title>
                                <Tag color={dsMetrics?.configured ? 'success' : 'warning'} style={{ marginLeft: 12 }}>
                                    {dsMetrics?.configured ? '已配置' : '待配置'}
                                </Tag>
                                <Tag color="blue">天机v9.1</Tag>
                            </span>
                        </Space>
                    </Col>
                    <Col>
                        <Space>
                            <Text type="secondary">
                                模型: {dsMetrics?.model || '未知'} ·
                                大脑: {dsMetrics?.brain || 'N/A'} ·
                                桥接: {dsMetrics?.bridge_injected ? '已注入' : '未注入'}
                            </Text>
                            <Button
                                icon={<ReloadOutlined />}
                                onClick={fetchAll}
                                loading={loading}
                                size="small"
                            >
                                刷新
                            </Button>
                            <Button
                                size="small"
                                type={autoRefresh ? 'primary' : 'default'}
                                onClick={() => setAutoRefresh(!autoRefresh)}
                            >
                                {autoRefresh ? '自动刷新中' : '已暂停'}
                            </Button>
                        </Space>
                    </Col>
                </Row>
            </Card>

            {error && (
                <Alert
                    message="DeepSeek引擎状态"
                    description={error}
                    type="warning"
                    showIcon
                    style={{ marginBottom: 16 }}
                />
            )}

            <Spin spinning={loading} tip="加载DeepSeek指标...">
                {/* Three-Cycle Architecture */}
                <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
                    <Col span={24}>
                        <Card
                            size="small"
                            title={
                                <Space>
                                    <DashboardOutlined style={{ color: '#722ed1' }} />
                                    <span>三循环并行架构 (DeepSeek驾驶者 v2.0)</span>
                                </Space>
                            }
                        >
                            <Row gutter={[16, 16]}>
                                <Col xs={24} md={8}>
                                    <Card
                                        size="small"
                                        style={{ borderLeft: '4px solid #52c41a', background: '#f6ffed' }}
                                        title={<Text strong style={{ color: '#52c41a' }}>🔄 循环A: 快速反应环</Text>}
                                    >
                                        <Descriptions column={1} size="small">
                                            <Descriptions.Item label="特点">
                                                <Tag color="green">实时 (&lt;100ms)</Tag>
                                            </Descriptions.Item>
                                            <Descriptions.Item label="延迟">
                                                <Text strong style={{ color: '#52c41a', fontSize: 18 }}>
                                                    {(cycleStats?.cycle_a_latency_ms ?? 0) > 0 ? `${cycleStats!.cycle_a_latency_ms} ms` : '未追踪'}
                                                </Text>
                                            </Descriptions.Item>
                                            <Descriptions.Item label="流程">
                                                <Text type="secondary">事件 → quick_decide → act</Text>
                                            </Descriptions.Item>
                                        </Descriptions>
                                    </Card>
                                </Col>
                                <Col xs={24} md={8}>
                                    <Card
                                        size="small"
                                        style={{ borderLeft: '4px solid #1890ff', background: '#e6f7ff' }}
                                        title={<Text strong style={{ color: '#1890ff' }}>🧠 循环B: 深度思考环</Text>}
                                    >
                                        <Descriptions column={1} size="small">
                                            <Descriptions.Item label="特点">
                                                <Tag color="blue">深度分析 (5min)</Tag>
                                            </Descriptions.Item>
                                            <Descriptions.Item label="延迟">
                                                <Text strong style={{ color: '#1890ff', fontSize: 18 }}>
                                                    {(cycleStats?.cycle_b_latency_ms ?? 0) > 0 ? `${cycleStats!.cycle_b_latency_ms} ms` : '未追踪'}
                                                </Text>
                                            </Descriptions.Item>
                                            <Descriptions.Item label="流程">
                                                <Text type="secondary">SENSE → EVALUATE → DECIDE → ACT → OBSERVE</Text>
                                            </Descriptions.Item>
                                        </Descriptions>
                                    </Card>
                                </Col>
                                <Col xs={24} md={8}>
                                    <Card
                                        size="small"
                                        style={{ borderLeft: '4px solid #722ed1', background: '#f9f0ff' }}
                                        title={<Text strong style={{ color: '#722ed1' }}>⚡ 循环C: 进化反思环</Text>}
                                    >
                                        <Descriptions column={1} size="small">
                                            <Descriptions.Item label="特点">
                                                <Tag color="purple">策略进化 (1天)</Tag>
                                            </Descriptions.Item>
                                            <Descriptions.Item label="延迟">
                                                <Text strong style={{ color: '#722ed1', fontSize: 18 }}>
                                                    {(cycleStats?.cycle_c_latency_ms ?? 0) > 0 
                                                        ? `${cycleStats!.cycle_c_latency_ms} ms` 
                                                        : '未追踪'}
                                                </Text>
                                            </Descriptions.Item>
                                            <Descriptions.Item label="流程">
                                                <Text type="secondary">汇总因果对 → LEARN → EVOLVE</Text>
                                            </Descriptions.Item>
                                            <Descriptions.Item label="来源">
                                                <Text type="secondary" style={{ fontSize: 11 }}>
                                                    {cycleStats && cycleStats.cycle_c_latency_ms > 0
                                                        ? 'Driver真实计时'
                                                        : '等待首次执行'}
                                                </Text>
                                            </Descriptions.Item>
                                        </Descriptions>
                                    </Card>
                                </Col>
                            </Row>
                        </Card>
                    </Col>
                </Row>

                {/* Key Metrics */}
                <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
                    {metricCards.map((card) => (
                        <Col xs={12} sm={8} lg={4} key={card.key}>
                            <Card size="small" hoverable>
                                <Statistic
                                    title={card.title}
                                    value={typeof card.value === 'number' ? card.value : 0}
                                    suffix={card.suffix}
                                    prefix={card.prefix}
                                    precision={card.precision}
                                    valueStyle={{ color: card.color, fontSize: 24 }}
                                />
                            </Card>
                        </Col>
                    ))}
                </Row>

                {/* Token Usage & Error Rate */}
                <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
                    <Col xs={24} md={12}>
                        <Card
                            size="small"
                            title={<Space><BarChartOutlined style={{ color: '#722ed1' }} /><span>Token消耗</span></Space>}
                        >
                            <Descriptions column={2} size="small" bordered>
                                <Descriptions.Item label="输入Token">
                                    <Text strong style={{ color: '#1890ff', fontSize: 16 }}>
                                        {cycleStats?.token_input?.toLocaleString() ?? 0}
                                    </Text>
                                </Descriptions.Item>
                                <Descriptions.Item label="输出Token">
                                    <Text strong style={{ color: '#52c41a', fontSize: 16 }}>
                                        {cycleStats?.token_output?.toLocaleString() ?? 0}
                                    </Text>
                                </Descriptions.Item>
                                <Descriptions.Item label="总计Token" span={2}>
                                    <Progress
                                        percent={parseFloat(tokenEfficiency)}
                                        format={() => `${cycleStats?.total_tokens?.toLocaleString() ?? 0} tokens (${tokenEfficiency}% 输出效率)`}
                                        strokeColor="#722ed1"
                                    />
                                </Descriptions.Item>
                            </Descriptions>
                        </Card>
                    </Col>
                    <Col xs={24} md={12}>
                        <Card
                            size="small"
                            title={<Space><ExclamationCircleOutlined style={{ color: '#ff4d4f' }} /><span>可靠性指标</span></Space>}
                        >
                            <Descriptions column={2} size="small" bordered>
                                <Descriptions.Item label="总调用">
                                    <Text strong>{cycleStats?.total_calls?.toLocaleString() ?? 0}</Text>
                                </Descriptions.Item>
                                <Descriptions.Item label="成功">
                                    <Text strong style={{ color: '#52c41a' }}>{cycleStats?.success_calls?.toLocaleString() ?? 0}</Text>
                                </Descriptions.Item>
                                <Descriptions.Item label="错误">
                                    <Text strong style={{ color: '#ff4d4f' }}>{cycleStats?.error_calls?.toLocaleString() ?? 0}</Text>
                                </Descriptions.Item>
                                <Descriptions.Item label="错误率">
                                    <Badge
                                        status={parseFloat(errorRate) < 5 ? 'success' : parseFloat(errorRate) < 15 ? 'warning' : 'error'}
                                        text={`${errorRate}%`}
                                    />
                                </Descriptions.Item>
                                <Descriptions.Item label="成功率" span={2}>
                                    <Progress
                                        percent={successRate}
                                        strokeColor={successRate >= 95 ? '#52c41a' : successRate >= 80 ? '#faad14' : '#ff4d4f'}
                                        format={() => `${successRate}%`}
                                    />
                                </Descriptions.Item>
                            </Descriptions>
                        </Card>
                    </Col>
                </Row>

                {/* Classification Statistics */}
                <Row gutter={[16, 16]}>
                    <Col span={24}>
                        <Card
                            size="small"
                            title={<Space><ApiOutlined style={{ color: '#13c2c2' }} /><span>分类功能统计 (5维度)</span></Space>}
                        >
                            {categoryData.length > 0 ? (
                                <Table
                                    dataSource={categoryData}
                                    columns={categoryColumns}
                                    size="small"
                                    pagination={false}
                                    rowKey="label"
                                />
                            ) : (
                                <Empty
                                    description={loading ? '加载中...' : '暂无分类统计数据（后端 /api/llm/stats 不可用）'}
                                    image={Empty.PRESENTED_IMAGE_SIMPLE}
                                />
                            )}
                        </Card>
                    </Col>
                </Row>
            </Spin>
        </div>
    )
}
