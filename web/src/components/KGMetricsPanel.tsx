import { Card, Tag, Progress, Statistic, Descriptions, Typography, Row, Col, Space } from 'antd'
import {
    CheckCircleOutlined,
    CloseCircleOutlined,
    SafetyCertificateOutlined,
} from '@ant-design/icons'
import { KGMetrics, SSSAuditResult, MemoryStats, getLayerCount, TYPE_COLORS } from '../types/kg-types'

const { Text } = Typography

interface KGMetricsPanelProps {
    metrics: KGMetrics | null
    auditData: SSSAuditResult | null
    memStats: MemoryStats | null
}

export function KGMetricsPanel({ metrics, auditData, memStats }: KGMetricsPanelProps) {
    if (!metrics) return null

    const gradeColor: Record<string, string> = {
        'S+': '#52c41a',
        S: '#73d13d',
        A: '#1890ff',
        B: '#faad14',
        C: '#ff4d4f',
        D: '#cf1322',
        F: '#8c8c8c',
    }

    return (
        <Row gutter={[16, 16]}>
            <Col span={24}>
                <Card
                    title={
                        <Space>
                            <SafetyCertificateOutlined />
                            <span>SSS审计结果</span>
                        </Space>
                    }
                    size="small"
                >
                    {auditData ? (
                        <>
                            <Row gutter={16}>
                                <Col span={6}>
                                    <Statistic
                                        title="总评分"
                                        value={auditData.score ?? 0}
                                        suffix="/ 100"
                                        valueStyle={{ color: gradeColor[auditData.grade] || '#8c8c8c' }}
                                    />
                                </Col>
                                <Col span={6}>
                                    <Statistic title="等级" value={auditData.grade ?? 'N/A'} />
                                </Col>
                                <Col span={6}>
                                    <Statistic
                                        title="通过"
                                        value={auditData.passed ?? '-'}
                                        suffix={auditData.total ? `/ ${auditData.total}` : ''}
                                        valueStyle={{ color: '#52c41a' }}
                                    />
                                </Col>
                                <Col span={6}>
                                    <Statistic
                                        title="失败"
                                        value={auditData.failed ?? '-'}
                                        valueStyle={{ color: (auditData.failed ?? 0) > 0 ? '#ff4d4f' : '#52c41a' }}
                                    />
                                </Col>
                            </Row>

                            {/* [FIX-BROWSER-REAL] auditData.results可能不存在，添加空值保护 */}
                            {Array.isArray(auditData.results) && auditData.results.length > 0 && (
                                <Descriptions size="small" column={2} style={{ marginTop: 16 }}>
                                    {auditData.results.slice(0, 8).map((r: any) => (
                                        <Descriptions.Item key={r.code ?? r.name ?? String(r)} label={r.name ?? r.code ?? '-'}>
                                            <Tag
                                                color={r.passed ? 'success' : 'error'}
                                                icon={r.passed ? <CheckCircleOutlined /> : <CloseCircleOutlined />}
                                            >
                                                {String(r.value ?? '-')}{r.unit ?? ''} {r.threshold ? `(≤${r.threshold})` : ''}
                                            </Tag>
                                        </Descriptions.Item>
                                    ))}
                                </Descriptions>
                            )}

                            {/* 显示后端实际返回的issues和recommendations（如果results不存在）*/}
                            {!Array.isArray(auditData.results) && (auditData.issues || auditData.recommendations) && (
                                <div style={{ marginTop: 16 }}>
                                    {Array.isArray(auditData.issues) && auditData.issues.length > 0 && (
                                        <div style={{ marginBottom: 8 }}>
                                            <Text strong>审计发现：</Text>
                                            {auditData.issues.map((issue: any, i: number) => (
                                                <Tag key={i} color="warning">{typeof issue === 'string' ? issue : JSON.stringify(issue)}</Tag>
                                            ))}
                                        </div>
                                    )}
                                    {Array.isArray(auditData.recommendations) && auditData.recommendations.length > 0 && (
                                        <div>
                                            <Text strong>建议：</Text>
                                            {auditData.recommendations.map((rec: any, i: number) => (
                                                <Tag key={i} color="blue">{typeof rec === 'string' ? rec : JSON.stringify(rec)}</Tag>
                                            ))}
                                        </div>
                                    )}
                                </div>
                            )}
                        </>
                    ) : (
                        <Text type="secondary">暂无审计数据</Text>
                    )}
                </Card>
            </Col>

            <Col span={24}>
                <Card title="T1-T8 指标概览" size="small">
                    <Row gutter={[12, 12]}>
                        {(() => {
                            // [FIX-KG-FORMAT] 兼容后端扁平格式和前端嵌套格式
                            const isFlat = metrics && !metrics.T1_scale && 'total_nodes' in (metrics as any)
                            if (isFlat) {
                                // 扁平格式: 展示实际可用的指标
                                const flat = metrics as any
                                const flatItems = [
                                    { label: '规模', value: flat.total_nodes ?? 0, max: 1000 },
                                    { label: '关系', value: flat.total_edges ?? 0, max: 10000 },
                                    { label: '密度', value: (flat.density ?? 0) * 100, max: 100 },
                                    { label: '幂律R²', value: (flat.power_law_r2 ?? 0) * 100, max: 100 },
                                    { label: '平均度', value: flat.avg_degree ?? 0, max: 100 },
                                    { label: '最大度', value: flat.max_degree ?? 0, max: 500 },
                                    { label: '路径长', value: (flat.avg_path_length ?? 0) * 20, max: 100 },
                                    { label: '类型数', value: Object.keys(flat.type_distribution || {}).length, max: 20 },
                                ]
                                return flatItems.map(item => (
                                    <Col key={item.label} span={6}>
                                        <Progress
                                            type="dashboard"
                                            percent={Math.min(100, Math.round((item.value / Math.max(item.max, 1)) * 100))}
                                            size={80}
                                            format={() => item.label}
                                        />
                                    </Col>
                                ))
                            }

                            // 嵌套格式: T1-T8
                            return Object.entries(metrics || {})
                                .filter(([k]) => k.startsWith('T') && k !== 'summary')
                                .map(([key, val]) => {
                                    const labelMap: Record<string, string> = {
                                        T1_scale: '规模',
                                        T2_topology: '拓扑',
                                        T3_small_world: '小世界',
                                        T4_scale_free: '无标度',
                                        T5_community: '社区',
                                        T6_semantic: '语义',
                                        T7_retrieval: '检索',
                                        T8_evolution: '演化',
                                    }
                                    const v = val as Record<string, any>
                                    return (
                                        <Col key={key} span={6}>
                                            <Progress
                                                type="dashboard"
                                                percent={Math.round((v.density ?? v.hubs ?? v.clustering_C ?? v.modularity_Q ?? 0) * 100)}
                                                size={80}
                                                format={() => labelMap[key] || key}
                                            />
                                        </Col>
                                    )
                                })
                        })()}
                    </Row>
                </Card>
            </Col>

            <Col span={24}>
                <Card title="六层记忆分布" size="small">
                    {memStats?.layers && (
                        <Row gutter={[8, 8]}>
                            {Object.entries(memStats.layers).map(([layer, val]) => {
                                const count = getLayerCount(val as any)
                                const total = memStats.total_entries || 1
                                const pct = ((count / total) * 100).toFixed(1)
                                const layerNames: Record<string, string> = {
                                    sensory: 'S 感知层',
                                    working: 'W 工作层',
                                    short_term: 'S-T 短期层',
                                    episodic: 'E 情景层',
                                    semantic: 'M 语义层',
                                    meta: 'Meta 元层',
                                }
                                return (
                                    <Col key={layer} span={8}>
                                        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                                            <div
                                                style={{
                                                    width: 12,
                                                    height: 12,
                                                    borderRadius: '50%',
                                                    backgroundColor: TYPE_COLORS[layer] || '#8c8c8c',
                                                }}
                                            />
                                            <Text>{layerNames[layer] || layer}</Text>
                                            <Text strong>{count.toLocaleString()}</Text>
                                            <Text type="secondary">{pct}%</Text>
                                        </div>
                                        <Progress
                                            percent={parseFloat(pct)}
                                            size="small"
                                            showInfo={false}
                                            strokeColor={TYPE_COLORS[layer] || '#8c8c8c'}
                                        />
                                    </Col>
                                )
                            })}
                            <Col span={24} style={{ textAlign: 'center', marginTop: 8 }}>
                                <Statistic title="记忆总量" value={memStats.total_entries} groupSeparator="," />
                            </Col>
                        </Row>
                    )}
                </Card>
            </Col>
        </Row>
    )
}
