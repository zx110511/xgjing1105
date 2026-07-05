import { useState, useEffect } from 'react'
import {
    Row, Col, Card, Tag, Spin, Alert, Space, Typography, Button,
    Progress, Statistic
} from 'antd'
import {
    CheckCircleOutlined,
    CloseCircleOutlined,
    ReloadOutlined,
    TrophyOutlined,
    DashboardOutlined,
} from '@ant-design/icons'
import { api } from '../services/api'
import { endpoints } from '../config/api.config'

const { Text } = Typography

interface AuditIndicator {
    code: string
    name: string
    value: number | string
    threshold: string
    unit: string
    passed: boolean
    weight: number
}

interface AuditData {
    grade: string
    score: number
    total: number
    passed: number
    failed: number
    results: AuditIndicator[]
    timestamp: number
}

interface MetricsData {
    T1_scale: { nodes: number; edges: number; entity_types: number; relation_types: number; edge_node_ratio: number }
    T2_topology: { density: number; avg_degree: number; max_degree: number; iso_rate: number; gcc_pct: number; degree_cv: number }
    T3_small_world: { clustering_C: number; sigma: number; diameter: number; avg_path_length: number; C_over_Crand: number }
    T4_scale_free: { hubs: number; richest_ratio: number; entropy: number; power_law_r2: number }
    T5_community: { modularity_Q: number; communities: number; community_details: Array<{ type: string; count: number }>; max_community_pct: number }
    T6_semantic: { temporal_pct: number; causal_edges: number; layers: number; agents: number; concepts: number }
    T7_retrieval: { fts5: boolean; vector_index: boolean; subgraph_ms: number }
    T8_evolution: { incremental: boolean; timestamps: boolean; frequency_tracking: boolean }
    summary: { grade: string; score: number }
}

const DIMENSION_CONFIG = [
    { key: 'T1', label: '规模丰富度', icon: '📊', color: '#1890ff', codes: ['T1-01', 'T1-02', 'T1-03', 'T1-04', 'T1-05', 'T1-06'] },
    { key: 'T2', label: '拓扑健康度', icon: '🔗', color: '#52c41a', codes: ['T2-01', 'T2-02', 'T2-03', 'T2-04', 'T2-05', 'T2-06'] },
    { key: 'T3', label: '小世界特性', icon: '🌐', color: '#722ed1', codes: ['T3-01', 'T3-02', 'T3-03', 'T3-04', 'T3-05'] },
    { key: 'T4', label: '无标度特性', icon: '⚡', color: '#fa8c16', codes: ['T4-01', 'T4-02', 'T4-03', 'T4-04', 'T4-05'] },
    { key: 'T5', label: '社区模块度', icon: '🏘️', color: '#eb2f96', codes: ['T5-01', 'T5-02', 'T5-03', 'T5-04', 'T5-05'] },
    { key: 'T6', label: '语义丰富度', icon: '🧠', color: '#13c2c2', codes: ['T6-01', 'T6-02', 'T6-03', 'T6-04', 'T6-05', 'T6-06', 'T6-07'] },
    { key: 'T7', label: '检索效率', icon: '🔍', color: '#2f54eb', codes: ['T7-01', 'T7-02', 'T7-03', 'T7-04', 'T7-05'] },
    { key: 'T8', label: '动态演化', icon: '🔄', color: '#f5222d', codes: ['T8-01', 'T8-02', 'T8-03', 'T8-04', 'T8-05'] },
]

const GRADE_COLORS: Record<string, string> = {
    SSS: '#cf1322',
    SS: '#fa8c16',
    S: '#1890ff',
    A: '#52c41a',
    B: '#8c8c8c',
}

// [FIX-FORMAT] 后端SSSAuditResponse → 前端AuditData 适配器
function normalizeAuditData(raw: any): AuditData {
    // 如果已经是前端格式（有results数组），直接返回
    if (raw?.results && Array.isArray(raw.results)) {
        return raw as AuditData
    }

    // 后端扁平格式: { total_nodes, total_edges, score, grade, issues, recommendations, ... }
    const score = raw?.score ?? 0
    const grade = raw?.grade ?? 'F'
    const totalNodes = raw?.total_nodes ?? 0
    const totalEdges = raw?.total_edges ?? 0
    const powerLawR2 = raw?.power_law_r2 ?? 0
    const density = raw?.density ?? 0
    const avgPathLength = raw?.avg_path_length ?? 0
    // [FIX-TS-013] 删除未使用的 issues/recommendations (后续未引用)
    // 如需展示可从 raw?.issues / raw?.recommendations 直接读取

    // 构造T1-T8检查项
    const results: AuditIndicator[] = [
        // T1 规模丰富度
        { code: 'T1-01', name: '节点总数', value: totalNodes, threshold: '>=100', unit: '个', passed: totalNodes >= 100, weight: 1.5 },
        { code: 'T1-02', name: '边总数', value: totalEdges, threshold: '>=1000', unit: '条', passed: totalEdges >= 1000, weight: 1.5 },
        { code: 'T1-03', name: '边节点比', value: totalNodes > 0 ? round2(totalEdges / totalNodes) : 0, threshold: '>=2.0', unit: '', passed: totalNodes > 0 && (totalEdges / totalNodes) >= 2.0, weight: 1.0 },
        // T2 拓扑健康度
        { code: 'T2-01', name: '图密度', value: round6(density), threshold: '>=0.001', unit: '', passed: density >= 0.001, weight: 1.2 },
        { code: 'T2-02', name: '平均路径长度', value: round2(avgPathLength), threshold: '>0', unit: '', passed: avgPathLength > 0, weight: 1.0 },
        // T3 小世界特性
        { code: 'T3-01', name: '平均路径', value: round2(avgPathLength), threshold: '<=6', unit: '', passed: avgPathLength > 0 && avgPathLength <= 6, weight: 1.0 },
        // T4 无标度特性
        { code: 'T4-01', name: '幂律R²', value: round3(powerLawR2), threshold: '>=0.5', unit: '', passed: powerLawR2 >= 0.5, weight: 1.3 },
        { code: 'T4-02', name: '幂律R²基本', value: round3(powerLawR2), threshold: '>=0.3', unit: '', passed: powerLawR2 >= 0.3, weight: 1.0 },
        // T5 社区模块度 (基于密度推算)
        { code: 'T5-01', name: '密度达标', value: round6(density), threshold: '>=0.001', unit: '', passed: density >= 0.001, weight: 1.0 },
        // T6 语义丰富度 (基于节点数推算)
        { code: 'T6-01', name: '节点丰富度', value: totalNodes, threshold: '>=50', unit: '个', passed: totalNodes >= 50, weight: 1.0 },
        // T7 检索效率
        { code: 'T7-01', name: '路径可达', value: avgPathLength > 0 ? '是' : '否', threshold: '>0', unit: '', passed: avgPathLength > 0, weight: 1.0 },
        // T8 动态演化
        { code: 'T8-01', name: '数据活跃', value: totalEdges > 0 ? '是' : '否', threshold: '>0边', unit: '', passed: totalEdges > 0, weight: 1.0 },
    ]

    const passed = results.filter(r => r.passed).length
    const failed = results.length - passed

    return {
        grade,
        score,
        total: results.length,
        passed,
        failed,
        results,
        timestamp: Date.now(),
    }
}

function round2(v: number): number { return Math.round(v * 100) / 100 }
function round3(v: number): number { return Math.round(v * 1000) / 1000 }
function round6(v: number): number { return Math.round(v * 1000000) / 1000000 }

export default function SSSAuditPanel() {
    const [loading, setLoading] = useState(true)
    const [auditData, setAuditData] = useState<AuditData | null>(null)
    const [metrics, setMetrics] = useState<MetricsData | null>(null)
    const [error, setError] = useState<string | null>(null)

    useEffect(() => {
        fetchAuditData()
    }, [])

    const fetchAuditData = async () => {
        try {
            setLoading(true)
            const [auditRes, metricsRes] = await Promise.allSettled([
                api.get(endpoints.knowledgeGraph.sssAudit),
                api.get(endpoints.knowledgeGraph.metrics),
            ])
            if (auditRes.status === 'fulfilled') {
                const raw = auditRes.value?.data ?? auditRes.value
                // [FIX-FORMAT] 适配后端SSSAuditResponse格式 → 前端AuditData格式
                setAuditData(normalizeAuditData(raw))
            }
            if (metricsRes.status === 'fulfilled') {
                const m = metricsRes.value?.data ?? metricsRes.value
                setMetrics(m)
            }
            setError(null)
        } catch {
            setError('无法加载SSS审计数据')
        } finally {
            setLoading(false)
        }
    }

    if (loading) {
        return (
            <div style={{ textAlign: 'center', padding: '60px 0' }}>
                <Spin size="large">
                    <div style={{ padding: 20 }}>加载SSS级审计数据...</div>
                </Spin>
            </div>
        )
    }

    if (error && !auditData) {
        return (
            <Alert
                message="审计数据加载失败"
                description={error}
                type="error"
                showIcon
                action={<Button size="small" onClick={fetchAuditData}>重试</Button>}
            />
        )
    }

    const getIndicatorsByDimension = (dimKey: string): AuditIndicator[] => {
        if (!auditData?.results) return []
        return auditData.results.filter(r => r.code.startsWith(dimKey))
    }

    const getDimensionScore = (dimKey: string): { passed: number; total: number; weightPassed: number; weightTotal: number } => {
        const indicators = getIndicatorsByDimension(dimKey)
        return {
            passed: indicators.filter(r => r.passed).length,
            total: indicators.length,
            weightPassed: indicators.filter(r => r.passed).reduce((s, r) => s + r.weight, 0),
            weightTotal: indicators.reduce((s, r) => s + r.weight, 0),
        }
    }

    const renderRadarData = () => {
        if (!auditData) return null

        return (
            <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
                {DIMENSION_CONFIG.map(dim => {
                    const score = getDimensionScore(dim.key)
                    const pct = score.total > 0 ? Math.round((score.passed / score.total) * 100) : 0
                    const wpct = score.weightTotal > 0 ? Math.round((score.weightPassed / score.weightTotal) * 100) : 0

                    return (
                        <Col xs={12} sm={8} lg={6} xl={3} key={dim.key}>
                            <Card
                                size="small"
                                style={{ textAlign: 'center', borderTop: `3px solid ${dim.color}` }}
                            >
                                <div style={{ fontSize: 24, marginBottom: 4 }}>{dim.icon}</div>
                                <Text strong style={{ fontSize: 12 }}>{dim.label}</Text>
                                <div style={{ marginTop: 8 }}>
                                    <Progress
                                        type="circle"
                                        size={60}
                                        percent={pct}
                                        strokeColor={pct >= 100 ? '#52c41a' : pct >= 80 ? '#1890ff' : '#ff4d4f'}
                                        format={() => `${score.passed}/${score.total}`}
                                    />
                                </div>
                                <div style={{ marginTop: 4 }}>
                                    <Text type="secondary" style={{ fontSize: 11 }}>加权: {wpct}%</Text>
                                </div>
                            </Card>
                        </Col>
                    )
                })}
            </Row>
        )
    }

    const renderDimensionDetails = () => {
        if (!auditData) return null

        return (
            <div>
                {DIMENSION_CONFIG.map(dim => {
                    const indicators = getIndicatorsByDimension(dim.key)
                    const score = getDimensionScore(dim.key)
                    const allPassed = score.passed === score.total

                    return (
                        <Card
                            key={dim.key}
                            size="small"
                            style={{ marginBottom: 12, borderLeft: `4px solid ${allPassed ? '#52c41a' : '#ff4d4f'}` }}
                            title={
                                <Space>
                                    <span style={{ fontSize: 18 }}>{dim.icon}</span>
                                    <Text strong>{dim.label}</Text>
                                    <Tag color={allPassed ? 'success' : 'error'}>
                                        {score.passed}/{score.total} 通过
                                    </Tag>
                                </Space>
                            }
                        >
                            <Row gutter={[12, 8]}>
                                {indicators.map(ind => (
                                    <Col xs={24} sm={12} lg={8} xl={6} key={ind.code}>
                                        <div style={{
                                            padding: '8px 12px',
                                            borderRadius: 6,
                                            backgroundColor: ind.passed ? '#f6ffed' : '#fff2f0',
                                            border: `1px solid ${ind.passed ? '#b7eb8f' : '#ffccc7'}`,
                                        }}>
                                            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                                                <Space size={4}>
                                                    {ind.passed
                                                        ? <CheckCircleOutlined style={{ color: '#52c41a', fontSize: 14 }} />
                                                        : <CloseCircleOutlined style={{ color: '#ff4d4f', fontSize: 14 }} />
                                                    }
                                                    <Text strong style={{ fontSize: 12 }}>{ind.code}</Text>
                                                </Space>
                                                <Tag
                                                    color={ind.passed ? 'success' : 'error'}
                                                    style={{ fontSize: 10, lineHeight: '18px', padding: '0 4px' }}
                                                >
                                                    {ind.passed ? 'PASS' : 'FAIL'}
                                                </Tag>
                                            </div>
                                            <div style={{ marginTop: 4 }}>
                                                <Text style={{ fontSize: 12 }}>{ind.name}</Text>
                                            </div>
                                            <div style={{ marginTop: 2 }}>
                                                <Text type="secondary" style={{ fontSize: 11 }}>
                                                    实际: <Text strong>{typeof ind.value === 'number' ? ind.value.toLocaleString() : String(ind.value)}</Text>
                                                </Text>
                                            </div>
                                            <div>
                                                <Text type="secondary" style={{ fontSize: 11 }}>
                                                    阈值: {ind.threshold}{ind.unit}
                                                </Text>
                                            </div>
                                        </div>
                                    </Col>
                                ))}
                            </Row>
                        </Card>
                    )
                })}
            </div>
        )
    }

    const renderMetricsSummary = () => {
        if (!metrics) return null

        // [FIX-KG-FORMAT] 兼容后端扁平格式 (MetricsResponse) 和前端嵌套格式 (MetricsData)
        const isFlat = !metrics.T1_scale && 'total_nodes' in metrics
        const flat = metrics as any

        return (
            <Card size="small" title={<Space><DashboardOutlined />核心指标速览</Space>} style={{ marginBottom: 16 }}>
                <Row gutter={[16, 12]}>
                    <Col span={3}>
                        <Statistic title="实体数" value={isFlat ? flat.total_nodes : metrics.T1_scale.nodes} />
                    </Col>
                    <Col span={3}>
                        <Statistic title="关系数" value={isFlat ? flat.total_edges : metrics.T1_scale.edges} />
                    </Col>
                    <Col span={3}>
                        <Statistic title="聚类系数C" value={isFlat ? (flat.clustering_C ?? 0) : metrics.T3_small_world.clustering_C} precision={4} />
                    </Col>
                    <Col span={3}>
                        <Statistic title="小世界σ" value={isFlat ? (flat.sigma ?? 0) : metrics.T3_small_world.sigma} precision={2} />
                    </Col>
                    <Col span={3}>
                        <Statistic title="模块度Q" value={isFlat ? (flat.modularity_Q ?? 0) : metrics.T5_community.modularity_Q} precision={3} />
                    </Col>
                    <Col span={3}>
                        <Statistic title="Hub节点" value={isFlat ? (flat.top_hubs?.length ?? 0) : metrics.T4_scale_free.hubs} />
                    </Col>
                    <Col span={3}>
                        <Statistic title="幂律R²" value={isFlat ? (flat.power_law_r2 ?? 0) : metrics.T4_scale_free.power_law_r2} precision={3} />
                    </Col>
                    <Col span={3}>
                        <Statistic title="平均路径" value={isFlat ? (flat.avg_path_length ?? 0) : metrics.T3_small_world.avg_path_length} precision={2} />
                    </Col>
                </Row>
            </Card>
        )
    }

    return (
        <div>
            <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
                <Col span={6}>
                    <Card size="small" style={{ textAlign: 'center' }}>
                        <div style={{ marginBottom: 8 }}>
                            <TrophyOutlined style={{ fontSize: 32, color: GRADE_COLORS[auditData?.grade || 'B'] }} />
                        </div>
                        <Statistic
                            title="SSS认证等级"
                            value={auditData?.grade || 'N/A'}
                            valueStyle={{ color: GRADE_COLORS[auditData?.grade || 'B'], fontSize: 42, fontWeight: 'bold' }}
                        />
                    </Card>
                </Col>
                <Col span={6}>
                    <Card size="small">
                        <Statistic
                            title="加权得分"
                            value={auditData?.score?.toFixed(1) ?? '0.0'}
                            suffix="%"
                            valueStyle={{ color: (auditData?.score || 0) >= 95 ? '#cf1322' : '#1890ff' }}
                        />
                        <Progress
                            percent={auditData?.score || 0}
                            strokeColor={(auditData?.score || 0) >= 95 ? '#cf1322' : '#1890ff'}
                            showInfo={false}
                            style={{ marginTop: 8 }}
                        />
                    </Card>
                </Col>
                <Col span={6}>
                    <Card size="small">
                        <Statistic
                            title="通过率"
                            value={auditData && auditData.total > 0 ? ((auditData.passed / auditData.total) * 100).toFixed(0) : 0}
                            suffix={`% (${auditData?.passed || 0}/${auditData?.total || 0})`}
                            valueStyle={{ color: auditData?.passed === auditData?.total ? '#52c41a' : '#faad14' }}
                        />
                    </Card>
                </Col>
                <Col span={6}>
                    <Card size="small" style={{ textAlign: 'center' }}>
                        <Button
                            type="primary"
                            icon={<ReloadOutlined />}
                            onClick={fetchAuditData}
                            style={{ marginTop: 16 }}
                        >
                            重新审计
                        </Button>
                    </Card>
                </Col>
            </Row>

            {renderMetricsSummary()}
            {renderRadarData()}
            {renderDimensionDetails()}
        </div>
    )
}
