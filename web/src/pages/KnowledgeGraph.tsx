import { useState } from 'react'
import {
    Row, Col, Card, Tag, Spin, Alert, Space,
    Typography, Button, Segmented, Divider, List, Empty, Statistic
} from 'antd'
import {
    SearchOutlined,
    ApartmentOutlined,
    ReloadOutlined,
    ClusterOutlined,
    SafetyCertificateOutlined,
} from '@ant-design/icons'
import { useKnowledgeGraph } from '../hooks/useKnowledgeGraph'
import { CytoscapeKG } from '../components/CytoscapeKG'
import { KGMetricsPanel } from '../components/KGMetricsPanel'
import { KGSearchBar } from '../components/KGSearchBar'
import {
    // [FIX-TS-013] 删除未使用的类型导入 (KGTopology/KGMetrics/SSSAuditResult/MemoryStats)
    TYPE_COLORS
} from '../types/kg-types'

const { Text } = Typography

export default function KnowledgeGraph() {
    const kg = useKnowledgeGraph()
    const [selectedNode, setSelectedNode] = useState<{
        id: string; type: string; degree: number; frequency: number
    } | null>(null)

    const nodeCount = kg.topology?.nodes?.length ?? 0
    const edgeCount = kg.topology?.edges?.length ?? 0
    const totalNodes = kg.topology?.meta?.total_nodes ?? 0
    const totalEdges = kg.topology?.meta?.total_edges ?? 0

    return (
        <div>
            <Card>
                <Row gutter={[16, 16]} align="middle">
                    <Col flex="auto">
                        <Space>
                            <ApartmentOutlined style={{ fontSize: 20, color: '#1890ff' }} />
                            <Typography.Title level={4} style={{ margin: 0 }}>
                                知识图谱
                            </Typography.Title>
                            <Tag color="purple">ICME六层架构</Tag>
                            <Tag color="blue">Cytoscape.js</Tag>
                        </Space>
                    </Col>
                    <Col>
                        <Space>
                            <Segmented
                                value={kg.viewMode}
                                onChange={v => kg.setViewMode(v)}
                                options={[
                                    { label: '网络拓扑', value: 'topology', icon: <ClusterOutlined /> },
                                    { label: '语义检索', value: 'search', icon: <SearchOutlined /> },
                                    { label: 'SSS审计', value: 'audit', icon: <SafetyCertificateOutlined /> },
                                ]}
                            />
                            <Button
                                icon={<ReloadOutlined />}
                                onClick={() => { setSelectedNode(null); kg.refreshData() }}
                                loading={kg.loading}
                            >
                                刷新
                            </Button>
                        </Space>
                    </Col>
                </Row>
            </Card>

            {kg.loading ? (
                <div style={{ textAlign: 'center', padding: 100 }}>
                    <Spin size="large">
                        <div style={{ padding: 60, color: '#999' }}>加载知识图谱数据...</div>
                    </Spin>
                </div>
            ) : kg.error ? (
                <Alert type="error" message={kg.error} showIcon />
            ) : (
                <>
                    {kg.viewMode === 'topology' && (
                        <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
                            <Col span={16}>
                                <Card
                                    title={
                                        <Space>
                                            <ApartmentOutlined />
                                            <span>记忆网络拓扑图</span>
                                            <Text type="secondary">
                                                {nodeCount}节点 · {edgeCount}边
                                                {totalNodes > 0 && ` (全量 ${totalNodes}/${totalEdges})`}
                                            </Text>
                                        </Space>
                                    }
                                >
                                    {kg.topology && Array.isArray(kg.topology.nodes) && kg.topology.nodes.length > 0 ? (
                                        <CytoscapeKG
                                            topology={kg.topology}
                                            onNodeSelect={(node) => setSelectedNode(node)}
                                        />
                                    ) : (
                                        <div style={{ textAlign: 'center', padding: 80, color: '#999' }}>
                                            暂无拓扑数据
                                        </div>
                                    )}

                                    {selectedNode && (
                                        <div style={{ marginTop: 12, padding: 12, background: '#f6f8fa', borderRadius: 8 }}>
                                            <Text strong>选中节点: </Text>
                                            <Tag color={TYPE_COLORS[selectedNode.type] || '#8c8c8c'}>{selectedNode.id}</Tag>
                                            <Text type="secondary">类型: {selectedNode.type}</Text>
                                            <Divider type="vertical" />
                                            <Text>度数: {selectedNode.degree}</Text>
                                            <Divider type="vertical" />
                                            <Text>频率: {selectedNode.frequency}</Text>
                                        </div>
                                    )}
                                </Card>
                            </Col>

                            <Col span={8}>
                                <KGMetricsPanel
                                    metrics={kg.metrics}
                                    auditData={kg.auditData}
                                    memStats={kg.memStats}
                                />
                            </Col>
                        </Row>
                    )}

                    {kg.viewMode === 'search' && (
                        <Card title="语义搜索" style={{ marginTop: 16 }}>
                            <KGSearchBar
                                searchQuery={kg.searchQuery}
                                searchType={kg.searchType}
                                searching={kg.searching}
                                onSearchChange={kg.setSearchQuery}
                                onTypeChange={kg.setSearchType}
                                onSearch={kg.handleSearch}
                            />

                            {kg.searchResults && (
                                <div style={{ marginTop: 16 }}>
                                    <Space size="large" style={{ marginBottom: 12 }}>
                                        <Statistic title="匹配实体" value={kg.searchResults.matched_nodes ?? 0} />
                                        <Statistic title="子图节点" value={kg.searchResults.subgraph_nodes ?? 0} />
                                        <Statistic title="关联边" value={kg.searchResults.edges ?? 0} />
                                    </Space>
                                    {Array.isArray(kg.searchResults.nodes) && kg.searchResults.nodes.length > 0 ? (
                                        <List
                                            size="small"
                                            bordered
                                            dataSource={kg.searchResults.nodes}
                                            renderItem={(item: any) => (
                                                <List.Item
                                                    style={{ cursor: 'pointer' }}
                                                    onClick={() => {
                                                        setSelectedNode({
                                                            id: item.id,
                                                            type: item.type,
                                                            degree: item.degree ?? 0,
                                                            frequency: item.frequency ?? 0,
                                                        })
                                                        kg.setViewMode('topology')
                                                    }}
                                                    actions={[
                                                        <Text type="secondary" key="freq">频率 {item.frequency ?? 0}</Text>,
                                                    ]}
                                                >
                                                    <Space>
                                                        <Tag color={TYPE_COLORS[item.type] || '#8c8c8c'}>{item.type}</Tag>
                                                        <Text strong>{item.id}</Text>
                                                    </Space>
                                                </List.Item>
                                            )}
                                        />
                                    ) : (
                                        <Empty description="无匹配实体" />
                                    )}
                                </div>
                            )}
                        </Card>
                    )}

                    {kg.viewMode === 'audit' && (
                        <div style={{ marginTop: 16 }}>
                            <KGMetricsPanel
                                metrics={kg.metrics}
                                auditData={kg.auditData}
                                memStats={kg.memStats}
                            />
                        </div>
                    )}
                </>
            )}
        </div>
    )
}
