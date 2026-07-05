import { useCallback, useRef } from 'react'
import { KGTopology, SimNode, KGEdge, CANVAS_CONFIG } from '../types/kg-types'

// [FIX-TS-008] 移除未使用的 ForceSimulationProps 声明
// (原本声明但未使用，已删除)

export function useForceSimulation() {
    const simulatingRef = useRef(false)

    const buildSimulation = useCallback((
        topo: KGTopology,
        onComplete: (nodes: SimNode[], edges: KGEdge[]) => void,
        onSimulatingChange: (v: boolean) => void
    ) => {
        const nodeMap = new Map<string, number>()
        const degreeMap: Record<string, number> = {}

        const safeEdges = topo.edges || []
        for (const e of safeEdges) {
            degreeMap[e.source] = (degreeMap[e.source] || 0) + 1
            degreeMap[e.target] = (degreeMap[e.target] || 0) + 1
        }

        const typeGroups: Record<string, typeof topo.nodes> = {}
        const safeNodes = topo.nodes || []
        for (const n of safeNodes) {
            if (!typeGroups[n.type]) typeGroups[n.type] = []
            typeGroups[n.type].push(n)
        }

        const newSimNodes: SimNode[] = []
        const types = Object.keys(typeGroups)
        const angleStep = (2 * Math.PI) / Math.max(types.length, 1)

        types.forEach((t, ti) => {
            const angle = angleStep * ti - Math.PI / 2
            const cx = CANVAS_CONFIG.WIDTH / 2 + Math.cos(angle) * 200
            const cy = CANVAS_CONFIG.HEIGHT / 2 + Math.sin(angle) * 200

            typeGroups[t].forEach((n) => {
                const spreadAngle = angle + (Math.random() - 0.5) * 1.2
                const spreadR = Math.random() * 80 + 20
                const idx = newSimNodes.length
                nodeMap.set(n.id, idx)
                newSimNodes.push({
                    id: n.id,
                    type: n.type,
                    x: cx + Math.cos(spreadAngle) * spreadR,
                    y: cy + Math.sin(spreadAngle) * spreadR,
                    vx: 0,
                    vy: 0,
                    degree: degreeMap[n.id] || 0,
                    frequency: n.frequency || 1,
                })
            })
        })

        const validEdges = (topo.edges || []).filter(e => nodeMap.has(e.source) && nodeMap.has(e.target))

        runSimulation(newSimNodes, validEdges, onComplete, onSimulatingChange)
    }, [])

    const runSimulation = useCallback(
        (
            initialNodes: SimNode[],
            initialEdges: KGEdge[],
            onComplete: (nodes: SimNode[], edges: KGEdge[]) => void,
            onSimulatingChange: (v: boolean) => void
        ) => {
            if (simulatingRef.current) return

            simulatingRef.current = true
            onSimulatingChange(true)

            const nodes = initialNodes.map(n => ({ ...n }))
            let iter = 0

            const step = () => {
                if (iter >= CANVAS_CONFIG.MAX_ITERATIONS) {
                    onComplete(nodes.map(n => ({ ...n, vx: 0, vy: 0 })), initialEdges)
                    onSimulatingChange(false)
                    simulatingRef.current = false
                    return
                }

                for (const node of nodes) {
                    node.vx *= CANVAS_CONFIG.DAMPING
                    node.vy *= CANVAS_CONFIG.DAMPING
                }

                for (let i = 0; i < nodes.length; i++) {
                    for (let j = i + 1; j < nodes.length; j++) {
                        const dx = nodes[j].x - nodes[i].x
                        const dy = nodes[j].y - nodes[i].y
                        const dist = Math.sqrt(dx * dx + dy * dy) || 1
                        const force = CANVAS_CONFIG.REPULSION / (dist * dist)

                        const fx = (dx / dist) * force
                        const fy = (dy / dist) * force

                        nodes[i].vx -= fx
                        nodes[i].vy -= fy
                        nodes[j].vx += fx
                        nodes[j].vy += fy
                    }
                }

                for (const edge of initialEdges) {
                    const srcIdx = nodes.findIndex(n => n.id === edge.source)
                    const tgtIdx = nodes.findIndex(n => n.id === edge.target)
                    if (srcIdx === -1 || tgtIdx === -1) continue

                    const dx = nodes[tgtIdx].x - nodes[srcIdx].x
                    const dy = nodes[tgtIdx].y - nodes[srcIdx].y
                    const dist = Math.sqrt(dx * dx + dy * dy) || 1
                    const force = dist * CANVAS_CONFIG.ATTRACTION

                    const fx = (dx / dist) * force
                    const fy = (dy / dist) * force

                    nodes[srcIdx].vx += fx
                    nodes[srcIdx].vy += fy
                    nodes[tgtIdx].vx -= fx
                    nodes[tgtIdx].vy -= fy
                }

                for (const node of nodes) {
                    node.x += node.vx
                    node.y += node.vy

                    node.x = Math.max(20, Math.min(CANVAS_CONFIG.WIDTH - 20, node.x))
                    node.y = Math.max(20, Math.min(CANVAS_CONFIG.HEIGHT - 20, node.y))
                }

                iter++
                requestAnimationFrame(step)
            }

            requestAnimationFrame(step)
        },
        []
    )

    return { buildSimulation }
}
