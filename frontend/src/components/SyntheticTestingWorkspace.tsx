import React, { useState, useMemo, useRef } from 'react';
import { useToast } from "@/components/ui/use-toast";
import {
    Upload, X, PlayCircle, Loader2, Gauge,
    BarChart3, AlertCircle, CheckCircle2,
    Edit2, Save, FolderOpen
} from 'lucide-react';
import {
    ScatterChart, Scatter, XAxis, YAxis, CartesianGrid,
    Tooltip, ResponsiveContainer, ZAxis, Cell
} from 'recharts';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { Separator } from '@/components/ui/separator';
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Select, SelectTrigger, SelectValue, SelectContent, SelectItem } from "@/components/ui/select";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogTrigger } from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { ScrollArea } from '@/components/ui/scroll-area';
import {
    SyntheticTestingAPI,
    type SyntheticTestingResponse,
    type SyntheticTestRun
} from '@/lib/api';
import { ComparativeAnalysisTable } from './ComparativeAnalysisTable';

interface Asset {
    id: string;
    name: string;
    file?: File;
    preview?: string;
    text?: string;
}

interface SyntheticTestingWorkspaceProps {
    selectedPersonaIds: number[];
    allPersonas?: any[]; // Full persona objects (Unused)
}

export function SyntheticTestingWorkspace({
    selectedPersonaIds
}: SyntheticTestingWorkspaceProps) {
    const [assets, setAssets] = useState<Asset[]>([]);
    const [isAnalyzing, setIsAnalyzing] = useState(false);
    const [results, setResults] = useState<SyntheticTestingResponse | null>(null);
    const { toast } = useToast();
    const fileInputRef = useRef<HTMLInputElement>(null);

    // Persistence State
    const [savedRuns, setSavedRuns] = useState<SyntheticTestRun[]>([]);
    const [saveDialogOpen, setSaveDialogOpen] = useState(false);
    const [runName, setRunName] = useState("");
    const [showHistory, setShowHistory] = useState(false);

    // Load history on mount
    React.useEffect(() => {
        loadHistory();
    }, []);

    const loadHistory = async () => {
        try {
            const runs = await SyntheticTestingAPI.listRuns();
            setSavedRuns(runs);
        } catch (e) {
            console.error("Failed to load history", e);
        }
    };

    const handleSaveRun = async () => {
        if (!runName.trim() || !results) return;
        try {
            // Reconstruct asset payload for saving (we might need full base64 if we want to restore exact state)
            // Ideally backend stores the base64. 
            // For now, we rely on the fact that assets state has the preview.

            // Map current assets to a persistable format
            const assetsPayload = assets.map(a => ({
                id: a.id,
                name: a.name,
                preview: a.preview // This is the dataURL
            }));

            await SyntheticTestingAPI.saveRun({
                name: runName,
                persona_ids: selectedPersonaIds,
                assets: assetsPayload,
                results: results
            });

            setSaveDialogOpen(false);
            setRunName("");
            loadHistory();
            toast({
                title: "Run Saved",
                description: "Test run saved successfully.",
            });
        } catch (e) {
            console.error("Failed to save run", e);
            toast({
                title: "Save Failed",
                description: "Failed to save test run.",
                variant: "destructive"
            });
        }
    };

    const loadRun = (run: SyntheticTestRun) => {
        // Restore results
        setResults(run.results);
        // Restore assets (if possible to recreate files? No, just previews)
        // We will create "Asset" objects but without the File object, just preview.
        // The workspace handles this fine as long as we don't try to re-upload.
        const restoredAssets: Asset[] = run.assets.map(a => ({
            id: a.id,
            name: a.name,
            preview: a.preview,
            // file object is lost, but that's ok for viewing results
        }));
        setAssets(restoredAssets);
        setShowHistory(false);
    };

    // Charts State
    const [xAxisMetric, setXAxisMetric] = useState<string>('stopping_power');
    const [yAxisMetric, setYAxisMetric] = useState<string>('motivation_to_prescribe');

    // Helpers
    const generateId = () => Math.random().toString(36).substring(2, 9);

    const handleFileUpload = (files: FileList | null) => {
        if (!files) return;

        const remainingSlots = 3 - assets.length;
        const filesToProcess = Array.from(files).slice(0, remainingSlots);

        if (filesToProcess.length === 0) {
            toast({
                title: "Limit Reached",
                description: "Maximum 3 assets allowed.",
                variant: "destructive"
            });
            return;
        }

        filesToProcess.forEach(file => {
            if (file.type.startsWith('image/')) {
                const reader = new FileReader();
                reader.onload = (e) => {
                    setAssets(prev => [...prev, {
                        id: generateId(),
                        name: file.name.split('.')[0].substring(0, 20),
                        file: file,
                        preview: e.target?.result as string
                    }]);
                };
                reader.readAsDataURL(file);
            }
        });
    };

    const removeAsset = (id: string) => {
        setAssets(prev => prev.filter(a => a.id !== id));
        // Clear results if assets change to avoid mismatch
        setResults(null);
    };

    const updateAssetName = (id: string, newName: string) => {
        setAssets(prev => prev.map(a => a.id === id ? { ...a, name: newName } : a));
    };

    const handleAnalyze = async () => {
        if (assets.length === 0 || selectedPersonaIds.length === 0) return;

        setIsAnalyzing(true);
        setResults(null);

        try {
            // Prepare payload
            const assetPayload = await Promise.all(assets.map(async (asset) => {
                let imageData = undefined;
                if (asset.file) {
                    imageData = await new Promise<string>((resolve) => {
                        const reader = new FileReader();
                        reader.onload = () => resolve((reader.result as string).split(',')[1]);
                        reader.readAsDataURL(asset.file!);
                    });
                }

                return {
                    id: asset.id,
                    name: asset.name,
                    image_data: imageData,
                    text_content: asset.text || ""
                };
            }));

            const response = await SyntheticTestingAPI.analyze(selectedPersonaIds, assetPayload);
            setResults(response);
        } catch (error) {
            console.error("Analysis failed:", error);
            toast({
                title: "Analysis Failed",
                description: "Analysis failed. See console for details.",
                variant: "destructive"
            });
        } finally {
            setIsAnalyzing(false);
        }
    };

    // --- Rendering Helpers ---

    const getMetricColor = (score: number) => {
        if (score >= 6) return 'bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-300';
        if (score >= 4) return 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-300';
        return 'bg-orange-100 text-orange-800 dark:bg-orange-900/30 dark:text-orange-300';
    };

    // Prepare chart data
    // One bubble per asset per persona? Or aggregated?
    // Request was: "X-Y axis graph. The specific default metrics... are customizable"
    // Usually this graph plots ASSETS as points, aggregated across personas.
    // Bubble size = Preference Score.

    const CustomScatterShape = (props: any) => {
        const { cx, cy, payload } = props;
        const imageSize = 40; // Size of image

        // Find asset to get preview
        // The payload name is the asset name. 
        // We might have duplicates if names are same, but id logic is cleaner. 
        // Let's rely on name for now as per chartData construction.
        const asset = assets.find(a => a.name === payload.name);

        if (asset?.preview) {
            return (
                <svg x={cx - imageSize / 2} y={cy - imageSize / 2} width={imageSize} height={imageSize} className="overflow-visible">
                    <defs>
                        <clipPath id={`circleView-${payload.name}`}>
                            <circle cx={imageSize / 2} cy={imageSize / 2} r={imageSize / 2} />
                        </clipPath>
                    </defs>
                    <circle cx={imageSize / 2} cy={imageSize / 2} r={imageSize / 2 + 2} fill={props.fill} opacity={0.8} />
                    <image
                        width={imageSize}
                        height={imageSize}
                        href={asset.preview}
                        clipPath={`url(#circleView-${payload.name})`}
                        preserveAspectRatio="xMidYMid slice"
                    />
                </svg>
            );
        }

        return <circle cx={cx} cy={cy} r={6} fill={props.fill} />;
    };

    const chartData = useMemo(() => {
        if (!results) return [];

        // We want to plot each ASSET.
        // X = Average Metric A
        // Y = Average Metric B
        // Size = Avg Preference
        // Tag = Asset Name

        return Object.values(results.aggregated).map(agg => ({
            name: agg.asset_name,
            x: agg.average_scores[xAxisMetric] || 0,
            y: agg.average_scores[yAxisMetric] || 0,
            size: agg.average_preference, // 0-100
            respondents: agg.respondent_count
        }));
    }, [results, xAxisMetric, yAxisMetric]);

    const METRIC_OPTIONS = [
        { value: 'motivation_to_prescribe', label: 'Motivation to Prescribe' },
        { value: 'connection_to_story', label: 'Connection to Story' },
        { value: 'differentiation', label: 'Differentiation' },
        { value: 'believability', label: 'Believability' },
        { value: 'stopping_power', label: 'Stopping Power' },
    ];

    const getMetricLabel = (key: string) => METRIC_OPTIONS.find(m => m.value === key)?.label || key;

    return (
        <div className="flex h-full w-full bg-slate-50 dark:bg-slate-950">
            {/* LEFT: Config & Assets */}
            <aside className="w-[350px] border-r bg-white dark:bg-gray-900 flex flex-col shrink-0">
                <div className="p-4 border-b space-y-4">
                    <div className="space-y-1">
                        <h2 className="font-semibold text-lg flex items-center gap-2">
                            <Gauge className="h-5 w-5 text-violet-600" />
                            Synthetic Testing
                        </h2>
                        <p className="text-xs text-muted-foreground">
                            Objective 1-7 scoring & competitive benchmarking
                        </p>
                    </div>

                    <div className="flex items-center justify-between text-sm bg-violet-50 dark:bg-violet-900/20 p-2 rounded-md border border-violet-100 dark:border-violet-800">
                        <span className="font-medium text-violet-700 dark:text-violet-300">Target Panel</span>
                        <Badge variant="secondary">{selectedPersonaIds.length} Personas</Badge>
                    </div>
                </div>

                <ScrollArea className="flex-1 p-4">
                    <div className="space-y-6">
                        {/* Asset Upload */}
                        <div className="space-y-3">
                            <div className="flex items-center justify-between">
                                <label className="text-sm font-medium">Test Assets (Max 3)</label>
                                <span className="text-xs text-muted-foreground">{assets.length}/3</span>
                            </div>

                            <div className="grid gap-3">
                                {assets.map((asset) => (
                                    <div key={asset.id} className="relative group border rounded-lg p-2 bg-slate-50 dark:bg-slate-800 flex gap-3 items-center">
                                        <div className="h-12 w-12 shrink-0 bg-white rounded border overflow-hidden">
                                            {asset.preview ? (
                                                <img src={asset.preview} className="h-full w-full object-cover" alt="preview" />
                                            ) : (
                                                <div className="h-full w-full flex items-center justify-center text-xs bg-slate-100">TxT</div>
                                            )}
                                        </div>
                                        <div className="flex-1 min-w-0">
                                            <Input
                                                value={asset.name}
                                                onChange={(e) => updateAssetName(asset.id, e.target.value)}
                                                className="h-7 text-sm px-1 py-0 border-transparent hover:border-input focus:border-input bg-transparent"
                                            />
                                            <p className="text-[10px] text-muted-foreground px-1 truncate">
                                                {asset.file ? `${(asset.file.size / 1024).toFixed(0)}KB` : 'Text Only'}
                                            </p>
                                        </div>
                                        <button
                                            onClick={() => removeAsset(asset.id)}
                                            className="absolute top-1 right-1 p-1 hover:bg-slate-200 dark:hover:bg-slate-700 rounded-full opacity-0 group-hover:opacity-100 transition-opacity"
                                        >
                                            <X className="h-3 w-3 text-slate-500" />
                                        </button>
                                    </div>
                                ))}

                                {assets.length < 3 && (
                                    <div
                                        onClick={() => fileInputRef.current?.click()}
                                        className="border-2 border-dashed border-slate-200 dark:border-slate-700 rounded-lg p-4 text-center hover:bg-slate-50 dark:hover:bg-slate-800 cursor-pointer transition-colors"
                                    >
                                        <input
                                            ref={fileInputRef}
                                            id="syn-upload"
                                            type="file"
                                            accept="image/*"
                                            className="hidden"
                                            multiple
                                            onChange={(e) => handleFileUpload(e.target.files)}
                                        />
                                        <Upload className="h-5 w-5 mx-auto text-slate-400 mb-1" />
                                        <span className="text-xs font-medium text-slate-500">Add Concept</span>
                                    </div>
                                )}
                            </div>
                        </div>

                        <Button
                            className="w-full"
                            onClick={handleAnalyze}
                            disabled={isAnalyzing || assets.length === 0 || selectedPersonaIds.length === 0}
                        >
                            {isAnalyzing ? (
                                <>
                                    <Loader2 className="h-4 w-4 mr-2 animate-spin" /> Analyzing...
                                </>
                            ) : (
                                <>
                                    <PlayCircle className="h-4 w-4 mr-2" /> Run Test
                                </>
                            )}
                        </Button>

                        {/* Save & History Controls */}
                        <div className="flex gap-2 pt-2">
                            <Dialog open={saveDialogOpen} onOpenChange={setSaveDialogOpen}>
                                <DialogTrigger asChild>
                                    <Button variant="outline" className="flex-1" disabled={!results}>
                                        <Save className="h-4 w-4 mr-2" /> Save
                                    </Button>
                                </DialogTrigger>
                                <DialogContent>
                                    <DialogHeader>
                                        <DialogTitle>Save Test Run</DialogTitle>
                                    </DialogHeader>
                                    <div className="grid gap-4 py-4">
                                        <div className="grid grid-cols-4 items-center gap-4">
                                            <Label htmlFor="name" className="text-right">Name</Label>
                                            <Input id="name" value={runName} onChange={(e) => setRunName(e.target.value)} className="col-span-3" placeholder="e.g. Hiking Ad V1" />
                                        </div>
                                    </div>
                                    <DialogFooter>
                                        <Button onClick={handleSaveRun}>Save Run</Button>
                                    </DialogFooter>
                                </DialogContent>
                            </Dialog>

                            <Dialog open={showHistory} onOpenChange={setShowHistory}>
                                <DialogTrigger asChild>
                                    <Button variant="outline" className="flex-1">
                                        <FolderOpen className="h-4 w-4 mr-2" /> History
                                    </Button>
                                </DialogTrigger>
                                <DialogContent className="max-w-md">
                                    <DialogHeader>
                                        <DialogTitle>Saved Runs</DialogTitle>
                                    </DialogHeader>
                                    <ScrollArea className="h-[300px] pr-4">
                                        <div className="space-y-2">
                                            {savedRuns.length === 0 && <p className="text-sm text-muted-foreground text-center py-4">No saved runs yet.</p>}
                                            {savedRuns.map(run => (
                                                <div key={run.id} className="flex items-center justify-between p-3 border rounded-lg hover:bg-slate-50 dark:hover:bg-slate-800 cursor-pointer" onClick={() => loadRun(run)}>
                                                    <div>
                                                        <p className="font-medium text-sm">{run.name}</p>
                                                        <p className="text-xs text-muted-foreground">{new Date(run.created_at).toLocaleDateString()}</p>
                                                    </div>
                                                    <Badge variant="secondary">Load</Badge>
                                                </div>
                                            ))}
                                        </div>
                                    </ScrollArea>
                                </DialogContent>
                            </Dialog>
                        </div>
                    </div>
                </ScrollArea>
            </aside>

            {/* RIGHT: Results */}
            <main className="flex-1 overflow-auto p-6 space-y-8">
                {!results ? (
                    <div className="h-full flex flex-col items-center justify-center text-muted-foreground space-y-4">
                        <div className="p-4 bg-violet-50 dark:bg-violet-900/20 rounded-full">
                            <BarChart3 className="h-12 w-12 text-violet-300" />
                        </div>
                        <div className="text-center max-w-md">
                            <h3 className="font-semibold text-lg text-foreground">Ready to Test</h3>
                            <p className="text-sm mt-1">Upload up to 3 marketing concepts to get objective scoring (1-7) and competitive benchmarking against your personas.</p>
                        </div>
                    </div>
                ) : (
                    <div className="space-y-8 max-w-6xl mx-auto">

                        {/* 1. SCATTER CHART */}
                        <Card>
                            <CardHeader className="pb-2">
                                <div className="flex items-center justify-between">
                                    <CardTitle>Unmet Need vs. Performance</CardTitle>
                                    <div className="flex gap-2">
                                        <Select value={xAxisMetric} onValueChange={setXAxisMetric}>
                                            <SelectTrigger className="w-[180px] h-8 text-xs">
                                                <span className="text-muted-foreground mr-2">X:</span>
                                                <SelectValue />
                                            </SelectTrigger>
                                            <SelectContent>
                                                {METRIC_OPTIONS.map(m => <SelectItem key={m.value} value={m.value}>{m.label}</SelectItem>)}
                                            </SelectContent>
                                        </Select>
                                        <Select value={yAxisMetric} onValueChange={setYAxisMetric}>
                                            <SelectTrigger className="w-[180px] h-8 text-xs">
                                                <span className="text-muted-foreground mr-2">Y:</span>
                                                <SelectValue />
                                            </SelectTrigger>
                                            <SelectContent>
                                                {METRIC_OPTIONS.map(m => <SelectItem key={m.value} value={m.value}>{m.label}</SelectItem>)}
                                            </SelectContent>
                                        </Select>
                                    </div>
                                </div>
                                <CardDescription>
                                    Bubble size represents Overall Preference Score (%).
                                    Scale: 1 (Poor) to 7 (Excellent).
                                </CardDescription>
                            </CardHeader>
                            <CardContent className="h-[400px] w-full pt-4">
                                <ResponsiveContainer width="100%" height="100%">
                                    <ScatterChart margin={{ top: 20, right: 20, bottom: 60, left: 20 }}>
                                        <CartesianGrid strokeDasharray="3 3" opacity={0.6} />
                                        <XAxis
                                            type="number"
                                            dataKey="x"
                                            name={getMetricLabel(xAxisMetric)}
                                            domain={[1, 7]}
                                            ticks={[1, 2, 3, 4, 5, 6, 7]} // Explicit integer ticks
                                            label={{
                                                value: `X-Axis: ${getMetricLabel(xAxisMetric)}`,
                                                position: 'bottom',
                                                offset: 40,
                                                style: { fontWeight: 'bold', fontSize: '14px', fill: '#64748b' }
                                            }}
                                        />
                                        <YAxis
                                            type="number"
                                            dataKey="y"
                                            name={getMetricLabel(yAxisMetric)}
                                            domain={[1, 7]}
                                            ticks={[1, 2, 3, 4, 5, 6, 7]}
                                            label={{
                                                value: `Y-Axis: ${getMetricLabel(yAxisMetric)}`,
                                                angle: -90,
                                                position: 'insideLeft',
                                                offset: 10,
                                                style: { fontWeight: 'bold', fontSize: '14px', fill: '#64748b' }
                                            }}
                                        />
                                        <ZAxis type="number" dataKey="size" range={[400, 2000]} name="Preference" unit="%" />
                                        <Tooltip
                                            cursor={{ strokeDasharray: '3 3' }}
                                            content={({ active, payload }) => {
                                                if (active && payload && payload.length) {
                                                    const data = payload[0].payload;
                                                    return (
                                                        <div className="bg-white dark:bg-slate-900 border p-3 rounded shadow-lg text-sm">
                                                            <p className="font-bold mb-1">{data.name}</p>
                                                            <p>X ({getMetricLabel(xAxisMetric)}): {data.x}</p>
                                                            <p>Y ({getMetricLabel(yAxisMetric)}): {data.y}</p>
                                                            <p>Preference: {data.size}%</p>
                                                            <p className="text-xs text-muted-foreground mt-1">N={data.respondents}</p>
                                                        </div>
                                                    );
                                                }
                                                return null;
                                            }}
                                        />
                                        {/* Legend removed to avoid confusion with "Black Dot" */}
                                        <Scatter name="Assets" data={chartData} shape={<CustomScatterShape />}>
                                            {chartData.map((_, index) => (
                                                <Cell key={`cell-${index}`} fill={['#8884d8', '#82ca9d', '#ffc658'][index % 3]} />
                                            ))}
                                        </Scatter>
                                    </ScatterChart>
                                </ResponsiveContainer>
                            </CardContent>
                        </Card>

                        {/* 2. HEATMAP TABLE */}
                        <Card>
                            <CardHeader>
                                <CardTitle>Detailed Scoring Heatmap</CardTitle>
                                <CardDescription>Average scores per metric across all personas.</CardDescription>
                            </CardHeader>
                            <CardContent>
                                <div className="overflow-x-auto rounded-md border text-sm">
                                    <table className="w-full text-left">
                                        <thead className="bg-muted/50 text-muted-foreground font-medium">
                                            <tr>
                                                <th className="p-3">Asset</th>
                                                {METRIC_OPTIONS.map(m => (
                                                    <th key={m.value} className="p-3 text-center">{m.label}</th>
                                                ))}
                                                <th className="p-3 text-center font-bold text-foreground">Overall Pref.</th>
                                            </tr>
                                        </thead>
                                        <tbody>
                                            {Object.values(results.aggregated).map((agg, idx) => (
                                                <tr key={idx} className="border-t hover:bg-muted/10 transition-colors">
                                                    <td className="p-3 font-medium">{agg.asset_name}</td>
                                                    {METRIC_OPTIONS.map(m => {
                                                        const val = agg.average_scores[m.value];
                                                        return (
                                                            <td key={m.value} className="p-3 text-center">
                                                                <span className={`inline-block px-2.5 py-0.5 rounded-full font-semibold ${getMetricColor(val)}`}>
                                                                    {val}
                                                                </span>
                                                            </td>
                                                        );
                                                    })}
                                                    <td className="p-3 text-center">
                                                        <Badge variant="outline" className={`font-bold ${agg.average_preference >= 70 ? 'border-green-500 text-green-600 bg-green-50' :
                                                            agg.average_preference >= 40 ? 'border-yellow-500 text-yellow-600 bg-yellow-50' : ''
                                                            }`}>
                                                            {agg.average_preference}%
                                                        </Badge>
                                                    </td>
                                                </tr>
                                            ))}
                                        </tbody>
                                    </table>
                                </div>
                            </CardContent>
                        </Card>

                        {/* 3. QUALITATIVE COMPARISON */}
                        <Tabs defaultValue="comparative" className="w-full">
                            <TabsList className="grid w-full grid-cols-2 lg:w-[400px]">
                                <TabsTrigger value="comparative">Comparative View</TabsTrigger>
                                <TabsTrigger value="detailed">Detailed Breakdown</TabsTrigger>
                            </TabsList>
                            <TabsContent value="comparative" className="mt-4">
                                <ComparativeAnalysisTable results={results} assets={assets} />
                            </TabsContent>
                            <TabsContent value="detailed" className="mt-4">
                                <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                                    {results.results.map((res) => (
                                        <Card key={res.asset_id + res.persona_id} className="h-full flex flex-col">
                                            <CardHeader className="pb-3 bg-muted/10 border-b">
                                                <div className="flex justify-between items-start">
                                                    <div>
                                                        <div className="flex items-center gap-2 mb-1">
                                                            <Badge variant="outline">{res.persona_name}</Badge>
                                                            <span className="text-muted-foreground text-xs">evaluated</span>
                                                        </div>
                                                        <CardTitle className="text-base truncate" title={assets.find(a => a.id === res.asset_id)?.name}>
                                                            {assets.find(a => a.id === res.asset_id)?.name || 'Asset'}
                                                        </CardTitle>
                                                    </div>
                                                    <Badge className={getMetricColor(res.overall_preference_score / 14)}>
                                                        {res.overall_preference_score}% Pref
                                                    </Badge>
                                                </div>
                                            </CardHeader>
                                            <CardContent className="p-0 flex-1 flex flex-col">
                                                <div className="p-4 space-y-4">
                                                    <div>
                                                        <h4 className="text-xs font-bold uppercase tracking-wider text-green-700 dark:text-green-400 mb-2 flex items-center gap-1">
                                                            <CheckCircle2 className="h-3 w-3" /> Does Well
                                                        </h4>
                                                        <ul className="list-disc list-inside text-sm space-y-1 text-muted-foreground">
                                                            {res.feedback?.does_well?.slice(0, 3).map((pt, i) => <li key={i}>{pt}</li>)}
                                                        </ul>
                                                    </div>

                                                    <Separator />

                                                    <div>
                                                        <h4 className="text-xs font-bold uppercase tracking-wider text-red-700 dark:text-red-400 mb-2 flex items-center gap-1">
                                                            <AlertCircle className="h-3 w-3" /> Challenges
                                                        </h4>
                                                        <ul className="list-disc list-inside text-sm space-y-1 text-muted-foreground">
                                                            {res.feedback?.does_not_do_well?.slice(0, 3).map((pt, i) => <li key={i}>{pt}</li>)}
                                                        </ul>
                                                    </div>

                                                    <Separator />

                                                    <div>
                                                        <h4 className="text-xs font-bold uppercase tracking-wider text-blue-700 dark:text-blue-400 mb-2 flex items-center gap-1">
                                                            <Edit2 className="h-3 w-3" /> Considerations
                                                        </h4>
                                                        <ul className="list-disc list-inside text-sm space-y-1 text-muted-foreground">
                                                            {res.feedback?.considerations?.slice(0, 3).map((pt, i) => <li key={i}>{pt}</li>)}
                                                        </ul>
                                                    </div>
                                                </div>
                                            </CardContent>
                                        </Card>
                                    ))}
                                </div>
                            </TabsContent>
                        </Tabs>

                    </div>
                )
                }
            </main >
        </div >
    );
}
