import React, { useState, useEffect, useMemo } from 'react';
import { KnowledgeGraphAPI } from '@/lib/api';
import type { KnowledgeNode } from '@/lib/api';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Search, Filter, Quote, ExternalLink, CheckCircle2, AlertCircle, Loader2 } from 'lucide-react';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';

interface KnowledgeFactsViewProps {
    brandId: number;
    brandName?: string;
}

export function KnowledgeFactsView({ brandId, brandName }: KnowledgeFactsViewProps) {
    const [nodes, setNodes] = useState<KnowledgeNode[]>([]);
    const [loading, setLoading] = useState(true);
    const [searchQuery, setSearchQuery] = useState('');
    const [filterVerify, setFilterVerify] = useState<string>('all'); // all, verified, unverified
    const [filterType, setFilterType] = useState<string>('all');

    useEffect(() => {
        fetchNodes();
    }, [brandId]);

    const fetchNodes = async () => {
        setLoading(true);
        try {
            // Fetch all nodes initially
            const response = await KnowledgeGraphAPI.getNodes(brandId, { limit: 1000 } as any);
            setNodes(response.nodes);
        } catch (error) {
            console.error("Failed to fetch knowledge nodes", error);
        } finally {
            setLoading(false);
        }
    };

    // Derived state for filtering
    const filteredNodes = useMemo(() => {
        return nodes.filter(node => {
            const matchesSearch =
                node.text.toLowerCase().includes(searchQuery.toLowerCase()) ||
                (node.source_quote && node.source_quote.toLowerCase().includes(searchQuery.toLowerCase())) ||
                (node.segment && node.segment.toLowerCase().includes(searchQuery.toLowerCase()));

            const matchesVerify =
                filterVerify === 'all' ? true :
                    filterVerify === 'verified' ? node.verified :
                        !node.verified;

            const matchesType =
                filterType === 'all' ? true :
                    filterType === 'patient_insight' ? (node.node_type === 'patient_motivation' || node.node_type === 'patient_belief' || node.node_type === 'patient_tension') :
                        node.node_type === filterType;

            return matchesSearch && matchesVerify && matchesType;
        });
    }, [nodes, searchQuery, filterVerify, filterType]);

    // Grouping nodes by category for cleaner display
    const groupedNodes = useMemo(() => {
        const groups: Record<string, KnowledgeNode[]> = {};

        filteredNodes.forEach(node => {
            // Map raw node types to friendly categories
            let category = 'General Knowledge';
            if (node.node_type.includes('patient')) category = 'Patient Insights';
            else if (node.node_type.includes('hcp')) category = 'HCP Insights';
            else if (node.node_type.includes('clinical') || node.node_type.includes('efficacy') || node.node_type.includes('safety')) category = 'Clinical Data';
            else if (node.node_type.includes('market')) category = 'Market Landscape';
            else if (node.node_type.includes('competitor')) category = 'Competitive Intel';
            else if (node.node_type.includes('key_message')) category = 'Key Messages';

            if (!groups[category]) groups[category] = [];
            groups[category].push(node);
        });

        // Sort categories to put Patient/HCP first
        return Object.entries(groups).sort((a, b) => {
            const priority = ['Key Messages', 'Clinical Data', 'Patient Insights', 'HCP Insights'];
            const idxA = priority.indexOf(a[0]);
            const idxB = priority.indexOf(b[0]);
            if (idxA > -1 && idxB > -1) return idxA - idxB;
            if (idxA > -1) return -1;
            if (idxB > -1) return 1;
            return a[0].localeCompare(b[0]);
        });
    }, [filteredNodes]);

    // Format confidence as percentage
    const formatConfidence = (conf: number) => `${Math.round(conf * 100)}%`;

    if (loading) {
        return (
            <div className="flex h-full w-full items-center justify-center bg-gray-50/50">
                <div className="text-center">
                    <Loader2 className="h-10 w-10 animate-spin mx-auto text-violet-500" />
                    <p className="mt-3 text-sm text-muted-foreground">Loading brand evidence...</p>
                </div>
            </div>
        );
    }

    if (nodes.length === 0) {
        return (
            <div className="flex h-full flex-col items-center justify-center bg-gray-50/30 p-8 text-center">
                <div className="bg-violet-100 rounded-full p-6 w-20 h-20 mb-4 flex items-center justify-center">
                    <Quote className="h-10 w-10 text-violet-500" />
                </div>
                <h3 className="text-xl font-semibold mb-2">Evidence Bank Empty</h3>
                <p className="text-muted-foreground max-w-md mb-6">
                    No facts or insights have been extracted yet. Upload clinical studies, market research, or detail aids to populate your Evidence Bank.
                </p>
                <Button>Upload Documents</Button>
            </div>
        );
    }

    return (
        <div className="flex flex-col h-full bg-slate-50/50 dark:bg-slate-950/50">
            {/* Toolbar */}
            <div className="p-4 border-b bg-background flex flex-col md:flex-row gap-4 items-center justify-between sticky top-0 z-10 shadow-sm">
                <div className="relative w-full md:w-96">
                    <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
                    <Input
                        placeholder="Search facts, quotes, sources..."
                        className="pl-9 bg-muted/30 border-muted-foreground/20"
                        value={searchQuery}
                        onChange={(e) => setSearchQuery(e.target.value)}
                    />
                </div>

                <div className="flex items-center gap-2 w-full md:w-auto">
                    <Select value={filterType} onValueChange={setFilterType}>
                        <SelectTrigger className="w-[160px] h-9">
                            <SelectValue placeholder="Category" />
                        </SelectTrigger>
                        <SelectContent>
                            <SelectItem value="all">All Categories</SelectItem>
                            <SelectItem value="key_message">Key Messages</SelectItem>
                            <SelectItem value="clinical_outcome">Clinical Data</SelectItem>
                            <SelectItem value="patient_insight">Patient Insights</SelectItem>
                            <SelectItem value="hcp_insight">HCP Insights</SelectItem>
                        </SelectContent>
                    </Select>

                    <Select value={filterVerify} onValueChange={setFilterVerify}>
                        <SelectTrigger className="w-[140px] h-9">
                            <SelectValue placeholder="Verification" />
                        </SelectTrigger>
                        <SelectContent>
                            <SelectItem value="all">Mq Verification</SelectItem>
                            <SelectItem value="verified">✅ Verified</SelectItem>
                            <SelectItem value="unverified">⚠️ Unverified</SelectItem>
                        </SelectContent>
                    </Select>
                </div>
            </div>

            {/* Content Area */}
            <ScrollArea className="flex-1 p-6">
                <div className="max-w-6xl mx-auto space-y-8 pb-10">

                    {groupedNodes.length === 0 ? (
                        <div className="text-center py-12 text-muted-foreground">
                            No evidence found matching your filters.
                        </div>
                    ) : (
                        groupedNodes.map(([category, categoryNodes]) => (
                            <div key={category} className="space-y-4">
                                <h2 className="text-lg font-semibold flex items-center gap-2 text-slate-800 dark:text-slate-200">
                                    {category}
                                    <Badge variant="secondary" className="rounded-full px-2 py-0.5 text-xs font-normal">
                                        {categoryNodes.length}
                                    </Badge>
                                </h2>

                                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                                    {categoryNodes.map(node => (
                                        <Card key={node.id} className="group hover:shadow-md transition-shadow border-slate-200 dark:border-slate-800 bg-white">
                                            <CardHeader className="p-4 pb-2">
                                                <div className="flex justify-between items-start gap-2">
                                                    <Badge variant={node.verified ? "default" : "outline"} className={`mb-2 ${node.verified ? 'bg-emerald-100 text-emerald-800 hover:bg-emerald-100 border-0' : 'text-amber-600 border-amber-200 bg-amber-50'}`}>
                                                        {node.verified ? (
                                                            <><CheckCircle2 className="h-3 w-3 mr-1" /> Verified</>
                                                        ) : (
                                                            <><AlertCircle className="h-3 w-3 mr-1" /> Needs Review</>
                                                        )}
                                                    </Badge>
                                                    {node.confidence < 0.8 && (
                                                        <span className="text-xs font-mono text-amber-600 bg-amber-50 px-1.5 py-0.5 rounded" title="AI Confidence Score">
                                                            {formatConfidence(node.confidence)}
                                                        </span>
                                                    )}
                                                </div>
                                                <CardTitle className="text-sm font-medium leading-snug text-slate-900">
                                                    {node.text}
                                                </CardTitle>
                                            </CardHeader>
                                            <CardContent className="p-4 pt-2 space-y-3">
                                                {node.source_quote && (
                                                    <div className="bg-slate-50 dark:bg-slate-900 rounded-md p-2 text-xs italic text-slate-600 dark:text-slate-400 relative">
                                                        <Quote className="h-3 w-3 absolute -top-1.5 -left-1 text-slate-300" />
                                                        "{node.source_quote}"
                                                    </div>
                                                )}

                                                <div className="flex items-center justify-between pt-2 border-t border-slate-100 dark:border-slate-800 mt-2">
                                                    <div className="flex items-center gap-2 text-xs text-muted-foreground">
                                                        <span className="truncate max-w-[120px]" title={node.segment || 'General'}>
                                                            {node.segment || 'General'}
                                                        </span>
                                                        {node.source_document_id && (
                                                            <span className="flex items-center hover:text-violet-600 cursor-pointer transition-colors">
                                                                <ExternalLink className="h-3 w-3 mr-0.5" /> Source
                                                            </span>
                                                        )}
                                                    </div>
                                                </div>
                                            </CardContent>
                                        </Card>
                                    ))}
                                </div>
                            </div>
                        ))
                    )}
                </div>
            </ScrollArea>
        </div>
    );
}
