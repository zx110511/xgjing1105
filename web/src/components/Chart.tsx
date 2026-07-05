import React, { useEffect, useRef, useState } from 'react'
import * as echarts from 'echarts'
import type { EChartsOption, ECharts } from 'echarts'
import { Spin } from 'antd'

export interface ChartProps {
  option: EChartsOption
  style?: React.CSSProperties
  className?: string
  loading?: boolean
  onChartReady?: (chart: ECharts) => void
}

const Chart: React.FC<ChartProps> = ({
  option,
  style,
  className,
  loading = false,
  onChartReady,
}) => {
  const chartRef = useRef<HTMLDivElement>(null)
  const chartInstance = useRef<ECharts | null>(null)
  const [chartLoading, setChartLoading] = useState(true)

  useEffect(() => {
    if (!chartRef.current) return

    const chart = echarts.init(chartRef.current)
    chartInstance.current = chart

    chart.setOption(option)
    setChartLoading(false)

    if (onChartReady) {
      onChartReady(chart)
    }

    const handleResize = () => {
      chart.resize()
    }

    window.addEventListener('resize', handleResize)

    return () => {
      window.removeEventListener('resize', handleResize)
      chart.dispose()
    }
  }, [])

  useEffect(() => {
    if (chartInstance.current) {
      chartInstance.current.setOption(option, true)
    }
  }, [option])

  return (
    <div style={{ position: 'relative', ...style }} className={className}>
      {(loading || chartLoading) && (
        <div
          style={{
            position: 'absolute',
            top: '50%',
            left: '50%',
            transform: 'translate(-50%, -50%)',
            zIndex: 10,
          }}
        >
          <Spin />
        </div>
      )}
      <div
        ref={chartRef}
        style={{
          width: '100%',
          height: '100%',
          minHeight: 300,
        }}
      />
    </div>
  )
}

export default Chart

export const createPieChartOption = (
  data: Array<{ name: string; value: number }>,
  title?: string
): EChartsOption => ({
  title: {
    text: title,
    left: 'center',
  },
  tooltip: {
    trigger: 'item',
    formatter: '{a} <br/>{b}: {c} ({d}%)',
  },
  legend: {
    orient: 'vertical',
    left: 'left',
  },
  series: [
    {
      name: title || '数据',
      type: 'pie',
      radius: '50%',
      data,
      emphasis: {
        itemStyle: {
          shadowBlur: 10,
          shadowOffsetX: 0,
          shadowColor: 'rgba(0, 0, 0, 0.5)',
        },
      },
    },
  ],
})

export const createBarChartOption = (
  xAxisData: string[],
  seriesData: number[],
  title?: string
): EChartsOption => ({
  title: {
    text: title,
    left: 'center',
  },
  tooltip: {
    trigger: 'axis',
  },
  xAxis: {
    type: 'category',
    data: xAxisData,
  },
  yAxis: {
    type: 'value',
  },
  series: [
    {
      data: seriesData,
      type: 'bar',
      itemStyle: {
        color: '#1890ff',
      },
    },
  ],
})

export const createLineChartOption = (
  xAxisData: string[],
  seriesData: number[],
  title?: string
): EChartsOption => ({
  title: {
    text: title,
    left: 'center',
  },
  tooltip: {
    trigger: 'axis',
  },
  xAxis: {
    type: 'category',
    data: xAxisData,
  },
  yAxis: {
    type: 'value',
  },
  series: [
    {
      data: seriesData,
      type: 'line',
      smooth: true,
      itemStyle: {
        color: '#1890ff',
      },
    },
  ],
})

export const createMemoryLayerChart = (
  layerData: Record<string, number>
): EChartsOption => {
  const data = Object.entries(layerData).map(([name, value]) => ({
    name,
    value,
  }))

  return createPieChartOption(data, '记忆层级分布')
}

export const createMemoryPriorityChart = (
  priorityData: Record<string, number>
): EChartsOption => {
  const data = Object.entries(priorityData).map(([name, value]) => ({
    name,
    value,
  }))

  return createPieChartOption(data, '记忆优先级分布')
}

export const createMemoryTrendChart = (
  trendData: Array<{ date: string; count: number }>
): EChartsOption => {
  const dates = trendData.map((item) => item.date)
  const counts = trendData.map((item) => item.count)

  return createLineChartOption(dates, counts, '记忆创建趋势')
}
