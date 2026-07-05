import { useEffect, useRef, useState } from 'react'
import cytoscape, { Core, NodeSingular } from 'cytoscape'
import coseBilkent from 'cytoscape-cose-bilkent'
import { Spin } from 'antd'
import type { KGTopology } from '../types/kg-types'

cytoscape.use(coseBilkent)

const TYPE_COLORS: Record<string, string> = {
    concept: '#ffadd2', process: '#91d5ff', system: '#69c0ff',
    agent: '#b7eb8f', technology: '#d3adf7', event: '#ff85c0',
    metric: '#ffc069', data_structure: '#87e8de', layer: '#ffd666',
    module: '#91d5ff', skill: '#d3adf7', function: '#ffc069',
    class: '#87e8de', config: '#ff9c6e', route: '#95de64',
    model: '#69c0ff', tool: '#bae637',
}

const DEFAULT_COLOR = '#8c8c8c'
const MAX_NODES = 500
const MAX_EDGES = 3000

interface CytoscapeKGProps {
    topology: KGTopology | null
    onNodeSelect?: (node: { id: string; type: string; degree: number; frequency: number } | null) => void
}

export function CytoscapeKG({ topology, onNodeSelect }: CytoscapeKGProps) {
    const containerRef = useRef<HTMLDivElement>(null)
    const cyRef = useRef<Core | null>(null)
    const [rendering, setRendering] = useState(false)

    useEffect(() => {
        if (!containerRef.current || !topology) return

        // [FIX-KG-CRASH] 防御性检查: 确保nodes和edges是有效数组
        const safeNodes = Array.isArray(topology.nodes) ? topology.nodes : []
        const safeEdges = Array.isArray(topology.edges) ? topology.edges : []

        // [FIX-TS-009] 修复类型比较: safeEdges 是数组, 不是 boolean
        if (safeNodes.length === 0 || safeEdges.length === 0) return

        try {
            if (cyRef.current) {
                cyRef.current.destroy()
                cyRef.current = null
            }

            const degreeMap: Record<string, number> = {}

            let displayNodes = safeNodes
            let displayEdges = safeEdges

            if (safeNodes.length > MAX_NODES) {
                displayNodes = safeNodes.slice(0, MAX_NODES)
                console.log(`[Cytoscape] 采样节点: ${safeNodes.length} → ${MAX_NODES}`)
            }

            const displayNodeSet = new Set(displayNodes.map(n => n.id))

            const validEdges = []
            for (const e of displayEdges) {
                if (!displayNodeSet.has(e.source) || !displayNodeSet.has(e.target)) continue
                degreeMap[e.source] = (degreeMap[e.source] || 0) + 1
                degreeMap[e.target] = (degreeMap[e.target] || 0) + 1
                validEdges.push(e)
            }

            if (validEdges.length > MAX_EDGES) {
                validEdges.sort((a, b) => (b.weight || 1) - (a.weight || 1))
                validEdges.splice(MAX_EDGES)
                console.log(`[Cytoscape] 采样边: ${displayEdges.length} → ${MAX_EDGES}`)
            }
            displayEdges = validEdges

            const cyElements: Array<cytoscape.ElementDefinition> = []

            for (const n of displayNodes) {
                cyElements.push({
                    data: {
                        id: n.id,
                        label: n.id.length > 12 ? n.id.slice(0, 12) + '…' : n.id,
                        type: n.type,
                        degree: degreeMap[n.id] || 0,
                        frequency: n.frequency || 1,
                    },
                })
            }

            for (const e of displayEdges) {
                cyElements.push({
                    data: {
                        id: `${e.source}→${e.target}:${(e.relation || '').slice(0, 10)}`,
                        source: e.source,
                        target: e.target,
                        relation: e.relation,
                        weight: e.weight || 1,
                    },
                })
            }

            setRendering(true)

            requestAnimationFrame(() => {
                if (!containerRef.current) return

                try {
                    const cy = cytoscape({
                        container: containerRef.current,
                        elements: cyElements,
                        style: [
                            {
                                selector: 'node',
                                style: {
                                    'background-color': 'data(type)',
                                    'label': 'data(label)',
                                    'color': '#333',
                                    'font-size': '10px',
                                    'text-valign': 'center',
                                    'text-halign': 'center',
                                    'width': 'mapData(degree, 0, 200, 12, 40)',
                                    'height': 'mapData(degree, 0, 200, 12, 40)',
                                    'border-width': 1,
                                    'border-color': '#555',
                                    'text-outline-color': '#fff',
                                    'text-outline-width': 2,
                                    'text-wrap': 'ellipsis',
                                    'text-max-width': '80px',
                                },
                            },
                            {
                                selector: 'node:selected',
                                style: {
                                    'border-width': 3,
                                    'border-color': '#1890ff',
                                    'background-blacken': 0.1,
                                },
                            },
                            {
                                selector: 'edge',
                                style: {
                                    'width': 'mapData(weight, 1, 10, 0.3, 2)',
                                    'line-color': '#bbb',
                                    'target-arrow-color': '#bbb',
                                    'target-arrow-shape': 'triangle',
                                    'curve-style': 'bezier',
                                    'opacity': 0.3,
                                    'arrow-scale': 0.5,
                                },
                            },
                            {
                                selector: 'edge.highlighted',
                                style: {
                                    'line-color': '#1890ff',
                                    'target-arrow-color': '#1890ff',
                                    'opacity': 0.9,
                                    'width': 2,
                                },
                            },
                        ],
                        layout: {
                            name: 'cose-bilkent',
                            animate: true as any,
                            animationDuration: 800,
                            animationEasing: 'ease-out',
                            randomize: true,
                            idealEdgeLength: 60,
                            nodeRepulsion: 4000,
                            gravity: 0.3,
                            numIter: 150,
                            tile: true,
                            tilingPaddingVertical: 15,
                            tilingPaddingHorizontal: 15,
                            packComponents: true,
                        } as any,
                    })

                    const typeMapping = { ...TYPE_COLORS }
                    cy.nodes().forEach((n: NodeSingular) => {
                        const t = n.data('type') as string
                        n.style('background-color', typeMapping[t] || DEFAULT_COLOR)
                    })

                    cy.on('tap', 'node', (evt: { target: NodeSingular }) => {
                        const nd = evt.target
                        const connectedEdges = nd.connectedEdges()
                        const connectedNodes = connectedEdges.connectedNodes()

                        cy.elements().removeClass('highlighted')
                        connectedEdges.addClass('highlighted')

                        cy.nodes().not(connectedNodes.union(nd)).style({ opacity: 0.15 })
                        connectedNodes.union(nd).style({ opacity: 1 })

                        if (onNodeSelect) {
                            onNodeSelect({
                                id: nd.data('id'),
                                type: nd.data('type'),
                                degree: nd.data('degree'),
                                frequency: nd.data('frequency'),
                            })
                        }
                    })

                    cy.on('tap', () => {
                        cy.elements().removeClass('highlighted')
                        cy.nodes().style({ opacity: 1 })
                        cy.edges().style({ opacity: 0.3 })
                        if (onNodeSelect) onNodeSelect(null)
                    })

                    cyRef.current = cy
                } catch (err) {
                    console.error('[Cytoscape] 渲染错误:', err)
                } finally {
                    setRendering(false)
                }
            })

            return () => {
                if (cyRef.current) {
                    cyRef.current.destroy()
                    cyRef.current = null
                }
            }
        } catch (err) {
            console.error('[CytoscapeKG] 渲染异常:', err)
            setRendering(false)
        }
    }, [topology])

    useEffect(() => {
        return () => {
            if (cyRef.current) {
                cyRef.current.destroy()
                cyRef.current = null
            }
        }
    }, [])

    return (
        <div style={{ position: 'relative', width: '100%', height: '650px' }}>
            <div
                ref={containerRef}
                style={{
                    width: '100%',
                    height: '100%',
                    background: '#fafafa',
                    borderRadius: 8,
                    border: '1px solid #f0f0f0',
                }}
            />
            {rendering && (
                <div style={{
                    position: 'absolute', top: 0, left: 0, right: 0, bottom: 0,
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    background: 'rgba(250,250,250,0.7)', borderRadius: 8,
                }}>
                    <Spin size="large" />
                </div>
            )}
        </div>
    )
}
