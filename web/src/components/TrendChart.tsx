import { useMemo } from 'react'
import { Card, Button, Empty } from 'antd'
import { CloseOutlined } from '@ant-design/icons'

export interface TrendPoint {
    time: string
    value: number
}

export interface SnapshotLike {
    timestamp: number
    [key: string]: number
}

/**
 * 将历史快照数组映射为趋势图数据点。
 * timestamp 兼容秒级与毫秒级 Unix 时间戳。
 */
export function mapSnapshotsToTrend(
    snapshots: SnapshotLike[],
    field: string
): TrendPoint[] {
    return (snapshots || []).map((s) => {
        const raw = Number(s?.timestamp ?? 0)
        const ms = raw > 1e12 ? raw : raw * 1000
        const d = new Date(ms)
        const pad = (n: number) => String(n).padStart(2, '0')
        const time = `${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(
            d.getHours()
        )}:${pad(d.getMinutes())}`
        return { time, value: Number(s?.[field] ?? 0) }
    })
}

export interface TrendChartProps {
    visible: boolean
    title: string
    data: TrendPoint[]
    height?: number
    color?: string
    onClose: () => void
}

/**
 * 轻量级历史趋势折线图（纯 SVG，无第三方图表依赖）。
 */
const TrendChart: React.FC<TrendChartProps> = ({
    visible,
    title,
    data,
    height = 240,
    color = '#1890ff',
    onClose,
}) => {
    const geometry = useMemo(() => {
        const width = 720
        const padding = { top: 16, right: 16, bottom: 28, left: 40 }
        const innerW = width - padding.left - padding.right
        const innerH = height - padding.top - padding.bottom

        const values = data.map((d) => d.value)
        const minV = values.length ? Math.min(...values) : 0
        const maxV = values.length ? Math.max(...values) : 1
        const span = maxV - minV || 1

        const points = data.map((d, i) => {
            const x =
                padding.left +
                (data.length <= 1 ? innerW / 2 : (i / (data.length - 1)) * innerW)
            const y = padding.top + innerH - ((d.value - minV) / span) * innerH
            return { x, y, ...d }
        })

        const linePath = points
            .map((p, i) => `${i === 0 ? 'M' : 'L'} ${p.x.toFixed(1)} ${p.y.toFixed(1)}`)
            .join(' ')

        const areaPath =
            points.length > 0
                ? `${linePath} L ${points[points.length - 1].x.toFixed(1)} ${(
                    padding.top + innerH
                ).toFixed(1)} L ${points[0].x.toFixed(1)} ${(
                    padding.top + innerH
                ).toFixed(1)} Z`
                : ''

        return { width, padding, innerH, points, linePath, areaPath, minV, maxV }
    }, [data, height])

    if (!visible) {
        return null
    }

    const { width, padding, innerH, points, linePath, areaPath, minV, maxV } =
        geometry

    return (
        <Card
            size="small"
            title={<span style={{ fontSize: 14 }}>{title}</span>}
            styles={{ body: { padding: 8 } }}
            extra={
                <Button
                    type="text"
                    size="small"
                    icon={<CloseOutlined />}
                    onClick={onClose}
                />
            }
        >
            {data.length > 0 ? (
                <svg
                    width="100%"
                    height={height}
                    viewBox={`0 0 ${width} ${height}`}
                    preserveAspectRatio="none"
                    role="img"
                    aria-label={title}
                >
                    {/* Y 轴参考线与刻度 */}
                    {[0, 0.5, 1].map((r) => {
                        const y = padding.top + innerH - r * innerH
                        const val = (minV + (maxV - minV) * r).toFixed(1)
                        return (
                            <g key={r}>
                                <line
                                    x1={padding.left}
                                    y1={y}
                                    x2={width - padding.right}
                                    y2={y}
                                    stroke="#f0f0f0"
                                />
                                <text x={4} y={y + 4} fontSize={10} fill="#999">
                                    {val}
                                </text>
                            </g>
                        )
                    })}
                    {areaPath && <path d={areaPath} fill={color} fillOpacity={0.12} />}
                    <path d={linePath} fill="none" stroke={color} strokeWidth={2} />
                    {points.map((p, i) => (
                        <circle key={i} cx={p.x} cy={p.y} r={2.5} fill={color}>
                            <title>{`${p.time}: ${p.value}`}</title>
                        </circle>
                    ))}
                </svg>
            ) : (
                <Empty description="暂无趋势数据" />
            )}
        </Card>
    )
}

export default TrendChart
