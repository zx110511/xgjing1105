import { useState, useEffect, useCallback } from 'react'
import { api } from '../services/api'
import { endpoints } from '../config/api.config'
import {
    KGTopology,
    KGMetrics,
    SSSAuditResult,
    MemoryStats,
    SimNode,
    KGEdge,
} from '../types/kg-types'

interface UseKnowledgeGraphReturn {
    loading: boolean
    error: string | null
    topology: KGTopology | null
    metrics: KGMetrics | null
    auditData: SSSAuditResult | null
    memStats: MemoryStats | null
    simNodes: SimNode[]
    simEdges: KGEdge[]
    selectedNode: SimNode | null
    searchQuery: string
    searchType: string | undefined
    searching: boolean
    searchResults: any | null
    simulating: boolean
    viewMode: string
    topoMode: string
    zoom: number
    rebuildStatus: any | null
    subgraphData: any | null
    highlightType: string | undefined
    setSelectedNode: (node: SimNode | null) => void
    setSearchQuery: (query: string) => void
    setSearchType: (type: string | undefined) => void
    setViewMode: (mode: string) => void
    setTopoMode: (mode: string) => void
    setZoom: (zoom: number) => void
    refreshData: () => Promise<void>
    handleSearch: () => Promise<void>
}

export function useKnowledgeGraph(): UseKnowledgeGraphReturn {
    const [loading, setLoading] = useState(true)
    const [error, setError] = useState<string | null>(null)
    const [topology, setTopology] = useState<KGTopology | null>(null)
    const [metrics, setMetrics] = useState<KGMetrics | null>(null)
    const [auditData, setAuditData] = useState<SSSAuditResult | null>(null)
    const [memStats, setMemStats] = useState<MemoryStats | null>(null)
    const [simNodes] = useState<SimNode[]>([])
    const [simEdges] = useState<KGEdge[]>([])
    const [selectedNode, setSelectedNode] = useState<SimNode | null>(null)
    const [searchQuery, setSearchQuery] = useState('')
    const [searchType, setSearchType] = useState<string | undefined>(undefined)
    const [searching, setSearching] = useState(false)
    const [searchResults, setSearchResults] = useState<any | null>(null)
    const [simulating] = useState(false)
    const [viewMode, setViewMode] = useState('topology')
    const [topoMode, setTopoMode] = useState('sample')
    const [zoom, setZoom] = useState(1)
    const [rebuildStatus] = useState<any>(null)
    const [subgraphData] = useState<any>(null)
    const [highlightType] = useState<string | undefined>(undefined)

    const fetchAllData = useCallback(async () => {
        try {
            setLoading(true)
            const [topoRes, metricsRes, auditRes, statsRes] = await Promise.allSettled([
                api.get(`${endpoints.knowledgeGraph.topology}?mode=sample&sample_rate=0.3&max_nodes=500`),
                api.get(endpoints.knowledgeGraph.metrics),
                api.get(endpoints.knowledgeGraph.sssAudit),
                api.get(endpoints.memories.stats),
            ])

            if (topoRes.status === 'fulfilled') {
                // [FIX-KG-CRASH] 解包AxiosResponse: 取.data字段
                const raw = topoRes.value
                setTopology(raw?.data ?? raw)
            }
            if (metricsRes.status === 'fulfilled') {
                const m = metricsRes.value
                setMetrics(m?.data ?? m)
            }
            if (auditRes.status === 'fulfilled') {
                const a = auditRes.value
                setAuditData(a?.data ?? a)
            }
            if (statsRes.status === 'fulfilled') {
                const s = statsRes.value
                setMemStats(s?.data ?? s)
            }

            setError(null)
        } catch {
            setError('无法加载知识图谱数据')
        } finally {
            setLoading(false)
        }
    }, [])

    const handleSearch = useCallback(async () => {
        if (!searchQuery.trim()) return

        try {
            setSearching(true)
            const res = await api.post(endpoints.knowledgeGraph.search, {
                query: searchQuery,
                type: searchType,
                limit: 20,
            })
            // [FIX-KG-CRASH] 解包AxiosResponse
            setSearchResults(res?.data ?? res)
        } catch {
            setSearchResults(null)
        } finally {
            setSearching(false)
        }
    }, [searchQuery, searchType])

    useEffect(() => {
        fetchAllData()
    }, [fetchAllData])

    return {
        loading,
        error,
        topology,
        metrics,
        auditData,
        memStats,
        simNodes,
        simEdges,
        selectedNode,
        searchQuery,
        searchType,
        searching,
        searchResults,
        simulating,
        viewMode,
        topoMode,
        zoom,
        rebuildStatus,
        subgraphData,
        highlightType,
        setSelectedNode,
        setSearchQuery,
        setSearchType,
        setViewMode,
        setTopoMode,
        setZoom,
        refreshData: fetchAllData,
        handleSearch,
    }
}
