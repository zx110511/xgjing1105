import { useState, useEffect, ReactNode } from 'react'
import {
    Row,
    Col,
    Card,
    Statistic,
    Tag,
    Spin,
    Alert,
    Progress,
    Timeline,
    Badge,
    Tooltip,
    Typography,
    Tabs,
    Table,
    Space,
    Descriptions,
    Button,
    Empty,
    message,
} from 'antd'
import { MetricsLatestResponse, MetricEntry } from '../types/metrics'
import { metricsService } from '../services/metrics-service'
import {
    DatabaseOutlined,
    ApartmentOutlined,
    ThunderboltOutlined,
    SyncOutlined,
    TeamOutlined,
    ApiOutlined,
    AimOutlined,
    CloudServerOutlined,
    ExperimentOutlined,
    ScheduleOutlined,
    ToolOutlined,
    RocketOutlined,
    LineChartOutlined,
    HistoryOutlined,
    BarChartOutlined,
    DashboardOutlined,
    PieChartOutlined,
    FilterOutlined,
    FireOutlined,
    SearchOutlined,
    SafetyOutlined,
    SettingOutlined,
    LockOutlined,
    TrophyOutlined,
    FileProtectOutlined,
    BulbOutlined,
    ControlOutlined,
} from '@ant-design/icons'
import { api, operationsApi, memoryApi } from '../services/api'
import TrendChart, { mapSnapshotsToTrend } from '../components/TrendChart'

const { Text, Title } = Typography

interface SystemModuleStats {
    [key: string]: any
}

interface DimensionsData {
    realtime: {
        [key: string]: {
            status: string
            last_update?: number
            key_metrics?: any
        }
    }
    cumulative: {
        [key: string]: {
            [key: string]: any
            _meta?: {
                collection_start: number
                total_fields: number
            }
        }
    }
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

interface SystemStatsResponse {
    timestamp: number
    version: string
    dimensions: DimensionsData
    modules: SystemModuleStats
    module_count: number
    coverage: {
        total: number
        online: number
        with_stats: number
    }
    summary?: any
    memory_total?: number
    uptime_seconds?: number
    hit_rate?: number
    storage_backend?: string
    consolidations?: number
    db_size_mb?: number
    memory_by_layer?: Record<string, number>
    error?: string
    fallback?: any
}

const MODULE_CONFIG_3D = {
    engine: {
        icon: <DashboardOutlined />,
        title: 'ICME核心引擎',
        color: '#1890ff',
        category: 'core',
        realtime_fields: ['consolidations', 'uptime_seconds'],
        cumulative_fields: ['consolidations', 'uptime_seconds'],
        history_trend: 'engine_throughput',
    },
    deepseek_driver: {
        icon: <AimOutlined />,
        title: 'DeepSeek大脑',
        color: '#722ed1',
        category: 'brain',
        realtime_fields: ['events', 'decisions'],
        cumulative_fields: ['events', 'decisions'],
        history_trend: 'decision_rate',
    },
    enforcement_hook: {
        icon: <CloudServerOutlined />,
        title: '强制记录钩子',
        color: '#fa8c16',
        category: 'enforcement',
        realtime_fields: ['captured', 'stored'],
        cumulative_fields: ['captured', 'stored'],
        history_trend: 'compliance_trend',
    },
    chain_dashboard: {
        icon: <RocketOutlined />,
        title: '8链能力仪表盘',
        color: '#1890ff',
        category: 'core',
        realtime_fields: ['captured', 'events'],
        cumulative_fields: ['events', 'decisions'],
        history_trend: 'chain_health',
    },
    quality_gate: {
        icon: <SafetyOutlined />,
        title: '质量门禁 (Consumer-Aware)',
        color: '#fa8c16',
        category: 'core',
        realtime_fields: ['captured', 'stored'],
        cumulative_fields: ['captured', 'stored'],
        history_trend: 'quality_trend',
    },
    memory_api: {
        icon: <DatabaseOutlined />,
        title: '天机记忆API',
        color: '#1890ff',
        category: 'core',
        realtime_fields: ['total_entries', 'hit_rate'],
        cumulative_fields: ['total_entries', 'total_entries'],
        history_trend: 'api_throughput',
    },
    standards_compliance: {
        icon: <FileProtectOutlined />,
        title: '标准合规 (P15-P17)',
        color: '#52c41a',
        category: 'core',
        realtime_fields: ['captured', 'stored'],
        cumulative_fields: ['captured', 'stored'],
        history_trend: 'compliance_score',
    },
    api_exposure: {
        icon: <ApiOutlined />,
        title: 'API暴露层',
        color: '#2f54eb',
        category: 'core',
        realtime_fields: ['captured', 'events'],
        cumulative_fields: ['captured', 'events'],
        history_trend: 'api_traffic',
    },
    intelligent_scheduler: {
        icon: <ScheduleOutlined />,
        title: '智能调度器',
        color: '#faad14',
        category: 'scheduling',
        realtime_fields: ['tasks_executed', 'events'],
        cumulative_fields: ['events', 'decisions'],
        history_trend: 'scheduling_efficiency',
    },
    learning_loop: {
        icon: <ExperimentOutlined />,
        title: '闭环学习引擎',
        color: '#13c2c2',
        category: 'learning',
        realtime_fields: ['captured', 'events'],
        cumulative_fields: ['captured', 'events'],
        history_trend: 'learning_rate',
    },
    knowledge_extractor: {
        icon: <BulbOutlined />,
        title: '知识抽取器',
        color: '#722ed1',
        category: 'learning',
        realtime_fields: ['captured', 'events'],
        cumulative_fields: ['captured', 'events'],
        history_trend: 'extraction_quality',
    },
    hybrid_engine: {
        icon: <SearchOutlined />,
        title: '混合检索引擎',
        color: '#fa8c16',
        category: 'infrastructure',
        realtime_fields: ['captured', 'events'],
        cumulative_fields: ['captured', 'events'],
        history_trend: 'search_performance',
    },
    resilience: {
        icon: <ControlOutlined />,
        title: '韧性降级管理器',
        color: '#f5222d',
        category: 'infrastructure',
        realtime_fields: ['captured', 'events'],
        cumulative_fields: ['captured', 'events'],
        history_trend: 'resilience_score',
    },
    encoding_safe: {
        icon: <LockOutlined />,
        title: '编码安全模块',
        color: '#fa8c16',
        category: 'infrastructure',
        realtime_fields: ['captured', 'events'],
        cumulative_fields: ['captured', 'events'],
        history_trend: 'encoding_safety',
    },
    search_indexer: {
        icon: <FilterOutlined />,
        title: '语义索引器',
        color: '#2f54eb',
        category: 'infrastructure',
        realtime_fields: ['captured', 'events'],
        cumulative_fields: ['captured', 'events'],
        history_trend: 'indexing_rate',
    },
} as const

export default function Dashboard() {
    const [loading, setLoading] = useState(true)
    const [stats, setStats] = useState<SystemStatsResponse | null>(null)
    const [error, setError] = useState<string | null>(null)
    const [activeDimension, setActiveDimension] = useState<'realtime' | 'cumulative' | 'history'>(
        'realtime'
    )
    const [opsLog, setOpsLog] = useState<any[]>([])
    const [memoryLayerData, setMemoryLayerData] = useState<Record<
        string,
        number | { entry_count?: number;[key: string]: any }
    > | null>(null)
    const [opsSummary, setOpsSummary] = useState<any>(null)
    const [metricsData, setMetricsData] = useState<MetricsLatestResponse | null>(null)
    const [metricsLoading, setMetricsLoading] = useState(false)
    const [activatingModule, setActivatingModule] = useState<string | null>(null)
    const [chainScores, setChainScores] = useState<
        Array<{
            key: string
            name: string
            module: string
            composite: number
            features: string
            color: string
        }>
    >([])
    const [standardScores, setStandardScores] = useState<
        Array<{ standard: string; pct: number; tag: string }>
    >([])
    const [capabilityMatrix, setCapabilityMatrix] = useState<
        Array<{ module: string; composite: string; grade: string; deliverables: string }>
    >([])
    const [governanceLoaded, setGovernanceLoaded] = useState(false)
    const [showTrendChart, setShowTrendChart] = useState(false)

    useEffect(() => {
        fetchStats()
        fetchGovernanceData()
        const interval = setInterval(fetchStats, 10000)
        return () => clearInterval(interval)
    }, [])

    const fetchGovernanceData = async () => {
        try {
            const res = await api.get('/api/governance/status')
            if (res?.chains) {
                const CHAIN_COLORS = [
                    '#52c41a',
                    '#1890ff',
                    '#fa8c16',
                    '#722ed1',
                    '#13c2c2',
                    '#eb2f96',
                    '#2f54eb',
                    '#f5222d',
                ]
                setChainScores(
                    res.chains.map((c: any, i: number) => ({
                        key: c.key || c.name,
                        name: c.name || c.key,
                        module: c.module || 'engine',
                        composite: c.composite || c.score || 0,
                        features: c.features || c.description || '',
                        color: CHAIN_COLORS[i % CHAIN_COLORS.length],
                    }))
                )
            }
            if (res?.standards) {
                setStandardScores(
                    res.standards.map((s: any) => ({
                        standard: s.name || s.standard || s.key,
                        pct: s.score || s.pct || 0,
                        tag: s.tag || s.deliverable || '',
                    }))
                )
            }
            if (res?.capabilities) {
                setCapabilityMatrix(
                    res.capabilities.map((c: any) => ({
                        module: c.module || c.name,
                        composite: String(c.composite || c.score || 0),
                        grade: c.grade || 'N/A',
                        deliverables: c.deliverables || c.description || '',
                    }))
                )
            }
            setGovernanceLoaded(true)
        } catch {
            setGovernanceLoaded(true)
        }
    }

    const fetchStats = async () => {
        try {
            setLoading(true)
            // 真实数据源：/api/system/stats（失败时由外层 catch 统一提示错误，不做死降级）
            const response: any = await api.get('/api/system/stats')

            if (response) {
                setStats(response)
                setMemoryLayerData(response.memory_by_layer ?? null)
            }

            const [opsLogRes, opsSumRes, memStatsRes] = await Promise.allSettled([
                operationsApi.getLog({ limit: 20 }),
                operationsApi.getSummary(),
                memoryApi.getStats(),
            ])

            if (opsLogRes.status === 'fulfilled' && opsLogRes.value?.entries) {
                setOpsLog((opsLogRes.value?.data ?? opsLogRes.value).entries)
            }
            if (opsSumRes.status === 'fulfilled') {
                setOpsSummary(opsSumRes.value?.data ?? opsSumRes.value)
            }
            if (memStatsRes.status === 'fulfilled') {
                const m = memStatsRes.value?.data ?? memStatsRes.value
                setMemoryLayerData(m.layers ?? m.memory_by_layer ?? null)
            }

            setError(null)
        } catch (err) {
            console.error('Failed to fetch system stats:', err)
            setError('无法连接到系统统计服务')
        } finally {
            setLoading(false)
        }
    }

    const fetchMetrics = async () => {
        setMetricsLoading(true)
        try {
            const data = await metricsService.getLatest()
            setMetricsData(data)
        } catch (err) {
            console.error('Failed to fetch metrics:', err)
        } finally {
            setMetricsLoading(false)
        }
    }

    useEffect(() => {
        fetchMetrics()
        const metricsInterval = setInterval(fetchMetrics, 15000)
        return () => clearInterval(metricsInterval)
    }, [])

    const getNestedValue = (obj: any, path: string): any => {
        if (!obj || !path) return undefined
        const keys = path.split('.')
        let current = obj
        for (const key of keys) {
            if (current === null || current === undefined || typeof current !== 'object') {
                return undefined
            }
            current = current[key]
        }
        return current
    }

    const formatValue = (value: any, formatFn?: (v: any) => string): string => {
        if (value === null || value === undefined) return '-'
        if (formatFn) return formatFn(value)
        if (typeof value === 'boolean') return value ? '✅ 是' : '❌ 否'
        if (typeof value === 'number') return value.toLocaleString()
        return String(value)
    }

    const renderRealtimeView = () => {
        const memTotal = stats?.memory_total ?? 0
        const uptime = stats?.uptime_seconds ?? 0
        const onlineCount = stats?.coverage?.online ?? 0
        const storage = stats?.storage_backend ?? 'sqlite'

        const getModuleDisplayValue = (
            key: string,
            _config: any
        ): { value: number; label: string; suffix?: string } => {
            const realtimeData = stats?.dimensions?.realtime?.[key]
            const moduleData = stats?.modules?.[key]
            const isOnline = realtimeData?.status === 'pend_active' || realtimeData?.status === 'online'
            const isAvailable = realtimeData?.status === 'available'

            if (!isOnline && !isAvailable) return { value: 0, label: '未安装' }
            if (!isOnline && isAvailable) return { value: 0, label: '可激活' }

            const km = (realtimeData?.key_metrics || moduleData || {}) as Record<string, unknown>
            const META_KEYS = new Set([
                'state',
                'runs',
                'last_run',
                'interval',
                'thread_active',
                'mode',
                'buffer_size',
                'subscribers',
                'total_bytes',
                'last_content_preview',
            ])
            const bestMetric = (): { value: number; label: string } | null => {
                if (!km || typeof km !== 'object') return null
                const nums = Object.entries(km).filter(
                    ([k, v]) => !META_KEYS.has(k) && typeof v === 'number'
                )
                if (!nums.length) return null
                const [k, v] = nums.reduce((a, b) => ((a[1] as number) > (b[1] as number) ? a : b))
                return { value: v as number, label: k }
            }

            if (key === 'deepseek_driver')
                return { value: uptime > 0 ? 1 : 0, label: uptime > 0 ? '已激活' : '待命' }
            if (key === 'auto_capture') return { value: Number(km?.captured ?? 0), label: '已捕获' }
            if (key === 'backup_manager') return { value: Number(km?.backups ?? 0), label: '次备份' }
            if (key === 'enforcement_hook')
                return { value: Number(km?.intercepted ?? km?.captured ?? 0), label: '已拦截' }
            if (key === 'workflow_engine') {
                const wf = Number(km?.registered_workflows ?? km?.active_executions ?? 0)
                return { value: wf, label: '工作流' }
            }
            if (key === 'message_gateway') return { value: 1, label: 'trae_ide' }
            if (key === 'evolution_engine' || key === 'evolution_loop')
                return {
                    value: Number(km?.cycles ?? km?.triggered ?? Math.floor(uptime / 300)),
                    label: '循环',
                }
            if (key === 'intelligent_scheduler' || key === 'agent_scheduler')
                return { value: Number(km?.dispatched ?? km?.completed ?? onlineCount), label: '已调度' }
            if (key === 'tvp_bridge' || key === 'async_bridge')
                return { value: isOnline ? 1 : 0, label: '运行中' }
            if (key === 'skill_registry' || key === 'learning_engine') {
                const bm = bestMetric()
                if (bm) return bm
            }

            const bm = bestMetric()
            if (bm) return bm
            return { value: isOnline ? 1 : 0, label: '在线' }
        }

        return (
            <Row gutter={[16, 16]}>
                <Col span={24}>
                    <Card
                        size="small"
                        title={
                            <Space>
                                <LineChartOutlined />
                                <strong>实时状态监控 (29核心模块 v9.1.0 全链路交付)</strong>
                            </Space>
                        }
                    >
                        {(() => {
                            const categories = [
                                'core',
                                'brain',
                                'scheduling',
                                'communication',
                                'evolution',
                                'monitoring',
                                'infrastructure',
                                'learning',
                            ] as const
                            const categoryNames: Record<string, string> = {
                                core: '核心层',
                                brain: '智能决策',
                                scheduling: '编排调度',
                                communication: '通信协议',
                                evolution: '进化学习',
                                monitoring: '监控观测',
                                infrastructure: '基础设施',
                                learning: '学习引擎',
                            }
                            return categories.map((cat) => {
                                const catModules = Object.entries(MODULE_CONFIG_3D).filter(
                                    ([, c]) => c.category === cat
                                )
                                if (catModules.length === 0) return null
                                return (
                                    <div key={cat} style={{ marginBottom: 16 }}>
                                        <Title level={5} style={{ margin: '12px 0 8px' }}>
                                            {categoryNames[cat] || cat} ({catModules.length})
                                        </Title>
                                        <Row gutter={[12, 12]}>
                                            {catModules.map(([key, config]) => {
                                                const realtimeData = stats?.dimensions?.realtime?.[key]
                                                const display = getModuleDisplayValue(key, config)
                                                const status = realtimeData?.status || 'unavailable'
                                                const isOnline = status === 'pend_active' || status === 'online'
                                                const isAvailable = status === 'available'
                                                const statusColor = isOnline ? 'green' : isAvailable ? 'orange' : 'default'
                                                const statusLabel = isOnline ? '在线' : isAvailable ? '可激活' : '未安装'
                                                const valueColor = isOnline
                                                    ? config.color
                                                    : isAvailable
                                                        ? '#faad14'
                                                        : '#d9d9d9'
                                                const handleActivate = async () => {
                                                    setActivatingModule(key)
                                                    try {
                                                        const res = await api.post<{ status: string; detail?: string }>(
                                                            `/api/container/module/${key}/activate`
                                                        )
                                                        if (res.status === 'activated' || res.status === 'already_active') {
                                                            message.success(`${config.title} 激活成功！`)
                                                            fetchStats()
                                                        } else {
                                                            message.warning(res.detail || '激活异常')
                                                        }
                                                    } catch (e: any) {
                                                        message.error(`激活失败: ${e.message}`)
                                                    } finally {
                                                        setActivatingModule(null)
                                                    }
                                                }
                                                const handleInstall = async () => {
                                                    setActivatingModule(key)
                                                    try {
                                                        const res = await api.post<{
                                                            status: string
                                                            message?: string
                                                            detail?: string
                                                        }>(`/api/container/module/${key}/install`)
                                                        if (res.status === 'activated') {
                                                            message.success(`${config.title} 安装并激活成功！`)
                                                            fetchStats()
                                                        } else if (res.status === 'partial') {
                                                            message.warning(res.message)
                                                        } else if (res.status === 'missing_dependency') {
                                                            message.error(res.message)
                                                        } else {
                                                            message.info(res.message || '安装处理中')
                                                        }
                                                    } catch (e: any) {
                                                        message.error(`安装失败: ${e.message}`)
                                                    } finally {
                                                        setActivatingModule(null)
                                                    }
                                                }
                                                return (
                                                    <Col xs={24} sm={12} lg={6} xl={4} key={key}>
                                                        <Card hoverable size="small" style={{ borderColor: valueColor }}>
                                                            <Statistic
                                                                title={
                                                                    <Tooltip
                                                                        title={`${config.title} — ${display.label} · 数据源: icme.db(${storage})`}
                                                                    >
                                                                        <span>
                                                                            {config.icon} {config.title}
                                                                        </span>
                                                                    </Tooltip>
                                                                }
                                                                value={display.value}
                                                                prefix={config.icon}
                                                                valueStyle={{ color: valueColor, fontSize: 18 }}
                                                                suffix={display.label}
                                                            />
                                                            <div
                                                                style={{
                                                                    marginTop: 4,
                                                                    display: 'flex',
                                                                    alignItems: 'center',
                                                                    gap: 4,
                                                                }}
                                                            >
                                                                <Tag color={statusColor} style={{ fontSize: 10 }}>
                                                                    {statusLabel}
                                                                </Tag>
                                                                {isOnline && realtimeData?.last_update && (
                                                                    <Text type="secondary" style={{ fontSize: 10 }}>
                                                                        {new Date(realtimeData.last_update * 1000).toLocaleTimeString()}
                                                                    </Text>
                                                                )}
                                                                {isAvailable && (
                                                                    <Button
                                                                        size="small"
                                                                        type="primary"
                                                                        loading={activatingModule === key}
                                                                        onClick={handleActivate}
                                                                        style={{ fontSize: 10, padding: '0 6px', height: 20 }}
                                                                    >
                                                                        立即激活
                                                                    </Button>
                                                                )}
                                                                {!isOnline && !isAvailable && (
                                                                    <Button
                                                                        size="small"
                                                                        type="dashed"
                                                                        loading={activatingModule === key}
                                                                        onClick={handleInstall}
                                                                        style={{ fontSize: 10, padding: '0 6px', height: 20 }}
                                                                    >
                                                                        立即安装
                                                                    </Button>
                                                                )}
                                                            </div>
                                                        </Card>
                                                    </Col>
                                                )
                                            })}
                                        </Row>
                                    </div>
                                )
                            })
                        })()}
                    </Card>
                </Col>

                <Col span={24}>
                    <Card
                        size="small"
                        title={
                            <Space>
                                <BarChartOutlined />
                                <strong>📈 系统覆盖率</strong>
                            </Space>
                        }
                    >
                        <Row gutter={[16, 16]} align="middle">
                            <Col xs={24} sm={8}>
                                <Progress
                                    type="dashboard"
                                    percent={
                                        stats?.coverage?.total
                                            ? Math.round(((stats.coverage?.online ?? 0) / stats.coverage.total) * 100)
                                            : 0
                                    }
                                    format={(percent) => `${percent}%`}
                                    status={
                                        (stats?.coverage?.online ?? 0) >= (stats?.module_count ?? 0) * 0.6
                                            ? 'success'
                                            : 'active'
                                    }
                                />
                            </Col>
                            <Col xs={24} sm={16}>
                                <Descriptions size="small" column={2}>
                                    <Descriptions.Item label="总模块数">
                                        {stats?.coverage?.total ?? stats?.module_count ?? 0}
                                    </Descriptions.Item>
                                    <Descriptions.Item label="在线模块">
                                        <Text strong style={{ color: '#52c41a' }}>
                                            {stats?.coverage?.online ?? 0}
                                        </Text>
                                    </Descriptions.Item>
                                    <Descriptions.Item label="记忆总量">
                                        <Text strong style={{ color: '#1890ff' }}>
                                            {memTotal}
                                        </Text>
                                    </Descriptions.Item>
                                    <Descriptions.Item label="运行时间">{Math.floor(uptime)}秒</Descriptions.Item>
                                    <Descriptions.Item label="存储后端">{storage}</Descriptions.Item>
                                    <Descriptions.Item label="系统版本">
                                        {stats?.version ?? '9.1.0'}
                                    </Descriptions.Item>
                                </Descriptions>
                            </Col>
                        </Row>
                    </Card>
                </Col>
            </Row>
        )
    }

    const renderCumulativeView = () => (
        <Row gutter={[16, 16]}>
            {Object.entries(MODULE_CONFIG_3D).map(([key, config]) => {
                const cumData = stats?.dimensions?.cumulative?.[key]
                const moduleData = stats?.modules?.[key]

                if (!cumData || !moduleData) {
                    return (
                        <Col xs={24} lg={12} key={key}>
                            <Card
                                size="small"
                                title={
                                    <span>
                                        {config.icon} {config.title}
                                    </span>
                                }
                            >
                                <Empty description="无累计数据" image={Empty.PRESENTED_IMAGE_SIMPLE} />
                            </Card>
                        </Col>
                    )
                }

                return (
                    <Col xs={24} lg={12} key={key}>
                        <Card
                            size="small"
                            title={
                                <Space>
                                    {config.icon}
                                    <span>{config.title}</span>
                                    <Badge count={cumData._meta?.total_fields ?? 0} showZero color="#1890ff" />
                                </Space>
                            }
                        >
                            <Descriptions size="small" column={2} bordered>
                                {config.cumulative_fields.map((fieldKey) => {
                                    const value = getNestedValue(cumData, fieldKey)
                                    return (
                                        <Descriptions.Item key={fieldKey} label={fieldKey.split('.').pop()}>
                                            {formatValue(value)}
                                        </Descriptions.Item>
                                    )
                                })}
                            </Descriptions>
                            {Object.keys(cumData).filter((k) => k !== '_module_status').length >
                                config.cumulative_fields.length && (
                                    <div style={{ marginTop: 8 }}>
                                        <Text type="secondary" style={{ fontSize: 12 }}>
                                            +
                                            {Object.keys(cumData).filter((k) => k !== '_module_status').length -
                                                config.cumulative_fields.length}{' '}
                                            更多字段
                                        </Text>
                                    </div>
                                )}
                        </Card>
                    </Col>
                )
            })}
        </Row>
    )

    const renderHistoryView = () => {
        const snapshots = stats?.dimensions?.history?.snapshots ?? []

        if (snapshots.length === 0) {
            return (
                <Alert
                    message="暂无历史数据"
                    description="系统正在收集历史快照，请稍后再查看..."
                    type="info"
                    showIcon
                />
            )
        }

        const columns = [
            {
                title: '时间戳',
                dataIndex: 'timestamp',
                key: 'timestamp',
                render: (ts: number) => new Date(ts * 1000).toLocaleString(),
            },
            {
                title: '在线模块数',
                dataIndex: 'online_modules',
                key: 'online_modules',
                render: (val: number) => <Tag color="green">{val}</Tag>,
            },
            {
                title: '总模块数',
                dataIndex: 'total_modules',
                key: 'total_modules',
            },
            {
                title: '覆盖率',
                dataIndex: 'coverage_pct',
                key: 'coverage_pct',
                render: (pct: number) => (
                    <Progress
                        percent={Math.round(pct)}
                        size="small"
                        status={pct >= 90 ? 'success' : 'active'}
                    />
                ),
            },
        ]

        return (
            <Table
                dataSource={[...snapshots].reverse()}
                columns={columns}
                rowKey="timestamp"
                size="small"
                pagination={{ pageSize: 10 }}
                title={() => (
                    <Space>
                        <HistoryOutlined />
                        <span>最近 {snapshots.length} 个历史快照（保留最近24小时）</span>
                    </Space>
                )}
            />
        )
    }

    const CATEGORY_COLOR_MAP: Record<string, string> = {
        system: '#10B981',
        container: '#6366F1',
        tvp: '#722ed1',
        mcp: '#fa8c16',
        memory: '#13c2c2',
        llm: '#eb2f96',
        ops: '#F59E0B',
    }

    const CATEGORY_ICON_MAP: Record<string, ReactNode> = {
        system: <SettingOutlined />,
        container: <CloudServerOutlined />,
        tvp: <ApartmentOutlined />,
        mcp: <ApiOutlined />,
        memory: <DatabaseOutlined />,
        llm: <ThunderboltOutlined />,
        ops: <ToolOutlined />,
    }

    const LAYER_CONFIG: Record<string, { name: string; color: string }> = {
        sensory: { name: '感知记忆', color: '#722ed1' },
        working: { name: '工作记忆', color: '#1890ff' },
        short_term: { name: '短期记忆', color: '#13c2c2' },
        episodic: { name: '情景记忆', color: '#52c41a' },
        semantic: { name: '语义记忆', color: '#fa8c16' },
        meta: { name: '元记忆', color: '#eb2f96' },
    }

    const renderModuleStatusGrid = () => {
        const modules = stats?.modules ?? {}
        const dimensions = stats?.dimensions?.realtime ?? {}
        const moduleEntries = Object.entries(modules)

        if (moduleEntries.length === 0) {
            return (
                <Card
                    size="small"
                    title={
                        <Space>
                            <TeamOutlined />
                            <strong>模块状态总览</strong>
                        </Space>
                    }
                >
                    <Empty description="暂无模块数据" image={Empty.PRESENTED_IMAGE_SIMPLE} />
                </Card>
            )
        }

        const columns = [
            {
                title: '模块名称',
                dataIndex: 'key',
                key: 'name',
                width: 180,
                render: (key: string) => {
                    const config = MODULE_CONFIG_3D[key as keyof typeof MODULE_CONFIG_3D]
                    return (
                        <Space size="small">
                            {config?.icon || <ToolOutlined />}
                            <Text strong style={{ fontSize: 13 }}>
                                {config?.title || key}
                            </Text>
                        </Space>
                    )
                },
                sorter: (a: any, b: any) => {
                    const configA = MODULE_CONFIG_3D[a.key as keyof typeof MODULE_CONFIG_3D]
                    const configB = MODULE_CONFIG_3D[b.key as keyof typeof MODULE_CONFIG_3D]
                    return (configA?.title || a.key).localeCompare(configB?.title || b.key)
                },
            },
            {
                title: '状态',
                dataIndex: 'key',
                key: 'status',
                width: 100,
                filters: [
                    { text: '在线', value: 'pend_active' },
                    { text: '离线', value: 'offline' },
                    { text: '错误', value: 'error' },
                ],
                onFilter: (value: any, record: any) => {
                    const rt = dimensions[record.key]
                    return rt?.status === value
                },
                render: (key: string) => {
                    const rt = dimensions[key]
                    if (!rt) return <Badge status="default" text="未知" />
                    if (rt.status === 'pend_active' || rt.status === 'online')
                        return <Badge status="success" text="在线" />
                    if (rt.status === 'error') return <Badge status="error" text="错误" />
                    return <Badge status="default" text="离线" />
                },
            },
            {
                title: '最后更新',
                dataIndex: 'key',
                key: 'last_update',
                width: 140,
                render: (key: string) => {
                    const rt = dimensions[key]
                    if (!rt?.last_update) return '-'
                    return new Date(rt.last_update * 1000).toLocaleTimeString()
                },
            },
            {
                title: '关键指标',
                dataIndex: 'key',
                key: 'metrics',
                render: (key: string) => {
                    const rt = dimensions[key]
                    const km = rt?.key_metrics as Record<string, unknown> | undefined

                    // 无 key_metrics 或仅 metadata → 显示 -
                    if (!km || Object.keys(km).length <= 1) return <Text type="secondary">-</Text>

                    const META_KEYS = new Set([
                        'state',
                        'runs',
                        'last_run',
                        'interval',
                        'thread_active',
                        'mode',
                        'buffer_size',
                        'subscribers',
                        'total_bytes',
                        'last_content_preview',
                        'status',
                        'ready',
                        'running',
                        'type',
                        'parent',
                        'importable',
                    ])

                    const config = MODULE_CONFIG_3D[key as keyof typeof MODULE_CONFIG_3D]
                    const tags: [string, string, string][] = []

                    // 尝试 config.realtime_fields → 从 km 读取对应值
                    if (config) {
                        for (const field of config.realtime_fields.slice(0, 2)) {
                            const val = km[field]
                            if (val !== undefined && val !== null) {
                                tags.push([field, formatValue(val), 'blue'])
                            }
                        }
                    }

                    // 实时字段未匹配 → 自动选取前2个有意义的 numeric 指标
                    if (tags.length === 0) {
                        const nums = Object.entries(km)
                            .filter(([k, v]) => !META_KEYS.has(k) && typeof v === 'number')
                            .sort(([, a], [, b]) => (b as number) - (a as number))
                            .slice(0, 2)
                        for (const [k, v] of nums) {
                            tags.push([k, formatValue(v), 'green'])
                        }
                        // 如果还是没有 → 显示任意可用字段
                        if (tags.length === 0) {
                            const other = Object.entries(km)
                                .filter(([k]) => !META_KEYS.has(k) && k !== 'state')
                                .slice(0, 2)
                            for (const [k, v] of other) {
                                tags.push([k, formatValue(v), 'default'])
                            }
                        }
                    }

                    if (tags.length === 0) return <Text type="secondary">-</Text>

                    return (
                        <Space size={4} wrap>
                            {tags.map(([label, val, color]) => (
                                <Tag key={label} color={color}>
                                    {label}: {val}
                                </Tag>
                            ))}
                        </Space>
                    )
                },
            },
        ]

        const dataSource = moduleEntries.map(([key]) => ({ key }))

        return (
            <Card
                size="small"
                title={
                    <Space>
                        <TeamOutlined />
                        <strong>模块状态总览</strong>
                        <Badge count={moduleEntries.length} showZero color="#1890ff" offset={[8, -2]} />
                    </Space>
                }
                extra={
                    <Space>
                        <Tag color="green">
                            在线:{' '}
                            {
                                Object.values(dimensions).filter(
                                    (d) => d.status === 'pend_active' || d.status === 'online'
                                ).length
                            }
                        </Tag>
                        <Tag color="red">
                            错误: {Object.values(dimensions).filter((d) => d.status === 'error').length}
                        </Tag>
                    </Space>
                }
            >
                <Table
                    dataSource={dataSource}
                    columns={columns}
                    rowKey="key"
                    size="small"
                    pagination={{
                        pageSize: 15,
                        showSizeChanger: false,
                        showTotal: (total) => `共 ${total} 个模块`,
                    }}
                    scroll={{ x: 700 }}
                    rowClassName={(record) => {
                        const rt = dimensions[record.key]
                        if (rt?.status === 'error') return 'row-error'
                        if (rt?.status !== 'pend_active' && rt?.status !== 'online') return 'row-offline'
                        return ''
                    }}
                />
            </Card>
        )
    }

    const renderOperationsTimeline = () => {
        if (!opsLog || opsLog.length === 0) {
            return (
                <Card
                    size="small"
                    title={
                        <Space>
                            <FireOutlined />
                            <strong>操作时间线</strong>
                        </Space>
                    }
                >
                    <Empty
                        description="暂无操作记录 — 操作天机功能后此处实时显示"
                        image={Empty.PRESENTED_IMAGE_SIMPLE}
                    />
                </Card>
            )
        }

        const timelineItems = opsLog.slice(0, 15).map((op: any, idx: number) => ({
            color: CATEGORY_COLOR_MAP[op.category] || 'gray',
            children: (
                <div key={idx} style={{ display: 'flex', alignItems: 'flex-start', gap: 8 }}>
                    <div style={{ flexShrink: 0, minWidth: 70 }}>
                        <Text code style={{ fontSize: 11 }}>
                            {op.time_str}
                        </Text>
                    </div>
                    <div style={{ flexShrink: 0 }}>
                        <Tag
                            color={CATEGORY_COLOR_MAP[op.category] || 'default'}
                            icon={CATEGORY_ICON_MAP[op.category]}
                            style={{ margin: 0 }}
                        >
                            {(op.category || '').toUpperCase()}
                        </Tag>
                    </div>
                    <div style={{ flex: 1, minWidth: 0 }}>
                        <Text strong style={{ fontSize: 13 }}>
                            {op.action}
                        </Text>
                        {op.detail && (
                            <div>
                                <Text type="secondary" ellipsis style={{ fontSize: 12, maxWidth: 400 }}>
                                    {op.detail}
                                </Text>
                            </div>
                        )}
                    </div>
                    <div style={{ flexShrink: 0 }}>
                        <Tag color={op.result === 'ok' ? 'success' : 'error'} style={{ margin: 0 }}>
                            {op.result?.toUpperCase()}
                        </Tag>
                    </div>
                </div>
            ),
        }))

        return (
            <Card
                size="small"
                title={
                    <Space>
                        <FireOutlined />
                        <strong>操作时间线</strong>
                        <Badge count={opsLog.length} showZero color="#722ed1" offset={[8, -2]} />
                    </Space>
                }
                extra={
                    <Space>
                        {opsSummary?.total_operations !== undefined && (
                            <Text type="secondary">总计 {opsSummary.total_operations} 次操作</Text>
                        )}
                    </Space>
                }
            >
                <Timeline items={timelineItems} />
            </Card>
        )
    }

    const renderMemoryLayerDistribution = () => {
        const layers = memoryLayerData ?? stats?.memory_by_layer ?? {}
        const layerEntries = Object.entries(layers)

        const getLayerCount = (val: any): number => {
            if (typeof val === 'number') return val
            if (val && typeof val === 'object' && typeof val.entry_count === 'number')
                return val.entry_count
            return 0
        }

        if (layerEntries.length === 0) {
            return (
                <Card
                    size="small"
                    title={
                        <Space>
                            <PieChartOutlined />
                            <strong>六层记忆分布</strong>
                        </Space>
                    }
                >
                    <Empty description="暂无记忆层数据" image={Empty.PRESENTED_IMAGE_SIMPLE} />
                </Card>
            )
        }

        const totalEntries = layerEntries.reduce((sum, [, count]) => sum + getLayerCount(count), 0)

        return (
            <Row gutter={[16, 16]}>
                {layerEntries.map(([layerKey, count]) => {
                    const numCount = getLayerCount(count)
                    const config = LAYER_CONFIG[layerKey] || { name: layerKey, color: '#999' }
                    const pct = totalEntries > 0 ? Math.round((numCount / totalEntries) * 100) : 0

                    return (
                        <Col xs={12} sm={8} lg={4} key={layerKey}>
                            <Card
                                hoverable
                                size="small"
                                style={{
                                    borderTop: `3px solid ${config.color}`,
                                    borderRadius: 8,
                                }}
                            >
                                <Statistic
                                    title={
                                        <Space size={4}>
                                            <span
                                                style={{
                                                    width: 10,
                                                    height: 10,
                                                    borderRadius: '50%',
                                                    background: config.color,
                                                    display: 'inline-block',
                                                }}
                                            />
                                            <span style={{ fontSize: 12 }}>{config.name}</span>
                                        </Space>
                                    }
                                    value={numCount}
                                    valueStyle={{ color: config.color, fontSize: 22, fontWeight: 700 }}
                                />
                                <Progress
                                    percent={pct}
                                    showInfo={false}
                                    strokeColor={config.color}
                                    trailColor="#f0f0f0"
                                    size="small"
                                    style={{ marginTop: 4 }}
                                />
                                <Text type="secondary" style={{ fontSize: 11 }}>
                                    {pct}% 占比
                                </Text>
                            </Card>
                        </Col>
                    )
                })}
                <Col span={24}>
                    <Card size="small">
                        <Row gutter={16} align="middle">
                            <Col>
                                <Statistic
                                    title="记忆总量"
                                    value={totalEntries}
                                    prefix={<DatabaseOutlined />}
                                    valueStyle={{ color: '#1890ff' }}
                                />
                            </Col>
                            <Col>
                                <Statistic
                                    title="活跃层数"
                                    value={layerEntries.filter(([, c]) => getLayerCount(c) > 0).length}
                                    suffix="/6"
                                />
                            </Col>
                            <Col flex="auto">
                                <Progress
                                    type="dashboard"
                                    percent={
                                        layerEntries.length > 0
                                            ? Math.round(
                                                (layerEntries.filter(([, c]) => getLayerCount(c) > 0).length / 6) * 100
                                            )
                                            : 0
                                    }
                                    size={80}
                                    format={(pct) => `${pct}%`}
                                    strokeColor="#52c41a"
                                />
                            </Col>
                        </Row>
                    </Card>
                </Col>
            </Row>
        )
    }

    if (loading && !stats) {
        return (
            <div style={{ textAlign: 'center', padding: '50px 0' }}>
                <Spin size="large">
                    <div>加载三维统计数据...</div>
                </Spin>
            </div>
        )
    }

    if (error) {
        return (
            <Alert
                message="数据加载失败"
                description={error}
                type="error"
                showIcon
                action={
                    <Button size="small" onClick={fetchStats}>
                        重试
                    </Button>
                }
            />
        )
    }

    const renderMetricsPanel = () => {
        if (!metricsData || metricsData.status !== 'ok') {
            return (
                <Card
                    size="small"
                    title={
                        <Space>
                            <LineChartOutlined />
                            <strong>📊 98分指标面板 (StatCollector)</strong>
                        </Space>
                    }
                >
                    <Spin spinning={metricsLoading}>
                        <Empty
                            description={metricsData ? 'StatCollector未就绪' : '正在连接采集引擎...'}
                            image={Empty.PRESENTED_IMAGE_SIMPLE}
                        />
                    </Spin>
                </Card>
            )
        }

        const categories = Object.entries(metricsData.by_category)
        const CATEGORY_COLORS: Record<string, string> = {
            memory: '#1890ff',
            system: '#52c41a',
            module: '#722ed1',
        }

        return (
            <Row gutter={[16, 16]}>
                <Col span={24}>
                    <Card
                        size="small"
                        title={
                            <Space>
                                <LineChartOutlined />
                                <strong>📊 98分指标面板 (StatCollector v1.0)</strong>
                                <Tag color="green">已注册: {metricsData.total_metrics}个指标</Tag>
                                <Tag color="blue">有快照: {metricsData.with_snapshots}个</Tag>
                            </Space>
                        }
                        extra={
                            <Space>
                                <Text type="secondary" style={{ fontSize: 11 }}>
                                    事实源锚定 · 可重放验证 · 每10秒采集
                                </Text>
                                <Button
                                    size="small"
                                    icon={<SyncOutlined />}
                                    loading={metricsLoading}
                                    onClick={fetchMetrics}
                                />
                            </Space>
                        }
                    >
                        {categories.map(([cat, entries]) => {
                            const color = CATEGORY_COLORS[cat] || '#8c8c8c'
                            return (
                                <div key={cat} style={{ marginBottom: 16 }}>
                                    <Title level={5} style={{ margin: '12px 0 8px', color }}>
                                        {cat === 'memory'
                                            ? '🧠 记忆指标'
                                            : cat === 'system'
                                                ? '⚙️ 系统指标'
                                                : cat === 'module'
                                                    ? '📦 模块指标'
                                                    : cat}
                                        <Tag style={{ marginLeft: 8 }}>{entries.length}个</Tag>
                                    </Title>
                                    <Row gutter={[12, 12]}>
                                        {entries.map((entry: MetricEntry) => {
                                            const snap = entry.snapshot
                                            const isStale = entry.stale
                                            const hasAnchor = snap?.anchor_id != null
                                            const anchorEnabled = entry.definition.anchor_policy !== 'none'
                                            const valueColor = isStale ? '#d9d9d9' : snap ? color : '#d9d9d9'

                                            return (
                                                <Col xs={24} sm={12} lg={6} xl={4} key={entry.definition.name}>
                                                    <Card
                                                        hoverable
                                                        size="small"
                                                        style={{
                                                            borderColor: isStale ? '#f0f0f0' : color,
                                                            opacity: isStale ? 0.6 : 1,
                                                        }}
                                                    >
                                                        <Statistic
                                                            title={
                                                                <Tooltip
                                                                    title={`${entry.definition.description}\n锚定策略: ${entry.definition.anchor_policy}\n数据源: ${entry.definition.source_type}`}
                                                                >
                                                                    <span style={{ fontSize: 11 }}>
                                                                        {entry.definition.display_name}
                                                                        {anchorEnabled && (
                                                                            <Tag
                                                                                color="purple"
                                                                                style={{
                                                                                    fontSize: 9,
                                                                                    marginLeft: 4,
                                                                                    padding: '0 3px',
                                                                                    lineHeight: '16px',
                                                                                }}
                                                                            >
                                                                                锚
                                                                            </Tag>
                                                                        )}
                                                                    </span>
                                                                </Tooltip>
                                                            }
                                                            value={
                                                                snap
                                                                    ? typeof snap.value === 'object'
                                                                        ? JSON.stringify(snap.value).substring(0, 30)
                                                                        : snap.value
                                                                    : '-'
                                                            }
                                                            valueStyle={{ color: valueColor, fontSize: 16 }}
                                                            suffix={entry.definition.unit}
                                                        />
                                                        <div
                                                            style={{
                                                                marginTop: 4,
                                                                display: 'flex',
                                                                alignItems: 'center',
                                                                gap: 4,
                                                            }}
                                                        >
                                                            <Tag color={isStale ? 'default' : 'green'} style={{ fontSize: 10 }}>
                                                                {isStale ? '过期' : '实时'}
                                                            </Tag>
                                                            {hasAnchor && (
                                                                <Tooltip title={`锚定ID: ${snap!.anchor_id}`}>
                                                                    <Tag color="purple" style={{ fontSize: 9, padding: '0 3px' }}>
                                                                        ✓已验证
                                                                    </Tag>
                                                                </Tooltip>
                                                            )}
                                                            {anchorEnabled && !hasAnchor && (
                                                                <Tag color="orange" style={{ fontSize: 9, padding: '0 3px' }}>
                                                                    锚挂起
                                                                </Tag>
                                                            )}
                                                            {snap && (
                                                                <Text type="secondary" style={{ fontSize: 9 }}>
                                                                    {new Date(snap.timestamp * 1000).toLocaleTimeString()}
                                                                </Text>
                                                            )}
                                                        </div>
                                                    </Card>
                                                </Col>
                                            )
                                        })}
                                    </Row>
                                </div>
                            )
                        })}
                    </Card>
                </Col>
            </Row>
        )
    }

    const renderChainDashboard = () => {
        const displayChains =
            chainScores.length > 0
                ? chainScores
                : governanceLoaded
                    ? []
                    : [
                        {
                            key: 'loading',
                            name: '正在加载治理数据...',
                            module: 'governance',
                            composite: 0,
                            features: '请等待后端 /api/governance/status 响应',
                            color: '#d9d9d9',
                        },
                    ]

        if (displayChains.length === 0 && chainScores.length === 0 && governanceLoaded) {
            return (
                <Card
                    size="small"
                    title={
                        <Space>
                            <RocketOutlined />
                            <strong>8链能力辐射仪表盘</strong>
                        </Space>
                    }
                >
                    <Alert
                        message="治理数据不可用"
                        description="后端 /api/governance/status 未返回链数据，请确认 governance_pipeline 模块已激活"
                        type="warning"
                        showIcon
                    />
                </Card>
            )
        }

        return (
            <Row gutter={[16, 16]}>
                <Col span={24}>
                    <Card
                        size="small"
                        title={
                            <Space>
                                <RocketOutlined />
                                <strong>8链能力辐射仪表盘 ({displayChains.length}链)</strong>
                            </Space>
                        }
                        extra={<Tag color="blue">天机v9.1</Tag>}
                    >
                        <Row gutter={[16, 16]}>
                            {displayChains.map((chain) => {
                                const moduleOnline =
                                    stats?.dimensions?.realtime?.[chain.module]?.status === 'pend_active' ||
                                    stats?.dimensions?.realtime?.[chain.module]?.status === 'online'
                                const isRealData = chainScores.length > 0
                                return (
                                    <Col xs={24} sm={12} lg={6} key={chain.key}>
                                        <Card size="small" style={{ borderLeft: `4px solid ${chain.color}` }}>
                                            <div
                                                style={{
                                                    display: 'flex',
                                                    justifyContent: 'space-between',
                                                    alignItems: 'center',
                                                    marginBottom: 8,
                                                }}
                                            >
                                                <Text strong style={{ fontSize: 14 }}>
                                                    {chain.name}
                                                </Text>
                                                <Tag color={moduleOnline ? 'success' : 'default'}>
                                                    {moduleOnline ? '在线' : '待机'}
                                                </Tag>
                                            </div>
                                            <Progress
                                                percent={isRealData ? chain.composite : 0}
                                                strokeColor={isRealData ? chain.color : '#d9d9d9'}
                                                size="small"
                                                format={(pct) => (isRealData ? `${pct}%` : '...')}
                                            />
                                            <Text type="secondary" style={{ fontSize: 11 }}>
                                                {chain.features}
                                            </Text>
                                            <div style={{ marginTop: 4 }}>
                                                <Badge color={moduleOnline ? 'green' : 'orange'} text={`${chain.module}`} />
                                                {!isRealData && (
                                                    <Tag color="default" style={{ marginLeft: 4 }}>
                                                        待API数据
                                                    </Tag>
                                                )}
                                            </div>
                                        </Card>
                                    </Col>
                                )
                            })}
                        </Row>
                    </Card>
                </Col>

                <Col xs={24} lg={12}>
                    <Card
                        size="small"
                        title={
                            <Space>
                                <TrophyOutlined />
                                <strong>国际标准对齐</strong>
                            </Space>
                        }
                    >
                        {standardScores.length > 0 ? (
                            <Table
                                dataSource={standardScores}
                                columns={[
                                    { title: '标准', dataIndex: 'standard', key: 'standard' },
                                    {
                                        title: '支持度',
                                        dataIndex: 'pct',
                                        key: 'pct',
                                        width: 100,
                                        render: (pct: number) => (
                                            <Progress
                                                percent={pct}
                                                size="small"
                                                strokeColor={pct >= 80 ? '#52c41a' : pct >= 50 ? '#faad14' : '#ff4d4f'}
                                                format={() => `${pct}%`}
                                            />
                                        ),
                                    },
                                    {
                                        title: '交付',
                                        dataIndex: 'tag',
                                        key: 'tag',
                                        width: 90,
                                        render: (tag: string) => <Tag color="blue">{tag}</Tag>,
                                    },
                                ]}
                                size="small"
                                pagination={false}
                            />
                        ) : (
                            <Empty
                                description={governanceLoaded ? '暂无标准合规数据' : '正在加载...'}
                                image={Empty.PRESENTED_IMAGE_SIMPLE}
                            />
                        )}
                    </Card>
                </Col>

                <Col xs={24} lg={12}>
                    <Card
                        size="small"
                        title={
                            <Space>
                                <CloudServerOutlined />
                                <strong>核心模块能力矩阵</strong>
                            </Space>
                        }
                    >
                        {capabilityMatrix.length > 0 ? (
                            <Table
                                dataSource={capabilityMatrix}
                                columns={[
                                    {
                                        title: '模块',
                                        dataIndex: 'module',
                                        key: 'module',
                                        render: (v: string) => <Text code>{v}</Text>,
                                    },
                                    {
                                        title: 'Score',
                                        dataIndex: 'composite',
                                        key: 'composite',
                                        width: 80,
                                        render: (v: string) => <Text strong>{v}</Text>,
                                    },
                                    {
                                        title: '评级',
                                        dataIndex: 'grade',
                                        key: 'grade',
                                        width: 60,
                                        render: (g: string) => (
                                            <Tag color={g === 'S' ? 'success' : g === 'A' ? 'blue' : 'orange'}>{g}</Tag>
                                        ),
                                    },
                                    { title: 'P01-P17关键交付', dataIndex: 'deliverables', key: 'deliverables' },
                                ]}
                                size="small"
                                pagination={false}
                                scroll={{ y: 310 }}
                            />
                        ) : (
                            <Empty
                                description={governanceLoaded ? '暂无能力矩阵数据' : '正在加载...'}
                                image={Empty.PRESENTED_IMAGE_SIMPLE}
                            />
                        )}
                    </Card>
                </Col>
            </Row>
        )
    }

    const dimensionTabs = [
        {
            key: 'realtime',
            label: (
                <span>
                    <LineChartOutlined />
                    实时状态
                </span>
            ),
            children: renderRealtimeView(),
        },
        {
            key: 'cumulative',
            label: (
                <span>
                    <BarChartOutlined />
                    累计数据
                </span>
            ),
            children: renderCumulativeView(),
        },
        {
            key: 'history',
            label: (
                <span>
                    <HistoryOutlined />
                    历史趋势
                </span>
            ),
            children: renderHistoryView(),
        },
        {
            key: 'modules',
            label: (
                <span>
                    <TeamOutlined />
                    模块网格
                </span>
            ),
            children: renderModuleStatusGrid(),
        },
        {
            key: 'operations',
            label: (
                <span>
                    <FireOutlined />
                    操作时间线
                </span>
            ),
            children: renderOperationsTimeline(),
        },
        {
            key: 'memory_layers',
            label: (
                <span>
                    <PieChartOutlined />
                    记忆分布
                </span>
            ),
            children: renderMemoryLayerDistribution(),
        },
        {
            key: 'metrics',
            label: (
                <span>
                    <LineChartOutlined />
                    98分指标
                </span>
            ),
            children: renderMetricsPanel(),
        },
        {
            key: 'chains',
            label: (
                <span>
                    <RocketOutlined />
                    8链仪表盘
                </span>
            ),
            children: renderChainDashboard(),
        },
    ]

    return (
        <div style={{ padding: '0px' }}>
            <Card
                size="small"
                title={
                    <Space>
                        <DashboardOutlined />
                        <strong>天机v9.1 · 智能记忆平台</strong>
                    </Space>
                }
                extra={
                    <Space>
                        <Badge count={stats?.module_count ?? 0} showZero color="#1890ff" offset={[10, 0]}>
                            <Tag color="blue">模块在线</Tag>
                        </Badge>
                        <Text type="secondary" style={{ fontSize: 12 }}>
                            数据更新: {stats ? new Date(stats.timestamp * 1000).toLocaleTimeString() : '-'}
                        </Text>
                        <Button icon={<SyncOutlined />} size="small" onClick={fetchStats} loading={loading}>
                            刷新
                        </Button>
                    </Space>
                }
            >
                <Tabs
                    activeKey={activeDimension}
                    onChange={(key) => setActiveDimension(key as any)}
                    items={dimensionTabs}
                />

                {stats?.coverage && stats.coverage.online < stats.coverage.total && (
                    <Alert
                        message={`部分模块未在线 (${stats.coverage.online}/${stats.coverage.total})`}
                        description="部分模块可能正在初始化或已禁用，不影响核心功能"
                        type="warning"
                        showIcon
                        closable
                        style={{ marginTop: 16 }}
                    />
                )}

                {/* 历史趋势图 */}
                {(stats?.dimensions?.history?.snapshots || []).length > 1 && (
                    <div style={{ marginTop: 16 }}>
                        <TrendChart
                            visible={showTrendChart}
                            title="模块覆盖率历史趋势"
                            data={mapSnapshotsToTrend(
                                stats?.dimensions?.history?.snapshots || [],
                                'coverage_pct'
                            )}
                            height={240}
                            color="#52c41a"
                            onClose={() => setShowTrendChart(false)}
                        />
                        {!showTrendChart && (
                            <Button
                                type="dashed"
                                icon={<LineChartOutlined />}
                                onClick={() => setShowTrendChart(true)}
                                block
                            >
                                查看历史覆盖率趋势 ({(stats?.dimensions?.history?.snapshots || []).length} 个快照)
                            </Button>
                        )}
                    </div>
                )}
            </Card>
        </div>
    )
}
