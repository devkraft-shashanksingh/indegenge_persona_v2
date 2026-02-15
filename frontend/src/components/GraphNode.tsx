import { memo } from 'react';
import { Handle, Position } from 'reactflow';
import {
    Heart,
    Brain,
    Zap,
    Target,
    Shield,
    Activity,
    Stethoscope,
    TrendingUp,
    AlertTriangle,
    MessageSquare,
    Lightbulb,
    FileText,
    Users,
    Globe,
    Map
} from 'lucide-react';
import { cn } from '@/lib/utils';
import {
    Tooltip,
    TooltipContent,
    TooltipProvider,
    TooltipTrigger,
} from "@/components/ui/tooltip"

// Icon mapping
const NODE_ICONS: Record<string, any> = {
    // Patient
    patient_motivation: Target,
    patient_belief: Brain,
    patient_tension: Heart, // Emotional tension
    journey_insight: Map,

    // Disease
    epidemiology: Globe,
    symptom_burden: Activity,
    treatment_landscape: Stethoscope,
    unmet_need: AlertTriangle,

    // Brand
    key_message: MessageSquare,
    value_proposition: Zap,
    differentiator: Lightbulb,
    proof_point: Shield,

    // Market/HCP
    competitor_position: Users,
    market_barrier: TrendingUp, // Using trending up as barrier/trend
    prescribing_driver: FileText,

    // Default
    default: FileText
};

// Style mapping
const NODE_STYLES: Record<string, { bg: string; text: string; border: string; shadow: string }> = {
    // Brand - Purple
    key_message: { bg: 'bg-purple-100', text: 'text-purple-700', border: 'border-purple-200', shadow: 'shadow-purple-100' },
    value_proposition: { bg: 'bg-fuchsia-100', text: 'text-fuchsia-700', border: 'border-fuchsia-200', shadow: 'shadow-fuchsia-100' },
    differentiator: { bg: 'bg-violet-100', text: 'text-violet-700', border: 'border-violet-200', shadow: 'shadow-violet-100' },
    proof_point: { bg: 'bg-indigo-100', text: 'text-indigo-700', border: 'border-indigo-200', shadow: 'shadow-indigo-100' },

    // Disease - Blue
    epidemiology: { bg: 'bg-blue-100', text: 'text-blue-700', border: 'border-blue-200', shadow: 'shadow-blue-100' },
    symptom_burden: { bg: 'bg-sky-100', text: 'text-sky-700', border: 'border-sky-200', shadow: 'shadow-sky-100' },
    treatment_landscape: { bg: 'bg-cyan-100', text: 'text-cyan-700', border: 'border-cyan-200', shadow: 'shadow-cyan-100' },
    unmet_need: { bg: 'bg-amber-100', text: 'text-amber-700', border: 'border-amber-200', shadow: 'shadow-amber-100' },

    // Patient - Green/Rose
    patient_motivation: { bg: 'bg-emerald-100', text: 'text-emerald-700', border: 'border-emerald-200', shadow: 'shadow-emerald-100' },
    patient_belief: { bg: 'bg-green-100', text: 'text-green-700', border: 'border-green-200', shadow: 'shadow-green-100' },
    patient_tension: { bg: 'bg-rose-100', text: 'text-rose-700', border: 'border-rose-200', shadow: 'shadow-rose-100' },
    journey_insight: { bg: 'bg-yellow-100', text: 'text-yellow-700', border: 'border-yellow-200', shadow: 'shadow-yellow-100' },

    // Default
    default: { bg: 'bg-slate-100', text: 'text-slate-700', border: 'border-slate-200', shadow: 'shadow-slate-100' }
};

export default memo(({ data, selected, zoom }: { data: any; selected?: boolean, zoom?: number }) => {
    const Icon = NODE_ICONS[data.node_type] || NODE_ICONS.default;
    const style = NODE_STYLES[data.node_type] || NODE_STYLES.default;

    // Semantic Zoom Logic
    const currentZoom = zoom || 1;
    const showLabel = currentZoom > 0.8; // Only show hover label at higher zoom
    const showIcon = currentZoom > 0.4; // Show dot instead of icon at very low zoom

    // Truncate label for the tooltip preview if needed
    const label = data.label || data.text || "Unknown Node";

    return (
        <TooltipProvider>
            <Tooltip delayDuration={300}>
                <TooltipTrigger asChild>
                    <div className={cn(
                        "relative group transition-all duration-300",
                        selected ? "scale-125 z-50" : "scale-100 hover:scale-110 z-10"
                    )}>
                        {/* Handles (Invisible but functional) */}
                        <Handle type="target" position={Position.Top} className="!w-2 !h-2 !opacity-0" />
                        <Handle type="source" position={Position.Bottom} className="!w-2 !h-2 !opacity-0" />

                        {/* Main Icon Node */}
                        <div className={cn(
                            "rounded-full flex items-center justify-center border-2 shadow-sm transition-all",
                            showIcon ? "w-10 h-10" : "w-4 h-4",
                            style.bg,
                            style.border,
                            style.text,
                            selected ? `ring-2 ring-offset-2 ring-indigo-500 ${style.shadow}` : "hover:shadow-md"
                        )}>
                            {showIcon && <Icon className="w-5 h-5 stroke-[2.5px]" />}
                        </div>

                        {/* Status Indicator (Verified) */}
                        {data.verified && showIcon && (
                            <div className="absolute -top-1 -right-1 w-3 h-3 bg-emerald-500 rounded-full border-2 border-white" />
                        )}

                        {/* Label (Only visible on zoom or if configured) */}
                        {showLabel && (
                            <div className={cn(
                                "absolute top-full left-1/2 -translate-x-1/2 mt-1.5 px-2 py-0.5 rounded-full bg-white/90 border shadow-sm text-[10px] font-medium whitespace-nowrap opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none",
                                style.text
                            )}>
                                {data.node_type?.replace(/_/g, ' ')}
                            </div>
                        )}
                    </div>
                </TooltipTrigger>
                <TooltipContent side="right" className="max-w-xs p-3 glass-panel">
                    <div className="space-y-2">
                        <div className="flex items-center gap-2 border-b pb-2">
                            <Icon className={cn("w-4 h-4", style.text)} />
                            <span className="font-semibold capitalize text-xs text-muted-foreground">
                                {data.node_type?.replace(/_/g, ' ')}
                            </span>
                        </div>
                        <p className="text-sm font-medium leading-snug">
                            {label}
                        </p>
                        {data.segment && (
                            <div className="flex items-center gap-1.5 pt-1">
                                <div className="w-1 h-1 rounded-full bg-slate-400" />
                                <span className="text-xs text-muted-foreground">{data.segment}</span>
                            </div>
                        )}
                    </div>
                </TooltipContent>
            </Tooltip>
        </TooltipProvider>
    );
});
