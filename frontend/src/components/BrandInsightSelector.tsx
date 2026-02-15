"use client";

import React, { useEffect, useMemo, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Select, SelectTrigger, SelectContent, SelectItem, SelectValue } from "@/components/ui/select";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Loader2, Sparkles, RefreshCcw } from "lucide-react";
import { useToast } from "@/components/ui/use-toast";
import { BrandsAPI } from "@/lib/api";
import type { BrandContextResponse, BrandSuggestionResponse, BrandInsight as ApiBrandInsight } from "@/lib/api";
import { cn } from "@/lib/utils";

export type BrandInsight = ApiBrandInsight;

interface Brand {
  id: number;
  name: string;
}

type InsightResponse = BrandContextResponse;
export type SuggestionResponse = BrandSuggestionResponse;

export interface BrandInsightSelectorProps {
  selectionLimit?: number;
  defaultSegment?: string;
  disabled?: boolean;
  onSelectionChange?: (insights: BrandInsight[]) => void;
  onSuggestions?: (suggestions: SuggestionResponse) => void;
  onBrandChange?: (brandId: number | null) => void;
  onTargetSegmentChange?: (segment: string) => void;
  brands?: Brand[];
  className?: string;
}

const emptyInsights: InsightResponse = {
  brand_id: 0,
  brand_name: "",
  motivations: [],
  beliefs: [],
  tensions: [],
};

export const BrandInsightSelector: React.FC<BrandInsightSelectorProps> = ({
  selectionLimit = 6,
  defaultSegment = "",
  disabled = false,
  onSelectionChange,
  onSuggestions,
  onBrandChange,
  onTargetSegmentChange,
  brands: initialBrands,
  className,
}) => {
  const { toast } = useToast();
  const [brands, setBrands] = useState<Brand[]>(initialBrands || []);
  const [selectedBrandId, setSelectedBrandId] = useState<string>("");
  const [targetSegment, setTargetSegment] = useState(defaultSegment);
  const [contextData, setContextData] = useState<InsightResponse>(emptyInsights);
  const [suggestions, setSuggestions] = useState<SuggestionResponse | null>(null);
  const [selectedInsights, setSelectedInsights] = useState<BrandInsight[]>([]);
  const [loadingContext, setLoadingContext] = useState(false);
  const [loadingSuggestions, setLoadingSuggestions] = useState(false);

  useEffect(() => {
    if (initialBrands && initialBrands.length > 0) {
      setBrands(initialBrands);
      if (!selectedBrandId) {
        setSelectedBrandId(String(initialBrands[0].id));
      }
      return;
    }

    const fetchBrands = async () => {
      try {
        const data = await BrandsAPI.list();
        setBrands(data);
        setSelectedBrandId((current) => {
          if (data.length && !current) {
            return String(data[0].id);
          }
          return current;
        });
      } catch (error) {
        console.error("Failed to fetch brands", error);
        toast({
          title: "Unable to fetch brands",
          description: "Please check the backend service.",
          variant: "destructive",
        });
      }
    };
    fetchBrands();
  }, [initialBrands]);

  useEffect(() => {
    onSelectionChange?.(selectedInsights);
  }, [selectedInsights, onSelectionChange]);

  useEffect(() => {
    onBrandChange?.(selectedBrandId ? Number(selectedBrandId) : null);
  }, [selectedBrandId, onBrandChange]);

  useEffect(() => {
    onTargetSegmentChange?.(targetSegment);
  }, [targetSegment, onTargetSegmentChange]);

  const hasContext = useMemo(() => {
    return (
      contextData.motivations.length > 0 ||
      contextData.beliefs.length > 0 ||
      contextData.tensions.length > 0
    );
  }, [contextData]);

  const handleLoadContext = async () => {
    if (!selectedBrandId) return;
    setLoadingContext(true);
    try {
      const data = await BrandsAPI.getContext(Number(selectedBrandId), targetSegment ? { target_segment: targetSegment } : undefined);
      setContextData(data);
      toast({
        title: "Brand insights ready",
        description: `Loaded MBT insights for ${data.brand_name}.`,
      });
    } catch (error: any) {
      console.error("Context load error", error);
      toast({
        title: "Failed to load insights",
        description: error?.response?.data?.detail || "Try again later.",
        variant: "destructive",
      });
    } finally {
      setLoadingContext(false);
    }
  };

  const handleLoadSuggestions = async () => {
    if (!selectedBrandId) return;
    setLoadingSuggestions(true);
    try {
      const data = await BrandsAPI.getSuggestions(Number(selectedBrandId), {
        target_segment: targetSegment || undefined,
        persona_type: "Patient",
      });
      setSuggestions(data);
      onSuggestions?.(data);
      toast({
        title: "Suggestions generated",
        description: "Use these to guide manual persona creation.",
      });
    } catch (error: any) {
      console.error("Suggestion load error", error);
      toast({
        title: "Failed to generate suggestions",
        description: error?.response?.data?.detail || "Try again later.",
        variant: "destructive",
      });
    } finally {
      setLoadingSuggestions(false);
    }
  };

  const toggleInsight = (insight: BrandInsight) => {
    setSelectedInsights((prev) => {
      const exists = prev.find((i) => i.text === insight.text && i.type === insight.type);
      if (exists) {
        return prev.filter((i) => !(i.text === insight.text && i.type === insight.type));
      }
      if (prev.length >= selectionLimit) {
        toast({
          title: "Selection limit reached",
          description: `You can only select up to ${selectionLimit} insights.`,
        });
        return prev;
      }
      return [...prev, insight];
    });
  };

  const clearSelections = () => {
    setSelectedInsights([]);
  };

  const insightGroup = (label: string, items: BrandInsight[]) => (
    <div>
      <div className="flex items-center justify-between mb-2">
        <p className="font-semibold text-sm">{label}</p>
        <span className="text-xs text-muted-foreground">{items.length} available</span>
      </div>
      <div className="flex flex-wrap gap-2">
        {items.length === 0 && (
          <p className="text-xs text-muted-foreground">No items yet.</p>
        )}
        {items.map((insight, idx) => {
          const isSelected = selectedInsights.some(
            (i) => i.text === insight.text && i.type === insight.type
          );
          return (
            <Badge
              key={`${insight.type}-${idx}`}
              variant={isSelected ? "default" : "outline"}
              className={cn(
                "cursor-pointer whitespace-normal py-2 px-3 text-left leading-snug",
                isSelected && "bg-primary text-primary-foreground"
              )}
              onClick={() => toggleInsight(insight)}
            >
              <span className="block text-xs uppercase tracking-wide opacity-80">
                {insight.type}
              </span>
              <span className="text-sm font-medium">{insight.text}</span>
              {insight.segment && (
                <span className="block text-[11px] opacity-70 mt-1">Segment: {insight.segment}</span>
              )}
            </Badge>
          );
        })}
      </div>
    </div>
  );

  return (
    <Card className={cn("border-dashed", className)}>
      <CardHeader>
        <CardTitle className="text-lg">Brand Insight Selector</CardTitle>
        <CardDescription>Ground personas with MBT-aligned brand knowledge.</CardDescription>
      </CardHeader>
      <CardContent className="space-y-6">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          <Select value={selectedBrandId} onValueChange={setSelectedBrandId} disabled={disabled}>
            <SelectTrigger className="w-full">
              <SelectValue placeholder="Select brand" />
            </SelectTrigger>
            <SelectContent>
              {brands.map((brand) => (
                <SelectItem key={brand.id} value={String(brand.id)}>
                  {brand.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>

          <Input
            value={targetSegment}
            onChange={(e) => setTargetSegment(e.target.value)}
            placeholder="Target segment (optional)"
            disabled={disabled}
          />

          <div className="flex gap-2">
            <Button
              variant="outline"
              className="flex-1"
              onClick={handleLoadContext}
              disabled={disabled || !selectedBrandId || loadingContext}
            >
              {loadingContext ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : <RefreshCcw className="h-4 w-4 mr-2" />}
              Load Insights
            </Button>
            <Button
              className="flex-1"
              onClick={handleLoadSuggestions}
              disabled={disabled || !selectedBrandId || loadingSuggestions}
            >
              {loadingSuggestions ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : <Sparkles className="h-4 w-4 mr-2" />}
              Get Suggestions
            </Button>
          </div>
        </div>

        <ScrollArea className="h-[280px] pr-4">
          {hasContext ? (
            <div className="space-y-5">
              {insightGroup("Motivations", contextData.motivations)}
              {insightGroup("Beliefs", contextData.beliefs)}
              {insightGroup("Tensions", contextData.tensions)}
            </div>
          ) : (
            <div className="text-sm text-muted-foreground py-8 text-center">
              Load a brand to view curated insights.
            </div>
          )}
        </ScrollArea>

        <div className="rounded-lg border p-4 space-y-3">
          <div className="flex items-center justify-between">
            <p className="text-sm font-semibold">Selected Insights</p>
            <Button variant="ghost" size="sm" onClick={clearSelections} disabled={!selectedInsights.length}>
              Clear
            </Button>
          </div>
          {selectedInsights.length === 0 ? (
            <p className="text-xs text-muted-foreground">Select up to {selectionLimit} insights.</p>
          ) : (
            <div className="flex flex-wrap gap-2">
              {selectedInsights.map((insight, idx) => (
                <Badge key={`${insight.type}-${idx}`} variant="secondary">
                  {insight.type}: {insight.text}
                </Badge>
              ))}
            </div>
          )}
        </div>

        {suggestions && (
          <div className="rounded-lg border border-primary/30 bg-primary/5 p-4 space-y-3">
            <p className="text-sm font-semibold flex items-center gap-2">
              <Sparkles className="h-4 w-4 text-primary" /> Suggested talking points
            </p>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 text-sm">
              <div>
                <p className="font-medium mb-1">Motivations</p>
                <ul className="list-disc list-inside space-y-1 text-muted-foreground">
                  {suggestions.motivations.map((item, idx) => (
                    <li key={`mot-${idx}`}>{item}</li>
                  ))}
                </ul>
              </div>
              <div>
                <p className="font-medium mb-1">Beliefs</p>
                <ul className="list-disc list-inside space-y-1 text-muted-foreground">
                  {suggestions.beliefs.map((item, idx) => (
                    <li key={`bel-${idx}`}>{item}</li>
                  ))}
                </ul>
              </div>
              <div>
                <p className="font-medium mb-1">Tensions</p>
                <ul className="list-disc list-inside space-y-1 text-muted-foreground">
                  {suggestions.tensions.map((item, idx) => (
                    <li key={`ten-${idx}`}>{item}</li>
                  ))}
                </ul>
              </div>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
};

export default BrandInsightSelector;

