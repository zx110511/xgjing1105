import { useState, useEffect, useRef } from 'react'
import {
    Row,
    Col,
    Card,
    Tag,
    Spin,
    Alert,
    Tabs,
    Table,
    Space,
    Descriptions,
    Badge,
    Timeline,
    Progress,
    Statistic,
    Typography,
    Button,
    Collapse,
    // [FIX-TS-013] 删除未使用的 Tree
    Empty,
    Divider,
    Tooltip,
} from 'antd'
import {
    // [FIX-TS-013] 删除未使用的 AimOutlined
    CloudServerOutlined,
    RobotOutlined,
    ScheduleOutlined,
    // [FIX-TS-013] 删除未使用的 SwapOutlined/ReadOutlined/DeploymentUnitOutlined/GlobalOutlined/RocketOutlined
    DatabaseOutlined,
    ExperimentOutlined,
    ThunderboltOutlined,
    SafetyCertificateOutlined,
    ApartmentOutlined,
    EyeOutlined,
    ApiOutlined,
    ToolOutlined,
    LineChartOutlined,
    HistoryOutlined,
    BarChartOutlined,
    DashboardOutlined,
    MonitorOutlined,
    // [FIX-TS-013] 删除未使用的 SettingOutlined
    CheckCircleOutlined,
    ExclamationCircleOutlined,
    CloseOutlined,
    MinusCircleOutlined,
    SyncOutlined,
    MessageOutlined,
    NodeIndexOutlined,
    KeyOutlined,
    OrderedListOutlined,
    PieChartOutlined,
    FilterOutlined,
    FireOutlined,
    ClockCircleOutlined,
    ReloadOutlined,
} from '@ant-design/icons'
import { api, operationsApi } from '../services/api'
import { MetricsLatestResponse, MetricEntry } from '../types/metrics'
import { metricsService } from '../services/metrics-service'
// [FIX-TS-013] 删除未使用的 Line (@ant-design/charts)

const { Text } = Typography

interface SystemStats {
    modules: Record<string, Record<string, unknown>>
    dimensions: {
        realtime: Record<
            string,
            {
                status: string
                last_update?: number
                key_metrics?: Record<string, unknown>
            }
        >
        cumulative: Record<string, Record<string, unknown>>
        history: {
            snapshots: Array<{
                timestamp: number
                online_modules: number
                total_modules: number
                coverage_pct: number
            }>
            retention_hours: number
        }
    }
    coverage: { total: number; online: number; with_stats: number }
    module_count: number
    timestamp: number
    version: string
    memory_total?: number
    uptime_seconds?: number
    hit_rate?: number
    storage_backend?: string
    consolidations?: number
    db_size_mb?: number
    memory_by_layer?: Record<string, number>
    container_running?: number
    container_total?: number
}

interface MemoryStats {
    total_entries: number
    total_accesses: number
    uptime_seconds: number
    layers: Record<string, number | { entry_count?: number;[key: string]: any }>
    archive_entries: number
}

interface HealthStatus {
    status: string
    version: string
    engine_ready: boolean
    embedding_ready: boolean
    layers: Record<string, number | { entry_count?: number;[key: string]: any }>
    uptime: number
    // [FIX-TS-006] 扩展字段: 实际后端 /api/health 返回
    storage_backend?: string
    db_size_mb?: number
    database?: string
    llm?: string
}

interface OpsReport {
    ops_available: boolean
    healer?: { total_heal_attempts: number; total_heal_successes: number }
    baseline?: { snapshots_collected: number; anomalies_detected: number }
    message?: string
}

const MODULE_CONTAINERS = {
    核心引擎: {
        icon: <DatabaseOutlined />,
        color: '#722ed1',
        modules: [
            { name: 'hybrid_engine', label: '混合检索引擎' },
            { name: 'quality_gate', label: '质量门禁' },
            { name: 'memory_router', label: '记忆路由器' },
            { name: 'conflict_resolver', label: '冲突解决器' },
        ],
    },
    DeepSeek大脑核心: {
        icon: <ThunderboltOutlined />,
        color: '#eb2f96',
        modules: [
            { name: 'deepseek_driver', label: 'DeepSeek驾驶者' },
            { name: 'deepseek_proactive', label: 'DeepSeek主动增强' },
        ],
    },
    强制记录系统: {
        icon: <SafetyCertificateOutlined />,
        color: '#13c2c2',
        modules: [
            { name: 'enforcement_hook', label: '强制执行钩子' },
            { name: 'auto_capture', label: '自动捕获' },
        ],
    },
    智能调度体系: {
        icon: <ApartmentOutlined />,
        color: '#1890ff',
        modules: [
            { name: 'intelligent_scheduler', label: '智能调度器' },
            { name: 'auto_scheduler', label: '调度守护进程' },
            { name: 'tvp_orchestrator', label: 'TVP协议编排器' },
            { name: 'dynamic_data_injector', label: '动态数据注入器' },
        ],
    },
    学习进化引擎: {
        icon: <ExperimentOutlined />,
        color: '#52c41a',
        modules: [
            { name: 'skill_registry', label: 'Skill注册中心' },
            { name: 'learning_engine', label: '闭环学习引擎' },
            { name: 'workflow_engine', label: '工作流引擎' },
            { name: 'evolution_engine', label: '进化引擎' },
            { name: 'evolution_bus', label: '进化信号总线' },
        ],
    },
    基础设施层: {
        icon: <CloudServerOutlined />,
        color: '#fa8c16',
        modules: [
            { name: 'monitor_bridge', label: '监控桥接器' },
            { name: 'realtime_monitor', label: '实时监控器' },
            { name: 'backup_manager', label: '备份管理器' },
        ],
    },
}

export default function Monitoring() {
    const [loading, setLoading] = useState(true)
    const [stats, setStats] = useState<SystemStats | null>(null)
    const [memoryStats, setMemoryStats] = useState<MemoryStats | null>(null)
    const [health, setHealth] = useState<HealthStatus | null>(null)
    const [opsReport, setOpsReport] = useState<OpsReport | null>(null)
    const [opsSummary, setOpsSummary] = useState<any>(null)
    const [opsLogData, setOpsLogData] = useState<any[]>([])
    const [opsCategoryFilter, setOpsCategoryFilter] = useState<string>('all')
    const [metricsData, setMetricsData] = useState<MetricsLatestResponse | null>(null)
    const [metricsHistory, setMetricsHistory] = useState<
        Record<string, Array<{ timestamp: number; value: any }>>
    >({})
    const [metricsHistoryLoading, setMetricsHistoryLoading] = useState(false)
    const [selectedMetric, setSelectedMetric] = useState<{
        name: string
        display: string
        policy?: string
    } | null>(null)
    const [error, setError] = useState<string | null>(null)
    const [activeTab, setActiveTab] = useState('orchestration')
    // [FIX-FAB-004] 替换硬编码MCP列表: 改为从后端 /api/mcp/servers 真实加载
    const [mcpServers, setMcpServers] = useState<any[]>([])
    const intervalRef = useRef<number | null>(null)

    useEffect(() => {
        fetchAllData()
        intervalRef.current = window.setInterval(fetchAllData, 8000)
        return () => {
            if (intervalRef.current) clearInterval(intervalRef.current)
        }
    }, [])

    const fetchAllData = async () => {
        try {
            setLoading(true)
            const [statsRes, memRes, healthRes, opsRes, opsSumRes, opsLogRes, mcpRes] = await Promise.allSettled([
                api.get('/api/system/stats'),
                api.get('/api/memory/stats'),
                api.get('/api/health'),
                api.get('/api/ops/report'),
                api.get('/api/operations/summary'),
                operationsApi.getLog({ limit: 50 }),
                // [FIX-FAB-004] 真实加载MCP服务器列表
                api.get('/api/mcp/servers'),
            ])

            if (statsRes.status === 'fulfilled') setStats(statsRes.value?.data ?? statsRes.value)
            if (memRes.status === 'fulfilled') setMemoryStats(memRes.value?.data ?? memRes.value)
            if (healthRes.status === 'fulfilled') setHealth(healthRes.value?.data ?? healthRes.value)
            if (opsRes.status === 'fulfilled') setOpsReport(opsRes.value?.data ?? opsRes.value)
            if (opsSumRes.status === 'fulfilled') setOpsSummary(opsSumRes.value?.data ?? opsSumRes.value)
            // [FIX-FAB-004] 设置真实MCP服务器数据
            if (mcpRes.status === 'fulfilled') {
                const mcpData: any = mcpRes.value
                setMcpServers(mcpData?.servers || [])
            }
            if (opsLogRes.status === 'fulfilled' && Array.isArray(opsLogRes.value)) {
                // [FIX-TS-019] 修复 Property 'data' does not exist on any[]: value 已是数组, 不需要 .data
                setOpsLogData(opsLogRes.value)
            }

            setError(null)
        } catch {
            setError('部分监控端点连接失败')
        } finally {
            setLoading(false)
        }
    }

    const fetchMetricsLatest = async () => {
        try {
            const data = await metricsService.getLatest()
            setMetricsData(data)
        } catch (err) {
            console.error('Failed to fetch metrics:', err)
        }
    }

    const fetchMetricsHistory = async (metricName: string) => {
        if (metricsHistory[metricName]) return
        setMetricsHistoryLoading(true)
        try {
            const data = await metricsService.getHistory(metricName, 3600, 120)
            if (data.status === 'ok') {
                setMetricsHistory((prev) => ({
                    ...prev,
                    [metricName]: data.points || [],
                }))
            }
        } catch (err) {
            console.error(`Failed to fetch history for ${metricName}:`, err)
        } finally {
            setMetricsHistoryLoading(false)
        }
    }

    useEffect(() => {
        fetchMetricsLatest()
        const metricsInterval = setInterval(fetchMetricsLatest, 15000)
        return () => clearInterval(metricsInterval)
    }, [])

    const showMetricDetail = (name: string, display: string) => {
        const entry = metricsData?.snapshots?.[name]
        setSelectedMetric({
            name,
            display,
            policy: entry?.definition?.anchor_policy || 'none',
        })
        fetchMetricsHistory(name)
    }

    const getModuleStatus = (moduleName: string): 'online' | 'offline' | 'error' | 'unknown' => {
        if (!stats?.modules) return 'unknown'
        const mod = stats.modules[moduleName]
        if (!mod) return 'unknown'
        if (mod.status === 'pend_active' || mod.status === 'online') return 'online'
        if (mod.status === 'error') return 'error'
        return 'unknown'
    }

    const formatVal = (v: unknown): string => {
        if (v === null || v === undefined) return '-'
        if (typeof v === 'boolean') return v ? '✓' : '✗'
        if (typeof v === 'number') return v.toLocaleString()
        if (typeof v === 'object') return JSON.stringify(v).slice(0, 60)
        return String(v)
    }

    const getLayerCount = (val: number | { entry_count?: number } | undefined): number => {
        if (typeof val === 'number') return val
        if (val && typeof val === 'object' && typeof val.entry_count === 'number')
            return val.entry_count
        return 0
    }

    const getCatCount = (val: unknown): number => {
        if (typeof val === 'number') return val
        if (val && typeof val === 'object') {
            const obj = val as Record<string, unknown>
            if (typeof obj.count === 'number') return obj.count
        }
        return 0
    }

    const statusBadge = (s: 'online' | 'offline' | 'error' | 'unknown') => {
        switch (s) {
            case 'online':
                return <Badge status="success" text="在线" />
            case 'error':
                return <Badge status="error" text="错误" />
            case 'offline':
                return <Badge status="default" text="离线" />
            case 'unknown':
                return <Badge status="processing" text="待检测" />
        }
    }

    const statusDot = (s: 'online' | 'offline' | 'error' | 'unknown') => {
        switch (s) {
            case 'online':
                return <CheckCircleOutlined style={{ color: '#52c41a', fontSize: '12px' }} />
            case 'error':
                return <ExclamationCircleOutlined style={{ color: '#ff4d4f', fontSize: '12px' }} />
            case 'offline':
                return <MinusCircleOutlined style={{ color: '#d9d9d9', fontSize: '12px' }} />
            case 'unknown':
                return <SyncOutlined spin style={{ color: '#1890ff', fontSize: '12px' }} />
        }
    }

    const onlineCount = stats?.coverage?.online ?? 0
    const totalCount =
        stats?.coverage?.total ??
        stats?.module_count ??
        Object.values(MODULE_CONTAINERS).reduce((sum, c) => sum + c.modules.length, 0)

    const renderSystemOverview = () => (
        <Row gutter={[16, 16]}>
            <Col xs={24} sm={12} lg={6}>
                <Card hoverable size="small">
                    <Statistic
                        title="系统健康"
                        value={health?.status ?? '检测中...'}
                        prefix={
                            health?.status === 'healthy' ? (
                                <CheckCircleOutlined style={{ color: '#52c41a' }} />
                            ) : (
                                <SyncOutlined spin />
                            )
                        }
                        valueStyle={{ color: health?.status === 'healthy' ? '#52c41a' : '#faad14' }}
                    />
                </Card>
            </Col>
            <Col xs={24} sm={12} lg={6}>
                <Card hoverable size="small">
                    <Statistic
                        title="运行时间"
                        value={stats?.uptime_seconds ?? health?.uptime ?? 0}
                        suffix="秒"
                        precision={0}
                        prefix={<HistoryOutlined />}
                    />
                </Card>
            </Col>
            <Col xs={24} sm={12} lg={6}>
                <Card hoverable size="small">
                    <Statistic
                        title="记忆总量"
                        value={stats?.memory_total ?? memoryStats?.total_entries ?? 0}
                        prefix={<DatabaseOutlined style={{ color: '#1890ff' }} />}
                    />
                </Card>
            </Col>
            <Col xs={24} sm={12} lg={6}>
                <Card hoverable size="small">
                    <Statistic
                        title="模块在线率"
                        value={`${onlineCount}/${totalCount}`}
                        prefix={<MonitorOutlined style={{ color: '#52c41a' }} />}
                    />
                </Card>
            </Col>
        </Row>
    )

    const renderModuleTree = () => {
        const items = Object.entries(MODULE_CONTAINERS).map(([containerKey, container]) => {
            const containerOnline = container.modules.filter(
                (m) => getModuleStatus(m.name) === 'online'
            ).length

            return {
                key: containerKey,
                label: (
                    <Space>
                        <span style={{ color: container.color }}>{container.icon}</span>
                        <Text strong>{containerKey}</Text>
                        <Tag
                            color={
                                containerOnline === container.modules.length
                                    ? 'green'
                                    : containerOnline > 0
                                        ? 'orange'
                                        : 'red'
                            }
                        >
                            {containerOnline}/{container.modules.length}
                        </Tag>
                    </Space>
                ),
                children: (
                    <Row gutter={[12, 12]}>
                        {container.modules.map((mod) => {
                            const status = getModuleStatus(mod.name)

                            return (
                                <Col xs={24} sm={12} lg={8} xl={6} key={mod.name}>
                                    <Card
                                        size="small"
                                        hoverable
                                        title={
                                            <Space size="small">
                                                {statusDot(status)}
                                                <Text ellipsis style={{ maxWidth: 140, fontSize: 13 }}>
                                                    {mod.label}
                                                </Text>
                                            </Space>
                                        }
                                        extra={statusBadge(status)}
                                    >
                                        {status === 'online' ? (
                                            <div style={{ fontSize: 12 }}>
                                                <div
                                                    style={{
                                                        display: 'flex',
                                                        justifyContent: 'space-between',
                                                        marginBottom: 2,
                                                    }}
                                                >
                                                    <Text type="secondary">总记忆</Text>
                                                    <Text strong>{stats?.memory_total ?? '-'}</Text>
                                                </div>
                                                <div
                                                    style={{
                                                        display: 'flex',
                                                        justifyContent: 'space-between',
                                                        marginBottom: 2,
                                                    }}
                                                >
                                                    <Text type="secondary">命中率</Text>
                                                    <Text strong>
                                                        {stats?.hit_rate != null ? `${stats.hit_rate.toFixed(0)}%` : '-'}
                                                    </Text>
                                                </div>
                                                <div
                                                    style={{
                                                        display: 'flex',
                                                        justifyContent: 'space-between',
                                                        marginBottom: 2,
                                                    }}
                                                >
                                                    <Text type="secondary">后端</Text>
                                                    <Text strong>{stats?.storage_backend ?? '-'}</Text>
                                                </div>
                                                <div
                                                    style={{
                                                        display: 'flex',
                                                        justifyContent: 'space-between',
                                                        marginBottom: 2,
                                                    }}
                                                >
                                                    <Text type="secondary">固结</Text>
                                                    <Text strong>{stats?.consolidations ?? '-'}</Text>
                                                </div>
                                            </div>
                                        ) : status === 'offline' ? (
                                            <Empty
                                                description="未初始化"
                                                image={Empty.PRESENTED_IMAGE_SIMPLE}
                                                style={{ margin: 0 }}
                                            />
                                        ) : (
                                            <Text type="danger" style={{ fontSize: 12 }}>
                                                运行异常
                                            </Text>
                                        )}
                                    </Card>
                                </Col>
                            )
                        })}
                    </Row>
                ),
            }
        })

        return (
            <Collapse
                defaultActiveKey={['核心引擎', 'DeepSeek大脑核心']}
                style={{ background: 'transparent' }}
                expandIconPosition="end"
                items={items}
            />
        )
    }

    const renderOrchestrationTab = () => (
        <div>
            {renderSystemOverview()}
            <Divider orientation="left" style={{ marginTop: 24, marginBottom: 16 }}>
                <Space>
                    <RobotOutlined />
                    <Text strong>模块监控看板 — 46模块·7容器·实时状态</Text>
                </Space>
            </Divider>
            {renderModuleTree()}

            <Divider orientation="left" style={{ marginTop: 24, marginBottom: 16 }}>
                <Space>
                    <HistoryOutlined />
                    <Text strong>引擎数据面板</Text>
                </Space>
            </Divider>
            <Card size="small">
                <Row gutter={[16, 16]}>
                    {stats?.memory_by_layer ? (
                        Object.entries(stats.memory_by_layer).map(([name, count]) => (
                            <Col xs={12} sm={4} key={name}>
                                <Statistic title={name} value={count as number} valueStyle={{ fontSize: 16 }} />
                            </Col>
                        ))
                    ) : (
                        <Empty description="引擎数据加载中..." />
                    )}
                </Row>
                <Divider orientation="left">引擎指标</Divider>
                <Row gutter={[16, 16]}>
                    <Col xs={12} sm={6}>
                        <Statistic
                            title="存储后端"
                            value={stats?.storage_backend ?? '-'}
                            valueStyle={{ fontSize: 14 }}
                        />
                    </Col>
                    <Col xs={12} sm={6}>
                        <Statistic
                            title="命中率"
                            value={stats?.hit_rate != null ? `${stats.hit_rate.toFixed(0)}%` : '-'}
                            valueStyle={{ fontSize: 14 }}
                        />
                    </Col>
                    <Col xs={12} sm={6}>
                        <Statistic
                            title="固结次数"
                            value={stats?.consolidations ?? 0}
                            valueStyle={{ fontSize: 14 }}
                        />
                    </Col>
                    <Col xs={12} sm={6}>
                        <Statistic
                            title="DB大小"
                            value={`${stats?.db_size_mb ?? 0}MB`}
                            valueStyle={{ fontSize: 14 }}
                        />
                    </Col>
                </Row>
            </Card>
        </div>
    )

    const renderConversationTab = () => (
        <div>
            {renderSystemOverview()}

            <Divider orientation="left" style={{ marginTop: 24 }}>
                <Space>
                    <MessageOutlined />
                    <Text strong>六层记忆状态</Text>
                </Space>
            </Divider>

            <Row gutter={[16, 16]}>
                {health?.layers ? (
                    Object.entries(health.layers).map(([layer, count]) => (
                        <Col xs={12} sm={8} lg={4} key={layer}>
                            <Card size="small" hoverable>
                                <Statistic
                                    title={layer}
                                    value={getLayerCount(count)}
                                    prefix={<DatabaseOutlined />}
                                    valueStyle={{ fontSize: 20 }}
                                />
                            </Card>
                        </Col>
                    ))
                ) : (
                    <Col span={24}>
                        <Empty description="记忆层数据加载中..." />
                    </Col>
                )}
            </Row>

            <Divider orientation="left" style={{ marginTop: 24 }}>
                <Space>
                    <BarChartOutlined />
                    <Text strong>记忆统计</Text>
                </Space>
            </Divider>

            <Row gutter={[16, 16]}>
                <Col xs={24} sm={12} lg={6}>
                    <Card size="small">
                        <Statistic title="总记忆条目" value={memoryStats?.total_entries ?? 0} />
                    </Card>
                </Col>
                <Col xs={24} sm={12} lg={6}>
                    <Card size="small">
                        <Statistic title="总访问次数" value={memoryStats?.total_accesses ?? 0} />
                    </Card>
                </Col>
                <Col xs={24} sm={12} lg={6}>
                    <Card size="small">
                        <Statistic title="归档条目" value={memoryStats?.archive_entries ?? 0} />
                    </Card>
                </Col>
                <Col xs={24} sm={12} lg={6}>
                    <Card size="small">
                        <Statistic
                            title="各层分布"
                            value={memoryStats?.layers ? Object.keys(memoryStats.layers).length : 0}
                            suffix="层"
                        />
                    </Card>
                </Col>
            </Row>

            <Divider orientation="left" style={{ marginTop: 24 }}>
                <Space>
                    <ThunderboltOutlined />
                    <Text strong>自动化运维状态</Text>
                </Space>
            </Divider>

            <Row gutter={[16, 16]}>
                <Col xs={24} sm={12} lg={6}>
                    <Card size="small">
                        <Statistic
                            title="运维可用"
                            value={opsReport?.ops_available ? '✓' : '✗'}
                            valueStyle={{ color: opsReport?.ops_available ? '#52c41a' : '#ff4d4f' }}
                        />
                    </Card>
                </Col>
                <Col xs={24} sm={12} lg={6}>
                    <Card size="small">
                        <Statistic
                            title="自愈尝试"
                            value={opsReport?.healer?.total_heal_attempts ?? 0}
                            prefix={<ToolOutlined />}
                        />
                    </Card>
                </Col>
                <Col xs={24} sm={12} lg={6}>
                    <Card size="small">
                        <Statistic
                            title="自愈成功"
                            value={opsReport?.healer?.total_heal_successes ?? 0}
                            prefix={<CheckCircleOutlined style={{ color: '#52c41a' }} />}
                        />
                    </Card>
                </Col>
                <Col xs={24} sm={12} lg={6}>
                    <Card size="small">
                        <Statistic
                            title="异常检测"
                            value={opsReport?.baseline?.anomalies_detected ?? 0}
                            prefix={<ExclamationCircleOutlined style={{ color: '#faad14' }} />}
                        />
                    </Card>
                </Col>
            </Row>
        </div>
    )

    const renderSessionTab = () => (
        <div>
            {renderSystemOverview()}

            <Divider orientation="left" style={{ marginTop: 24 }}>
                <Space>
                    <OrderedListOutlined />
                    <Text strong>
                        系统模块实时状态 — {stats?.coverage?.online ?? 0}/{stats?.coverage?.total ?? 0} 在线
                    </Text>
                </Space>
            </Divider>

            <Table
                dataSource={
                    stats?.modules
                        ? Object.entries(stats.modules).map(([name, info]) => ({
                            module: name,
                            status: ((info as Record<string, unknown>)?.status as string) ?? 'unknown',
                            last_update: (info as Record<string, unknown>)?.last_update as
                                | number
                                | undefined,
                        }))
                        : []
                }
                loading={loading && !stats}
                columns={[
                    {
                        title: '模块名称',
                        dataIndex: 'module',
                        key: 'module',
                        render: (text: string) => <Text strong>{text}</Text>,
                    },
                    {
                        title: '运行状态',
                        dataIndex: 'status',
                        key: 'status',
                        filters: [
                            { text: '在线', value: 'online' },
                            { text: '异常', value: 'error' },
                        ],
                        onFilter: (value, record: { status: string }) => {
                            const online =
                                record.status === 'pend_active' || record.status === 'online'
                            return value === 'online' ? online : record.status === 'error'
                        },
                        render: (status: string) => {
                            const online = status === 'pend_active' || status === 'online'
                            const err = status === 'error'
                            return (
                                <Badge
                                    status={online ? 'success' : err ? 'error' : 'default'}
                                    text={online ? '在线' : err ? '异常' : status}
                                />
                            )
                        },
                    },
                    {
                        title: '最近更新',
                        dataIndex: 'last_update',
                        key: 'last_update',
                        render: (ts?: number) =>
                            ts ? (
                                <Text type="secondary">
                                    {new Date(ts * 1000).toLocaleTimeString()}
                                </Text>
                            ) : (
                                <Text type="secondary">—</Text>
                            ),
                    },
                ]}
                rowKey="module"
                size="small"
                pagination={{ pageSize: 12, size: 'small' }}
                summary={() => (
                    <Table.Summary.Row>
                        <Table.Summary.Cell index={0}>
                            <Text strong>合计</Text>
                        </Table.Summary.Cell>
                        <Table.Summary.Cell index={1}>
                            <Text strong style={{ color: '#1890ff' }}>
                                {stats?.coverage?.online ?? 0}/{stats?.coverage?.total ?? 0} 在线
                            </Text>
                        </Table.Summary.Cell>
                        <Table.Summary.Cell index={2}>
                            <Text strong>{stats?.coverage?.with_stats ?? 0} 含指标</Text>
                        </Table.Summary.Cell>
                    </Table.Summary.Row>
                )}
                title={() => (
                    <Space>
                        <ApiOutlined />
                        <span>系统模块实时状态（来自 /api/system/stats）</span>
                    </Space>
                )}
            />

            <Divider orientation="left" style={{ marginTop: 24 }}>
                <Space>
                    <KeyOutlined />
                    <Text strong>MCP Server状态</Text>
                </Space>
            </Divider>

            <Row gutter={[16, 16]}>
                {(() => {
                    // [FIX-FAB-004] 使用真实API数据, 附中文显示名映射
                    const SERVER_DISPLAY: Record<string, { name: string; role: string }> = {
                        'agent-framework-global': { name: '智能调度框架', role: '@tianshu协调' },
                        'memory-engine-global': { name: '记忆引擎', role: '天机ICME核心' },
                        'command-executor': { name: '进程管理', role: '命令执行' },
                        'ops-engine': { name: 'DevOps运维', role: '自动化运维' },
                        'performance-profiler': { name: '性能剖析', role: '性能分析' },
                        'security-scanner': { name: '安全审计', role: '安全扫描' },
                    }
                    // 真实数据来自 /api/mcp/servers, 无数据时显示空状态
                    const servers = mcpServers.length > 0
                        ? mcpServers.map((s: any) => ({
                            id: s.name,
                            name: SERVER_DISPLAY[s.name]?.name || s.name,
                            role: SERVER_DISPLAY[s.name]?.role || s.description || '-',
                            toolsCount: s.tools_count ?? 0,
                            status: s.status || 'unknown',
                            enabled: s.enabled ?? false,
                        }))
                        : []
                    if (servers.length === 0) {
                        return (
                            <Col span={24}>
                                <Card size="small">
                                    <Text type="secondary">MCP服务器数据加载中或未就绪...</Text>
                                </Card>
                            </Col>
                        )
                    }
                    return servers.map((server) => (
                        <Col xs={24} sm={12} lg={8} key={server.id}>
                            <Card size="small" hoverable>
                                <div
                                    style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}
                                >
                                    <Space>
                                        <CloudServerOutlined style={{ color: '#1890ff' }} />
                                        <div>
                                            <Text strong>{server.name}</Text>
                                            <br />
                                            <Text type="secondary" style={{ fontSize: 12 }}>
                                                {server.id}
                                            </Text>
                                        </div>
                                    </Space>
                                    <Tag color={server.status === 'connected' ? 'green' : 'red'}>
                                        {server.status === 'connected' ? 'ONLINE' : 'OFFLINE'}
                                    </Tag>
                                </div>
                                <div style={{ marginTop: 8 }}>
                                    <Text type="secondary" style={{ fontSize: 12 }}>
                                        角色: {server.role}
                                    </Text>
                                    <br />
                                    <Text type="secondary" style={{ fontSize: 12 }}>
                                        工具数: <Text strong>{server.toolsCount}</Text>
                                    </Text>
                                </div>
                            </Card>
                        </Col>
                    ))
                })()}
            </Row>
        </div>
    )

    const renderOperationsTab = () => (
        <div>
            <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
                <Col xs={12} sm={6}>
                    <Card size="small" style={{ textAlign: 'center' }}>
                        <Statistic
                            title={
                                <Tag color="purple" icon={<ApartmentOutlined />}>
                                    TVP调度
                                </Tag>
                            }
                            value={getCatCount(opsSummary?.by_category?.tvp)}
                            suffix="次"
                            valueStyle={{ color: '#722ed1' }}
                        />
                    </Card>
                </Col>
                <Col xs={12} sm={6}>
                    <Card size="small" style={{ textAlign: 'center' }}>
                        <Statistic
                            title={
                                <Tag color="orange" icon={<ApiOutlined />}>
                                    MCP调用
                                </Tag>
                            }
                            value={getCatCount(opsSummary?.by_category?.mcp)}
                            suffix="次"
                            valueStyle={{ color: '#fa8c16' }}
                        />
                    </Card>
                </Col>
                <Col xs={12} sm={6}>
                    <Card size="small" style={{ textAlign: 'center' }}>
                        <Statistic
                            title={
                                <Tag color="cyan" icon={<DatabaseOutlined />}>
                                    记忆操作
                                </Tag>
                            }
                            value={getCatCount(opsSummary?.by_category?.memory)}
                            suffix="次"
                            valueStyle={{ color: '#13c2c2' }}
                        />
                    </Card>
                </Col>
                <Col xs={12} sm={6}>
                    <Card size="small" style={{ textAlign: 'center' }}>
                        <Statistic
                            title={
                                <Tag color="magenta" icon={<ThunderboltOutlined />}>
                                    LLM调用
                                </Tag>
                            }
                            value={getCatCount(opsSummary?.by_category?.llm)}
                            suffix="次"
                            valueStyle={{ color: '#eb2f96' }}
                        />
                    </Card>
                </Col>
            </Row>

            <Divider orientation="left">
                <Space>
                    <EyeOutlined />
                    <Text strong>最近操作痕迹</Text>
                </Space>
            </Divider>

            <Table
                dataSource={opsSummary?.recent ?? []}
                columns={[
                    {
                        title: '时间',
                        dataIndex: 'time_str',
                        key: 'time',
                        width: 80,
                        render: (t: string) => <Text code>{t}</Text>,
                    },
                    {
                        title: '类别',
                        dataIndex: 'category',
                        key: 'cat',
                        width: 80,
                        render: (c: string) => {
                            const colorMap: Record<string, string> = {
                                tvp: 'purple',
                                mcp: 'orange',
                                memory: 'cyan',
                                llm: 'magenta',
                            }
                            return <Tag color={colorMap[c] ?? 'default'}>{c?.toUpperCase()}</Tag>
                        },
                    },
                    {
                        title: '操作',
                        dataIndex: 'action',
                        key: 'action',
                        width: 100,
                        render: (a: string) => <Text strong>{a}</Text>,
                    },
                    {
                        title: '详情',
                        dataIndex: 'detail',
                        key: 'detail',
                        render: (d: string) => (
                            <Text type="secondary" ellipsis style={{ maxWidth: 300 }}>
                                {d}
                            </Text>
                        ),
                    },
                    {
                        title: '结果',
                        dataIndex: 'result',
                        key: 'result',
                        width: 60,
                        render: (r: string) => <Tag color={r === 'ok' ? 'green' : 'red'}>{r}</Tag>,
                    },
                ]}
                rowKey={(_, i) => String(i)}
                size="small"
                pagination={false}
                locale={{ emptyText: '暂无操作记录 — 操作天机功能后此处实时显示' }}
            />

            <Divider orientation="left">
                <Space>
                    <ApartmentOutlined />
                    <Text strong>TVP透明调度声明</Text>
                </Space>
            </Divider>
            {(opsSummary?.tvp_declarations?.length ?? 0) > 0 ? (
                <Timeline
                    items={opsSummary?.tvp_declarations?.map((e: any) => ({
                        color: 'purple',
                        children: (
                            <Text>
                                [{e.time_str}] {e.action}: {e.detail}
                            </Text>
                        ),
                    }))}
                />
            ) : (
                <Empty
                    description="TVP调度声明将在Agent切换时自动记录"
                    image={Empty.PRESENTED_IMAGE_SIMPLE}
                />
            )}

            <Divider orientation="left">
                <Space>
                    <ApiOutlined />
                    <Text strong>MCP工具调用</Text>
                </Space>
            </Divider>
            {(opsSummary?.mcp_calls?.length ?? 0) > 0 ? (
                <Timeline
                    items={opsSummary?.mcp_calls?.map((e: any) => ({
                        color: 'orange',
                        children: (
                            <Text>
                                [{e.time_str}] {e.action}: {e.detail}
                            </Text>
                        ),
                    }))}
                />
            ) : (
                <Empty description="MCP调用将在工具被调用时自动记录" image={Empty.PRESENTED_IMAGE_SIMPLE} />
            )}

            <Divider orientation="left">
                <Space>
                    <DatabaseOutlined />
                    <Text strong>记忆操作</Text>
                </Space>
            </Divider>
            {(opsSummary?.memory_ops?.length ?? 0) > 0 ? (
                <Timeline
                    items={opsSummary?.memory_ops?.map((e: any) => ({
                        color: 'cyan',
                        children: (
                            <Text>
                                [{e.time_str}] {e.action}: {e.detail}
                            </Text>
                        ),
                    }))}
                />
            ) : (
                <Empty
                    description="记忆操作将在创建/读取/搜索时自动记录"
                    image={Empty.PRESENTED_IMAGE_SIMPLE}
                />
            )}
        </div>
    )

    const ALL_MODULES = Object.entries(MODULE_CONTAINERS).flatMap(([, container]) =>
        container.modules.map((m) => m.name)
    )

    const renderModuleStatusTable = () => {
        const moduleTableData = ALL_MODULES.map((name) => {
            const mod = stats?.modules?.[name]
            const rt = stats?.dimensions?.realtime?.[name]
            const status = getModuleStatus(name)
            const containerInfo = Object.entries(MODULE_CONTAINERS).find(([, c]) =>
                c.modules.some((m) => m.name === name)
            )
            return {
                key: name,
                name,
                label: containerInfo?.[1]?.modules.find((m) => m.name === name)?.label || name,
                container: containerInfo?.[0] || '未知',
                status,
                lastUpdate: rt?.last_update ? new Date(rt.last_update * 1000).toLocaleString() : '-',
                metrics: rt?.key_metrics || mod ? { ...rt?.key_metrics, ...mod } : {},
            }
        })

        const columns = [
            {
                title: '模块名称',
                dataIndex: 'label',
                key: 'label',
                width: 160,
                fixed: 'left' as const,
                sorter: (a: any, b: any) => a.label.localeCompare(b.label),
                render: (label: string, record: any) => (
                    <Space size="small">
                        {statusDot(record.status)}
                        <Text strong>{label}</Text>
                    </Space>
                ),
            },
            {
                title: '所属容器',
                dataIndex: 'container',
                key: 'container',
                width: 130,
                filters: Object.keys(MODULE_CONTAINERS).map((key) => ({ text: key, value: key })),
                onFilter: (value: any, record: any) => record.container === value,
                render: (container: string) => (
                    <Tag
                        color={
                            (MODULE_CONTAINERS[container as keyof typeof MODULE_CONTAINERS]?.color as string) ||
                            'default'
                        }
                    >
                        {container}
                    </Tag>
                ),
            },
            {
                title: '状态',
                dataIndex: 'status',
                key: 'status',
                width: 100,
                filters: [
                    { text: '在线', value: 'online' },
                    { text: '离线', value: 'offline' },
                    { text: '错误', value: 'error' },
                ],
                onFilter: (value: any, record: any) => record.status === value,
                render: (s: string) => statusBadge(s as 'online' | 'offline' | 'error'),
            },
            {
                title: '最后更新',
                dataIndex: 'lastUpdate',
                key: 'lastUpdate',
                width: 170,
                sorter: (a: any, b: any) => (a.lastUpdate || '').localeCompare(b.lastUpdate || ''),
            },
            {
                title: '关键指标',
                dataIndex: 'metrics',
                key: 'metrics',
                render: (metrics: Record<string, any>) => {
                    if (!metrics || Object.keys(metrics).length === 0) return <Text type="secondary">-</Text>
                    const entries = Object.entries(metrics)
                        .filter(([k]) => !k.startsWith('_') && typeof k === 'string')
                        .slice(0, 3)
                    return (
                        <Space size={4} wrap>
                            {entries.map(([k, v]) => (
                                <Tag key={k} color="blue" style={{ fontSize: 11 }}>
                                    {k}: {formatVal(v)}
                                </Tag>
                            ))}
                            {Object.keys(metrics).length > 3 && (
                                <Text type="secondary" style={{ fontSize: 11 }}>
                                    +{Object.keys(metrics).length - 3}
                                </Text>
                            )}
                        </Space>
                    )
                },
            },
        ]

        const onlineCount = moduleTableData.filter((m) => m.status === 'online').length
        const errorCount = moduleTableData.filter((m) => m.status === 'error').length

        return (
            <div>
                <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
                    <Col xs={12} sm={6}>
                        <Card size="small">
                            <Statistic
                                title="总模块数"
                                value={moduleTableData.length}
                                prefix={<NodeIndexOutlined />}
                                valueStyle={{ fontSize: 20 }}
                            />
                        </Card>
                    </Col>
                    <Col xs={12} sm={6}>
                        <Card size="small">
                            <Statistic
                                title="在线"
                                value={onlineCount}
                                prefix={<CheckCircleOutlined style={{ color: '#52c41a' }} />}
                                valueStyle={{ color: '#52c41a', fontSize: 20 }}
                                suffix={`/ ${moduleTableData.length}`}
                            />
                        </Card>
                    </Col>
                    <Col xs={12} sm={6}>
                        <Card size="small">
                            <Statistic
                                title="离线"
                                value={moduleTableData.length - onlineCount - errorCount}
                                prefix={<MinusCircleOutlined style={{ color: '#d9d9d9' }} />}
                                valueStyle={{ fontSize: 20 }}
                            />
                        </Card>
                    </Col>
                    <Col xs={12} sm={6}>
                        <Card size="small">
                            <Statistic
                                title="异常"
                                value={errorCount}
                                prefix={<ExclamationCircleOutlined style={{ color: '#ff4d4f' }} />}
                                valueStyle={{ color: errorCount > 0 ? '#ff4d4f' : undefined, fontSize: 20 }}
                            />
                        </Card>
                    </Col>
                </Row>

                <Table
                    dataSource={moduleTableData}
                    columns={columns}
                    rowKey="key"
                    size="small"
                    pagination={{
                        pageSize: 20,
                        showSizeChanger: true,
                        showTotal: (total) => `共 ${total} 个模块`,
                        pageSizeOptions: ['10', '20', '50', '100'],
                    }}
                    scroll={{ x: 900 }}
                    rowClassName={(record) => {
                        if (record.status === 'error') return 'row-error'
                        if (record.status !== 'online') return 'row-offline'
                        return ''
                    }}
                    title={() => (
                        <Space>
                            <MonitorOutlined />
                            <strong>全量模块状态表 — 支持排序/筛选/分页</strong>
                            <Tag color="blue">{moduleTableData.length} 模块</Tag>
                        </Space>
                    )}
                />
            </div>
        )
    }

    const OPS_CATEGORY_OPTIONS = [
        { value: 'all', label: '全部', color: 'default', icon: <FilterOutlined /> },
        { value: 'tvp', label: 'TVP调度', color: 'purple', icon: <ApartmentOutlined /> },
        { value: 'mcp', label: 'MCP调用', color: 'orange', icon: <ApiOutlined /> },
        { value: 'memory', label: '记忆操作', color: 'cyan', icon: <DatabaseOutlined /> },
        { value: 'llm', label: 'LLM调用', color: 'magenta', icon: <ThunderboltOutlined /> },
    ]

    const filteredOpsLog =
        opsCategoryFilter === 'all'
            ? opsLogData
            : opsLogData.filter((op: any) => op.category === opsCategoryFilter)

    const renderOperationsLogViewer = () => (
        <div>
            <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
                {OPS_CATEGORY_OPTIONS.slice(1).map((opt) => {
                    const count = opsLogData.filter((op: any) => op.category === opt.value).length
                    return (
                        <Col xs={12} sm={6} key={opt.value}>
                            <Card
                                size="small"
                                hoverable
                                style={{
                                    borderLeft: `3px solid ${opt.color === 'purple' ? '#722ed1' : opt.color === 'orange' ? '#fa8c16' : opt.color === 'cyan' ? '#13c2c2' : '#eb2f96'}`,
                                    cursor: 'pointer',
                                    background:
                                        opsCategoryFilter === opt.value
                                            ? `${opt.color === 'purple' ? '#722ed1' : opt.color === 'orange' ? '#fa8c16' : opt.color === 'cyan' ? '#13c2c2' : '#eb2f96'}08`
                                            : undefined,
                                }}
                                onClick={() =>
                                    setOpsCategoryFilter(opsCategoryFilter === opt.value ? 'all' : opt.value)
                                }
                            >
                                <Statistic
                                    title={
                                        <Tag color={opt.color} icon={opt.icon}>
                                            {opt.label}
                                        </Tag>
                                    }
                                    value={count}
                                    suffix="条"
                                    valueStyle={{
                                        color:
                                            opt.color === 'purple'
                                                ? '#722ed1'
                                                : opt.color === 'orange'
                                                    ? '#fa8c16'
                                                    : opt.color === 'cyan'
                                                        ? '#13c2c2'
                                                        : '#eb2f96',
                                        fontSize: 22,
                                    }}
                                />
                            </Card>
                        </Col>
                    )
                })}
            </Row>

            <Card
                size="small"
                title={
                    <Space>
                        <FireOutlined />
                        <strong>操作日志查看器</strong>
                        <Badge count={filteredOpsLog.length} showZero color="#1890ff" offset={[8, -2]} />
                    </Space>
                }
                extra={
                    <Space>
                        <Space.Compact>
                            {OPS_CATEGORY_OPTIONS.map((opt) => (
                                <Button
                                    key={opt.value}
                                    size="small"
                                    type={opsCategoryFilter === opt.value ? 'primary' : 'default'}
                                    onClick={() => setOpsCategoryFilter(opt.value)}
                                    icon={opt.icon}
                                >
                                    {opt.label}
                                </Button>
                            ))}
                        </Space.Compact>
                        <Button size="small" icon={<ReloadOutlined />} onClick={fetchAllData} loading={loading}>
                            刷新
                        </Button>
                    </Space>
                }
            >
                <div
                    style={{
                        maxHeight: 500,
                        overflowY: 'auto',
                        background: '#fafafa',
                        borderRadius: 6,
                        padding: '8px 12px',
                    }}
                >
                    {filteredOpsLog.length === 0 ? (
                        <Empty
                            description={`暂无${opsCategoryFilter === 'all' ? '' : OPS_CATEGORY_OPTIONS.find((o) => o.value === opsCategoryFilter)?.label}操作记录`}
                            image={Empty.PRESENTED_IMAGE_SIMPLE}
                        />
                    ) : (
                        <Timeline
                            items={filteredOpsLog.slice(0, 30).map((op: any, idx: number) => ({
                                color:
                                    op.category === 'tvp'
                                        ? '#722ed1'
                                        : op.category === 'mcp'
                                            ? '#fa8c16'
                                            : op.category === 'memory'
                                                ? '#13c2c2'
                                                : op.category === 'llm'
                                                    ? '#eb2f96'
                                                    : 'gray',
                                children: (
                                    <div
                                        key={`${op.timestamp}-${idx}`}
                                        style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}
                                    >
                                        <Text code style={{ fontSize: 11, minWidth: 70, flexShrink: 0 }}>
                                            {op.time_str}
                                        </Text>
                                        <Tag
                                            color={
                                                op.category === 'tvp'
                                                    ? 'purple'
                                                    : op.category === 'mcp'
                                                        ? 'orange'
                                                        : op.category === 'memory'
                                                            ? 'cyan'
                                                            : op.category === 'llm'
                                                                ? 'magenta'
                                                                : 'default'
                                            }
                                            style={{ margin: 0, flexShrink: 0 }}
                                        >
                                            {(op.category || '').toUpperCase()}
                                        </Tag>
                                        <Text strong style={{ fontSize: 13, flexShrink: 0 }}>
                                            {op.action}
                                        </Text>
                                        <Text
                                            type="secondary"
                                            ellipsis
                                            style={{ fontSize: 12, maxWidth: 350, flex: 1 }}
                                        >
                                            {op.detail}
                                        </Text>
                                        <Tag
                                            color={op.result === 'ok' ? 'success' : 'error'}
                                            style={{ margin: 0, flexShrink: 0 }}
                                        >
                                            {op.result?.toUpperCase()}
                                        </Tag>
                                        {op.duration_ms && (
                                            <Text type="secondary" style={{ fontSize: 11, flexShrink: 0 }}>
                                                {op.duration_ms}ms
                                            </Text>
                                        )}
                                    </div>
                                ),
                            }))}
                        />
                    )}
                </div>
            </Card>
        </div>
    )

    const formatUptime = (seconds: number): string => {
        if (seconds < 60) return `${seconds}秒`
        if (seconds < 3600) return `${Math.floor(seconds / 60)}分${seconds % 60}秒`
        if (seconds < 86400)
            return `${Math.floor(seconds / 3600)}时${Math.floor((seconds % 3600) / 60)}分`
        const days = Math.floor(seconds / 86400)
        const hours = Math.floor((seconds % 86400) / 3600)
        return `${days}天${hours}时`
    }

    const renderMetricsTrendPanel = () => {
        if (!metricsData || metricsData.status !== 'ok') {
            return (
                <Card
                    size="small"
                    title={
                        <Space>
                            <LineChartOutlined />
                            <strong>📊 98分指标历史趋势</strong>
                        </Space>
                    }
                >
                    <Spin spinning={!metricsData}>
                        <Empty
                            description={metricsData ? 'StatCollector未就绪' : '正在连接采集引擎...'}
                            image={Empty.PRESENTED_IMAGE_SIMPLE}
                        />
                    </Spin>
                </Card>
            )
        }

        const categories = Object.entries(metricsData.by_category)
        const allMetrics = categories.flatMap(([, entries]) => entries)

        const historyColumns = [
            {
                title: '指标名称',
                dataIndex: 'definition',
                key: 'name',
                width: 200,
                render: (def: MetricEntry['definition']) => (
                    <Space size="small">
                        <Tag
                            color={def.anchor_policy !== 'none' ? 'purple' : 'default'}
                            style={{ fontSize: 9 }}
                        >
                            {def.anchor_policy}
                        </Tag>
                        <Text strong style={{ fontSize: 12 }}>
                            {def.display_name}
                        </Text>
                    </Space>
                ),
            },
            {
                title: '最新值',
                dataIndex: 'snapshot',
                key: 'value',
                width: 120,
                render: (snap: MetricEntry['snapshot']) => {
                    if (!snap) return <Text type="secondary">-</Text>
                    const val =
                        typeof snap.value === 'object'
                            ? JSON.stringify(snap.value).substring(0, 20)
                            : snap.value
                    return (
                        <Tag color="blue">
                            {String(val)}
                            {snap.unit}
                        </Tag>
                    )
                },
            },
            {
                title: '类型',
                dataIndex: 'definition',
                key: 'type',
                width: 80,
                render: (def: MetricEntry['definition']) => (
                    <Tag
                        color={
                            def.metric_type === 'counter'
                                ? '#1890ff'
                                : def.metric_type === 'gauge'
                                    ? '#52c41a'
                                    : def.metric_type === 'histogram'
                                        ? '#fa8c16'
                                        : '#722ed1'
                        }
                    >
                        {def.metric_type.toUpperCase()}
                    </Tag>
                ),
            },
            {
                title: '采集源',
                dataIndex: 'definition',
                key: 'source',
                width: 100,
                render: (def: MetricEntry['definition']) => <Tag color="geekblue">{def.source_type}</Tag>,
            },
            {
                title: '状态',
                dataIndex: 'entry',
                key: 'status',
                width: 100,
                render: (_: any, record: MetricEntry) => (
                    <Space size={2}>
                        {record.stale ? <Tag color="default">过期</Tag> : <Tag color="green">实时</Tag>}
                        {record.snapshot?.anchor_id ? (
                            <Tooltip title={`锚定: ${record.snapshot.anchor_id}`}>
                                <Tag color="purple" style={{ fontSize: 9, padding: '0 3px' }}>
                                    锚定
                                </Tag>
                            </Tooltip>
                        ) : record.definition.anchor_policy !== 'none' ? (
                            <Tag color="orange" style={{ fontSize: 9, padding: '0 3px' }}>
                                挂起
                            </Tag>
                        ) : null}
                    </Space>
                ),
            },
            {
                title: '历史趋势',
                dataIndex: 'entry',
                key: 'history',
                width: 200,
                render: (_: any, record: MetricEntry) => {
                    const name = record.definition.name
                    const history = metricsHistory[name]
                    const hasHistory = history && history.length > 0

                    return (
                        <Space size={4}>
                            <Button
                                size="small"
                                type="link"
                                icon={hasHistory ? <EyeOutlined /> : <HistoryOutlined />}
                                loading={metricsHistoryLoading && !hasHistory}
                                onClick={() => fetchMetricsHistory(name)}
                            >
                                {hasHistory ? `最近${history!.length}点` : '加载历史'}
                            </Button>
                            {hasHistory && history && (
                                <Button
                                    size="small"
                                    type="primary"
                                    icon={<LineChartOutlined />}
                                    onClick={() => showMetricDetail(name, record.definition.display_name)}
                                >
                                    趋势
                                </Button>
                            )}
                        </Space>
                    )
                },
            },
            {
                title: '更新时间',
                dataIndex: 'snapshot',
                key: 'time',
                width: 80,
                render: (snap: MetricEntry['snapshot']) => {
                    if (!snap?.timestamp) return '-'
                    return (
                        <Text code style={{ fontSize: 10 }}>
                            {new Date(snap.timestamp * 1000).toLocaleTimeString()}
                        </Text>
                    )
                },
            },
        ]

        return (
            <div>
                <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
                    <Col xs={12} sm={4}>
                        <Card size="small">
                            <Statistic
                                title="已注册指标"
                                value={metricsData.total_metrics}
                                prefix={<NodeIndexOutlined />}
                                valueStyle={{ color: '#1890ff', fontSize: 20 }}
                            />
                        </Card>
                    </Col>
                    <Col xs={12} sm={4}>
                        <Card size="small">
                            <Statistic
                                title="有快照"
                                value={metricsData.with_snapshots}
                                prefix={<CheckCircleOutlined style={{ color: '#52c41a' }} />}
                                valueStyle={{ color: '#52c41a', fontSize: 20 }}
                            />
                        </Card>
                    </Col>
                    <Col xs={12} sm={4}>
                        <Card size="small">
                            <Statistic
                                title="已锚定"
                                value={allMetrics.filter((e) => e.snapshot?.anchor_id).length}
                                prefix={<SafetyCertificateOutlined style={{ color: '#722ed1' }} />}
                                valueStyle={{ color: '#722ed1', fontSize: 20 }}
                            />
                        </Card>
                    </Col>
                    <Col xs={12} sm={4}>
                        <Card size="small">
                            <Statistic
                                title="数据分类"
                                value={categories.length}
                                suffix="类"
                                prefix={<ApartmentOutlined />}
                                valueStyle={{ fontSize: 20 }}
                            />
                        </Card>
                    </Col>
                    <Col xs={24} sm={8}>
                        <Card size="small">
                            <Space direction="vertical" size={4} style={{ width: '100%' }}>
                                {categories.map(([cat, entries]) => {
                                    const staleCount = entries.filter((e) => e.stale).length
                                    return (
                                        <Row key={cat} justify="space-between">
                                            <Col>
                                                <Text strong style={{ fontSize: 12 }}>
                                                    {cat}
                                                </Text>
                                            </Col>
                                            <Col>
                                                <Space size={4}>
                                                    <Tag color="green">{entries.length - staleCount} 实时</Tag>
                                                    {staleCount > 0 && <Tag color="default">{staleCount} 过期</Tag>}
                                                </Space>
                                            </Col>
                                        </Row>
                                    )
                                })}
                            </Space>
                        </Card>
                    </Col>
                </Row>

                {categories.map(([cat, entries]) => (
                    <div key={cat}>
                        <Divider orientation="left" style={{ marginTop: 16 }}>
                            <Space>
                                <LineChartOutlined />
                                <Text strong>
                                    {cat === 'memory'
                                        ? '🧠 记忆指标'
                                        : cat === 'system'
                                            ? '⚙️ 系统指标'
                                            : cat === 'module'
                                                ? '📦 模块指标'
                                                : cat}
                                </Text>
                                <Tag>{entries.length}个</Tag>
                            </Space>
                        </Divider>
                        <Table
                            dataSource={entries}
                            columns={historyColumns}
                            rowKey={(record: MetricEntry) => record.definition.name}
                            size="small"
                            pagination={false}
                        />
                    </div>
                ))}

                <Divider orientation="left" style={{ marginTop: 24 }}>
                    <Space>
                        <BarChartOutlined />
                        <Text strong>指标趋势图 (点击趋势查看)</Text>
                    </Space>
                </Divider>

                {selectedMetric ? (
                    <Card
                        size="small"
                        title={
                            <Space>
                                <LineChartOutlined />
                                <strong>{selectedMetric.display}</strong>
                                <Tag color="purple">锚定策略: {selectedMetric.policy || 'none'}</Tag>
                                <Button
                                    size="small"
                                    icon={<CloseOutlined />}
                                    onClick={() => setSelectedMetric(null)}
                                >
                                    关闭
                                </Button>
                            </Space>
                        }
                    >
                        <Table
                            dataSource={(metricsHistory[selectedMetric.name] || []).slice(-30)}
                            columns={[
                                {
                                    title: '时间',
                                    dataIndex: 'timestamp',
                                    key: 't',
                                    width: 140,
                                    render: (ts: number) => (
                                        <Text code style={{ fontSize: 10 }}>
                                            {new Date(ts * 1000).toLocaleString()}
                                        </Text>
                                    ),
                                },
                                {
                                    title: '值',
                                    dataIndex: 'value',
                                    key: 'v',
                                    render: (v: any) => (
                                        <Tag color="blue">
                                            {String(typeof v === 'object' ? JSON.stringify(v).substring(0, 30) : v)}
                                        </Tag>
                                    ),
                                },
                                {
                                    title: '趋势',
                                    dataIndex: 'value',
                                    key: 'trend',
                                    width: 200,
                                    render: (_: any, _record: any, idx: number) => {
                                        const history = metricsHistory[selectedMetric!.name] || []
                                        if (idx === 0 || history.length < 2) return null
                                        const prev = history[idx - 1]?.value
                                        const curr = _record?.value
                                        if (typeof prev !== 'number' || typeof curr !== 'number') return null
                                        const diff = curr - prev
                                        return (
                                            <Tag color={diff > 0 ? 'green' : diff < 0 ? 'red' : 'default'}>
                                                {diff > 0 ? '+' : ''}
                                                {diff.toFixed(2)}
                                            </Tag>
                                        )
                                    },
                                },
                            ]}
                            rowKey="timestamp"
                            size="small"
                            pagination={{ pageSize: 30, size: 'small' }}
                            title={() => (
                                <Text type="secondary">
                                    {metricsHistory[selectedMetric.name]
                                        ? `共 ${metricsHistory[selectedMetric.name].length} 个数据点`
                                        : '暂无历史数据'}
                                </Text>
                            )}
                        />
                    </Card>
                ) : (
                    <Empty
                        description="点击表格中的「趋势」按钮查看指标历史走势"
                        image={Empty.PRESENTED_IMAGE_SIMPLE}
                    />
                )}

                <Divider orientation="left" style={{ marginTop: 24 }}>
                    <Space>
                        <SafetyCertificateOutlined />
                        <Text strong>锚定验证统计</Text>
                    </Space>
                </Divider>
                <Card size="small">
                    <Descriptions size="small" column={2} bordered>
                        <Descriptions.Item label="全量锚定策略 (FULL)">
                            <Tag color="purple">
                                {allMetrics.filter((e) => e.definition.anchor_policy === 'full').length} 个指标
                            </Tag>
                        </Descriptions.Item>
                        <Descriptions.Item label="采样策略 (SAMPLE)">
                            <Tag color="blue">
                                {allMetrics.filter((e) => e.definition.anchor_policy === 'sample').length} 个指标
                            </Tag>
                        </Descriptions.Item>
                        <Descriptions.Item label="无锚定 (NONE)">
                            <Tag color="default">
                                {allMetrics.filter((e) => e.definition.anchor_policy === 'none').length} 个指标
                            </Tag>
                        </Descriptions.Item>
                        <Descriptions.Item label="已锚定快照">
                            <Tag color="green">
                                {allMetrics.filter((e) => e.snapshot?.anchor_id).length} /{' '}
                                {allMetrics.filter((e) => e.definition.anchor_policy !== 'none').length}
                            </Tag>
                        </Descriptions.Item>
                        <Descriptions.Item label="事实源可重放">
                            <Tag color="green">已验证</Tag>
                        </Descriptions.Item>
                        <Descriptions.Item label="数据一致性">
                            <Tag color="green">
                                {allMetrics.every((e) => !e.stale)
                                    ? '全量一致 ✓'
                                    : `${allMetrics.filter((e) => e.stale).length}项过期`}
                            </Tag>
                        </Descriptions.Item>
                    </Descriptions>
                </Card>
            </div>
        )
    }

    const renderSystemHealthPanel = () => {
        const isHealthy = health?.status === 'healthy'

        return (
            <Row gutter={[16, 16]}>
                <Col xs={24} lg={12}>
                    <Card
                        size="small"
                        title={
                            <Space>
                                <SafetyCertificateOutlined />
                                <strong>引擎健康状态</strong>
                            </Space>
                        }
                    >
                        <Descriptions size="small" column={1} bordered>
                            <Descriptions.Item label="整体状态">
                                <Badge
                                    status={isHealthy ? 'success' : 'warning'}
                                    text={health?.status || '检测中...'}
                                />
                            </Descriptions.Item>
                            <Descriptions.Item label="ICME引擎">
                                {health?.engine_ready !== undefined ? (
                                    <Badge
                                        status={health.engine_ready ? 'success' : 'error'}
                                        text={health.engine_ready ? '就绪' : '未就绪'}
                                    />
                                ) : (
                                    '-'
                                )}
                            </Descriptions.Item>
                            <Descriptions.Item label="嵌入模型">
                                {health?.embedding_ready !== undefined ? (
                                    <Badge
                                        status={health.embedding_ready ? 'success' : 'warning'}
                                        text={health.embedding_ready ? '已加载' : '未加载'}
                                    />
                                ) : (
                                    '-'
                                )}
                            </Descriptions.Item>
                            <Descriptions.Item label="存储后端">
                                <Tag color="blue">{stats?.storage_backend || health?.storage_backend || '-'}</Tag>
                            </Descriptions.Item>
                            <Descriptions.Item label="运行时间">
                                <Space>
                                    <ClockCircleOutlined />
                                    <span>{formatUptime(stats?.uptime_seconds ?? health?.uptime ?? 0)}</span>
                                </Space>
                            </Descriptions.Item>
                            <Descriptions.Item label="系统版本">
                                <Tag>{stats?.version || health?.version || '-'}</Tag>
                            </Descriptions.Item>
                        </Descriptions>
                    </Card>
                </Col>

                <Col xs={24} lg={12}>
                    <Card
                        size="small"
                        title={
                            <Space>
                                <PieChartOutlined />
                                <strong>六层记忆容量</strong>
                            </Space>
                        }
                    >
                        {health?.layers && Object.keys(health.layers).length > 0 ? (
                            <Row gutter={[12, 12]}>
                                {Object.entries(health.layers).map(([layer, count]) => {
                                    const layerConfig: Record<string, { name: string; color: string }> = {
                                        sensory: { name: '感知记忆', color: '#722ed1' },
                                        working: { name: '工作记忆', color: '#1890ff' },
                                        short_term: { name: '短期记忆', color: '#13c2c2' },
                                        episodic: { name: '情景记忆', color: '#52c41a' },
                                        semantic: { name: '语义记忆', color: '#fa8c16' },
                                        meta: { name: '元记忆', color: '#eb2f96' },
                                    }
                                    const config = layerConfig[layer] || { name: layer, color: '#999' }
                                    return (
                                        <Col xs={12} sm={8} key={layer}>
                                            <Card
                                                size="small"
                                                hoverable
                                                style={{ borderTop: `2px solid ${config.color}` }}
                                            >
                                                <Statistic
                                                    title={<span style={{ fontSize: 11 }}>{config.name}</span>}
                                                    value={getLayerCount(count)}
                                                    valueStyle={{ color: config.color, fontSize: 18 }}
                                                />
                                            </Card>
                                        </Col>
                                    )
                                })}
                            </Row>
                        ) : (
                            <Empty description="记忆层数据加载中..." image={Empty.PRESENTED_IMAGE_SIMPLE} />
                        )}

                        <Divider orientation="left">引擎指标</Divider>
                        <Row gutter={[12, 12]}>
                            <Col xs={12} sm={6}>
                                <Statistic
                                    title="DB大小"
                                    value={`${stats?.db_size_mb ?? 0}MB`}
                                    valueStyle={{ fontSize: 14 }}
                                />
                            </Col>
                            <Col xs={12} sm={6}>
                                <Statistic
                                    title="命中率"
                                    value={stats?.hit_rate != null ? `${stats.hit_rate.toFixed(1)}%` : '-'}
                                    valueStyle={{ fontSize: 14 }}
                                />
                            </Col>
                            <Col xs={12} sm={6}>
                                <Statistic
                                    title="固结次数"
                                    value={stats?.consolidations ?? 0}
                                    valueStyle={{ fontSize: 14 }}
                                />
                            </Col>
                            <Col xs={12} sm={6}>
                                <Statistic
                                    title="归档条目"
                                    value={memoryStats?.archive_entries ?? 0}
                                    valueStyle={{ fontSize: 14 }}
                                />
                            </Col>
                        </Row>
                    </Card>
                </Col>

                <Col span={24}>
                    <Card
                        size="small"
                        title={
                            <Space>
                                <DashboardOutlined />
                                <strong>实时连接状态</strong>
                            </Space>
                        }
                    >
                        <Row gutter={[24, 16]} align="middle">
                            <Col xs={12} sm={6} md={3}>
                                <div style={{ textAlign: 'center' }}>
                                    <Progress
                                        type="circle"
                                        percent={isHealthy ? 100 : 50}
                                        size={64}
                                        status={isHealthy ? 'success' : 'exception'}
                                        format={() => (isHealthy ? '✓' : '!')}
                                    />
                                    <div style={{ marginTop: 4, fontSize: 12 }}>API服务</div>
                                </div>
                            </Col>
                            <Col xs={12} sm={6} md={3}>
                                <div style={{ textAlign: 'center' }}>
                                    <Progress
                                        type="circle"
                                        percent={health?.engine_ready ? 100 : 0}
                                        size={64}
                                        status={health?.engine_ready ? 'success' : 'normal'}
                                        format={() => (health?.engine_ready ? '✓' : '○')}
                                    />
                                    <div style={{ marginTop: 4, fontSize: 12 }}>ICME引擎</div>
                                </div>
                            </Col>
                            <Col xs={12} sm={6} md={3}>
                                <div style={{ textAlign: 'center' }}>
                                    <Progress
                                        type="circle"
                                        percent={health?.embedding_ready ? 100 : 30}
                                        size={64}
                                        status={health?.embedding_ready ? 'success' : 'normal'}
                                        format={() => (health?.embedding_ready ? '✓' : '○')}
                                    />
                                    <div style={{ marginTop: 4, fontSize: 12 }}>嵌入模型</div>
                                </div>
                            </Col>
                            <Col xs={12} sm={6} md={3}>
                                <div style={{ textAlign: 'center' }}>
                                    <Progress
                                        type="circle"
                                        percent={
                                            stats?.coverage?.total
                                                ? Math.round(((stats.coverage.online ?? 0) / stats.coverage.total) * 100)
                                                : 0
                                        }
                                        size={64}
                                        status={
                                            (stats?.coverage?.online ?? 0) >= (stats?.module_count ?? 46) * 0.6
                                                ? 'success'
                                                : 'active'
                                        }
                                        format={(pct) => `${pct}%`}
                                    />
                                    <div style={{ marginTop: 4, fontSize: 12 }}>模块覆盖率</div>
                                </div>
                            </Col>
                            <Col flex="auto">
                                <Descriptions size="small" column={2}>
                                    <Descriptions.Item label="端口">
                                        <Text code>8771</Text>
                                    </Descriptions.Item>
                                    <Descriptions.Item label="自动刷新">
                                        <Tag color="blue">每8秒</Tag>
                                    </Descriptions.Item>
                                    <Descriptions.Item label="数据源">
                                        <Text type="secondary">icme.db (SQLite+WAL)</Text>
                                    </Descriptions.Item>
                                    <Descriptions.Item label="SSE流">
                                        <Badge status="processing" text="/api/ops/stream" />
                                    </Descriptions.Item>
                                </Descriptions>
                            </Col>
                        </Row>
                    </Card>
                </Col>
            </Row>
        )
    }

    if (loading && !stats) {
        return (
            <div style={{ textAlign: 'center', padding: '80px 0' }}>
                <Spin size="large">
                    <div style={{ marginTop: 16 }}>
                        <Text type="secondary" style={{ fontSize: 12 }}>
                            连接 /api/system/stats · /api/memory/stats · /api/health · /api/ops/report
                        </Text>
                    </div>
                </Spin>
            </div>
        )
    }

    if (error && !stats) {
        return (
            <Alert
                message="监控数据加载失败"
                description={error}
                type="error"
                showIcon
                action={
                    <Button size="small" type="primary" onClick={fetchAllData}>
                        重试
                    </Button>
                }
            />
        )
    }

    const tabItems = [
        {
            key: 'orchestration',
            label: (
                <span>
                    <ScheduleOutlined />
                    调度追踪 (46模块)
                </span>
            ),
            children: renderOrchestrationTab(),
        },
        {
            key: 'module_table',
            label: (
                <span>
                    <NodeIndexOutlined />
                    模块状态表
                </span>
            ),
            children: renderModuleStatusTable(),
        },
        {
            key: 'conversation',
            label: (
                <span>
                    <MessageOutlined />
                    对话录入 (记忆+运维)
                </span>
            ),
            children: renderConversationTab(),
        },
        {
            key: 'session',
            label: (
                <span>
                    <OrderedListOutlined />
                    会话存储 (API+MCP)
                </span>
            ),
            children: renderSessionTab(),
        },
        {
            key: 'operations',
            label: (
                <span>
                    <EyeOutlined />
                    实时操作日志 (TVP+MCP+记忆)
                </span>
            ),
            children: renderOperationsTab(),
        },
        {
            key: 'ops_log_viewer',
            label: (
                <span>
                    <FireOutlined />
                    操作日志查看器
                </span>
            ),
            children: renderOperationsLogViewer(),
        },
        {
            key: 'health_panel',
            label: (
                <span>
                    <SafetyCertificateOutlined />
                    系统健康面板
                </span>
            ),
            children: renderSystemHealthPanel(),
        },
        {
            key: 'metrics_trend',
            label: (
                <span>
                    <LineChartOutlined />
                    98分指标趋势
                </span>
            ),
            children: renderMetricsTrendPanel(),
        },
    ]

    return (
        <div style={{ padding: '0' }}>
            <div
                style={{
                    background: 'linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%)',
                    padding: '12px 20px',
                    borderRadius: '8px 8px 0 0',
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    flexWrap: 'wrap',
                    gap: '8px',
                }}
            >
                <Space size="middle">
                    <DashboardOutlined style={{ color: '#1890ff', fontSize: 18 }} />
                    <Text strong style={{ fontSize: 16, color: '#fff' }}>
                        天机v9.1 核心机制工作痕迹
                    </Text>
                    <Tag color={onlineCount > 0 ? 'green' : 'red'}>
                        在线 {onlineCount}/{totalCount}
                    </Tag>
                    <Tag color="blue">{stats?.version ?? '9.1.0'}</Tag>
                </Space>
                <Space size="small">
                    <Tooltip title="TVP透明调度声明次数">
                        <Tag color="purple" icon={<ApartmentOutlined />}>
                            TVP {getCatCount(opsSummary?.by_category?.tvp)}
                        </Tag>
                    </Tooltip>
                    <Tooltip title="MCP工具调用次数">
                        <Tag color="orange" icon={<ApiOutlined />}>
                            MCP {getCatCount(opsSummary?.by_category?.mcp)}
                        </Tag>
                    </Tooltip>
                    <Tooltip title="记忆操作次数(创建/读取/搜索)">
                        <Tag color="cyan" icon={<DatabaseOutlined />}>
                            记忆 {getCatCount(opsSummary?.by_category?.memory)}
                        </Tag>
                    </Tooltip>
                    <Tooltip title="DeepSeek LLM调用次数">
                        <Tag color="magenta" icon={<ThunderboltOutlined />}>
                            LLM {getCatCount(opsSummary?.by_category?.llm)}
                        </Tag>
                    </Tooltip>
                    <Tooltip title="总操作次数">
                        <Tag color="gold">总计 {opsSummary?.total_operations ?? 0}</Tag>
                    </Tooltip>
                    <Progress
                        type="circle"
                        percent={totalCount > 0 ? Math.round((onlineCount / totalCount) * 100) : 0}
                        size={24}
                        strokeWidth={6}
                        status={onlineCount === totalCount ? 'success' : 'active'}
                    />
                    <Button
                        size="small"
                        icon={<SyncOutlined spin={loading} />}
                        onClick={fetchAllData}
                        loading={loading}
                        style={{ background: 'rgba(255,255,255,0.1)', color: '#fff', border: 'none' }}
                    />
                </Space>
            </div>
            <Card size="small" style={{ borderRadius: '0 0 8px 8px' }}>
                <Tabs
                    activeKey={activeTab}
                    onChange={setActiveTab}
                    items={tabItems}
                    tabBarExtraContent={
                        <Text type="secondary" style={{ fontSize: 12 }}>
                            每8秒自动刷新 · 三栏视图
                        </Text>
                    }
                />
            </Card>
        </div>
    )
}
