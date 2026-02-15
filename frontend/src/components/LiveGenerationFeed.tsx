import { useEffect, useRef, useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from './ui/card';
import { Badge } from './ui/badge';

import { Loader2, CheckCircle, Brain, User, Target, Activity, FileText } from 'lucide-react';
import clsx from 'clsx';

interface LogEntry {
    timestamp: string;
    message: string;
    type: 'info' | 'success' | 'warning' | 'error';
    step?: string;
}

interface PartialResult {
    demographics?: any;
    psychographics?: any;
    behavioral?: any;
    citations?: Array<{
        step: string;
        filename: string;
        quote: string;
    }>;
}

interface LiveGenerationFeedProps {
    isVisible: boolean;
    brandId: number;
    segmentName: string;
    segmentDescription: string;
    onComplete: (persona: any) => void;
    onError: (error: string) => void;
}

export function LiveGenerationFeed({
    isVisible,
    brandId,
    segmentName,
    segmentDescription,
    onComplete,
    onError
}: LiveGenerationFeedProps) {
    const [logs, setLogs] = useState<LogEntry[]>([]);
    const [currentStep, setCurrentStep] = useState<string>('initializing');
    const [partialData, setPartialData] = useState<PartialResult>({});
    const [progress, setProgress] = useState(0);
    const eventSourceRef = useRef<EventSource | null>(null);
    const scrollRef = useRef<HTMLDivElement>(null);

    const steps = [
        { id: 'initializing', label: 'Initializing', icon: Brain },
        { id: 'demographics', label: 'Demographics Scan', icon: User },
        { id: 'psychographics', label: 'Psychographics Map', icon: Target },
        { id: 'behavioral', label: 'Behavioral Analysis', icon: Activity },
        { id: 'synthesizing', label: 'Final Synthesis', icon: CheckCircle },
    ];

    useEffect(() => {
        if (!isVisible) return;

        // Reset state
        setLogs([]);
        setPartialData({});
        setProgress(0);
        setCurrentStep('initializing');

        // Connect to SSE endpoint
        const baseUrl = (import.meta as any).env?.VITE_API_URL || 'http://localhost:8000';
        const url = new URL(`${baseUrl}/api/personas/stream-generation`);
        url.searchParams.append('brand_id', brandId.toString());
        url.searchParams.append('segment_name', segmentName);
        url.searchParams.append('segment_description', segmentDescription);

        const es = new EventSource(url.toString());
        eventSourceRef.current = es;

        es.onopen = () => {
            addLog('Connection established. Starting research agent...', 'info', 'initializing');
        };

        es.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);

                if (data.type === 'log') {
                    addLog(data.message, 'info', data.step);
                } else if (data.type === 'progress') {
                    setCurrentStep(data.step);
                    setProgress(data.percentage);
                    addLog(`Step started: ${data.step}`, 'info', data.step);
                } else if (data.type === 'partial_result') {
                    setPartialData(prev => ({ ...prev, ...data.data }));
                    addLog(`Insight extracted: ${Object.keys(data.data)[0]}`, 'success', currentStep);
                } else if (data.type === 'citations') {
                    const newCitations = data.data.map((c: any) => ({ ...c, step: data.step }));
                    setPartialData(prev => ({
                        ...prev,
                        citations: [...(prev.citations || []), ...newCitations]
                    }));
                    addLog(`Verified ${newCitations.length} sources for ${data.step}`, 'success', currentStep);
                } else if (data.type === 'complete') {
                    addLog("Generation complete!", "success", "synthesizing");
                    es.close();
                    onComplete(data.persona);
                } else if (data.type === 'error') {
                    addLog(`Error: ${data.message}`, "error");
                    es.close();
                    onError(data.message);
                }
            } catch (err) {
                console.error('Failed to parse SSE event:', err);
            }
        };

        es.onerror = (err) => {
            console.error("SSE Error:", err);
            es.close();
            // Trigger error so UI doesn't silently freeze
            onError('Connection lost during persona generation. Please try again.');
        };

        return () => {
            if (eventSourceRef.current) {
                eventSourceRef.current.close();
            }
        };
    }, [isVisible, brandId, segmentName]);

    // Auto-scroll logs
    useEffect(() => {
        if (scrollRef.current) {
            scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
        }
    }, [logs]);

    const addLog = (message: string, type: LogEntry['type'] = 'info', step?: string) => {
        setLogs(prev => [...prev, {
            timestamp: new Date().toLocaleTimeString(),
            message,
            type,
            step
        }]);
    };

    if (!isVisible) return null;

    return (
        <Card className="w-full border-violet-500/20 shadow-lg animate-in fade-in slide-in-from-top-4 duration-300 overflow-hidden mb-8">
            <CardHeader className="bg-muted/50 border-b pb-4">
                <div className="flex items-center justify-between">
                    <CardTitle className="flex items-center gap-2 text-xl">
                        <Brain className="h-6 w-6 text-violet-600 animate-pulse" />
                        Research Agent Active
                        <Badge variant="outline" className="ml-2 font-normal text-muted-foreground whitespace-nowrap">
                            Building "{segmentName}"
                        </Badge>
                    </CardTitle>
                    <div className="text-sm font-medium text-violet-600">
                        {Math.round(progress)}% Complete
                    </div>
                </div>

                {/* Stepper */}
                <div className="flex items-center justify-between mt-6 px-2 relative">
                    {/* Progress Bar Background */}
                    <div className="absolute left-0 top-1/2 w-full h-1 bg-gray-200 -z-10 rounded-full" />
                    {/* Active Progress Bar */}
                    <div
                        className="absolute left-0 top-1/2 h-1 bg-violet-600 -z-10 rounded-full transition-all duration-500"
                        style={{ width: `${progress}%` }}
                    />

                    {steps.map((step, idx) => {
                        const isActive = step.id === currentStep;
                        const isCompleted = steps.findIndex(s => s.id === currentStep) > idx;
                        const Icon = step.icon;

                        return (
                            <div key={step.id} className="flex flex-col items-center gap-2 bg-background px-2">
                                <div className={clsx(
                                    "w-10 h-10 rounded-full flex items-center justify-center border-2 transition-all duration-300",
                                    isActive ? "border-violet-600 bg-violet-50 text-violet-600 scale-110 shadow-sm" :
                                        isCompleted ? "border-green-500 bg-green-50 text-green-600" :
                                            "border-gray-200 text-gray-400"
                                )}>
                                    {isCompleted ? <CheckCircle className="h-5 w-5" /> : <Icon className="h-5 w-5" />}
                                </div>
                                <span className={clsx(
                                    "text-xs font-medium transition-colors",
                                    isActive ? "text-violet-700" :
                                        isCompleted ? "text-green-600" : "text-gray-400"
                                )}>
                                    {step.label}
                                </span>
                            </div>
                        );
                    })}
                </div>
            </CardHeader>

            <CardContent className="h-[400px] overflow-hidden p-0 flex">
                {/* Left: Terminal / Logs */}
                <div className="w-1/2 border-r flex flex-col bg-black/95 text-green-400 font-mono text-xs p-4">
                    <div className="flex items-center gap-2 mb-2 text-gray-400 uppercase tracking-wider text-[10px] border-b border-gray-800 pb-2">
                        <Activity className="h-3 w-3" /> Agent Activity Log
                    </div>
                    <div className="flex-1 overflow-y-auto space-y-1.5 scrollbar-thin scrollbar-thumb-gray-800" ref={scrollRef}>
                        {logs.map((log, i) => (
                            <div key={i} className="flex gap-2 animate-in fade-in slide-in-from-left-2">
                                <span className="text-gray-600 shrink-0">[{log.timestamp}]</span>
                                <span className={clsx(
                                    log.type === 'error' ? 'text-red-400' :
                                        log.type === 'success' ? 'text-green-400' :
                                            'text-gray-300'
                                )}>
                                    {log.type === 'info' && '> '}
                                    {log.message}
                                </span>
                            </div>
                        ))}
                        {currentStep !== 'synthesizing' && (
                            <div className="flex gap-2">
                                <span className="text-gray-600 shrink-0">[{new Date().toLocaleTimeString()}]</span>
                                <span className="animate-pulse">_</span>
                            </div>
                        )}
                    </div>
                </div>

                {/* Right: Partial Results Preview */}
                <div className="w-1/2 p-4 bg-slate-50 overflow-y-auto">
                    <div className="text-sm font-semibold text-gray-500 mb-4 uppercase tracking-wider flex items-center gap-2">
                        <Activity className="h-4 w-4" /> Live Insights
                    </div>

                    <div className="space-y-4">
                        {/* Demographics Card */}
                        {partialData.demographics && (
                            <div className="bg-white p-3 rounded-lg shadow-sm border border-l-4 border-l-blue-500 animate-in fade-in slide-in-from-bottom-4">
                                <div className="flex items-center gap-2 text-blue-700 font-medium mb-2">
                                    <User className="h-4 w-4" /> Demographics
                                </div>
                                <div className="grid grid-cols-2 gap-2 text-sm">
                                    <div><span className="text-gray-500">Age:</span> {partialData.demographics.age || 'N/A'}</div>
                                    <div><span className="text-gray-500">Gender:</span> {partialData.demographics.gender || 'N/A'}</div>
                                    <div className="col-span-2"><span className="text-gray-500">Occupation:</span> {partialData.demographics.occupation || 'N/A'}</div>
                                </div>
                            </div>
                        )}

                        {/* Psychographics Card */}
                        {partialData.psychographics && (
                            <div className="bg-white p-3 rounded-lg shadow-sm border border-l-4 border-l-purple-500 animate-in fade-in slide-in-from-bottom-4">
                                <div className="flex items-center gap-2 text-purple-700 font-medium mb-2">
                                    <Target className="h-4 w-4" /> Psychographics
                                </div>
                                <div className="space-y-2 text-sm">
                                    <div>
                                        <div className="text-gray-500 text-xs mb-1">Motivations</div>
                                        <div className="flex flex-wrap gap-1">
                                            {(partialData.psychographics.motivations || []).slice(0, 2).map((m: string, i: number) => (
                                                <Badge key={i} variant="secondary" className="text-[10px]">{m}</Badge>
                                            ))}
                                        </div>
                                    </div>
                                    <div>
                                        <div className="text-gray-500 text-xs mb-1">Core Belief</div>
                                        <div className="italic text-gray-600 text-xs line-clamp-2">
                                            "{(partialData.psychographics.beliefs || [])[0]}"
                                        </div>
                                    </div>
                                </div>
                            </div>
                        )}

                        {/* Behavioral Card */}
                        {partialData.behavioral && (
                            <div className="bg-white p-3 rounded-lg shadow-sm border border-l-4 border-l-amber-500 animate-in fade-in slide-in-from-bottom-4">
                                <div className="flex items-center gap-2 text-amber-700 font-medium mb-2">
                                    <Activity className="h-4 w-4" /> Behavioral
                                </div>
                                <div className="text-sm text-gray-600">
                                    {(partialData.behavioral.adoption_curve || 'Adoption pattern analyzed.')}
                                </div>
                            </div>
                        )}

                        {/* Citations / Sources Card */}
                        {partialData.citations && partialData.citations.length > 0 && (
                            <div className="bg-white p-3 rounded-lg shadow-sm border border-l-4 border-l-emerald-500 animate-in fade-in slide-in-from-bottom-4">
                                <div className="flex items-center gap-2 text-emerald-700 font-medium mb-2">
                                    <FileText className="h-4 w-4" /> Validated Sources
                                </div>
                                <div className="space-y-2 max-h-40 overflow-y-auto pr-1">
                                    {partialData.citations.slice(0, 5).map((cit, idx) => (
                                        <div key={idx} className="text-xs border-b border-gray-100 last:border-0 pb-1">
                                            <div className="font-medium text-gray-700 truncate">{cit.filename}</div>
                                            {cit.quote && (
                                                <div className="text-gray-500 italic mt-0.5 line-clamp-2">
                                                    "{cit.quote}"
                                                </div>
                                            )}
                                            <div className="text-[10px] text-gray-400 mt-0.5 uppercase tracking-wide">
                                                Used for: {cit.step}
                                            </div>
                                        </div>
                                    ))}
                                    {partialData.citations.length > 5 && (
                                        <div className="text-xs text-center text-gray-500 pt-1">
                                            + {partialData.citations.length - 5} more citations
                                        </div>
                                    )}
                                </div>
                            </div>
                        )}

                        {Object.keys(partialData).length === 0 && (
                            <div className="flex flex-col items-center justify-center h-40 text-gray-400 text-center">
                                <Loader2 className="h-8 w-8 animate-spin mb-2 opacity-20" />
                                <p className="text-sm">Researching documents...</p>
                            </div>
                        )}
                    </div>
                </div>
            </CardContent>
        </Card>
    );
}
