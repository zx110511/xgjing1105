import { useState } from 'react'
import { Tag, Tooltip } from 'antd'
import {
  SwapOutlined,
  ToolOutlined,
  DatabaseOutlined,
  ExperimentOutlined,
  CheckCircleOutlined,
  LoadingOutlined,
  ClockCircleOutlined,
  CloseCircleOutlined,
} from '@ant-design/icons'

export interface OpTransparencyEvent {
  // [FIX-TS-005] 扩展 type 联合类型: Chat.tsx 使用 'agent' | 'tool'
  type: 'tvp' | 'mcp' | 'memory' | 'llm' | 'agent' | 'tool'
  action: string
  detail: string
  color: string
  label: string
  desc: string
  timestamp: number
  time_str: string
  status?: string
  count?: number
  tool?: string
  char_count?: number
}

interface Props {
  events: OpTransparencyEvent[]
  compact?: boolean
  showTimeline?: boolean
}

const CATEGORY_CONFIG = {
  tvp: {
    icon: <SwapOutlined />,
    color: '#8B5CF6',
    bg: '#8B5CF618',
    border: '#8B5CF640',
    label: 'TVP',
    desc: 'Agent Scheduling',
  },
  mcp: {
    icon: <ToolOutlined />,
    color: '#F97316',
    bg: '#F9731618',
    border: '#F9731640',
    label: 'MCP',
    desc: 'Tool Calls',
  },
  memory: {
    icon: <DatabaseOutlined />,
    color: '#06B6D4',
    bg: '#06B6D418',
    border: '#06B6D440',
    label: 'Memory',
    desc: 'Memory Ops',
  },
  llm: {
    icon: <ExperimentOutlined />,
    color: '#EC4899',
    bg: '#EC489918',
    border: '#EC489940',
    label: 'LLM',
    desc: 'DeepSeek AI',
  },
}

const STATUS_ICON: Record<string, React.ReactNode> = {
  switching: <LoadingOutlined spin style={{ fontSize: 10 }} />,
  querying: <LoadingOutlined spin style={{ fontSize: 10 }} />,
  ready: <CheckCircleOutlined style={{ fontSize: 10, color: '#34D399' }} />,
  calling: <LoadingOutlined spin style={{ fontSize: 10 }} />,
  thinking: <LoadingOutlined spin style={{ fontSize: 10 }} />,
  reasoning: <LoadingOutlined spin style={{ fontSize: 10 }} />,
  complete: <CheckCircleOutlined style={{ fontSize: 10, color: '#34D399' }} />,
  done: <CheckCircleOutlined style={{ fontSize: 10, color: '#34D399' }} />,
  error: <CloseCircleOutlined style={{ fontSize: 10, color: '#F87171' }} />,
  default: <ClockCircleOutlined style={{ fontSize: 10, color: '#94A3B8' }} />,
}

function getStatusIcon(status?: string) {
  return STATUS_ICON[status || ''] || STATUS_ICON.default
}

export default function OperationTransparencyInline({ events, compact = false, showTimeline = false }: Props) {
  const [expandedEvent, setExpandedEvent] = useState<string | null>(null)

  if (!events || events.length === 0) return null

  const grouped = events.reduce((acc, event) => {
    if (!acc[event.type]) acc[event.type] = []
    acc[event.type].push(event)
    return acc
  }, {} as Record<string, OpTransparencyEvent[]>)

  return (
    <div
      className="ops-transparency-inline"
      style={{
        background: compact ? 'transparent' : 'linear-gradient(135deg, #1E293B 0%, #0F172A 100%)',
        borderRadius: compact ? 6 : 10,
        padding: compact ? '4px 8px' : '8px 14px',
        marginBottom: compact ? 6 : 12,
        border: compact ? `1px solid rgba(148,163,184,0.12)` : '1px solid rgba(148,163,184,0.15)',
        fontFamily: "'JetBrains Mono', 'Fira Code', Consolas, monospace",
        fontSize: compact ? 11 : 12,
      }}
    >
      {showTimeline && (
        <div style={{
          display: 'flex',
          alignItems: 'center',
          gap: 6,
          marginBottom: 6,
          paddingBottom: 6,
          borderBottom: '1px solid rgba(148,163,184,0.1)',
          fontSize: 10,
          color: '#64748B',
        }}>
          <ClockCircleOutlined />
          <span>OPERATION TRANSPARENCY</span>
          <span style={{ marginLeft: 'auto' }}>{events.length} events</span>
        </div>
      )}

      <div style={{ display: 'flex', flexWrap: 'wrap', gap: compact ? 4 : 8, alignItems: 'center' }}>
        {(Object.keys(CATEGORY_CONFIG) as Array<keyof typeof CATEGORY_CONFIG>).map(cat => {
          const cfg = CATEGORY_CONFIG[cat]
          const catEvents = grouped[cat] || []
          const latest = catEvents[catEvents.length - 1]
          const isDone = latest?.status === 'done' || latest?.status === 'complete'
          const isActive = ['switching','querying','calling','thinking','reasoning'].includes(latest?.status || '')
          const hasError = latest?.status === 'error'

          if (catEvents.length === 0 && !compact) return null

          return (
            <Tooltip
              key={cat}
              title={
                <div style={{ maxWidth: 280 }}>
                  <div style={{ fontWeight: 600, color: cfg.color, marginBottom: 4, fontSize: 11 }}>
                    {cfg.desc}
                  </div>
                  {catEvents.map((ev, i) => (
                    <div key={i} style={{ fontSize: 10, lineHeight: 1.7, color: '#CBD5E1' }}>
                      <span style={{ color: '#64748B' }}>{ev.time_str}</span>
                      {' '}
                      <span style={{
                        color: ev.status === 'error' ? '#F87171' :
                               ev.status === 'done' ? '#34D399' : cfg.color,
                        fontWeight: ev.status === 'error' ? 600 : 400,
                      }}>
                        {ev.action}
                      </span>
                      {' '}
                      <span style={{ color: '#94A3B8' }}>{ev.detail}</span>
                    </div>
                  ))}
                </div>
              }
              placement="top"
            >
              <Tag
                style={{
                  margin: 0,
                  cursor: 'pointer',
                  padding: compact ? '1px 7px' : '2px 10px',
                  borderRadius: 4,
                  border: hasError
                    ? '1px solid #EF444450'
                    : isDone
                      ? `1px solid ${cfg.color}60`
                      : isActive
                        ? `1px solid ${cfg.color}`
                        : `1px solid ${cfg.border}`,
                  background: hasError
                    ? '#EF444418'
                    : isDone
                      ? `${cfg.bg}`
                      : isActive
                        ? `${cfg.color}25`
                        : 'rgba(71,85,105,0.2)',
                  color: hasError
                    ? '#F87171'
                    : isDone
                      ? cfg.color
                      : isActive
                        ? cfg.color
                        : '#64748B',
                  fontWeight: 600,
                  letterSpacing: 0.3,
                  transition: 'all 0.2s ease',
                  opacity: catEvents.length > 0 ? 1 : 0.35,
                  userSelect: 'none',
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: 4,
                }}
                onClick={() => setExpandedEvent(expandedEvent === cat ? null : cat)}
              >
                {getStatusIcon(latest?.status)}
                {cfg.icon}
                <span>{cfg.label}</span>
                {catEvents.length > 0 && (
                  <span style={{
                    background: isDone ? `${cfg.color}30` : isActive ? `${cfg.color}40` : 'rgba(255,255,255,0.08)',
                    padding: '0 5px',
                    borderRadius: 8,
                    fontSize: 10,
                    fontWeight: 700,
                    minWidth: 16,
                    textAlign: 'center',
                  }}>
                    {latest?.count !== undefined ? latest.count :
                     latest?.char_count !== undefined ? `${Math.floor(latest.char_count/100)}k` :
                     catEvents.length}
                  </span>
                )}
              </Tag>
            </Tooltip>
          )
        })}

        {!compact && showTimeline && expandedEvent && grouped[expandedEvent] && (
          <div style={{
            width: '100%',
            marginTop: 6,
            paddingTop: 6,
            borderTop: '1px dashed rgba(148,163,184,0.15)',
          }}>
            {grouped[expandedEvent].map((ev, i) => (
              <div key={i} style={{
                display: 'flex',
                alignItems: 'center',
                gap: 8,
                padding: '3px 0',
                fontSize: 10,
                color: '#94A3B8',
              }}>
                <span style={{ color: '#64748B', whiteSpace: 'nowrap' }}>{ev.time_str}</span>
                <span style={{
                  width: 6,
                  height: 6,
                  borderRadius: '50%',
                  background: ev.status === 'error' ? '#EF4444' :
                             ev.status === 'done' ? '#34D399' : ev.color,
                  flexShrink: 0,
                }} />
                <span style={{ color: '#CBD5E1', fontWeight: 500 }}>{ev.action}</span>
                <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  {ev.detail}
                </span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
