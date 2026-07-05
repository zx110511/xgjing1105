import { useEffect, useRef, useState, useCallback } from 'react'
import { Card, Tag, Badge, Space, Typography, Empty, Spin, Tooltip, Button } from 'antd'
import { ReloadOutlined } from '@ant-design/icons'
import cytoscape, { Core, EventObject } from 'cytoscape'
import dagre from 'cytoscape-dagre'
import type { DAGPipelineData, DAGNodeData } from '../types/orchestrator'
import { NODE_STATUS_COLORS } from '../types/orchestrator'
import { orchestratorService } from '../services/orchestrator-service'

cytoscape.use(dagre)

const { Text } = Typography

interface PipelineCanvasProps {
  pipelineId?: string | null
  dagData?: DAGPipelineData | null
  onNodeClick?: (node: DAGNodeData) => void
  refreshInterval?: number
}

const STATUS_LABELS: Record<string, string> = {
  pending: '等待',
  ready: '就绪',
  running: '执行中',
  completed: '已完成',
  failed: '失败',
  skipped: '跳过',
  cancelled: '已取消',
}

function PipelineCanvas({
  pipelineId,
  dagData,
  onNodeClick,
  refreshInterval = 5000,
}: PipelineCanvasProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const cyRef = useRef<Core | null>(null)
  const [dag, setDag] = useState<DAGPipelineData | null>(dagData || null)
  const [loading, setLoading] = useState(false)
  const [selectedNode, setSelectedNode] = useState<DAGNodeData | null>(null)
  const [error, setError] = useState<string | null>(null)

  const fetchDAG = useCallback(async () => {
    if (!pipelineId) return
    try {
      const data = await orchestratorService.getDAGTopology(pipelineId)
      setDag(data)
      setError(null)
    } catch {
      if (!dag) setError('无法加载流水线数据')
    }
  }, [pipelineId, dag])

  useEffect(() => {
    if (dagData) {
      setDag(dagData)
    } else if (pipelineId) {
      setLoading(true)
      fetchDAG().finally(() => setLoading(false))
    }
  }, [pipelineId, dagData, fetchDAG])

  // Auto-refresh
  useEffect(() => {
    if (!pipelineId || !refreshInterval) return
    const timer = setInterval(fetchDAG, refreshInterval)
    return () => clearInterval(timer)
  }, [pipelineId, refreshInterval, fetchDAG])

  // Cytoscape render
  useEffect(() => {
    if (!containerRef.current || !dag) return

    if (cyRef.current) {
      cyRef.current.destroy()
    }

    const nodes = dag.nodes.map((n) => ({
      data: {
        id: n.id,
        label: n.data.label.length > 30 ? n.data.label.slice(0, 30) + '…' : n.data.label,
        fullLabel: n.data.label,
        agentName: n.data.agent_name,
        agentEmoji: n.data.agent_emoji,
        status: n.data.status,
        duration: n.data.duration_s ? `${n.data.duration_s.toFixed(1)}s` : '',
        error: n.data.error,
        nodeData: n,
      },
    }))

    const edges = dag.edges.map((e) => ({
      data: {
        id: e.id,
        source: e.source,
        target: e.target,
        type: e.data.type,
        animated: e.animated,
      },
    }))

    const cy = cytoscape({
      container: containerRef.current,
      elements: [...nodes, ...edges],
      style: [
        {
          selector: 'node',
          style: {
            'background-color': (ele: any) => NODE_STATUS_COLORS[ele.data('status')] || '#d9d9d9',
            label: 'data(label)',
            'text-valign': 'center',
            'text-halign': 'center',
            'font-size': '11px',
            'text-wrap': 'wrap',
            'text-max-width': '120px',
            color: '#333',
            width: 130,
            height: 60,
            shape: 'round-rectangle',
            'border-width': 2,
            'border-color': (ele: any) => {
              const s = ele.data('status')
              if (s === 'running') return '#1890ff'
              if (s === 'failed') return '#ff4d4f'
              if (s === 'completed') return '#52c41a'
              return '#d9d9d9'
            },
          },
        },
        {
          selector: 'node[status="running"]',
          style: {
            'border-style': 'dashed',
            'border-width': 3,
          },
        },
        {
          selector: 'edge',
          style: {
            width: 2,
            'line-color': '#b0b0b0',
            'target-arrow-color': '#b0b0b0',
            'target-arrow-shape': 'triangle',
            'curve-style': 'bezier',
            'arrow-scale': 1.2,
          },
        },
        {
          selector: 'edge[type="conditional"]',
          style: {
            'line-style': 'dashed',
            'line-color': '#faad14',
            'target-arrow-color': '#faad14',
          },
        },
        {
          selector: 'edge[type="data_flow"]',
          style: {
            'line-color': '#1890ff',
            'target-arrow-color': '#1890ff',
            width: 3,
          },
        },
        {
          selector: 'edge[animated]',
          style: {
            'line-style': 'dashed',
          },
        },
      ],
      layout: {
        name: 'dagre',
        // [FIX-TS-017] 修复 rankDir 类型错误: cytoscape-dagre 接受 rankDir 但 BaseLayoutOptions 不识别
        // 使用 as any 断言或扩展类型
        ...({ rankDir: 'LR' } as any),
        spacingFactor: 1.5,
        nodeDimensionsIncludeLabels: true,
      },
      wheelSensitivity: 0.3,
      minZoom: 0.3,
      maxZoom: 3,
    })

    cy.on('tap', 'node', (evt: EventObject) => {
      const nodeData = evt.target.data('nodeData') as DAGNodeData
      setSelectedNode(nodeData)
      onNodeClick?.(nodeData)
    })

    cy.on('tap', (evt: EventObject) => {
      if (evt.target === cy) {
        setSelectedNode(null)
      }
    })

    cyRef.current = cy

    return () => {
      cy.destroy()
      cyRef.current = null
    }
  }, [dag, onNodeClick])

  if (!pipelineId && !dagData) {
    return (
      <Empty
        description="选择或创建一个DAG流水线以查看可视化"
        image={Empty.PRESENTED_IMAGE_SIMPLE}
      />
    )
  }

  return (
    <div style={{ position: 'relative' }}>
      {/* 工具栏 */}
      <div
        style={{
          marginBottom: 12,
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          flexWrap: 'wrap',
          gap: 8,
        }}
      >
        <Space>
          <Text strong>{dag?.pipeline_name || 'DAG流水线'}</Text>
          {dag && (
            <Tag
              color={
                dag.status === 'completed' ? 'green' : dag.status === 'failed' ? 'red' : 'blue'
              }
            >
              {dag.status}
            </Tag>
          )}
        </Space>
        <Space>
          {dag && (
            <Space size={4} wrap>
              <Tooltip title="总计">
                <Tag>总计: {dag.stats.total}</Tag>
              </Tooltip>
              <Tooltip title="已完成">
                <Tag color="green">{dag.stats.completed}</Tag>
              </Tooltip>
              <Tooltip title="执行中">
                <Tag color="blue">{dag.stats.running}</Tag>
              </Tooltip>
              <Tooltip title="失败">
                <Tag color="red">{dag.stats.failed}</Tag>
              </Tooltip>
            </Space>
          )}
          <Button
            size="small"
            icon={<ReloadOutlined spin={loading} />}
            onClick={fetchDAG}
            disabled={!pipelineId}
          >
            刷新
          </Button>
        </Space>
      </div>

      {/* 图例 */}
      <div style={{ marginBottom: 8 }}>
        <Space size={12} wrap>
          {Object.entries(STATUS_LABELS).map(([key, label]) => (
            <Badge
              key={key}
              color={NODE_STATUS_COLORS[key]}
              text={<Text style={{ fontSize: 12 }}>{label}</Text>}
            />
          ))}
        </Space>
      </div>

      {/* 画布 */}
      <div style={{ position: 'relative', width: '100%', height: 480 }}>
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
              top: '50%',
              left: '50%',
              transform: 'translate(-50%, -50%)',
              zIndex: 10,
            }}
          >
            <Spin tip="加载流水线..." />
          </div>
        )}
        {error && (
          <div
            style={{
              position: 'absolute',
              top: '50%',
              left: '50%',
              transform: 'translate(-50%, -50%)',
            }}
          >
            <Text type="danger">{error}</Text>
          </div>
        )}
      </div>

      {/* 选中节点详情 */}
      {selectedNode && (
        <Card
          size="small"
          title={
            <Space>
              <span>{selectedNode.data.agent_emoji}</span>
              <span>@{selectedNode.data.agent_name}</span>
              <Tag
                color={
                  selectedNode.data.status === 'completed'
                    ? 'green'
                    : selectedNode.data.status === 'failed'
                      ? 'red'
                      : selectedNode.data.status === 'running'
                        ? 'blue'
                        : 'default'
                }
              >
                {STATUS_LABELS[selectedNode.data.status] || selectedNode.data.status}
              </Tag>
            </Space>
          }
          style={{ marginTop: 12 }}
        >
          <Text>{selectedNode.data.label}</Text>
          {selectedNode.data.duration_s > 0 && (
            <Text type="secondary" style={{ marginLeft: 16 }}>
              耗时: {selectedNode.data.duration_s.toFixed(1)}s
            </Text>
          )}
          {selectedNode.data.error && (
            <Text type="danger" style={{ display: 'block', marginTop: 8 }}>
              错误: {selectedNode.data.error}
            </Text>
          )}
        </Card>
      )}
    </div>
  )
}

export default PipelineCanvas
