import React, { useState, useEffect, useCallback } from 'react'
import { Card, Row, Col, Statistic, Progress, Space, Tag, Table, Button, Input, Select, Modal, message, Popconfirm, Tooltip, Alert, Descriptions, Divider } from 'antd'
import { PlusOutlined, DeleteOutlined, SearchOutlined, ReloadOutlined, ExportOutlined, DatabaseOutlined, ClusterOutlined, FolderOpenOutlined, RiseOutlined, FallOutlined, WarningOutlined, CheckCircleOutlined, HistoryOutlined } from '@ant-design/icons'
import type { ColumnsType } from 'antd/es/table'
import { api } from '../services/api'

const { Search } = Input
const { Option } = Select

const LAYER_COLORS: Record<string, string> = {
    sensory: '#722ed1', working: '#1677ff', short_term: '#13c2c2',
    episodic: '#52c41a', semantic: '#fa8c16', meta: '#eb2f96',
}
const LAYER_LABELS: Record<string, string> = {
    sensory: '感枢L0', working: '运枢L1', short_term: '近枢L2',
    episodic: '忆枢L3', semantic: '知枢L4', meta: '元枢L5',
}

interface LayerInfo {
    entry_count: number; max_entries: number; usage_ratio: number;
    size_bytes: number; max_size_bytes: number; needs_consolidation: boolean;
    entries_k?: number; max_entries_k?: number;
    delta_k?: number; rate_k_per_min?: number;
    thresholds?: { warn_k: number; critical_k: number; growth_rate_warn_k_per_min: number };
    status?: string;
}

interface StorageManagement {
    unit_system?: { capacity_unit: string; capacity_unit_label: string; rate_unit: string; base: number }
    summary?: {
        total_entries: number; total_entries_k: number; prev_total_k: number; delta_total_k: number;
        total_layers: number; total_db_size_mb: number; physical_total_kb: number; physical_total_mb: number;
        archive_entries: number; consolidations: number;
    }
    layers?: Record<string, LayerInfo>
    physical_storage?: Array<{ name: string; path: string; size_kb: number; size_mb: number; modified: string }>
    alerts?: Array<{
        level: string; layer: string; status: string; message: string;
        entries_k: number; delta_k: number; rate_k_per_min: number;
    }>
    threshold_config?: Record<string, { warn_k: number; critical_k: number; growth_rate_warn: number }>
    change_mechanism?: {
        snapshot_enabled: boolean; snapshot_path: string | null;
        prev_snapshot_age_min: number; auto_cleanup_wal: boolean;
    }
    orchestration?: { actions_taken?: any[] }
}

interface MemoryEntry {
    id: string; content: string; layer: string; tags: string[];
    priority: string; created_at: string; effectiveness_score?: number;
    access_count?: number; metadata?: Record<string, any>;
}

export default function MemoryManagement() {
    const [memories, setMemories] = useState<MemoryEntry[]>([])
    const [loading, setLoading] = useState(false)
    const [total, setTotal] = useState(0)
    const [page, setPage] = useState(1)
    const [pageSize, setPageSize] = useState(20)
    const [query, setQuery] = useState('')
    const [layerFilter, setLayerFilter] = useState<string | undefined>()
    const [priorityFilter, setPriorityFilter] = useState<string | undefined>()
    const [selectedRowKeys, setSelectedRowKeys] = useState<React.Key[]>([])
    const [layerInfo, setLayerInfo] = useState<Record<string, LayerInfo>>({})
    const [stats, setStats] = useState<any>({})
    const [storageData, setStorageData] = useState<StorageManagement | null>(null)
    const [storageLoading, setStorageLoading] = useState(false)
    const [storageError, setStorageError] = useState<string | null>(null)
    const [managementLogs, setManagementLogs] = useState<any[]>([])
    const [managing, setManaging] = useState(false)
    const [createVisible, setCreateVisible] = useState(false)
    const [detailVisible, setDetailVisible] = useState(false)
    const [currentMemory, setCurrentMemory] = useState<MemoryEntry | null>(null)
    const [newContent, setNewContent] = useState('')
    const [newLayer, setNewLayer] = useState('working')
    const [newTags, setNewTags] = useState('')
    const [newPriority, setNewPriority] = useState('medium')
    // [FIX-TS-013] 删除未使用的 viewMode state

    const fetchMemories = useCallback(async () => {
        setLoading(true)
        try {
            const params: any = { limit: pageSize, offset: (page - 1) * pageSize }
            if (query) params.query = query
            if (layerFilter) params.layer = layerFilter
            if (priorityFilter) params.priority = priorityFilter
            const res = await api.get('/api/memory/', { params })
            const dataList = Array.isArray(res) ? res : (res.memories || res.data || res.items || [])
            setMemories(dataList)
            setTotal(Array.isArray(res) ? dataList.length : (res.total || dataList.length || 0))
        } catch { message.error('记忆列表加载失败') }
        finally { setLoading(false) }
    }, [page, pageSize, query, layerFilter, priorityFilter])

    const fetchStats = useCallback(async () => {
        // 使用 allSettled 保证 stats 与 storage/management 相互独立；
        // storage/management 实测较慢，单独设置 60s 超时并展示加载/错误状态。
        setStorageLoading(true)
        setStorageError(null)
        const [statsResult, storageResult] = await Promise.allSettled([
            api.get('/api/memory/stats'),
            api.get('/api/memory/storage/management', { timeout: 60000 }),
        ])

        if (statsResult.status === 'fulfilled') {
            setStats(statsResult.value)
        } else {
            message.error('记忆统计加载失败')
        }

        if (storageResult.status === 'fulfilled') {
            const storageRes = storageResult.value
            if (storageRes?.layers) {
                setLayerInfo(storageRes.layers)
                setStorageData(storageRes as StorageManagement)
            }
        } else {
            const err: any = storageResult.reason
            const reason =
                err?.code === 'ECONNABORTED'
                    ? '存储管理数据加载超时（>60s），后端统计耗时过长'
                    : `存储管理数据加载失败: ${err?.message || '未知错误'}`
            setStorageError(reason)
        }
        setStorageLoading(false)
    }, [])

    useEffect(() => { fetchMemories() }, [fetchMemories])
    useEffect(() => { fetchStats() }, [fetchStats])

    const handleStorageManage = async (action: string, layer?: string) => {
        setManaging(true)
        try {
            const res = await api.post('/api/memory/storage/manage', { action, layer })
            if (res.actions_performed?.length > 0) {
                message.success(`执行 ${action}: ${res.total_actions} 个动作完成`)
                fetchStats()
                if (action === 'get_logs' && res.logs) {
                    setManagementLogs(res.logs.reverse())
                }
            } else {
                message.info('无需执行管理动作')
            }
        } catch (err: any) {
            message.error(`管理操作失败: ${err?.message || '未知错误'}`)
        } finally {
            setManaging(false)
        }
    }

    const handleCreate = async () => {
        if (!newContent.trim()) return
        try {
            await api.post('/api/memory/', {
                content: newContent,
                layer: newLayer,
                tags: newTags.split(',').map(t => t.trim()).filter(Boolean),
                priority: newPriority,
            })
            message.success('记忆创建成功')
            setCreateVisible(false)
            setNewContent(''); setNewLayer('working'); setNewTags(''); setNewPriority('medium')
            fetchMemories(); fetchStats()
        } catch (err: any) {
            const errMsg = err?.response?.data?.detail || err?.message || '创建失败'
            message.error(`记忆创建失败: ${errMsg}`)
        }
    }

    const handleDelete = async (id: string) => {
        try {
            await api.delete(`/api/memory/${id}`)
            message.success('已删除')
            fetchMemories(); fetchStats()
        } catch { message.error('删除失败') }
    }

    const handleBatchDelete = async () => {
        try {
            await api.post('/api/memory/batch-delete', { ids: selectedRowKeys })
            message.success(`已删除 ${selectedRowKeys.length} 条`)
            setSelectedRowKeys([])
            fetchMemories(); fetchStats()
        } catch { message.error('批量删除失败') }
    }

    const columns: ColumnsType<MemoryEntry> = [
        {
            title: '内容', dataIndex: 'content', key: 'content', ellipsis: true,
            render: (text, record) => (
                <a onClick={() => { setCurrentMemory(record); setDetailVisible(true) }}>{text?.slice(0, 80)}{text?.length > 80 ? '...' : ''}</a>
            ),
        },
        {
            title: '层级', dataIndex: 'layer', key: 'layer', width: 100,
            render: (layer: string) => <Tag color={LAYER_COLORS[layer]}>{LAYER_LABELS[layer] || layer}</Tag>,
        },
        {
            title: '溯源', key: 'provenance', width: 90,
            render: (_, record) => {
                const path = `icme.db → ${LAYER_LABELS[record.layer] || record.layer} → id:${record.id?.slice(0, 8)}...`
                return (
                    <Tooltip title={<span style={{ fontSize: 12 }}>{path}<br /><span style={{ color: '#999' }}>SQLite FTS5 全文索引</span></span>}>
                        <Tag color="blue" icon={<FolderOpenOutlined />} style={{ cursor: 'pointer' }}
                            onClick={() => { navigator.clipboard?.writeText(`icme.db → layer:${record.layer} → id:${record.id}`); message.success('溯源路径已复制') }}>
                            📁 溯源
                        </Tag>
                    </Tooltip>
                )
            },
        },
        {
            title: '标签', dataIndex: 'tags', key: 'tags', width: 200,
            render: (tags: string[]) => (Array.isArray(tags) ? tags : []).map(t => <Tag key={t}>{t}</Tag>),
        },
        {
            title: '优先级', dataIndex: 'priority', key: 'priority', width: 80,
            render: (p: string) => {
                const colors: Record<string, string> = { critical: 'red', high: 'orange', medium: 'blue', low: 'default' }
                return <Tag color={colors[p]}>{p}</Tag>
            },
        },
        {
            title: '创建时间', dataIndex: 'created_at', key: 'created_at', width: 160,
            render: (d: string) => d ? new Date(d).toLocaleString('zh-CN') : '-'
        },
        {
            title: '操作', key: 'action', width: 80,
            render: (_, record) => (
                <Popconfirm title="确定删除?" onConfirm={() => handleDelete(record.id)}>
                    <Button type="link" danger icon={<DeleteOutlined />} size="small" />
                </Popconfirm>
            ),
        },
    ]

    const layerNames = ['sensory', 'working', 'short_term', 'episodic', 'semantic', 'meta']
    // [FIX-TS-013] 删除未使用的 layerStats/getLayerCount (与 KGMetricsPanel 重复)
    // 如需统计可从 stats?.layers 直接读取

    return (
        <div style={{ padding: 24 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
                <h2 style={{ margin: 0 }}>
                    <DatabaseOutlined style={{ marginRight: 8 }} />
                    天机六层记忆管理 (ICME)
                </h2>
            </div>

            <Row gutter={[16, 16]} style={{ marginBottom: 24 }}>
                <Col xs={12} sm={6}><Card size="small"><Statistic title="总记忆数" value={stats?.total_entries || total} prefix={<DatabaseOutlined />} /></Card></Col>
                <Col xs={12} sm={6}><Card size="small"><Statistic title="命中率" value={stats?.hit_rate != null ? `${stats.hit_rate.toFixed(1)}%` : 'N/A'} prefix={<SearchOutlined />} /></Card></Col>
                <Col xs={12} sm={6}><Card size="small"><Statistic title="固结次数" value={stats?.consolidations || 0} prefix={<ReloadOutlined />} /></Card></Col>
                <Col xs={12} sm={6}><Card size="small"><Statistic title="归档条目" value={stats?.archive_entries || 0} prefix={<ExportOutlined />} /></Card></Col>
            </Row>

            <Card size="small" style={{ marginBottom: 16, background: 'linear-gradient(135deg, #e6f7ff 0%, #f0f5ff 100%)', border: '1px solid #91d5ff' }}>
                <Space size="large" wrap>
                    <Tooltip title="ICME混合存储架构主存储后端">
                        <Tag color="blue" icon={<DatabaseOutlined />}>存储后端: SQLite (icme.db)</Tag>
                    </Tooltip>
                    <Tooltip title="点击复制路径">
                        <Tag color="geekblue" icon={<FolderOpenOutlined />}
                            style={{ cursor: 'pointer', maxWidth: 360 }}
                            onClick={() => { navigator.clipboard?.writeText('D:\\元初系统\\天机v9.1\\data\\.memory\\icme.db'); message.success('路径已复制') }}>
                            数据库路径: D:\元初系统\天机v9.1\data\.memory\icme.db
                        </Tag>
                    </Tooltip>
                    {stats?.db_size_mb != null && (
                        <Tag color="green">数据库大小: {typeof stats.db_size_mb === 'number' ? stats.db_size_mb.toFixed(2) : stats.db_size_mb} MB</Tag>
                    )}
                    {stats?.last_updated && (
                        <Tag color="orange">最后更新: {new Date(stats.last_updated).toLocaleString('zh-CN')}</Tag>
                    )}
                </Space>
            </Card>

            <Card title={<><ClusterOutlined /> ICME六层架构概览 <Tag color="blue" style={{ marginLeft: 8 }}>单位: k (千条)</Tag></>} style={{ marginBottom: 16 }}>
                {storageLoading && !storageData && (
                    <Alert type="info" showIcon message="正在加载存储管理数据（后端统计较慢，最长等待 60 秒）..." style={{ marginBottom: 12 }} />
                )}
                {storageError && (
                    <Alert type="warning" showIcon closable message={storageError} style={{ marginBottom: 12 }} />
                )}
                {storageData?.summary && (
                    <Row gutter={[12, 8]} style={{ marginBottom: 16, background: '#fafafa', padding: '8px 16px', borderRadius: 6 }}>
                        <Col span={4}><Statistic title="总容量(k)" value={storageData.summary.total_entries_k} suffix="/ ∞" valueStyle={{ fontSize: 14 }} /></Col>
                        <Col span={4}>
                            <Statistic
                                title="变化量(Δk)"
                                value={Math.abs(storageData.summary.delta_total_k)}
                                prefix={storageData.summary.delta_total_k > 0 ? <RiseOutlined /> : (storageData.summary.delta_total_k < 0 ? <FallOutlined /> : null)}
                                suffix={<span style={{ fontSize: 11, color: '#888' }}>k</span>}
                                valueStyle={{ fontSize: 14, color: storageData.summary.delta_total_k > 0 ? '#cf1322' : (storageData.summary.delta_total_k < 0 ? '#389e0d' : undefined) }}
                            />
                        </Col>
                        <Col span={4}><Statistic title="DB大小(MB)" value={storageData.summary.total_db_size_mb} precision={1} valueStyle={{ fontSize: 14 }} /></Col>
                        <Col span={4}><Statistic title="物理存储(MB)" value={storageData.summary.physical_total_mb} precision={1} valueStyle={{ fontSize: 14 }} /></Col>
                        <Col span={4}><Statistic title="归档" value={storageData.summary.archive_entries} suffix="条" valueStyle={{ fontSize: 14 }} /></Col>
                        <Col span={4}><Statistic title="固结次数" value={storageData.summary.consolidations} valueStyle={{ fontSize: 14 }} /></Col>
                    </Row>
                )}
                {storageData?.alerts && storageData.alerts.length > 0 && (
                    <div style={{ marginBottom: 12 }}>
                        {storageData.alerts.map((alert, idx) => (
                            <Alert
                                key={idx}
                                type={alert.level === 'error' ? 'error' : (alert.level === 'warn' ? 'warning' : 'info')}
                                icon={alert.level === 'error' ? <WarningOutlined /> : (alert.status === 'GROWTH_ALERT' ? <RiseOutlined /> : (alert.status === 'SHRINK_ALERT' ? <FallOutlined /> : undefined))}
                                message={
                                    <span>
                                        {alert.message}
                                        {alert.rate_k_per_min !== undefined && Math.abs(alert.rate_k_per_min) > 0.0001 && (
                                            <span style={{ marginLeft: 8, fontWeight: 'bold', color: alert.rate_k_per_min > 0 ? '#cf1322' : '#389e0d' }}>
                                                变化率: {alert.rate_k_per_min > 0 ? '+' : ''}{alert.rate_k_per_min.toFixed(2)} k/min
                                            </span>
                                        )}
                                    </span>
                                }
                                showIcon
                                closable
                                style={{ marginBottom: 6 }}
                            />
                        ))}
                    </div>
                )}
                <Row gutter={[16, 8]}>
                    {layerNames.map(layer => {
                        const info = layerInfo[layer]
                        const entriesK = info?.entries_k ?? 0
                        const maxK = info?.max_entries_k ?? (info?.max_entries ?? 2000) / 1000
                        // [FIX-TS-013] 删除未使用的 ratio 变量
                        const delta = info?.delta_k ?? 0
                        const rate = info?.rate_k_per_min ?? 0
                        const status = info?.status || 'OK'
                        const pct = Math.max(1, Math.min(100, (entriesK / maxK) * 100))
                        const isOverThreshold = status !== 'OK'

                        return (
                            <Col xs={12} sm={4} key={layer}>
                                <Card size="small" style={{ borderLeft: `3px solid ${isOverThreshold ? (status === 'CRITICAL' ? '#ff4d4f' : '#faad14') : LAYER_COLORS[layer]}` }}>
                                    <Space direction="vertical" style={{ width: '100%' }} size={2}>
                                        <Space size={4}>
                                            <Tag color={LAYER_COLORS[layer]}>{LAYER_LABELS[layer]}</Tag>
                                            {isOverThreshold && (
                                                <Tag color={status === 'CRITICAL' ? 'red' : (status === 'WARNING' ? 'orange' : 'blue')}>
                                                    {status === 'GROWTH_ALERT' ? '增长' : (status === 'SHRINK_ALERT' ? '缩减' : status === 'CRITICAL' ? '临界' : '警告')}
                                                </Tag>
                                            )}
                                        </Space>
                                        <Statistic
                                            value={entriesK}
                                            suffix={`/ ${maxK} k`}
                                            valueStyle={{ fontSize: 18 }}
                                        />
                                        <Progress
                                            percent={Math.round(pct)}
                                            size="small"
                                            strokeColor={isOverThreshold ? (status === 'CRITICAL' ? '#ff4d4f' : '#faad14') : LAYER_COLORS[layer]}
                                            status={pct > 90 ? 'exception' : 'normal'}
                                        />
                                        {(Math.abs(delta) > 0.001 || Math.abs(rate) > 0.0001) && (
                                            <div style={{ fontSize: 11, display: 'flex', justifyContent: 'space-between', color: '#666' }}>
                                                <span>Δ{delta >= 0 ? '+' : ''}{delta.toFixed(3)}k</span>
                                                <span style={{ color: rate > 0 ? '#cf1322' : (rate < 0 ? '#389e0d' : '#999') }}>
                                                    {rate > 0 ? <RiseOutlined style={{ marginRight: 3 }} /> : (rate < 0 ? <FallOutlined style={{ marginRight: 3 }} /> : null)}
                                                    {rate > 0 ? '+' : ''}{rate.toFixed(2)} k/min
                                                </span>
                                            </div>
                                        )}
                                        {info?.thresholds && (
                                            <Tooltip title={`阈值: 警告≥${info.thresholds.warn_k}k | 临界≥${info.thresholds.critical_k}k | 增长率>${info.thresholds.growth_rate_warn_k_per_min}k/min`}>
                                                <div style={{ fontSize: 10, color: '#bbb' }}>⚡ 阈值: {info.thresholds.warn_k}k / {info.thresholds.critical_k}k</div>
                                            </Tooltip>
                                        )}
                                    </Space>
                                </Card>
                            </Col>
                        )
                    })}
                </Row>
            </Card>

            {storageData?.physical_storage && storageData.physical_storage.length > 0 && (
                <Card title={<><DatabaseOutlined /> 物理存储分布</>} style={{ marginBottom: 16 }} size="small">
                    <Descriptions column={4} size="small" bordered>
                        {storageData.physical_storage.map(pf => (
                            <Descriptions.Item key={pf.name} label={pf.name} span={1}>
                                <strong>{pf.size_mb}</strong> MB ({pf.size_kb} KB)
                                <br /><span style={{ fontSize: 10, color: '#999' }}>{pf.modified}</span>
                            </Descriptions.Item>
                        ))}
                        <Descriptions.Item label="总计" span={storageData.physical_storage.length % 4 || 4}>
                            <strong style={{ color: '#1677ff' }}>{storageData.summary?.physical_total_mb}</strong> MB
                        </Descriptions.Item>
                    </Descriptions>
                    {storageData.change_mechanism?.snapshot_path && (
                        <div style={{ marginTop: 8, fontSize: 12, color: '#888' }}>
                            <CheckCircleOutlined style={{ color: '#52c41a', marginRight: 4 }} />
                            变化量快照: 已启用 | 上次快照: {storageData.change_mechanism.prev_snapshot_age_min.toFixed(1)}分钟前
                            {storageData.change_mechanism.auto_cleanup_wal && <span style={{ marginLeft: 12 }}>| WAL日志: 待清理</span>}
                        </div>
                    )}
                </Card>
            )}

            <Card
                title={<><WarningOutlined /> 统筹管理面板</>}
                style={{ marginBottom: 16 }}
                extra={
                    <Space>
                        <Button type="primary" icon={<RiseOutlined />} loading={managing} onClick={() => handleStorageManage('consolidate_all')}>
                            全层固结
                        </Button>
                        <Button icon={<DatabaseOutlined />} loading={managing} onClick={() => handleStorageManage('cleanup_wal')}>
                            清理WAL日志
                        </Button>
                        <Button icon={<HistoryOutlined />} onClick={() => handleStorageManage('get_logs')}>
                            查看管理日志
                        </Button>
                    </Space>
                }
                size="small"
            >
                {storageData?.orchestration?.actions_taken && storageData.orchestration.actions_taken.length > 0 ? (
                    <>
                        <Alert
                            type="success"
                            message={`自动执行了 ${storageData.orchestration.actions_taken.length} 个管理动作`}
                            description={
                                <div style={{ marginTop: 8 }}>
                                    {storageData.orchestration.actions_taken.map((action: any, idx: number) => (
                                        <div key={idx} style={{ padding: '4px 0', borderBottom: '1px dashed #eee' }}>
                                            <Tag color={action.action === 'emergency_consolidate' ? 'red' : 'orange'}>
                                                {action.action === 'emergency_consolidate' ? '紧急固结' : (action.action === 'preventive_consolidate' ? '预防固结' : action.action)}
                                            </Tag>
                                            <strong>{LAYER_LABELS[action.layer] || action.layer}</strong>
                                            {' → '}
                                            {LAYER_LABELS[action.to_layer] || action.to_layer}
                                            {' | 固结: '}
                                            <span style={{ color: '#1677ff', fontWeight: 'bold' }}>{action.consolidated} 条</span>
                                            {' | 阈值: '}{action.threshold_used}
                                            {action.error && <span style={{ color: '#ff4d4f', marginLeft: 8 }}>错误: {action.error}</span>}
                                        </div>
                                    ))}
                                </div>
                            }
                            showIcon
                        />
                    </>
                ) : (
                    <div style={{ color: '#999', textAlign: 'center', padding: 12 }}>
                        <CheckCircleOutlined style={{ marginRight: 6, color: '#52c41a' }} />
                        当前无超限告警，存储状态正常
                    </div>
                )}

                {managementLogs.length > 0 && (
                    <div style={{ marginTop: 16 }}>
                        <Divider orientation="left" plain>历史管理记录</Divider>
                        <Table
                            size="small"
                            dataSource={managementLogs}
                            rowKey={(_, idx) => String(idx)}
                            pagination={false}
                            scroll={{ y: 200 }}
                            columns={[
                                {
                                    title: '时间',
                                    dataIndex: 'timestamp',
                                    width: 150,
                                    render: (t: number) => new Date(t * 1000).toLocaleString('zh-CN'),
                                },
                                {
                                    title: '动作',
                                    dataIndex: 'action',
                                    width: 140,
                                    render: (a: string) => (
                                        <Tag color={a.includes('emergency') ? 'red' : (a.includes('preventive') ? 'orange' : 'blue')}>{a}</Tag>
                                    ),
                                },
                                { title: '层级', dataIndex: 'layer', width: 90, render: (l: string) => LAYER_LABELS[l] || l },
                                { title: '目标层', dataIndex: 'to_layer', width: 90, render: (l: string) => LAYER_LABELS[l] || l },
                                {
                                    title: '固结数',
                                    dataIndex: 'consolidated',
                                    width: 80,
                                    render: (n: number) => n > 0 ? <strong>{n}</strong> : '-',
                                },
                                { title: '状态', dataIndex: 'status', width: 80 },
                            ]}
                        />
                    </div>
                )}
            </Card>

            <Card
                title="记忆列表"
                extra={
                    <Space wrap>
                        <Button icon={<ReloadOutlined />} onClick={() => { fetchMemories(); fetchStats() }}>刷新</Button>
                        <Button type="primary" icon={<PlusOutlined />} onClick={() => setCreateVisible(true)}>新建记忆</Button>
                    </Space>
                }
            >
                <Space style={{ marginBottom: 16 }} wrap>
                    <Search placeholder="搜索记忆内容..." allowClear onSearch={(v) => { setQuery(v); setPage(1); fetchMemories() }} style={{ width: 300 }} />
                    <Select placeholder="层级筛选" allowClear style={{ width: 120 }} value={layerFilter} onChange={(v) => { setLayerFilter(v); setPage(1); fetchMemories() }}>
                        {layerNames.map(l => <Option key={l} value={l}>{LAYER_LABELS[l]}</Option>)}
                    </Select>
                    <Select placeholder="优先级" allowClear style={{ width: 100 }} value={priorityFilter} onChange={(v) => { setPriorityFilter(v); setPage(1); fetchMemories() }}>
                        {['low', 'medium', 'high', 'critical'].map(p => <Option key={p} value={p}>{p}</Option>)}
                    </Select>
                    {selectedRowKeys.length > 0 && (
                        <Popconfirm title={`确定删除 ${selectedRowKeys.length} 条?`} onConfirm={handleBatchDelete}>
                            <Button danger>批量删除 ({selectedRowKeys.length})</Button>
                        </Popconfirm>
                    )}
                </Space>

                <Table
                    rowKey="id"
                    columns={columns}
                    dataSource={memories}
                    loading={loading}
                    rowSelection={{ selectedRowKeys, onChange: (keys) => setSelectedRowKeys(keys) }}
                    pagination={{ current: page, pageSize, total, onChange: (p, ps) => { setPage(p); setPageSize(ps) }, showSizeChanger: true, showTotal: (t) => `共 ${t} 条` }}
                    size="small"
                    scroll={{ x: 800 }}
                />
            </Card>

            <Modal title="新建记忆" open={createVisible} onOk={handleCreate} onCancel={() => setCreateVisible(false)} okText="创建">
                <Space direction="vertical" style={{ width: '100%' }} size="middle">
                    <div>
                        <div style={{ marginBottom: 4 }}>内容</div>
                        <Input.TextArea rows={4} value={newContent} onChange={e => setNewContent(e.target.value)} placeholder="输入记忆内容..." />
                    </div>
                    <div>
                        <div style={{ marginBottom: 4 }}>目标层级</div>
                        <Select value={newLayer} onChange={setNewLayer} style={{ width: '100%' }}>
                            {layerNames.map(l => <Option key={l} value={l}>{LAYER_LABELS[l]} ({l})</Option>)}
                        </Select>
                    </div>
                    <div>
                        <div style={{ marginBottom: 4 }}>标签 (逗号分隔)</div>
                        <Input value={newTags} onChange={e => setNewTags(e.target.value)} placeholder="天机, 记忆, 测试" />
                    </div>
                    <div>
                        <div style={{ marginBottom: 4 }}>优先级</div>
                        <Select value={newPriority} onChange={setNewPriority} style={{ width: '100%' }}>
                            {['low', 'medium', 'high', 'critical'].map(p => <Option key={p} value={p}>{p}</Option>)}
                        </Select>
                    </div>
                </Space>
            </Modal>

            <Modal title="记忆详情" open={detailVisible} onCancel={() => setDetailVisible(false)} footer={null} width={700}>
                {currentMemory && (
                    <div>
                        <p><strong>ID:</strong> {currentMemory.id}</p>
                        <p>
                            <strong>数据溯源:</strong>{' '}
                            <Tooltip title="点击复制完整存储路径">
                                <Tag color="blue" icon={<FolderOpenOutlined />} style={{ cursor: 'pointer' }}
                                    onClick={() => { navigator.clipboard?.writeText(`icme.db → layer:${currentMemory.layer} → id:${currentMemory.id}`); message.success('溯源路径已复制') }}>
                                    icme.db → {LAYER_LABELS[currentMemory.layer]}({currentMemory.layer}) → id:{currentMemory.id}
                                </Tag>
                            </Tooltip>
                            <Tag color="default" style={{ marginLeft: 4 }}>SQLite + FTS5</Tag>
                        </p>
                        <p><strong>层级:</strong> <Tag color={LAYER_COLORS[currentMemory.layer]}>{LAYER_LABELS[currentMemory.layer]}</Tag></p>
                        <p><strong>优先级:</strong> <Tag>{currentMemory.priority}</Tag></p>
                        <p><strong>标签:</strong> {currentMemory.tags?.map((t: string) => <Tag key={t}>{t}</Tag>)}</p>
                        <p><strong>创建时间:</strong> {currentMemory.created_at}</p>
                        <pre style={{ background: '#f5f5f5', padding: 16, borderRadius: 8, whiteSpace: 'pre-wrap', maxHeight: 400, overflow: 'auto' }}>
                            {currentMemory.content}
                        </pre>
                        {currentMemory.metadata && <pre style={{ background: '#f0f0f0', padding: 8, borderRadius: 4, marginTop: 8, fontSize: 12 }}>{JSON.stringify(currentMemory.metadata, null, 2)}</pre>}
                    </div>
                )}
            </Modal>
        </div>
    )
}
