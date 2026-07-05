import { useState, useEffect, useCallback } from 'react'
import {
    Row,
    Col,
    Card,
    Tag,
    Spin,
    Alert,
    Space,
    Typography,
    Button,
    Progress,
    Statistic,
    Table,
    Timeline,
    Modal,
    InputNumber,
    Checkbox,
    Divider,
    Badge,
    Tooltip,
    Empty,
    message,
    Collapse,
} from 'antd'
import {
    PlayCircleOutlined,
    ReloadOutlined,
    TrophyOutlined,
    ExperimentOutlined,
    SafetyCertificateOutlined,
    DashboardOutlined,
    ThunderboltOutlined,
    SecurityScanOutlined,
    CheckCircleOutlined,
    CloseCircleOutlined,
    WarningOutlined,
    HistoryOutlined,
    DeleteOutlined,
    InfoCircleOutlined,
    LoadingOutlined,
} from '@ant-design/icons'
import { api } from '../services/api'

const { Text, Title } = Typography

// ═══════════════════════════════════════════════════════════════
// 类型定义
// ═══════════════════════════════════════════════════════════════

interface DimensionSummary {
    dimension: string
    total_checks: number
    passed: number
    warned: number
    failed: number
    skipped: number
    errored: number
    score: number
    max_score: number
    pass_rate: number
    score_rate: number
}

interface CheckItem {
    check_id: string
    status: string
    severity: string
    score: number
    threshold: number
    message: string
    duration_ms: number
}

interface DimensionDetail extends DimensionSummary {
    checks: CheckItem[]
}

interface AuditReport {
    success: boolean
    audit_id: string
    rounds: number
    dimensions_run: string[]
    total_checks: number
    total_passed: number
    total_failed: number
    overall_pass_rate: number
    overall_score: number
    overall_max_score: number
    duration_ms: number
    verdict: string
    timestamp: string
    dimensions?: Record<string, DimensionDetail>
    error?: string
}

interface DimensionInfo {
    name: string
    label: string
    weight: number
    description: string
    checks_count: number
}

interface AuditStatus {
    running: boolean
    last_audit: AuditReport | null
    message?: string
}

interface HistoryEntry {
    audit_id: string
    rounds: number
    total_checks: number
    total_passed: number
    total_failed: number
    overall_pass_rate: number
    overall_score: number
    duration_ms: number
    verdict: string
    timestamp: string
    dimensions_run: string[]
}

// ═══════════════════════════════════════════════════════════════
// 5维配置
// ═══════════════════════════════════════════════════════════════

const DIMENSION_META: Record<
    string,
    { label: string; icon: React.ReactNode; color: string; description: string }
> = {
    functionality: {
        label: '功能完整性',
        icon: <CheckCircleOutlined />,
        color: '#1890ff',
        description: '文件/类/方法签名/E2E流程 — 核心模块是否完整可用',
    },
    stability: {
        label: '系统稳定性',
        icon: <ThunderboltOutlined />,
        color: '#52c41a',
        description: '重复操作/并发/错误恢复/资源清理 — 压力下是否稳定',
    },
    performance: {
        label: '性能指标',
        icon: <DashboardOutlined />,
        color: '#fa8c16',
        description: '延迟/吞吐量/批量性能 — 核心操作是否达标',
    },
    security: {
        label: '安全合规',
        icon: <SecurityScanOutlined />,
        color: '#722ed1',
        description: '敏感模式/危险操作/访问控制/密钥 — 是否存在隐患',
    },
    data_accuracy: {
        label: '数据准确性',
        icon: <SafetyCertificateOutlined />,
        color: '#eb2f96',
        description: '哈希一致性/引用完整性/层完整性 — 数据是否可靠',
    },
}

const DIMENSION_ORDER = ['functionality', 'stability', 'performance', 'security', 'data_accuracy']

const STATUS_COLORS: Record<string, string> = {
    passed: '#52c41a',
    warned: '#faad14',
    failed: '#ff4d4f',
    skipped: '#d9d9d9',
    errored: '#ff7a45',
}

const STATUS_ICONS: Record<string, React.ReactNode> = {
    passed: <CheckCircleOutlined style={{ color: '#52c41a' }} />,
    warned: <WarningOutlined style={{ color: '#faad14' }} />,
    failed: <CloseCircleOutlined style={{ color: '#ff4d4f' }} />,
    skipped: <InfoCircleOutlined style={{ color: '#d9d9d9' }} />,
    errored: <CloseCircleOutlined style={{ color: '#ff7a45' }} />,
}

const VERDICT_COLORS: Record<string, string> = {
    PASS: '#52c41a',
    FAIL: '#ff4d4f',
}

// ═══════════════════════════════════════════════════════════════
// 主组件
// ═══════════════════════════════════════════════════════════════

export default function AuditDashboard() {
    const [loading, setLoading] = useState(true)
    const [status, setStatus] = useState<AuditStatus>({ running: false, last_audit: null })
    const [dimensions, setDimensions] = useState<DimensionInfo[]>([])
    const [history, setHistory] = useState<HistoryEntry[]>([])
    const [error, setError] = useState<string | null>(null)
    const [runModalOpen, setRunModalOpen] = useState(false)
    const [runRounds, setRunRounds] = useState(1)
    const [skipDims, setSkipDims] = useState<string[]>([])
    const [running, setRunning] = useState(false)
    const [selectedReport, setSelectedReport] = useState<AuditReport | null>(null)
    const [reportModalOpen, setReportModalOpen] = useState(false)

    // 初始加载
    useEffect(() => {
        fetchAll()
    }, [])

    // 轮询运行状态
    useEffect(() => {
        if (!running) return
        const timer = setInterval(() => {
            api
                .get<AuditStatus>('/api/audit/status')
                .then((s) => {
                    if (!s.running) {
                        setRunning(false)
                        fetchAll()
                        clearInterval(timer)
                    }
                })
                .catch(() => { })
        }, 2000)
        return () => clearInterval(timer)
    }, [running])

    const STATUS_NORMALIZE: Record<string, string> = {
        PASS: 'passed', PASSED: 'passed', pass: 'passed', passed: 'passed',
        WARN: 'warned', WARNING: 'warned', warn: 'warned', warned: 'warned',
        FAIL: 'failed', FAILED: 'failed', fail: 'failed', failed: 'failed',
        ERROR: 'errored', ERRORED: 'errored', error: 'errored', errored: 'errored',
        SKIP: 'skipped', SKIPPED: 'skipped', skip: 'skipped', skipped: 'skipped',
    }

    const normalizeAuditReport = (data: any): AuditStatus => {
        if (!data?.last_audit) return data
        const la = { ...data.last_audit }
        if (la.dimensions) {
            const dims: Record<string, any> = {}
            for (const [dk, dv] of Object.entries(la.dimensions)) {
                const dim = { ...(dv as any) }
                if (Array.isArray(dim.checks)) {
                    dim.checks = dim.checks.map((c: any) => ({
                        ...c,
                        status: STATUS_NORMALIZE[c.status] || c.status?.toLowerCase() || 'skipped',
                        severity: c.severity?.toLowerCase() || 'info',
                    }))
                }
                dims[dk] = dim
            }
            la.dimensions = dims
        }
        return { ...data, last_audit: la }
    }

    const fetchAll = useCallback(async () => {
        try {
            setLoading(true)
            const [statusRes, dimsRes, histRes] = await Promise.allSettled([
                api.get<AuditStatus>('/api/audit/status'),
                api.get<{ dimensions: DimensionInfo[] }>('/api/audit/dimensions'),
                api.get<{ history: HistoryEntry[] }>('/api/audit/history', { params: { limit: 20 } }),
            ])
            // [FIX-TS-018] 修复 Property 'data' does not exist: value 类型可能是 AxiosResponse 或裸数据
            if (statusRes.status === 'fulfilled') setStatus(normalizeAuditReport((statusRes.value as any)?.data ?? statusRes.value))
            if (dimsRes.status === 'fulfilled') setDimensions(((dimsRes.value as any)?.data ?? dimsRes.value)?.dimensions || [])
            if (histRes.status === 'fulfilled') setHistory(((histRes.value as any)?.data ?? histRes.value)?.history || [])
            setError(null)
        } catch {
            setError('无法连接鉴衡审计引擎')
        } finally {
            setLoading(false)
        }
    }, [])

    const runAudit = async () => {
        try {
            setRunning(true)
            setRunModalOpen(false)
            message.loading({ content: '鉴衡审计引擎运行中…', key: 'audit-run', duration: 0 })
            const result = await api.post<AuditReport>('/api/audit/run', {
                rounds: runRounds,
                skip_dimensions: skipDims,
                timeout_seconds: 300,
            })
            message.success({
                content: `审计完成: ${result.verdict} | ${result.overall_pass_rate}% 通过率`,
                key: 'audit-run',
            })
            fetchAll()
        } catch (e: any) {
            message.error({
                content: `审计失败: ${e?.response?.data?.detail || e?.message || '未知错误'}`,
                key: 'audit-run',
            })
            setRunning(false)
        }
    }

    const viewReport = async (auditId: string) => {
        try {
            const report = await api.get<AuditReport>(`/api/audit/report/${auditId}`)
            // 归一化status值
            if (report.dimensions) {
                for (const dk of Object.keys(report.dimensions)) {
                    const dim = report.dimensions[dk]
                    if (Array.isArray(dim.checks)) {
                        dim.checks = dim.checks.map((c) => ({
                            ...c,
                            status: STATUS_NORMALIZE[c.status] || c.status?.toLowerCase() || 'skipped',
                            severity: c.severity?.toLowerCase() || 'info',
                        }))
                    }
                }
            }
            setSelectedReport(report)
            setReportModalOpen(true)
        } catch {
            message.error('无法加载审计报告')
        }
    }

    const clearHistory = async () => {
        Modal.confirm({
            title: '确认清空审计历史？',
            content: '此操作将清空内存中的历史记录（磁盘文件保留）',
            onOk: async () => {
                await api.delete('/api/audit/history')
                setHistory([])
                setStatus({ running: false, last_audit: null })
                message.success('审计历史已清空')
            },
        })
    }

    // ═══════════════════════════════════════════════════════════
    // 渲染: 加载态
    // ═══════════════════════════════════════════════════════════
    if (loading) {
        return (
            <div style={{ textAlign: 'center', padding: '100px 0' }}>
                <Spin size="large" indicator={<LoadingOutlined style={{ fontSize: 48 }} spin />}>
                    <div style={{ padding: 20, marginTop: 16 }}>加载鉴衡审计引擎…</div>
                </Spin>
            </div>
        )
    }

    // ═══════════════════════════════════════════════════════════
    // 渲染: 错误态
    // ═══════════════════════════════════════════════════════════
    if (error && !status.last_audit) {
        return (
            <Alert
                message="鉴衡审计引擎连接失败"
                description={error}
                type="error"
                showIcon
                action={
                    <Button size="small" onClick={fetchAll}>
                        重试
                    </Button>
                }
            />
        )
    }

    const lastAudit = status.last_audit

    // ═══════════════════════════════════════════════════════════
    // 渲染: 5维得分环
    // ═══════════════════════════════════════════════════════════
    const renderDimensionRings = () => (
        <Row gutter={[16, 16]}>
            {DIMENSION_ORDER.map((dimKey) => {
                const meta = DIMENSION_META[dimKey]
                const dimData = lastAudit?.dimensions?.[dimKey]
                const info = dimensions.find((d) => d.name === dimKey)
                const hasData = !!dimData

                return (
                    <Col xs={24} sm={12} md={Math.floor(24 / 5)} key={dimKey}>
                        <Card
                            size="small"
                            style={{
                                textAlign: 'center',
                                borderTop: `3px solid ${meta.color}`,
                                opacity: hasData ? 1 : 0.5,
                            }}
                        >
                            <div style={{ fontSize: 28, marginBottom: 4 }}>{meta.icon}</div>
                            <Text strong style={{ fontSize: 13 }}>
                                {meta.label}
                            </Text>
                            <div style={{ marginTop: 8 }}>
                                {hasData ? (
                                    <>
                                        <Progress
                                            type="circle"
                                            size={70}
                                            percent={dimData.pass_rate}
                                            strokeColor={
                                                dimData.pass_rate >= 90
                                                    ? '#52c41a'
                                                    : dimData.pass_rate >= 70
                                                        ? '#faad14'
                                                        : '#ff4d4f'
                                            }
                                            format={() => `${dimData.passed}/${dimData.total_checks}`}
                                        />
                                        <div style={{ marginTop: 4 }}>
                                            <Text type="secondary" style={{ fontSize: 11 }}>
                                                {dimData.score.toFixed(1)}/{dimData.max_score.toFixed(0)}分
                                            </Text>
                                        </div>
                                        <Space size={4} style={{ marginTop: 2 }}>
                                            {dimData.failed > 0 && (
                                                <Tag color="error" style={{ fontSize: 10, padding: '0 4px' }}>
                                                    {dimData.failed}失败
                                                </Tag>
                                            )}
                                            {dimData.warned > 0 && (
                                                <Tag color="warning" style={{ fontSize: 10, padding: '0 4px' }}>
                                                    {dimData.warned}警告
                                                </Tag>
                                            )}
                                        </Space>
                                    </>
                                ) : (
                                    <>
                                        <Progress
                                            type="circle"
                                            size={70}
                                            percent={0}
                                            strokeColor="#d9d9d9"
                                            format={() => `-/${info?.checks_count || '?'}`}
                                        />
                                        <div style={{ marginTop: 4 }}>
                                            <Text type="secondary" style={{ fontSize: 11 }}>
                                                未审计
                                            </Text>
                                        </div>
                                    </>
                                )}
                            </div>
                        </Card>
                    </Col>
                )
            })}
        </Row>
    )

    // ═══════════════════════════════════════════════════════════
    // 渲染: 维度详细结果
    // ═══════════════════════════════════════════════════════════
    const renderDimensionDetails = () => {
        if (!lastAudit?.dimensions) return null

        const dimKeys = Object.keys(lastAudit.dimensions)

        return (
            <Collapse
                size="small"
                items={dimKeys.map((dimKey) => {
                    const dim = lastAudit.dimensions![dimKey]
                    const meta = DIMENSION_META[dimKey] || { label: dimKey, icon: null, color: '#1890ff' }
                    const allPassed = dim.failed === 0 && dim.errored === 0

                    return {
                        key: dimKey,
                        label: (
                            <Space>
                                <span style={{ fontSize: 16 }}>{meta.icon}</span>
                                <Text strong>{meta.label}</Text>
                                <Tag color={allPassed ? 'success' : 'error'}>
                                    {dim.passed}/{dim.total_checks}
                                </Tag>
                                {dim.failed > 0 && <Tag color="error">{dim.failed} 失败</Tag>}
                                {dim.warned > 0 && <Tag color="warning">{dim.warned} 警告</Tag>}
                            </Space>
                        ),
                        children: (
                            <div style={{ maxHeight: 300, overflow: 'auto' }}>
                                {(dim.checks || []).map((check) => (
                                    <div
                                        key={check.check_id}
                                        style={{
                                            padding: '6px 12px',
                                            marginBottom: 4,
                                            borderRadius: 4,
                                            backgroundColor:
                                                check.status === 'passed'
                                                    ? '#f6ffed'
                                                    : check.status === 'warned'
                                                        ? '#fffbe6'
                                                        : check.status === 'failed'
                                                            ? '#fff2f0'
                                                            : check.status === 'errored'
                                                                ? '#fff2e8'
                                                                : '#fafafa',
                                            border: `1px solid ${check.status === 'passed'
                                                    ? '#b7eb8f'
                                                    : check.status === 'warned'
                                                        ? '#ffe58f'
                                                        : check.status === 'failed'
                                                            ? '#ffccc7'
                                                            : check.status === 'errored'
                                                                ? '#ffd8bf'
                                                                : '#e8e8e8'
                                                }`,
                                        }}
                                    >
                                        <div
                                            style={{
                                                display: 'flex',
                                                justifyContent: 'space-between',
                                                alignItems: 'center',
                                            }}
                                        >
                                            <Space size={4}>
                                                {STATUS_ICONS[check.status] || STATUS_ICONS.skipped}
                                                <Text code style={{ fontSize: 11 }}>
                                                    {check.check_id}
                                                </Text>
                                                <Tag
                                                    color={
                                                        check.severity === 'critical'
                                                            ? 'red'
                                                            : check.severity === 'high'
                                                                ? 'orange'
                                                                : check.severity === 'medium'
                                                                    ? 'blue'
                                                                    : 'default'
                                                    }
                                                    style={{ fontSize: 10, padding: '0 4px' }}
                                                >
                                                    {check.severity}
                                                </Tag>
                                            </Space>
                                            <Text type="secondary" style={{ fontSize: 11 }}>
                                                {check.duration_ms?.toFixed(0)}ms | {check.score}/{check.threshold}分
                                            </Text>
                                        </div>
                                        <div style={{ marginTop: 2 }}>
                                            <Text style={{ fontSize: 12 }}>{check.message}</Text>
                                        </div>
                                    </div>
                                ))}
                            </div>
                        ),
                    }
                })}
            />
        )
    }

    // ═══════════════════════════════════════════════════════════
    // 渲染: 审计历史表格
    // ═══════════════════════════════════════════════════════════
    const renderHistoryTable = () => {
        if (history.length === 0) {
            return (
                <Card
                    size="small"
                    title={
                        <Space>
                            <HistoryOutlined />
                            审计历史
                        </Space>
                    }
                >
                    <Empty
                        description="暂无审计记录，请点击「运行审计」"
                        image={Empty.PRESENTED_IMAGE_SIMPLE}
                    />
                </Card>
            )
        }

        const columns = [
            {
                title: '审计ID',
                dataIndex: 'audit_id',
                key: 'audit_id',
                width: 180,
                render: (id: string) => (
                    <Text code style={{ fontSize: 12 }}>
                        {id}
                    </Text>
                ),
            },
            {
                title: '时间',
                dataIndex: 'timestamp',
                key: 'timestamp',
                width: 160,
                render: (ts: string) => <Text style={{ fontSize: 12 }}>{ts?.replace('T', ' ')}</Text>,
            },
            {
                title: '轮次',
                dataIndex: 'rounds',
                key: 'rounds',
                width: 60,
                align: 'center' as const,
            },
            {
                title: '维度',
                dataIndex: 'dimensions_run',
                key: 'dimensions',
                width: 180,
                render: (dims: string[] | undefined) => (
                    <Space size={2} wrap>
                        {(dims || []).map((d) => {
                            const meta = DIMENSION_META[d]
                            return (
                                <Tag key={d} style={{ fontSize: 10, padding: '0 4px' }}>
                                    {meta?.label || d}
                                </Tag>
                            )
                        })}
                    </Space>
                ),
            },
            {
                title: '检查项',
                key: 'checks',
                width: 100,
                align: 'center' as const,
                render: (_: any, record: HistoryEntry) => (
                    <Tooltip title={`${record.total_passed} 通过 / ${record.total_failed} 失败`}>
                        <Progress
                            percent={
                                record.total_checks > 0
                                    ? Math.round((record.total_passed / record.total_checks) * 100)
                                    : 0
                            }
                            size="small"
                            style={{ width: 80 }}
                            strokeColor={record.total_failed === 0 ? '#52c41a' : '#ff4d4f'}
                            format={() => `${record.total_passed}/${record.total_checks}`}
                        />
                    </Tooltip>
                ),
            },
            {
                title: '得分',
                dataIndex: 'overall_score',
                key: 'score',
                width: 80,
                align: 'center' as const,
                render: (score: number, record: HistoryEntry) => (
                    <Text
                        style={{ color: record.verdict === 'PASS' ? '#52c41a' : '#ff4d4f', fontWeight: 'bold' }}
                    >
                        {score?.toFixed(1)}
                    </Text>
                ),
            },
            {
                title: '耗时',
                dataIndex: 'duration_ms',
                key: 'duration',
                width: 80,
                align: 'center' as const,
                render: (ms: number) => <Text style={{ fontSize: 12 }}>{(ms / 1000).toFixed(1)}s</Text>,
            },
            {
                title: '判定',
                dataIndex: 'verdict',
                key: 'verdict',
                width: 70,
                align: 'center' as const,
                render: (v: string) => <Badge status={v === 'PASS' ? 'success' : 'error'} text={v} />,
            },
            {
                title: '操作',
                key: 'actions',
                width: 80,
                align: 'center' as const,
                render: (_: any, record: HistoryEntry) => (
                    <Button type="link" size="small" onClick={() => viewReport(record.audit_id)}>
                        详情
                    </Button>
                ),
            },
        ]

        return (
            <Card
                size="small"
                title={
                    <Space>
                        <HistoryOutlined />
                        审计历史
                        <Tag>{history.length}条</Tag>
                    </Space>
                }
                extra={
                    <Button size="small" danger icon={<DeleteOutlined />} onClick={clearHistory}>
                        清空
                    </Button>
                }
            >
                <Table
                    dataSource={history}
                    columns={columns}
                    rowKey="audit_id"
                    size="small"
                    pagination={{ pageSize: 10, size: 'small' }}
                    scroll={{ x: 1000 }}
                />
            </Card>
        )
    }

    // ═══════════════════════════════════════════════════════════
    // 主渲染
    // ═══════════════════════════════════════════════════════════
    return (
        <div>
            {/* ── 页面标题 ── */}
            <div
                style={{
                    marginBottom: 16,
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                }}
            >
                <Space>
                    <ExperimentOutlined style={{ fontSize: 28, color: '#1890ff' }} />
                    <div>
                        <Title level={3} style={{ margin: 0 }}>
                            鉴衡 · 全维审计仪表盘
                        </Title>
                        <Text type="secondary">
                            L3 全维审计师 · 5维 × 4阶段审计流水线 · TianjiAuditEngine v1.0
                        </Text>
                    </div>
                </Space>
                <Space>
                    <Button icon={<ReloadOutlined />} onClick={fetchAll} disabled={running}>
                        刷新
                    </Button>
                    <Button
                        type="primary"
                        icon={running ? <LoadingOutlined /> : <PlayCircleOutlined />}
                        onClick={() => setRunModalOpen(true)}
                        disabled={running}
                        danger={!!lastAudit && lastAudit.verdict === 'FAIL'}
                    >
                        {running ? '审计运行中…' : '运行审计'}
                    </Button>
                </Space>
            </div>

            {/* ── 顶栏: Agent身份 + 上次结果摘要 ── */}
            <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
                {/* Agent身份卡 */}
                <Col xs={24} sm={8} lg={5}>
                    <Card size="small" style={{ textAlign: 'center', borderTop: '3px solid #1890ff' }}>
                        <div style={{ fontSize: 48, marginBottom: 4 }}>🔬</div>
                        <Title level={4} style={{ margin: 0 }}>
                            鉴衡
                        </Title>
                        <Tag color="blue">@jianheng</Tag>
                        <Tag color="purple">L3</Tag>
                        <div style={{ marginTop: 8 }}>
                            <Text type="secondary" style={{ fontSize: 12 }}>
                                全维审计师 · Omni-Dimensional Auditor
                            </Text>
                        </div>
                        <Divider style={{ margin: '8px 0' }} />
                        <div>
                            <Text type="secondary" style={{ fontSize: 11 }}>
                                5维 × 4阶段审计流水线
                                <br />
                                功能 · 稳定 · 性能 · 安全 · 数据
                            </Text>
                        </div>
                    </Card>
                </Col>

                {/* 上次审计摘要 */}
                <Col xs={24} sm={16} lg={13}>
                    <Card
                        size="small"
                        title={
                            <Space>
                                <TrophyOutlined
                                    style={{
                                        color: lastAudit
                                            ? lastAudit.verdict === 'PASS'
                                                ? '#52c41a'
                                                : '#ff4d4f'
                                            : '#d9d9d9',
                                    }}
                                />
                                上次审计
                            </Space>
                        }
                    >
                        {lastAudit ? (
                            <Row gutter={[16, 8]}>
                                <Col span={6}>
                                    <Statistic
                                        title="判定"
                                        value={lastAudit.verdict}
                                        valueStyle={{
                                            color: VERDICT_COLORS[lastAudit.verdict] || '#d9d9d9',
                                            fontSize: 32,
                                            fontWeight: 'bold',
                                        }}
                                    />
                                </Col>
                                <Col span={6}>
                                    <Statistic
                                        title="总得分"
                                        value={lastAudit.overall_score.toFixed(1)}
                                        suffix={`/ ${lastAudit.overall_max_score.toFixed(0)}`}
                                        valueStyle={{ fontSize: 24 }}
                                    />
                                </Col>
                                <Col span={4}>
                                    <Statistic
                                        title="通过率"
                                        value={lastAudit.overall_pass_rate}
                                        suffix="%"
                                        valueStyle={{
                                            color: lastAudit.overall_pass_rate >= 80 ? '#52c41a' : '#ff4d4f',
                                        }}
                                    />
                                    <Progress
                                        percent={lastAudit.overall_pass_rate}
                                        strokeColor={lastAudit.overall_pass_rate >= 80 ? '#52c41a' : '#ff4d4f'}
                                        showInfo={false}
                                        size="small"
                                    />
                                </Col>
                                <Col span={4}>
                                    <Statistic
                                        title="检查项"
                                        value={`${lastAudit.total_passed}/${lastAudit.total_checks}`}
                                        suffix={lastAudit.total_failed > 0 ? ` (${lastAudit.total_failed}失败)` : ''}
                                        valueStyle={{
                                            color: lastAudit.total_failed > 0 ? '#ff4d4f' : '#52c41a',
                                            fontSize: 20,
                                        }}
                                    />
                                </Col>
                                <Col span={4}>
                                    <Statistic
                                        title="耗时"
                                        value={(lastAudit.duration_ms / 1000).toFixed(1)}
                                        suffix="秒"
                                        valueStyle={{ fontSize: 20 }}
                                    />
                                </Col>
                            </Row>
                        ) : (
                            <Empty
                                description="尚未运行审计"
                                image={Empty.PRESENTED_IMAGE_SIMPLE}
                                style={{ margin: '12px 0' }}
                            >
                                <Button
                                    type="primary"
                                    icon={<PlayCircleOutlined />}
                                    onClick={() => setRunModalOpen(true)}
                                >
                                    首次审计
                                </Button>
                            </Empty>
                        )}
                    </Card>
                </Col>

                {/* 审计维度元信息 */}
                <Col xs={24} sm={24} lg={6}>
                    <Card
                        size="small"
                        title={
                            <Space>
                                <InfoCircleOutlined />
                                5维能力矩阵
                            </Space>
                        }
                    >
                        {dimensions.map((dim) => {
                            const meta = DIMENSION_META[dim.name]
                            return (
                                <div
                                    key={dim.name}
                                    style={{
                                        display: 'flex',
                                        justifyContent: 'space-between',
                                        alignItems: 'center',
                                        padding: '3px 0',
                                        borderBottom: '1px solid #f0f0f0',
                                    }}
                                >
                                    <Space size={4}>
                                        {meta?.icon}
                                        <Text style={{ fontSize: 12 }}>{meta?.label || dim.label}</Text>
                                    </Space>
                                    <Space size={4}>
                                        <Tag style={{ fontSize: 10, padding: '0 4px' }}>{dim.checks_count}项</Tag>
                                        <Text type="secondary" style={{ fontSize: 10 }}>
                                            ×{dim.weight}
                                        </Text>
                                    </Space>
                                </div>
                            )
                        })}
                    </Card>
                </Col>
            </Row>

            {/* ── 5维审计结果环形图 ── */}
            <Card
                size="small"
                title={
                    <Space>
                        <DashboardOutlined />
                        5维审计结果
                    </Space>
                }
                style={{ marginBottom: 16 }}
            >
                {renderDimensionRings()}
            </Card>

            {/* ── 维度详细检查项 ── */}
            {lastAudit?.dimensions && <div style={{ marginBottom: 16 }}>{renderDimensionDetails()}</div>}

            {/* ── 审计历史表格 ── */}
            <div style={{ marginBottom: 16 }}>{renderHistoryTable()}</div>

            {/* ═══════════════════════════════════════════════════════ */}
            {/* 运行审计弹窗 */}
            {/* ═══════════════════════════════════════════════════════ */}
            <Modal
                title={
                    <Space>
                        <PlayCircleOutlined />
                        运行鉴衡全维审计
                    </Space>
                }
                open={runModalOpen}
                onCancel={() => setRunModalOpen(false)}
                onOk={runAudit}
                okText="开始审计"
                cancelText="取消"
                confirmLoading={running}
            >
                <div style={{ marginBottom: 16 }}>
                    <Text strong>审计轮次</Text>
                    <div style={{ marginTop: 8 }}>
                        <InputNumber
                            min={1}
                            max={10}
                            value={runRounds}
                            onChange={(v) => setRunRounds(v || 1)}
                            style={{ width: '100%' }}
                        />
                    </div>
                    <Text type="secondary" style={{ fontSize: 12 }}>
                        多轮审计会重复执行检查项，用于验证稳定性
                    </Text>
                </div>

                <Divider style={{ margin: '12px 0' }} />

                <div>
                    <Text strong>跳过维度（可选）</Text>
                    <div style={{ marginTop: 8 }}>
                        <Checkbox.Group value={skipDims} onChange={(vals) => setSkipDims(vals as string[])}>
                            <Row>
                                {DIMENSION_ORDER.map((dimKey) => {
                                    const meta = DIMENSION_META[dimKey]
                                    return (
                                        <Col span={24} key={dimKey} style={{ marginBottom: 4 }}>
                                            <Checkbox value={dimKey}>
                                                <Space size={4}>
                                                    {meta.icon}
                                                    <Text>{meta.label}</Text>
                                                    <Text type="secondary" style={{ fontSize: 11 }}>
                                                        {meta.description}
                                                    </Text>
                                                </Space>
                                            </Checkbox>
                                        </Col>
                                    )
                                })}
                            </Row>
                        </Checkbox.Group>
                    </div>
                </div>

                <Divider style={{ margin: '12px 0' }} />

                <Alert
                    message="审计引擎说明"
                    description="TianjiAuditEngine 将执行 5维 × 4阶段 审计流水线（Precheck → Execute → Evaluate → Report）。审计期间会检查系统核心模块、稳定性、性能基准、安全合规和数据准确性。预计耗时 5-30 秒/轮。"
                    type="info"
                    showIcon
                    style={{ fontSize: 12 }}
                />
            </Modal>

            {/* ═══════════════════════════════════════════════════════ */}
            {/* 审计报告详情弹窗 */}
            {/* ═══════════════════════════════════════════════════════ */}
            <Modal
                title={
                    <Space>
                        <ExperimentOutlined />
                        审计报告详情
                    </Space>
                }
                open={reportModalOpen}
                onCancel={() => {
                    setReportModalOpen(false)
                    setSelectedReport(null)
                }}
                footer={null}
                width={800}
            >
                {selectedReport && (
                    <div>
                        <Row gutter={[16, 8]} style={{ marginBottom: 16 }}>
                            <Col span={6}>
                                <Statistic
                                    title="判定"
                                    value={selectedReport.verdict}
                                    valueStyle={{
                                        color: VERDICT_COLORS[selectedReport.verdict],
                                        fontSize: 28,
                                        fontWeight: 'bold',
                                    }}
                                />
                            </Col>
                            <Col span={6}>
                                <Statistic
                                    title="总得分"
                                    value={selectedReport.overall_score.toFixed(1)}
                                    suffix={`/ ${selectedReport.overall_max_score.toFixed(0)}`}
                                />
                            </Col>
                            <Col span={6}>
                                <Statistic title="通过率" value={selectedReport.overall_pass_rate} suffix="%" />
                            </Col>
                            <Col span={6}>
                                <Statistic
                                    title="耗时"
                                    value={(selectedReport.duration_ms / 1000).toFixed(1)}
                                    suffix="秒"
                                />
                            </Col>
                        </Row>

                        <Divider style={{ margin: '12px 0' }} />

                        <Text strong>审计ID: </Text>
                        <Text code>{selectedReport.audit_id}</Text>
                        <br />
                        <Text strong>时间: </Text>
                        <Text>{selectedReport.timestamp?.replace('T', ' ')}</Text>
                        <br />
                        <Text strong>轮次: </Text>
                        <Text>{selectedReport.rounds}</Text>
                        <br />
                        <Text strong>维度: </Text>
                        <Space size={2} wrap style={{ marginTop: 4 }}>
                            {selectedReport.dimensions_run?.map((d) => {
                                const meta = DIMENSION_META[d]
                                return <Tag key={d}>{meta?.label || d}</Tag>
                            })}
                        </Space>

                        {selectedReport.dimensions && (
                            <>
                                <Divider style={{ margin: '12px 0' }} />
                                <Title level={5}>维度详情</Title>
                                {Object.entries(selectedReport.dimensions).map(([dimKey, dim]) => {
                                    const meta = DIMENSION_META[dimKey] || { label: dimKey }
                                    return (
                                        <Card
                                            key={dimKey}
                                            size="small"
                                            style={{ marginBottom: 8 }}
                                            title={
                                                <Space>
                                                    {
                                                        STATUS_ICONS[
                                                        dim.failed === 0 && dim.errored === 0 ? 'passed' : 'failed'
                                                        ]
                                                    }
                                                    <Text strong>{meta.label}</Text>
                                                    <Tag>
                                                        {dim.passed}/{dim.total_checks} 通过
                                                    </Tag>
                                                    <Text type="secondary" style={{ fontSize: 12 }}>
                                                        {dim.score.toFixed(1)}/{dim.max_score.toFixed(0)}分
                                                    </Text>
                                                </Space>
                                            }
                                        >
                                            <Timeline
                                                items={(dim.checks || []).map((c) => ({
                                                    color: STATUS_COLORS[c.status] || '#d9d9d9',
                                                    children: (
                                                        <div>
                                                            <Space size={4}>
                                                                <Text code style={{ fontSize: 11 }}>
                                                                    {c.check_id}
                                                                </Text>
                                                                <Tag
                                                                    color={
                                                                        c.status === 'passed'
                                                                            ? 'success'
                                                                            : c.status === 'warned'
                                                                                ? 'warning'
                                                                                : c.status === 'failed'
                                                                                    ? 'error'
                                                                                    : c.status === 'errored'
                                                                                        ? 'error'
                                                                                        : 'default'
                                                                    }
                                                                    style={{ fontSize: 10, padding: '0 4px' }}
                                                                >
                                                                    {c.status.toUpperCase()}
                                                                </Tag>
                                                                <Text type="secondary" style={{ fontSize: 10 }}>
                                                                    {c.duration_ms?.toFixed(0)}ms
                                                                </Text>
                                                            </Space>
                                                            <div>
                                                                <Text style={{ fontSize: 12 }}>{c.message}</Text>
                                                            </div>
                                                        </div>
                                                    ),
                                                }))}
                                            />
                                        </Card>
                                    )
                                })}
                            </>
                        )}
                    </div>
                )}
            </Modal>
        </div>
    )
}
