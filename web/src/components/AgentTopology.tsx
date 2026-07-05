import { useEffect, useRef, useState, useCallback } from 'react'
import { Card, Space, Typography, Tag, Spin } from 'antd'
import cytoscape, { Core, EventObject } from 'cytoscape'
import coseBilkent from 'cytoscape-cose-bilkent'
import { orchestratorService } from '../services/orchestrator-service'

cytoscape.use(coseBilkent)

const { Text } = Typography

interface AgentNode {
    id: string
    name: string
    description: string
    utilization: number
    successRate: number
    taskCount: number
    avgDuration: number
    capabilities: string[]
    skills: string[]
}

interface TopologyEdge {
    source: string
    target: string
    /** 架构定义的协作链路强度，仅用于拓扑布局（非运行时统计） */
    weight: number
}

interface AgentTopologyProps {
    refreshInterval?: number
}

/**
 * 天机 Agent 层级协作链路（基于系统宪法的架构定义）
 * 仅定义 Agent 之间是否存在协作关系及链路强度(weight，用于布局)。
 * 不包含运行时 successRate / collaborationCount 等统计指标（后端暂无边级协作统计端点）。
 */
const AGENT_HIERARCHY_EDGES: TopologyEdge[] = [
    // L1 → L2 上游感知层 → 调度核心
    { source: 'yiku', target: 'tianshu', weight: 0.85 },
    { source: 'dongcha', target: 'tianshu', weight: 0.8 },
    { source: 'luling', target: 'tianshu', weight: 0.6 },
    { source: 'lingxi', target: 'tianshu', weight: 0.55 },
    // L2 工业流水线: 需求→架构→开发→审校→测试→部署
    { source: 'dongcha', target: 'jingwei', weight: 0.9 },
    { source: 'jingwei', target: 'miaobi', weight: 0.85 },
    { source: 'miaobi', target: 'mingjing', weight: 0.95 },
    { source: 'mingjing', target: 'tiewei', weight: 0.8 },
    { source: 'tiewei', target: 'gongzao', weight: 0.75 },
    // 天枢调度辐射
    { source: 'tianshu', target: 'dongcha', weight: 0.7 },
    { source: 'tianshu', target: 'tiansuan', weight: 0.65 },
    { source: 'tianshu', target: 'zhenshan', weight: 0.5 },
    { source: 'tianshu', target: 'zhuiguang', weight: 0.55 },
    { source: 'tianshu', target: 'jingwei', weight: 0.72 },
    { source: 'tianshu', target: 'wenzong', weight: 0.45 },
    // 双向反馈环
    { source: 'mingjing', target: 'miaobi', weight: 0.6 },
    // L3 归档与导出
    { source: 'jinshu', target: 'shiguan', weight: 0.4 },
    { source: 'baiqiao', target: 'tianshu', weight: 0.35 },
]

function AgentTopology(_props: AgentTopologyProps) {
    const containerRef = useRef<HTMLDivElement>(null)
    const cyRef = useRef<Core | null>(null)
    const [selectedAgent, setSelectedAgent] = useState<AgentNode | null>(null)
    const [loading, setLoading] = useState(true)
    const [agents, setAgents] = useState<AgentNode[]>([])
    const [error, setError] = useState<string | null>(null)
    const [totalTasks, setTotalTasks] = useState(0)

    /** 从 A2A API 加载真实 Agent 卡片与调度统计 */
    const loadAgentData = useCallback(async () => {
        try {
            const [cardResp, statsResp, a2aStats, agentStatsResp] = await Promise.all([
                orchestratorService.getAgentCards().catch(() => null),
                orchestratorService.getStats().catch(() => null),
                orchestratorService.getA2AStats().catch(() => null),
                orchestratorService.getAgentStats().catch(() => null),
            ])

            if (cardResp?.agent_cards) {
                const dagStats = statsResp?.dag_scheduler
                const totalNodes = dagStats?.nodes_executed || 0
                const failedNodes = dagStats?.nodes_failed || 0
                const baseSuccess = totalNodes > 0 ? (totalNodes - failedNodes) / totalNodes : null

                // 真实 Agent 运行统计 (来自 ToolCallTracker)，无记录时回退 DAG 基线
                const realStats = agentStatsResp?.agents || {}

                setTotalTasks(a2aStats?.total_tasks || 0)

                const agentList: AgentNode[] = cardResp.agent_cards.map((card) => {
                    const agentId = card.url.split('/').pop() || card.name
                    const working = a2aStats?.tasks_by_state?.working || 0
                    const submitted = a2aStats?.tasks_by_state?.submitted || 0
                    const utilization = Math.min(1, (working + submitted * 0.5) / Math.max(1, cardResp.count))

                    const stat = realStats[agentId]

                    return {
                        id: agentId,
                        name: card.name,
                        description: card.description,
                        // [FIX-FAB-007] 无真实数据时显示 0 而非伪造的 0.15
                        utilization: utilization || 0,
                        // [FIX-FAB-007] 无真实数据时显示 0 而非伪造的 0.95
                        successRate: stat ? stat.success_rate : (baseSuccess ?? 0),
                        taskCount: stat ? stat.task_count : 0,
                        avgDuration: stat ? stat.avg_duration_s : 0,
                        capabilities: Object.keys(card.capabilities || {}).filter((k) => card.capabilities[k]),
                        skills: (card.skills || []).map((s) => s.name),
                    }
                })

                setAgents(agentList)
                setError(null)
            } else {
                setError('无法获取 Agent 数据')
            }
        } catch {
            setError('天机调度引擎未连接')
        } finally {
            setLoading(false)
        }
    }, [])

    useEffect(() => {
        loadAgentData()
    }, [loadAgentData])

    /** 构建 Cytoscape 拓扑图 */
    const buildGraph = useCallback(() => {
        if (!containerRef.current || agents.length === 0) return

        if (cyRef.current) {
            cyRef.current.destroy()
        }

        const cyNodes = agents.map((a) => ({
            data: {
                id: a.id,
                label: a.name,
                utilization: a.utilization,
                successRate: a.successRate,
                taskCount: a.taskCount,
                agentData: a,
            },
        }))

        // 只保留两端 Agent 均存在的边
        const agentIdSet = new Set(agents.map((a) => a.id))
        const validEdges = AGENT_HIERARCHY_EDGES.filter(
            (e) => agentIdSet.has(e.source) && agentIdSet.has(e.target)
        )

        const cyEdges = validEdges.map((e) => ({
            data: {
                id: `${e.source}-${e.target}`,
                source: e.source,
                target: e.target,
                weight: e.weight,
            },
        }))

        const cy = cytoscape({
            container: containerRef.current,
            elements: [...cyNodes, ...cyEdges],
            style: [
                {
                    selector: 'node',
                    style: {
                        'background-color': (ele: any) => {
                            const sr = ele.data('successRate')
                            if (sr >= 0.95) return '#52c41a'
                            if (sr >= 0.85) return '#1890ff'
                            if (sr >= 0.7) return '#faad14'
                            return '#ff4d4f'
                        },
                        label: 'data(label)',
                        'text-valign': 'bottom',
                        'text-halign': 'center',
                        'font-size': '11px',
                        color: '#333',
                        'text-margin-y': 6,
                        width: (ele: any) => Math.max(42, 30 + ele.data('taskCount') * 1.2),
                        height: (ele: any) => Math.max(42, 30 + ele.data('taskCount') * 1.2),
                        'border-width': 2,
                        'border-color': '#fff',
                    },
                },
                {
                    selector: 'edge',
                    style: {
                        width: (ele: any) => Math.max(1, ele.data('weight') * 4),
                        'line-color': '#c0c0c0',
                        'target-arrow-color': '#b0b0b0',
                        'target-arrow-shape': 'triangle',
                        'curve-style': 'bezier',
                        opacity: (ele: any) => Math.max(0.3, ele.data('weight')),
                    },
                },
            ],
            layout: {
                name: 'cose-bilkent',
                animate: 'end',
                animationDuration: 2000,
                gravity: 0.4,
                idealEdgeLength: 120,
                nodeRepulsion: 8000,
            } as any,
            wheelSensitivity: 0.3,
            minZoom: 0.2,
            maxZoom: 3,
        })

        cy.on('tap', 'node', (evt: EventObject) => {
            setSelectedAgent(evt.target.data('agentData'))
        })

        cy.on('tap', (evt: EventObject) => {
            if (evt.target === cy) setSelectedAgent(null)
        })

        cyRef.current = cy
    }, [agents])

    useEffect(() => {
        buildGraph()
        return () => {
            cyRef.current?.destroy()
            cyRef.current = null
        }
    }, [buildGraph])

    return (
        <div style={{ position: 'relative' }}>
            <div
                style={{
                    marginBottom: 12,
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                }}
            >
                <Space>
                    <Text strong>Agent 协作拓扑</Text>
                    {totalTasks > 0 && <Tag color="purple">{totalTasks} 个活跃任务</Tag>}
                    <Tag color="green">成功率 ≥95%</Tag>
                    <Tag color="blue">≥85%</Tag>
                    <Tag color="orange">≥70%</Tag>
                    <Tag color="red">&lt;70%</Tag>
                </Space>
                <Text type="secondary" style={{ fontSize: 12 }}>
                    {agents.length} Agent · 节点大小=任务量 · 节点颜色=成功率 · 边粗细=架构协作权重
                </Text>
            </div>

            {error && (
                <Text type="secondary" style={{ display: 'block', marginBottom: 12 }}>
                    {error} — 显示 DAG 拓扑基线，数据来源于 <Text code>AGENT_HIERARCHY_EDGES</Text>
                </Text>
            )}

            <div style={{ display: 'flex', gap: 12 }}>
                <div style={{ position: 'relative', flex: 1, height: 520 }}>
                    <div
                        ref={containerRef}
                        style={{
                            width: '100%',
                            height: '100%',
                            border: '1px solid #f0f0f0',
                            borderRadius: 8,
                            background: '#fafafa',
                        }}
                    />
                    {loading && (
                        <div
                            style={{
                                position: 'absolute',
                                top: 0,
                                left: 0,
                                right: 0,
                                bottom: 0,
                                display: 'flex',
                                alignItems: 'center',
                                justifyContent: 'center',
                                background: 'rgba(250,250,250,0.7)',
                                borderRadius: 8,
                                zIndex: 10,
                            }}
                        >
                            <Spin tip="正在从天机引擎加载 Agent 拓扑..." />
                        </div>
                    )}
                </div>

                {selectedAgent && (
                    <Card
                        size="small"
                        title={<Text strong>{selectedAgent.name}</Text>}
                        style={{ width: 240, flexShrink: 0 }}
                    >
                        <Space direction="vertical" size={8} style={{ width: '100%' }}>
                            <Text type="secondary" style={{ fontSize: 12 }}>
                                {selectedAgent.description}
                            </Text>
                            <div>
                                <Text>利用率: {(selectedAgent.utilization * 100).toFixed(0)}%</Text>
                            </div>
                            <div>
                                <Text>成功率: {(selectedAgent.successRate * 100).toFixed(0)}%</Text>
                            </div>
                            <div>
                                <Text>任务数: {selectedAgent.taskCount}</Text>
                            </div>
                            <div>
                                <Text>平均耗时: {selectedAgent.avgDuration.toFixed(1)}s</Text>
                            </div>
                            {selectedAgent.capabilities.length > 0 && (
                                <div>
                                    <Text type="secondary" style={{ fontSize: 11 }}>
                                        能力:
                                    </Text>
                                    <div style={{ marginTop: 2 }}>
                                        {selectedAgent.capabilities.map((c) => (
                                            <Tag key={c} color="blue" style={{ fontSize: 10, marginBottom: 2 }}>
                                                {c}
                                            </Tag>
                                        ))}
                                    </div>
                                </div>
                            )}
                            {selectedAgent.skills.length > 0 && (
                                <div>
                                    <Text type="secondary" style={{ fontSize: 11 }}>
                                        技能:
                                    </Text>
                                    <div style={{ marginTop: 2 }}>
                                        {selectedAgent.skills.slice(0, 5).map((s) => (
                                            <Tag key={s} style={{ fontSize: 10, marginBottom: 2 }}>
                                                {s}
                                            </Tag>
                                        ))}
                                    </div>
                                </div>
                            )}
                        </Space>
                    </Card>
                )}
            </div>
        </div>
    )
}

export default AgentTopology
