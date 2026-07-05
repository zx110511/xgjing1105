import { useState, useEffect, useRef, useCallback } from 'react'
import {
  CloudServerOutlined,
  RobotOutlined,
  ReadOutlined,
  DatabaseOutlined,
  SettingOutlined,
  MonitorOutlined,
  RightOutlined,
  DownOutlined,
  ReloadOutlined,
  CloseOutlined,
  CheckCircleOutlined,
  ExclamationCircleOutlined,
  MinusCircleOutlined,
  ThunderboltOutlined,
  MenuFoldOutlined,
  MenuUnfoldOutlined,
  AimOutlined,
  WifiOutlined,
  DashboardOutlined,
} from '@ant-design/icons'
import { api } from '../services/api'

const CONTAINERS = [
  {
    key: 'brain_core',
    label: 'DeepSeek大脑核心',
    icon: <AimOutlined />,
    color: '#722ed1',
    modules: ['deepseek_driver'],
  },
  {
    key: 'enforcement_system',
    label: '强制记录系统',
    icon: <CloudServerOutlined />,
    color: '#13c2c2',
    modules: ['enforcement_hook', 'skill_pipeline'],
  },
  {
    key: 'scheduling_intelligence',
    label: '统一调度体系 ★',
    icon: <RobotOutlined />,
    color: '#52c41a',
    modules: ['trae_agent_scheduler', 'tvp_bridge', 'async_bridge'],
  },
  {
    key: 'learning_evolution',
    label: '学习进化引擎',
    icon: <ReadOutlined />,
    color: '#1890ff',
    modules: [
      'skill_registry',
      'learning_engine',
      'workflow_engine',
      'evolution_engine',
      'evolution_loop',
    ],
  },
  {
    key: 'infrastructure',
    label: '基础设施层',
    icon: <DatabaseOutlined />,
    color: '#fa8c16',
    modules: ['auto_capture', 'backup_manager', 'message_gateway'],
  },
  {
    key: 'daemon_agents',
    label: '守护进程+Agent',
    icon: <SettingOutlined />,
    color: '#eb2f96',
    modules: [
      'daemon_watchdog',
      'daemon_autobackup',
      'daemon_autorepair',
      'daemon_integrity',
      'agent_build',
      'agent_test',
      'agent_recovery',
      'agent_pipeline_logger',
      'agent_runtime_recovery',
    ],
  },
]

interface ModuleStats {
  status: string
  last_update?: number
  key_metrics?: Record<string, unknown>
  error?: string
}

interface SystemStats {
  modules: Record<string, Record<string, unknown>>
  dimensions: {
    realtime: Record<string, ModuleStats>
    cumulative: Record<string, Record<string, unknown>>
    history: {
      snapshots: Array<{ timestamp: number; online_modules: number; coverage_pct: number }>
    }
  }
  coverage: { total: number; online: number; with_stats: number }
  module_count: number
}

interface SSEData {
  timestamp: number
  rt_cache: Record<string, unknown>
  modules: Record<string, unknown>
}

export default function MonitoringSidebar() {
  const [collapsed, setCollapsed] = useState(true)
  const [expandedContainers, setExpandedContainers] = useState<Set<string>>(
    new Set(['brain_core', 'scheduling_intelligence'])
  )
  const [expandedInstances, setExpandedInstances] = useState<Set<string>>(new Set())
  const [stats, setStats] = useState<SystemStats | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [sseConnected, setSseConnected] = useState(false)
  const [sseData, setSseData] = useState<SSEData | null>(null)
  const [schedulerInfo, setSchedulerInfo] = useState<Record<string, unknown>>({})
  const intervalRef = useRef<number | null>(null)
  const sseRef = useRef<EventSource | null>(null)

  const connectSSE = useCallback(() => {
    if (sseRef.current) return
    try {
      const es = new EventSource('/api/container/monitoring/stream')
      es.onmessage = (e) => {
        try {
          const data: SSEData = JSON.parse(e.data)
          setSseData(data)
          setSseConnected(true)
          setError(null)
          if (data.modules?.['trae_agent_scheduler']) {
            setSchedulerInfo(data.modules['trae_agent_scheduler'] as Record<string, unknown>)
          }
        } catch {
          /* skip malformed SSE data */
        }
      }
      es.onerror = () => {
        setSseConnected(false)
      }
      sseRef.current = es
    } catch {
      setSseConnected(false)
    }
  }, [])

  const disconnectSSE = useCallback(() => {
    if (sseRef.current) {
      sseRef.current.close()
      sseRef.current = null
      setSseConnected(false)
      setSseData(null)
    }
  }, [])

  useEffect(() => {
    fetchStats()
    intervalRef.current = window.setInterval(fetchStats, 6000)
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current)
      disconnectSSE()
    }
  }, [])

  useEffect(() => {
    if (!collapsed && !sseConnected) {
      connectSSE()
    } else if (collapsed) {
      disconnectSSE()
    }
  }, [collapsed, connectSSE, disconnectSSE])

  const fetchStats = async () => {
    try {
      setLoading(true)
      const response = await api.get('/api/system/stats')
      setStats(response as SystemStats)
      setError(null)
    } catch {
      setError('监控离线')
    } finally {
      setLoading(false)
    }
  }

  const toggleContainer = (key: string) => {
    setExpandedContainers((prev) => {
      const next = new Set(prev)
      if (next.has(key)) next.delete(key)
      else next.add(key)
      return next
    })
  }

  const toggleInstance = (key: string) => {
    setExpandedInstances((prev) => {
      const next = new Set(prev)
      if (next.has(key)) next.delete(key)
      else next.add(key)
      return next
    })
  }

  const getModuleStatus = (moduleName: string): 'online' | 'offline' | 'error' => {
    const rt = stats?.dimensions?.realtime?.[moduleName]
    if (!rt) return 'offline'
    if (rt.status === 'online') return 'online'
    if (rt.status === 'error') return 'error'
    return 'offline'
  }

  const formatVal = (v: unknown): string => {
    if (v === null || v === undefined) return '-'
    if (typeof v === 'boolean') return v ? '✓' : '✗'
    if (typeof v === 'number') return v.toLocaleString()
    if (typeof v === 'object')
      return JSON.stringify(v).slice(0, 40) + (JSON.stringify(v).length > 40 ? '...' : '')
    return String(v)
  }

  const statusIcon = (s: 'online' | 'offline' | 'error') => {
    switch (s) {
      case 'online':
        return <CheckCircleOutlined style={{ color: '#52c41a' }} />
      case 'error':
        return <ExclamationCircleOutlined style={{ color: '#ff4d4f' }} />
      case 'offline':
        return <MinusCircleOutlined style={{ color: '#d9d9d9' }} />
    }
  }

  const onlineCount = stats?.coverage?.online ?? 0
  const totalCount = stats?.coverage?.total ?? 44

  return (
    <>
      <div
        className="monitoring-toggle"
        onClick={() => setCollapsed(!collapsed)}
        title={collapsed ? '展开监控面板' : '收起监控面板'}
      >
        {collapsed ? <MenuUnfoldOutlined /> : <MenuFoldOutlined />}
        {!collapsed ? null : (
          <span
            className="monitoring-toggle-badge"
            style={{
              background: error ? '#ff4d4f' : onlineCount > 0 ? '#52c41a' : '#faad14',
            }}
          >
            {error ? '!' : `${onlineCount}/${totalCount}`}
          </span>
        )}
      </div>

      {!collapsed && (
        <div className="monitoring-sidebar">
          <div className="monitoring-sidebar-header">
            <MonitorOutlined style={{ marginRight: 8 }} />
            <span style={{ flex: 1 }}>天机监控 v9.1</span>
            <span className="monitoring-sidebar-stats">
              {onlineCount}/{totalCount} 在线
            </span>
            {sseConnected ? (
              <WifiOutlined style={{ color: '#52c41a', marginLeft: 6 }} title="SSE实时连接" />
            ) : (
              <WifiOutlined style={{ color: '#d9d9d9', marginLeft: 6 }} title="轮询模式" />
            )}
            <ReloadOutlined
              onClick={fetchStats}
              style={{
                marginLeft: 10,
                cursor: 'pointer',
                opacity: 0.7,
                animation: loading ? 'spin 1s linear infinite' : 'none',
              }}
            />
            <CloseOutlined
              onClick={() => setCollapsed(true)}
              style={{ marginLeft: 10, cursor: 'pointer', opacity: 0.7 }}
            />
          </div>

          <div className="monitoring-sidebar-body">
            {error && (
              <div className="monitoring-error-bar">
                <ExclamationCircleOutlined /> {error}
              </div>
            )}

            {sseData && (
              <div
                style={{
                  padding: '8px 12px',
                  background: '#f6ffed',
                  borderLeft: '3px solid #52c41a',
                  marginBottom: 4,
                  fontSize: 11,
                }}
              >
                <DashboardOutlined style={{ marginRight: 4, color: '#52c41a' }} /> SSE实时 ·{' '}
                {Object.keys(sseData.modules || {}).length}模块数据
              </div>
            )}

            {schedulerInfo && Object.keys(schedulerInfo).length > 0 && (
              <div
                style={{
                  padding: '8px 12px',
                  background: '#fff7e6',
                  borderLeft: '3px solid #faad14',
                  marginBottom: 4,
                  fontSize: 11,
                }}
              >
                <RobotOutlined style={{ marginRight: 4, color: '#faad14' }} /> 统一调度: 调度
                {formatVal(schedulerInfo.dispatched)} · 编排
                {formatVal(schedulerInfo.orchestrations)} · TVP
                {formatVal(schedulerInfo.tvp_declarations)}
                待处理{formatVal(schedulerInfo.pending_tasks)}
              </div>
            )}

            {CONTAINERS.map((container) => {
              const isContainerExpanded = expandedContainers.has(container.key)
              const containerOnlineCount = container.modules.filter(
                (m) => getModuleStatus(m) === 'online'
              ).length

              return (
                <div key={container.key} className="monitoring-container">
                  <div
                    className="monitoring-container-header"
                    onClick={() => toggleContainer(container.key)}
                    style={{ borderLeftColor: container.color }}
                  >
                    <span className="monitoring-container-icon">
                      {isContainerExpanded ? <DownOutlined /> : <RightOutlined />}
                    </span>
                    <span className="monitoring-container-label-icon">{container.icon}</span>
                    <span className="monitoring-container-label">{container.label}</span>
                    <span
                      className="monitoring-container-count"
                      style={{ background: container.color }}
                    >
                      {containerOnlineCount}/{container.modules.length}
                    </span>
                  </div>

                  {isContainerExpanded && (
                    <div className="monitoring-instances">
                      {container.modules.map((moduleName) => {
                        const status = getModuleStatus(moduleName)
                        const isExpanded = expandedInstances.has(`${container.key}:${moduleName}`)
                        const metrics = stats?.dimensions?.realtime?.[moduleName]?.key_metrics
                        const cumData = stats?.dimensions?.cumulative?.[moduleName]
                        const sseMetrics = sseData?.modules?.[moduleName] as
                          | Record<string, unknown>
                          | undefined

                        return (
                          <div key={moduleName} className="monitoring-instance">
                            <div
                              className="monitoring-instance-header"
                              onClick={() => toggleInstance(`${container.key}:${moduleName}`)}
                            >
                              <span className="monitoring-instance-arrow">
                                {isExpanded ? (
                                  <DownOutlined style={{ fontSize: 10 }} />
                                ) : (
                                  <RightOutlined style={{ fontSize: 10 }} />
                                )}
                              </span>
                              {statusIcon(status)}
                              <span className="monitoring-instance-name">{moduleName}</span>
                              {sseConnected && sseMetrics && (
                                <span style={{ fontSize: 9, color: '#52c41a', marginLeft: 4 }}>
                                  ●LIVE
                                </span>
                              )}
                              <span
                                className={`monitoring-instance-status monitoring-instance-status-${status}`}
                              >
                                {status === 'online'
                                  ? '在线'
                                  : status === 'error'
                                    ? '错误'
                                    : '离线'}
                              </span>
                            </div>

                            {isExpanded && (
                              <div className="monitoring-instance-details">
                                {status === 'online' &&
                                  sseMetrics &&
                                  Object.keys(sseMetrics).length > 0 && (
                                    <div
                                      className="monitoring-metrics-grid"
                                      style={{ background: '#f0fdf4', borderRadius: 4, padding: 4 }}
                                    >
                                      <div
                                        style={{
                                          fontSize: 10,
                                          color: '#16a34a',
                                          fontWeight: 600,
                                          gridColumn: '1/-1',
                                        }}
                                      >
                                        📡 SSE实时数据
                                      </div>
                                      {Object.entries(sseMetrics)
                                        .filter(([k]) => !k.startsWith('_'))
                                        .slice(0, 8)
                                        .map(([k, v]) => (
                                          <div key={`sse-${k}`} className="monitoring-metric-item">
                                            <span className="monitoring-metric-key">{k}</span>
                                            <span
                                              className="monitoring-metric-value"
                                              style={{ color: '#16a34a', fontWeight: 600 }}
                                            >
                                              {formatVal(v)}
                                            </span>
                                          </div>
                                        ))}
                                    </div>
                                  )}
                                {status === 'online' && metrics && (
                                  <div className="monitoring-metrics-grid">
                                    {Object.entries(metrics)
                                      .slice(0, 8)
                                      .map(([k, v]) => (
                                        <div key={k} className="monitoring-metric-item">
                                          <span className="monitoring-metric-key">{k}</span>
                                          <span className="monitoring-metric-value">
                                            {formatVal(v)}
                                          </span>
                                        </div>
                                      ))}
                                  </div>
                                )}
                                {status === 'online' &&
                                  cumData &&
                                  Object.keys(cumData).length > 0 && (
                                    <div className="monitoring-cumulative-section">
                                      <div className="monitoring-cumulative-title">累计统计</div>
                                      <div className="monitoring-metrics-grid">
                                        {Object.entries(cumData)
                                          .filter(([k]) => !k.startsWith('_'))
                                          .slice(0, 6)
                                          .map(([k, v]) => (
                                            <div key={k} className="monitoring-metric-item">
                                              <span className="monitoring-metric-key">{k}</span>
                                              <span className="monitoring-metric-value">
                                                {formatVal(v)}
                                              </span>
                                            </div>
                                          ))}
                                      </div>
                                    </div>
                                  )}
                                {status === 'offline' && (
                                  <div className="monitoring-instance-empty">
                                    模块未初始化或无统计数据
                                  </div>
                                )}
                                {status === 'error' && (
                                  <div className="monitoring-instance-error">
                                    错误:{' '}
                                    {(stats?.modules?.[moduleName]?.error as string) || '未知错误'}
                                  </div>
                                )}
                              </div>
                            )}
                          </div>
                        )
                      })}
                    </div>
                  )}
                </div>
              )
            })}
          </div>

          <div className="monitoring-sidebar-footer">
            <ThunderboltOutlined /> 每6秒刷新{sseConnected ? '+SSE每3秒' : ''} | v9.1 SSS审计版
          </div>
        </div>
      )}
    </>
  )
}
