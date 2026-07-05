import { ReactNode, useState, useEffect, useCallback } from 'react'
import { Layout, Menu, Badge, Button, Tooltip } from 'antd'
import {
  DashboardOutlined,
  DatabaseOutlined,
  ApartmentOutlined,
  SettingOutlined,
  MonitorOutlined,
  ApiOutlined,
  RobotOutlined,
  ThunderboltOutlined,
  MenuFoldOutlined,
  MenuUnfoldOutlined,
  EyeOutlined,
  CloudServerOutlined,
  MessageOutlined,
  SafetyCertificateOutlined,
  NodeIndexOutlined,
  ExperimentOutlined,
  LoadingOutlined,
} from '@ant-design/icons'
import { useNavigate, useLocation } from 'react-router-dom'
import OperationTransparencyBar from '../components/OperationTransparencyBar'
import { api } from '../services/api'

const { Header, Sider, Content } = Layout

interface MainLayoutProps {
  children: ReactNode
}

const menuItems = [
  {
    key: '/dashboard',
    icon: <DashboardOutlined />,
    label: '仪表盘',
  },
  {
    key: '/chat',
    icon: <MessageOutlined />,
    label: 'AI 对话',
  },
  {
    key: '/memory',
    icon: <DatabaseOutlined />,
    label: '记忆管理',
  },
  {
    key: '/knowledge-graph',
    icon: <ApartmentOutlined />,
    label: '知识图谱',
  },
  {
    key: '/config',
    icon: <SettingOutlined />,
    label: '系统配置',
  },
  {
    key: '/monitoring',
    icon: <MonitorOutlined />,
    label: '监控日志',
  },
  {
    key: '/mcp-tools',
    icon: <ApiOutlined />,
    label: 'MCP工具',
  },
  {
    key: '/sss-audit',
    icon: <SafetyCertificateOutlined />,
    label: 'SSS审计',
  },
  {
    key: '/audit',
    icon: <ExperimentOutlined />,
    label: '鉴衡审计',
  },
  {
    key: '/standards',
    icon: <ThunderboltOutlined />,
    label: '标准合规',
  },
  {
    key: '/orchestrator',
    icon: <NodeIndexOutlined />,
    label: '调度引擎',
  },
  {
    key: '/deepseek',
    icon: <ExperimentOutlined />,
    label: 'DeepSeek',
  },
]

interface HeaderStats {
  status: 'healthy' | 'degraded' | 'unreachable' | 'loading'
  version: string
  endpoints: number
  agents: number
  mcpServers: number
  engineReady: boolean
}

function MainLayout({ children }: MainLayoutProps) {
  const navigate = useNavigate()
  const location = useLocation()
  const [collapsed, setCollapsed] = useState(false)
  const [headerStats, setHeaderStats] = useState<HeaderStats>({
    status: 'loading',
    version: 'v9.1',
    endpoints: 0,
    agents: 0,
    mcpServers: 0,
    engineReady: false,
  })

  const fetchHeaderStats = useCallback(async () => {
    try {
      const [healthRes, agentsRes, mcpRes] = await Promise.allSettled([
        api.get('/api/health'),
        api.get('/api/orchestrator/agents'),
        api.get('/api/mcp/'),
      ])

      let status: HeaderStats['status'] = 'healthy'
      let endpoints = 71
      let agents = 19
      let mcpServers = 6
      let engineReady = false
      let version = 'v9.1'

      if (healthRes.status === 'fulfilled') {
        const h = healthRes.value
        version = h.version || version
        engineReady = h.engine_ready === true
        endpoints = h.endpoints || endpoints
        if (h.status !== 'healthy') status = 'degraded'
      } else {
        status = 'degraded'
      }

      if (agentsRes.status === 'fulfilled') {
        const a = agentsRes.value
        agents = a?.agents
          ? Array.isArray(a.agents)
            ? a.agents.length
            : a.count || a.total || agents
          : agents
      }

      if (mcpRes.status === 'fulfilled') {
        const m = mcpRes.value
        mcpServers = m?.servers
          ? Array.isArray(m.servers)
            ? m.servers.length
            : m.count || m.total || mcpServers
          : mcpServers
      }

      if (
        healthRes.status === 'rejected' &&
        agentsRes.status === 'rejected' &&
        mcpRes.status === 'rejected'
      ) {
        status = 'unreachable'
      }

      setHeaderStats({ status, version, endpoints, agents, mcpServers, engineReady })
    } catch {
      setHeaderStats((prev) => ({ ...prev, status: 'unreachable' }))
    }
  }, [])

  useEffect(() => {
    fetchHeaderStats()
    const interval = setInterval(fetchHeaderStats, 15000)
    return () => clearInterval(interval)
  }, [fetchHeaderStats])

  const handleMenuClick = ({ key }: { key: string }) => {
    navigate(key)
  }

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Sider
        collapsible
        collapsed={collapsed}
        onCollapse={(value) => setCollapsed(value)}
        width={220}
        collapsedWidth={64}
        trigger={null}
        className="app-sider"
        theme="light"
        style={{
          borderRight: '1px solid #f0f0f0',
          boxShadow: collapsed ? undefined : '2px 0 8px rgba(0,0,0,0.06)',
        }}
      >
        <div
          style={{
            height: 56,
            display: 'flex',
            alignItems: 'center',
            justifyContent: collapsed ? 'center' : 'flex-start',
            padding: collapsed ? '0' : '0 16px',
            borderBottom: '1px solid #f0f0f0',
            gap: collapsed ? 0 : 10,
            overflow: 'hidden',
            transition: 'all 0.2s',
          }}
        >
          <div
            style={{
              width: 36,
              height: 36,
              borderRadius: 8,
              background: 'linear-gradient(135deg, #1890ff 0%, #722ed1 100%)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              flexShrink: 0,
              boxShadow: '0 2px 6px rgba(24,144,255,0.35)',
            }}
          >
            <EyeOutlined
              style={{
                color: '#fff',
                fontSize: 20,
                fontWeight: 700,
                lineHeight: 1,
              }}
            />
          </div>
          {!collapsed && (
            <div style={{ overflow: 'hidden', whiteSpace: 'nowrap' }}>
              <div
                style={{
                  fontSize: 15,
                  fontWeight: 600,
                  color: '#1a1a1a',
                  letterSpacing: 1,
                  lineHeight: 1.2,
                }}
              >
                天机 v9.1
              </div>
              <div
                style={{
                  fontSize: 11,
                  color: '#999',
                  letterSpacing: 0.5,
                }}
              >
                天机 · 智能记忆平台
              </div>
            </div>
          )}
        </div>

        <Menu
          mode="inline"
          selectedKeys={[
            menuItems.find((m) => location.pathname.startsWith(m.key))?.key || location.pathname,
          ]}
          items={menuItems}
          onClick={handleMenuClick}
          style={{ height: 'calc(100% - 80px)', borderRight: 0, marginTop: 4 }}
        />

        {!collapsed && (
          <div
            style={{
              position: 'absolute',
              bottom: 12,
              left: 0,
              right: 0,
              textAlign: 'center',
              pointerEvents: 'none',
            }}
          >
            <span
              style={{
                fontSize: 10,
                color: '#d9d9d9',
                letterSpacing: 1,
              }}
            >
              ONEDIR · ICME六层架构
            </span>
          </div>
        )}
      </Sider>

      <Layout>
        <Header
          className="app-header"
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            paddingRight: 24,
            paddingLeft: 16,
            background: '#fff',
            borderBottom: '1px solid #f0f0f0',
            height: 56,
            lineHeight: '56px',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <Button
              type="text"
              icon={collapsed ? <MenuUnfoldOutlined /> : <MenuFoldOutlined />}
              onClick={() => setCollapsed(!collapsed)}
              size="small"
              style={{
                fontSize: 16,
                color: '#666',
                width: 32,
                height: 32,
                borderRadius: 6,
              }}
            />
            <span style={{ color: '#999', fontSize: 13, userSelect: 'none' }}>当前页面：</span>
            <Badge dot status="processing" style={{ marginRight: 4 }}>
              <span style={{ fontSize: 14, fontWeight: 500, color: '#333' }}>
                {menuItems.find((m) => m.key === location.pathname)?.label || '首页'}
              </span>
            </Badge>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: 18 }}>
            <Tooltip title={`API端点 (来自 /api/health)`}>
              <span style={{ color: '#888', fontSize: 13, cursor: 'default' }}>
                <ApiOutlined style={{ marginRight: 4 }} />
                {headerStats.status === 'loading' ? '...' : `${headerStats.endpoints}端点`}
              </span>
            </Tooltip>
            <Tooltip title={`注册Agent (来自 /api/orchestrator/agents)`}>
              <span style={{ color: '#888', fontSize: 13, cursor: 'default' }}>
                <RobotOutlined style={{ marginRight: 4 }} />
                {headerStats.status === 'loading' ? '...' : `${headerStats.agents}Agent`}
              </span>
            </Tooltip>
            <Tooltip title={`MCP服务器 (来自 /api/mcp)`}>
              <span style={{ color: '#888', fontSize: 13, cursor: 'default' }}>
                <CloudServerOutlined style={{ marginRight: 4 }} />
                {headerStats.status === 'loading' ? '...' : `${headerStats.mcpServers}MCP`}
              </span>
            </Tooltip>
            <Tooltip
              title={`系统状态: ${headerStats.status === 'healthy' ? '健康' : headerStats.status === 'degraded' ? '降级' : headerStats.status === 'unreachable' ? '不可达' : '检测中...'} | 引擎: ${headerStats.engineReady ? '就绪' : '待命'} | ${headerStats.version}`}
            >
              <Badge
                count={
                  headerStats.status === 'healthy'
                    ? '在线'
                    : headerStats.status === 'degraded'
                      ? '降级'
                      : headerStats.status === 'unreachable'
                        ? '离线'
                        : '...'
                }
                size="small"
                style={{
                  backgroundColor:
                    headerStats.status === 'healthy'
                      ? '#52c41a'
                      : headerStats.status === 'degraded'
                        ? '#faad14'
                        : headerStats.status === 'unreachable'
                          ? '#ff4d4f'
                          : '#d9d9d9',
                  fontSize: 11,
                  padding: '0 5px',
                  lineHeight: '18px',
                }}
              >
                {headerStats.status === 'loading' ? (
                  <LoadingOutlined style={{ fontSize: 15, color: '#1890ff', cursor: 'pointer' }} />
                ) : (
                  <ThunderboltOutlined
                    style={{
                      fontSize: 15,
                      color:
                        headerStats.status === 'healthy'
                          ? '#52c41a'
                          : headerStats.status === 'degraded'
                            ? '#faad14'
                            : '#ff4d4f',
                      cursor: 'pointer',
                    }}
                    onClick={fetchHeaderStats}
                  />
                )}
              </Badge>
            </Tooltip>
          </div>
        </Header>

        <Content
          className="app-content"
          style={{
            margin: 0,
            overflow: 'auto',
            background: '#f5f7fa',
            paddingBottom: 40,
          }}
        >
          {children}
        </Content>
      </Layout>
      <OperationTransparencyBar />
    </Layout>
  )
}

export default MainLayout
