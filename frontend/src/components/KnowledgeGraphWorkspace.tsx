'use client'

import React, { useEffect, useState, useCallback, useMemo } from 'react'
import ReactFlow, {
    Background,
    Controls,
    MiniMap,
    useNodesState,
    useEdgesState,
    MarkerType,
    Position,
    useStore,
    ReactFlowProvider,
} from 'reactflow'
import type { Node, Edge } from 'reactflow'
import 'reactflow/dist/style.css'
import dagre from 'dagre'
import {
    forceSimulation,
    forceLink,
    forceManyBody,
    forceCenter,
    forceCollide
} from 'd3-force'
import { api } from '@/lib/api'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Loader2, RefreshCw, Network, AlertTriangle, Filter, X, GitMerge, Share2 } from 'lucide-react'
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@/components/ui/select"
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group"
import { Slider } from "@/components/ui/slider"
import { Switch } from "@/components/ui/switch"
import GraphNode from './GraphNode'

// Register safe default
const ZoomAwareGraphNode = (props: any) => {
    // Access zoom level from ReactFlow store
    const zoom = useStore((s) => s.transform[2]);
    return <GraphNode {...props} zoom={zoom} />;
};

// Update nodeTypes to use the wrapper
const nodeTypes = {
    knowledgeNode: ZoomAwareGraphNode,
}

// Relationship type colors
const RELATION_COLORS: Record<string, string> = {
    addresses: '#10b981', // green-500
    supports: '#3b82f6',  // blue-500
    contradicts: '#ef4444', // red-500
    triggers: '#f59e0b',  // amber-500
    influences: '#8b5cf6', // violet-500
    resonates: '#ec4899', // pink-500
}

interface KnowledgeGraphWorkspaceProps {
    brandId: number
    brandName?: string
    onNodeSelect?: (nodeId: string) => void
}

type LayoutMode = 'dagre' | 'force';

export function KnowledgeGraphWorkspace({ brandId, onNodeSelect }: KnowledgeGraphWorkspaceProps) {
    const [nodes, setNodes, onNodesChange] = useNodesState([])
    const [edges, setEdges, onEdgesChange] = useEdgesState([])
    const [loading, setLoading] = useState(true)
    const [error, setError] = useState<string | null>(null)
    const [layoutMode, setLayoutMode] = useState<LayoutMode>('dagre')
    const [stats, setStats] = useState<{
        total_nodes: number
        total_edges: number
        contradictions: number
        node_types: Record<string, number>
    } | null>(null)
    const [selectedNode, setSelectedNode] = useState<any>(null)
    const [selectedEdge, setSelectedEdge] = useState<any>(null)
    const [filterType, setFilterType] = useState<string>('all')
    const [filterRelation, setFilterRelation] = useState<string>('all')
    const [filterSegment, setFilterSegment] = useState<string>('all')
    const [focusNodeId, setFocusNodeId] = useState<string | null>(null)
    const [strictFocus, setStrictFocus] = useState<boolean>(false)
    const [minConfidence, setMinConfidence] = useState<number>(0)
    const [hoveredEdgeId, setHoveredEdgeId] = useState<string | null>(null)
    const [relationTypes, setRelationTypes] = useState<string[]>([])


    // Layout Strategies
    const executeLayout = useCallback((nodes: Node[], edges: Edge[], mode: LayoutMode) => {
        if (mode === 'dagre') {
            const dagreGraph = new dagre.graphlib.Graph()
            dagreGraph.setDefaultEdgeLabel(() => ({}))
            dagreGraph.setGraph({ rankdir: 'TB', nodesep: 60, ranksep: 100 })

            nodes.forEach((node) => {
                dagreGraph.setNode(node.id, { width: 60, height: 60 })
            })
            edges.forEach((edge) => {
                dagreGraph.setEdge(edge.source, edge.target)
            })

            dagre.layout(dagreGraph)

            return {
                nodes: nodes.map((node) => {
                    const nodeWithPosition = dagreGraph.node(node.id)
                    return {
                        ...node,
                        targetPosition: Position.Top,
                        sourcePosition: Position.Bottom,
                        position: {
                            x: nodeWithPosition.x - 30,
                            y: nodeWithPosition.y - 30,
                        },
                    }
                }),
                edges,
            }
        } else {
            // D3 Force Simulation
            const simulationNodes = nodes.map(n => ({
                ...n,
                x: n.position.x || Math.random() * 800,
                y: n.position.y || Math.random() * 600
            })) as any[];
            const simulationEdges = edges.map(e => ({ ...e, source: e.source, target: e.target })) as any[];

            const simulation = forceSimulation(simulationNodes)
                .force('charge', forceManyBody().strength(-150))
                .force('center', forceCenter(0, 0))
                .force('link', forceLink(simulationEdges).id((d: any) => d.id).distance(100))
                .force('collide', forceCollide(35))
                .stop()

            simulation.tick(300)

            return {
                nodes: simulationNodes.map((n, i) => ({
                    ...nodes[i],
                    position: { x: n.x, y: n.y },
                    targetPosition: Position.Left,
                    sourcePosition: Position.Right,
                })),
                edges
            }
        }
    }, [])

    // Fetch graph data
    const fetchGraph = useCallback(async () => {
        setLoading(true)
        setError(null)
        try {
            const response = await api.get(`/api/knowledge/brands/${brandId}/graph`)
            const { nodes: rawNodes, edges: rawEdges, stats: graphStats } = response.data

            const flowNodes: Node[] = rawNodes.map((n: any) => ({
                id: n.id,
                type: 'knowledgeNode',
                data: n.data,
                position: n.position || { x: 0, y: 0 }
            }))

            const flowEdges: Edge[] = rawEdges.map((edge: any) => {
                const relationType = edge.data?.relation_type || edge.label || 'related'
                const color = RELATION_COLORS[relationType] || '#6b7280'
                return {
                    id: edge.id || `${edge.source}-${edge.target}`,
                    source: String(edge.source),
                    target: String(edge.target),
                    type: 'smoothstep',
                    animated: relationType === 'contradicts',
                    label: relationType.replace(/_/g, ' ').toUpperCase(),
                    labelStyle: {
                        fill: color,
                        fontWeight: 700,
                        fontSize: 10,
                        textTransform: 'uppercase' as const,
                    },
                    labelBgStyle: {
                        fill: '#ffffff',
                        fillOpacity: 0.9,
                        rx: 4,
                        ry: 4,
                    },
                    labelBgPadding: [6, 4] as [number, number],
                    style: {
                        stroke: color,
                        strokeWidth: 2,
                        strokeDasharray: relationType === 'contradicts' ? '5,5' : undefined,
                    },
                    markerEnd: {
                        type: MarkerType.ArrowClosed,
                        color: color,
                        width: 20,
                        height: 20,
                    },
                    data: edge.data
                }
            })

            const { nodes: layoutedNodes, edges: layoutedEdges } = executeLayout(flowNodes, flowEdges, layoutMode)

            setNodes(layoutedNodes)
            setEdges(layoutedEdges)
            setStats(graphStats)

            // Update relationTypes state
            const uniqueRelationTypes = new Set<string>()
            flowEdges.forEach(e => {
                const relType = e.data?.relation_type || (e.label as string)?.toLowerCase() || 'related'
                uniqueRelationTypes.add(relType)
            })
            setRelationTypes(Array.from(uniqueRelationTypes))

        } catch (err: any) {
            console.error('Failed to fetch knowledge graph:', err)
            setError(err.message || 'Failed to load knowledge graph')
        } finally {
            setLoading(false)
        }
    }, [brandId, executeLayout, layoutMode, setNodes, setEdges])

    useEffect(() => {
        fetchGraph()
    }, [fetchGraph])

    // Find all connected nodes for focus mode
    const getConnectedNodeIds = useCallback((nodeId: string): Set<string> => {
        const connected = new Set<string>([nodeId])
        const toProcess = [nodeId]

        while (toProcess.length > 0) {
            const current = toProcess.pop()!
            edges.forEach(e => {
                if (e.source === current && !connected.has(e.target)) {
                    connected.add(e.target)
                    toProcess.push(e.target)
                }
                if (e.target === current && !connected.has(e.source)) {
                    connected.add(e.source)
                    toProcess.push(e.source)
                }
            })
        }
        return connected
    }, [edges])

    // Filter logic
    const { filteredNodes, filteredEdges } = useMemo(() => {
        let visibleEdges = edges

        // 1. Confidence Filter (Edges)
        if (minConfidence > 0) {
            visibleEdges = visibleEdges.filter(e => (e.data?.strength || 1) * 100 >= minConfidence)
        }

        if (filterRelation !== 'all') {
            visibleEdges = visibleEdges.filter(e => {
                const relType = e.data?.relation_type || (e.label as string)?.toLowerCase() || 'related'
                return relType === filterRelation
            })
        }

        const connectedByEdges = new Set<string>()
        visibleEdges.forEach(e => {
            connectedByEdges.add(e.source)
            connectedByEdges.add(e.target)
        })

        let visibleNodes = [...nodes]

        // 2. Confidence Filter (Nodes)
        if (minConfidence > 0) {
            visibleNodes = visibleNodes.filter(n => (n.data.confidence || 1) * 100 >= minConfidence)
        }

        if (filterSegment !== 'all') {
            visibleNodes = visibleNodes.filter(n => {
                const segment = (n.data.segment || '').toLowerCase()
                if (filterSegment === 'hcp') {
                    return segment.includes('hcp') || segment.includes('physician') || segment.includes('doctor')
                } else if (filterSegment === 'patient') {
                    return segment.includes('patient') || segment.includes('all') || segment === ''
                }
                return true
            })
        }

        if (filterType !== 'all') {
            visibleNodes = visibleNodes.filter(n => n.data.node_type === filterType)
        }

        if (filterRelation !== 'all') {
            visibleNodes = visibleNodes.filter(n => connectedByEdges.has(n.id))
        }

        if (focusNodeId) {
            const connectedIds = getConnectedNodeIds(focusNodeId)

            if (strictFocus) {
                // 3. Strict Focus: Hide unconnected
                visibleNodes = visibleNodes.filter(n => connectedIds.has(n.id))
                visibleEdges = visibleEdges.filter(e => connectedIds.has(e.source) && connectedIds.has(e.target))
            } else {
                // Dim unconnected
                visibleNodes = visibleNodes.map(n => ({
                    ...n,
                    style: {
                        ...n.style,
                        opacity: connectedIds.has(n.id) ? 1 : 0.1,
                        transition: 'opacity 0.3s'
                    }
                }))
                visibleEdges = visibleEdges.map(e => ({
                    ...e,
                    style: {
                        ...e.style,
                        opacity: (connectedIds.has(e.source) && connectedIds.has(e.target)) ? 1 : 0.05,
                        stroke: (connectedIds.has(e.source) && connectedIds.has(e.target)) ? e.style?.stroke : '#e2e8f0',
                        transition: 'opacity 0.3s'
                    }
                }))
            }
        }

        // 4. Edge Label Visibility logic
        // Only show label if edge is hovered or selected
        visibleEdges = visibleEdges.map(e => {
            const isHovered = e.id === hoveredEdgeId || e.id === selectedEdge?.id;
            return {
                ...e,
                labelStyle: {
                    ...e.labelStyle,
                    opacity: isHovered ? 1 : 0, // Semantic Zoom/Hover logic for edges
                    transition: 'opacity 0.2s',
                },
                labelBgStyle: {
                    ...e.labelBgStyle,
                    fillOpacity: isHovered ? 0.9 : 0,
                    transition: 'fill-opacity 0.2s',
                }
            }
        })

        const visibleNodeIds = new Set(visibleNodes.map(n => n.id))
        visibleEdges = visibleEdges.filter(e => visibleNodeIds.has(e.source) && visibleNodeIds.has(e.target))

        return { filteredNodes: visibleNodes, filteredEdges: visibleEdges }
    }, [nodes, edges, filterType, filterRelation, filterSegment, focusNodeId, getConnectedNodeIds, strictFocus, minConfidence, hoveredEdgeId, selectedEdge])

    const onNodeClick = useCallback((_event: React.MouseEvent, node: Node) => {
        setSelectedNode(node.data)
        setSelectedEdge(null)
        onNodeSelect?.(node.id)
        setFocusNodeId(prev => prev === node.id ? null : node.id)
    }, [onNodeSelect])

    const onEdgeClick = useCallback((_event: React.MouseEvent, edge: Edge) => {
        setSelectedEdge(edge.data)
        setSelectedNode(null)
    }, [])

    // New Edge Interactions
    const onEdgeMouseEnter = useCallback((_event: React.MouseEvent, edge: Edge) => {
        setHoveredEdgeId(edge.id)
    }, [])

    const onEdgeMouseLeave = useCallback(() => {
        setHoveredEdgeId(null)
    }, [])

    // Render Logic
    if (loading) {
        return (
            <div className="flex h-full w-full items-center justify-center bg-gray-50/50">
                <div className="text-center">
                    <Loader2 className="h-10 w-10 animate-spin mx-auto text-indigo-500" />
                    <p className="mt-3 text-sm text-muted-foreground">Mapping knowledge network...</p>
                </div>
            </div>
        )
    }

    if (error) {
        return (
            <div className="flex h-full w-full items-center justify-center bg-red-50/50">
                <div className="text-center">
                    <AlertTriangle className="h-10 w-10 mx-auto text-red-500" />
                    <p className="mt-3 text-sm text-red-600 font-medium">{error}</p>
                    <Button variant="outline" onClick={fetchGraph} className="mt-4">
                        <RefreshCw className="h-4 w-4 mr-2" /> Retry
                    </Button>
                </div>
            </div>
        )
    }

    if (nodes.length === 0) {
        return (
            <div className="flex h-full w-full items-center justify-center bg-gray-50/50">
                <div className="text-center max-w-md">
                    <div className="bg-gray-100 rounded-full p-6 w-20 h-20 mx-auto mb-6 flex items-center justify-center">
                        <Network className="h-10 w-10 text-gray-400" />
                    </div>
                    <h3 className="text-xl font-semibold">Knowledge Graph Empty</h3>
                    <p className="mt-2 text-muted-foreground mb-6">
                        No insights extracted yet. Upload brand documents to generate the knowledge graph.
                    </p>
                </div>
            </div>
        )
    }

    return (
        <ReactFlowProvider>
            <div className="flex h-full w-full bg-background overflow-hidden border-t">
                {/* LEFT SIDEBAR: Filters & Legend */}
                <div className="w-80 flex-shrink-0 border-r bg-muted/10 flex flex-col z-20">
                    <div className="p-4 border-b space-y-4">
                        <h2 className="font-semibold flex items-center gap-2">
                            <Filter className="h-4 w-4 text-violet-500" />
                            Graph Controls
                        </h2>

                        {/* Layout Toggle */}
                        <div className="space-y-2">
                            <label className="text-xs font-semibold text-muted-foreground uppercase">Layout</label>
                            <ToggleGroup type="single" value={layoutMode} onValueChange={(v) => v && setLayoutMode(v as LayoutMode)} className="w-full justify-start gap-1">
                                <ToggleGroupItem value="dagre" size="sm" className="flex-1 text-xs data-[state=on]:bg-violet-100 data-[state=on]:text-violet-800">
                                    <GitMerge className="h-3 w-3 mr-2 rotate-90" /> Tree
                                </ToggleGroupItem>
                                <ToggleGroupItem value="force" size="sm" className="flex-1 text-xs data-[state=on]:bg-violet-100 data-[state=on]:text-violet-800">
                                    <Share2 className="h-3 w-3 mr-2" /> Force
                                </ToggleGroupItem>
                            </ToggleGroup>
                        </div>

                        {/* New Controls */}
                        <div className="space-y-4 pt-2 border-t mt-2">
                            <div className="flex items-center justify-between">
                                <label className="text-xs font-semibold text-muted-foreground uppercase">Strict Focus</label>
                                <Switch checked={strictFocus} onCheckedChange={setStrictFocus} disabled={!focusNodeId} />
                            </div>

                            <div className="space-y-3">
                                <div className="flex items-center justify-between">
                                    <label className="text-xs font-semibold text-muted-foreground uppercase">Min Confidence</label>
                                    <span className="text-xs text-muted-foreground font-mono">{minConfidence}%</span>
                                </div>
                                <Slider
                                    value={[minConfidence]}
                                    onValueChange={(vals) => setMinConfidence(vals[0])}
                                    max={95}
                                    step={5}
                                />
                            </div>
                        </div>
                    </div>

                    <ScrollArea className="flex-1">
                        <div className="p-4 space-y-6">
                            {/* Filters */}
                            <div className="space-y-3">
                                <label className="text-xs font-semibold text-muted-foreground uppercase">View By</label>

                                <Select value={filterType} onValueChange={setFilterType}>
                                    <SelectTrigger className="w-full bg-background">
                                        <SelectValue placeholder="All Categories" />
                                    </SelectTrigger>
                                    <SelectContent>
                                        <SelectItem value="all">All Categories</SelectItem>
                                        {stats?.node_types && Object.keys(stats.node_types).map(type => (
                                            <SelectItem key={type} value={type}>
                                                {type.replace(/_/g, ' ')} ({stats.node_types[type]})
                                            </SelectItem>
                                        ))}
                                    </SelectContent>
                                </Select>

                                <Select value={filterSegment} onValueChange={(val) => { setFilterSegment(val); setFocusNodeId(null); }}>
                                    <SelectTrigger className="w-full bg-background">
                                        <SelectValue placeholder="All Segments" />
                                    </SelectTrigger>
                                    <SelectContent>
                                        <SelectItem value="all">👥 All Segments</SelectItem>
                                        <SelectItem value="patient">😷 Patients</SelectItem>
                                        <SelectItem value="hcp">🩺 HCPs</SelectItem>
                                    </SelectContent>
                                </Select>

                                <Select value={filterRelation} onValueChange={(val) => { setFilterRelation(val); setFocusNodeId(null); }}>
                                    <SelectTrigger className="w-full bg-background">
                                        <SelectValue placeholder="All Relations" />
                                    </SelectTrigger>
                                    <SelectContent>
                                        <SelectItem value="all">All Relations</SelectItem>
                                        {relationTypes.map(type => (
                                            <SelectItem key={type} value={type}>
                                                {type.replace(/_/g, ' ').toUpperCase()}
                                            </SelectItem>
                                        ))}
                                    </SelectContent>
                                </Select>
                            </div>

                            {/* Quick Views */}
                            <div className="space-y-2">
                                <label className="text-xs font-semibold text-muted-foreground uppercase">Story Views</label>
                                <div className="grid grid-cols-1 gap-1">
                                    <Button variant="ghost" size="sm" className="justify-start h-8 font-normal"
                                        onClick={() => { setFilterType('all'); setFilterRelation('all'); setFocusNodeId(null); }}>
                                        🔍 Full Graph
                                    </Button>
                                    <Button variant="ghost" size="sm" className="justify-start h-8 font-normal text-rose-700 hover:bg-rose-50 hover:text-rose-800"
                                        onClick={() => { setFilterType('patient_tension'); setFilterRelation('all'); setFocusNodeId(null); }}>
                                        😰 Patient Tensions
                                    </Button>
                                    <Button variant="ghost" size="sm" className="justify-start h-8 font-normal text-purple-700 hover:bg-purple-50 hover:text-purple-800"
                                        onClick={() => { setFilterType('key_message'); setFilterRelation('all'); setFocusNodeId(null); }}>
                                        💬 Key Messages
                                    </Button>
                                    <Button variant="ghost" size="sm" className="justify-start h-8 font-normal text-emerald-700 hover:bg-emerald-50 hover:text-emerald-800"
                                        onClick={() => { setFilterType('all'); setFilterRelation('addresses'); setFocusNodeId(null); }}>
                                        🎯 Messages → Tensions
                                    </Button>
                                </div>
                            </div>

                            {/* Legend */}
                            <div>
                                <label className="text-xs font-semibold text-muted-foreground uppercase mb-2 block">Legend</label>
                                <div className="space-y-2 bg-background p-3 rounded-lg border text-xs">
                                    <div className="flex items-center gap-2">
                                        <div className="w-3 h-3 rounded-full bg-emerald-500" />
                                        <span>Addresses (Solution)</span>
                                    </div>
                                    <div className="flex items-center gap-2">
                                        <div className="w-3 h-3 rounded-full bg-blue-500" />
                                        <span>Supports (Reinforce)</span>
                                    </div>
                                    <div className="flex items-center gap-2">
                                        <div className="w-3 h-3 rounded-full bg-red-500" />
                                        <span>Contradicts (Conflict)</span>
                                    </div>
                                    <div className="flex items-center gap-2">
                                        <div className="w-3 h-3 rounded-full bg-amber-500" />
                                        <span>Triggers (Cause)</span>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </ScrollArea>

                    <div className="p-4 border-t bg-background">
                        <Button variant="outline" className="w-full" onClick={fetchGraph}>
                            <RefreshCw className="h-4 w-4 mr-2" /> Refresh Data
                        </Button>
                    </div>
                </div>

                {/* CENTER: Canvas */}
                <div className="flex-1 bg-dots-pattern relative overflow-hidden flex flex-col">
                    <ReactFlow
                        nodes={filteredNodes}
                        edges={filteredEdges}
                        onNodesChange={onNodesChange}
                        onEdgesChange={onEdgesChange}
                        onNodeClick={onNodeClick}
                        onEdgeClick={onEdgeClick}
                        onEdgeMouseEnter={onEdgeMouseEnter}
                        onEdgeMouseLeave={onEdgeMouseLeave}
                        nodeTypes={nodeTypes}
                        fitView
                        minZoom={0.2}
                        maxZoom={2}
                        className="bg-gray-50/50"
                    >
                        <Background color="#94a3b8" gap={20} size={1} style={{ opacity: 0.15 }} />
                        <Controls showInteractive={false} className="bg-white shadow border rounded-lg" />
                        <MiniMap
                            className="!bottom-4 !right-4 rounded-lg overflow-hidden border shadow-lg"
                            zoomable
                            pannable
                            nodeColor={(n) => {
                                return n.data?.node_type?.includes('patient') ? '#10b981' :
                                    n.data?.node_type?.includes('disease') ? '#3b82f6' :
                                        n.data?.node_type?.includes('hcp') ? '#f97316' : '#8b5cf6'
                            }}
                        />
                    </ReactFlow>

                    {/* Overlay Focus Indicator */}
                    {focusNodeId && (
                        <div className="absolute top-4 left-4 z-10 w-auto">
                            <Badge variant="secondary" className="px-3 py-1.5 bg-indigo-100 text-indigo-700 shadow-sm border-indigo-200 flex items-center gap-2">
                                <span>Focus Mode Active</span>
                                <button onClick={() => setFocusNodeId(null)} className="hover:text-indigo-900"><X className="h-3 w-3" /></button>
                            </Badge>
                        </div>
                    )}
                </div>

                {/* RIGHT: Detail Panel */}
                <div className={`w-[350px] border-l bg-background p-4 shadow-xl z-10 transition-transform duration-300 ${selectedNode || selectedEdge ? 'translate-x-0' : 'translate-x-full absolute right-0'}`}>
                    <div className="flex items-center justify-between mb-6">
                        <span className={`px-2 py-1 rounded-full text-xs font-semibold ${selectedEdge
                            ? 'bg-purple-100 text-purple-700'
                            : 'bg-indigo-100 text-indigo-700'
                            }`}>
                            {selectedEdge ? (selectedEdge.relation_type || 'relationship').replace(/_/g, ' ') : (selectedNode?.node_type?.replace(/_/g, ' ') || 'insight details')}
                        </span>
                        <Button variant="ghost" size="sm" onClick={() => { setSelectedNode(null); setSelectedEdge(null); }}>
                            <X className="h-4 w-4" />
                        </Button>
                    </div>

                    {selectedNode && (
                        <div className="space-y-6">
                            <div>
                                <h3 className="text-xs font-semibold text-muted-foreground uppercase mb-2">Content</h3>
                                <div className="p-3 bg-gray-50 rounded-lg border text-sm font-medium">
                                    {selectedNode.text}
                                </div>
                            </div>

                            {selectedNode.source_quote && (
                                <div>
                                    <h3 className="text-xs font-semibold text-muted-foreground uppercase mb-2">Source Evidence</h3>
                                    <blockquote className="pl-3 border-l-2 border-indigo-300 text-sm italic text-muted-foreground">
                                        "{selectedNode.source_quote}"
                                    </blockquote>
                                </div>
                            )}

                            <div className="grid grid-cols-2 gap-4">
                                <div>
                                    <h3 className="text-xs font-semibold text-muted-foreground uppercase mb-1">Segment</h3>
                                    <p className="text-sm font-medium">{selectedNode.segment || 'General'}</p>
                                </div>
                                <div>
                                    <h3 className="text-xs font-semibold text-muted-foreground uppercase mb-1">Confidence</h3>
                                    <div className="flex items-center gap-2">
                                        <div className="flex-1 h-2 bg-gray-100 rounded-full overflow-hidden">
                                            <div
                                                className="h-full bg-emerald-500 rounded-full"
                                                style={{ width: `${(selectedNode.confidence || 0) * 100}%` }}
                                            />
                                        </div>
                                        <span className="text-xs text-muted-foreground">{Math.round((selectedNode.confidence || 0) * 100)}%</span>
                                    </div>
                                </div>
                            </div>

                            <div className="pt-4 border-t">
                                <div className="flex items-center gap-2 text-xs text-muted-foreground">
                                    <span>ID:</span>
                                    <code className="bg-gray-100 px-1 py-0.5 rounded text-[10px]">{selectedNode.id}</code>
                                </div>
                            </div>
                        </div>
                    )}

                    {selectedEdge && (
                        <div className="space-y-6">
                            <div>
                                <h3 className="text-xs font-semibold text-muted-foreground uppercase mb-2">Relationship Context</h3>
                                <div className="p-3 bg-purple-50 rounded-lg border border-purple-100 text-sm">
                                    {selectedEdge.context || "No detailed context available."}
                                </div>
                            </div>

                            <div className="grid grid-cols-2 gap-4">
                                <div>
                                    <h3 className="text-xs font-semibold text-muted-foreground uppercase mb-1">Type</h3>
                                    <p className="text-sm font-medium capitalize">{(selectedEdge.relation_type || 'Related to').replace(/_/g, ' ')}</p>
                                </div>
                                <div>
                                    <h3 className="text-xs font-semibold text-muted-foreground uppercase mb-1">Strength</h3>
                                    <div className="flex items-center gap-2">
                                        <div className="flex-1 h-2 bg-gray-100 rounded-full overflow-hidden">
                                            <div
                                                className="h-full bg-purple-500 rounded-full"
                                                style={{ width: `${(selectedEdge.strength || 0) * 100}%` }}
                                            />
                                        </div>
                                        <span className="text-xs text-muted-foreground">{Math.round((selectedEdge.strength || 0) * 100)}%</span>
                                    </div>
                                </div>
                            </div>
                        </div>
                    )}
                </div>
            </div>
        </ReactFlowProvider>
    )
}
