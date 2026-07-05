import { useState, useEffect, useRef, useCallback } from 'react'
import { Tag, Tooltip, Badge, Space } from 'antd'
import {
  SwapOutlined,
  ToolOutlined,
  DatabaseOutlined,
  ExperimentOutlined,
  ThunderboltOutlined,
} from '@ant-design/icons'

interface OpEvent {
  type: string
  timestamp: number
  time_str: string
  category: string
  action: string
  detail: string
  result: string
  color: string
  label: string
  desc: string
}

interface CategoryConfig {
  [key: string]: { label: string; color: string; desc: string }
}

const CATEGORY_CONFIG: CategoryConfig = {
  tvp: { label: 'TVP', color: '#8B5CF6', desc: 'Agent Scheduling' },
  mcp: { label: 'MCP', color: '#F97316', desc: 'Tool Calls' },
  memory: { label: '记忆操作', color: '#06B6D4', desc: '记忆操作次数(非条目数)' },
  llm: { label: 'LLM', color: '#EC4899', desc: 'DeepSeek AI' },
}

const CATEGORY_ORDER = ['tvp', 'mcp', 'memory', 'llm']

const ICON_MAP: Record<string, React.ReactNode> = {
  tvp: <SwapOutlined />,
  mcp: <ToolOutlined />,
  memory: <DatabaseOutlined />,
  llm: <ExperimentOutlined />,
}

const MAX_RECENT_EVENTS = 5

export default function OperationTransparencyBar() {
  const [counts, setCounts] = useState<Record<string, number>>({
    tvp: 0,
    mcp: 0,
    memory: 0,
    llm: 0,
  })
  const [recentEvents, setRecentEvents] = useState<OpEvent[]>([])
  const [connected, setConnected] = useState(false)
  const [lastActivity, setLastActivity] = useState<string>('')
  const esRef = useRef<EventSource | null>(null)
  const countsRef = useRef(counts)
  const recentRef = useRef<OpEvent[]>([])

  countsRef.current = counts
  recentRef.current = recentEvents

  const handleEvent = useCallback((event: OpEvent) => {
    if (event.type === 'heartbeat') return

    setCounts(prev => ({
      ...prev,
      [event.category]: (prev[event.category] || 0) + 1,
    }))

    setRecentEvents(prev => {
      const next = [event, ...prev].slice(0, MAX_RECENT_EVENTS)
      return next
    })

    setLastActivity(`${event.label}: ${event.action}`)
  }, [])

  useEffect(() => {
    const baseUrl = window.location.origin || `${window.location.protocol}//${window.location.host}`
    let reconnectTimer: ReturnType<typeof setTimeout> | null = null

    const connect = () => {
      const es = new EventSource(`${baseUrl}/api/ops/stream`)
      esRef.current = es

      es.onopen = () => setConnected(true)
      es.onerror = () => {
        setConnected(false)
        es.close()
        esRef.current = null
        reconnectTimer = setTimeout(connect, 5000)
      }

      es.onmessage = (e) => {
        try {
          const data: OpEvent = JSON.parse(e.data)
          if (data.type === 'op_event') {
            handleEvent(data)
          }
        } catch {
          // ignore parse errors
        }
      }
    }

    connect()

    fetch(`${baseUrl}/api/operations/summary`)
      .then(r => r.json())
      .then(data => {
        if (data.by_category) {
          const initialCounts: Record<string, number> = {}
          for (const cat of CATEGORY_ORDER) {
            const info = data.by_category[cat]
            initialCounts[cat] = (typeof info === 'number' ? info : (info?.count || 0))
          }
          setCounts(initialCounts)
        }
      })
      .catch(() => { })

    return () => {
      if (reconnectTimer) clearTimeout(reconnectTimer)
      if (esRef.current) {
        esRef.current.close()
        esRef.current = null
      }
      setConnected(false)
    }
  }, [handleEvent])

  return (
    <div
      style={{
        position: 'fixed',
        bottom: 0,
        left: 0,
        right: 0,
        zIndex: 1000,
        background: 'linear-gradient(180deg, rgba(15,23,42,0.95), rgba(15,23,42,0.98))',
        borderTop: '1px solid rgba(148,163,184,0.15)',
        padding: '6px 20px',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        fontFamily: "'JetBrains Mono', 'Fira Code', 'Consolas', monospace",
        fontSize: '12px',
        backdropFilter: 'blur(12px)',
        boxShadow: '0 -4px 24px rgba(0,0,0,0.3)',
      }}
    >
      <Space size={12} style={{ flex: 1 }}>
        {CATEGORY_ORDER.map(cat => {
          const cfg = CATEGORY_CONFIG[cat]
          const count = counts[cat] || 0
          return (
            <Tooltip
              key={cat}
              title={
                <div style={{ fontSize: '11px', lineHeight: '1.6' }}>
                  <div style={{ fontWeight: 600, color: cfg.color }}>
                    {cfg.desc}
                  </div>
                  <div>Total: {count} operations</div>
                  <div style={{ opacity: 0.7, marginTop: 4 }}>
                    Click to see recent events
                  </div>
                </div>
              }
              placement="top"
            >
              <Tag
                style={{
                  margin: 0,
                  cursor: 'pointer',
                  padding: '2px 10px',
                  borderRadius: '4px',
                  border: `1px solid ${cfg.color}40`,
                  background: count > 0 ? `${cfg.color}18` : 'rgba(71,85,105,0.25)',
                  color: count > 0 ? cfg.color : '#64748B',
                  fontWeight: 600,
                  letterSpacing: '0.5px',
                  transition: 'all 0.2s ease',
                  minWidth: '72px',
                  textAlign: 'center',
                  userSelect: 'none',
                }}
              >
                <span style={{ marginRight: 4 }}>{ICON_MAP[cat]}</span>
                <span>{cfg.label}</span>
                <span
                  style={{
                    marginLeft: 6,
                    background: count > 0 ? `${cfg.color}30` : 'transparent',
                    padding: '0 6px',
                    borderRadius: '10px',
                    fontSize: '11px',
                    fontWeight: 700,
                  }}
                >
                  {count}
                </span>
              </Tag>
            </Tooltip>
          )
        })}
      </Space>

      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 10,
          color: '#94A3B8',
          fontSize: '11px',
          minWidth: 200,
          justifyContent: 'flex-end',
        }}
      >
        {lastActivity && (
          <Tooltip title="Last operation">
            <span
              style={{
                maxWidth: 180,
                overflow: 'hidden',
                textOverflow: 'ellipsis',
                whiteSpace: 'nowrap',
                color: '#CBD5E1',
              }}
            >
              <ThunderboltOutlined style={{ marginRight: 4 }} />
              {lastActivity}
            </span>
          </Tooltip>
        )}
        <Badge
          status={connected ? 'success' : 'error'}
          text={connected ? 'LIVE' : 'OFF'}
          style={{ fontSize: '10px' }}
        />
      </div>

      {recentEvents.length > 0 && (
        <div
          style={{
            position: 'absolute',
            bottom: '100%',
            left: 0,
            right: 0,
            maxHeight: 160,
            overflowY: 'auto',
            background: 'rgba(15,23,42,0.97)',
            border: '1px solid rgba(148,163,184,0.12)',
            borderRadius: '8px 8px 0 0',
            padding: '8px 12px',
            display: 'none',
          }}
          className="ops-recent-events"
        >
          {recentEvents.map((ev, i) => (
            <div
              key={`${ev.timestamp}-${i}`}
              style={{
                display: 'flex',
                gap: 8,
                padding: '4px 0',
                borderBottom:
                  i < recentEvents.length - 1
                    ? '1px solid rgba(148,163,184,0.08)'
                    : 'none',
                fontSize: '11px',
                alignItems: 'center',
              }}
            >
              <span style={{ color: '#64748B', whiteSpace: 'nowrap' }}>
                {ev.time_str}
              </span>
              <Tag
                style={{
                  margin: 0,
                  fontSize: '10px',
                  padding: '0 5px',
                  lineHeight: '18px',
                  border: `1px solid ${ev.color}40`,
                  background: `${ev.color}18`,
                  color: ev.color,
                  borderRadius: '3px',
                }}
              >
                {ev.label}
              </Tag>
              <span style={{ color: '#CBD5E1' }}>{ev.action}</span>
              <span
                style={{
                  color: '#64748B',
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                  whiteSpace: 'nowrap',
                  maxWidth: 300,
                }}
              >
                {ev.detail}
              </span>
              <span
                style={{
                  marginLeft: 'auto',
                  color: ev.result === 'ok' ? '#34D399' : '#F87171',
                  fontSize: '10px',
                  whiteSpace: 'nowrap',
                }}
              >
                {ev.result.toUpperCase()}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
