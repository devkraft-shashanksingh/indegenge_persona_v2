import React, { useEffect, useState, useRef } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { PersonasAPI } from '@/lib/api';
import type { ComparisonInsights, ComparisonAnswer } from '@/lib/api';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible';
import { ScrollArea } from '@/components/ui/scroll-area';
import {
  ArrowLeft, Brain, Target, Shield, MessageSquare, Activity, AlertTriangle, AlertCircle,
  Sparkles, ChevronDown, ChevronUp, ThumbsUp, Send, Loader2,
  Lightbulb, GitCompare, Zap, Building, Briefcase
} from 'lucide-react';

interface ComparisonRowProps {
  label: string;
  icon?: React.ReactNode;
  data: (string | string[] | null | undefined)[];
  type?: 'text' | 'list' | 'badge';
  highlightLevel?: 'high' | 'medium' | 'low';
  similarityScore?: number;
}

const ComparisonRow = ({ label, icon, data, type = 'text', highlightLevel, similarityScore }: ComparisonRowProps) => {
  // Determine row styling based on highlight level
  const getRowStyles = () => {
    if (!highlightLevel) return '';
    switch (highlightLevel) {
      case 'high':
        return 'bg-red-50/50 dark:bg-red-950/20 border-l-4 border-l-red-400';
      case 'medium':
        return 'bg-amber-50/30 dark:bg-amber-950/10';
      case 'low':
        return 'opacity-70';
      default:
        return '';
    }
  };

  const getScoreBadge = () => {
    if (similarityScore === undefined) return null;
    const scorePercent = Math.round(similarityScore * 100);
    if (scorePercent >= 80) {
      return <Badge className="text-[10px] bg-green-100 text-green-700 border-0">Similar</Badge>;
    } else if (scorePercent >= 40) {
      return <Badge className="text-[10px] bg-amber-100 text-amber-700 border-0">Partial</Badge>;
    } else {
      return <Badge className="text-[10px] bg-red-100 text-red-700 border-0">Different</Badge>;
    }
  };

  return (
    <tr className={`border-b border-gray-100 dark:border-gray-800 last:border-0 hover:bg-slate-50/50 dark:hover:bg-slate-900/50 transition-colors ${getRowStyles()}`}>
      <td className="p-4 bg-gray-50/50 dark:bg-gray-900/50 font-medium text-sm text-gray-700 dark:text-gray-300 w-[200px] align-top">
        <div className="flex items-center gap-2">
          {icon}
          <span>{label}</span>
          {getScoreBadge()}
        </div>
      </td>
      {data.map((item, idx) => (
        <td key={idx} className="p-4 border-r border-gray-100 dark:border-gray-800 last:border-0 text-sm align-top">
          {type === 'list' && Array.isArray(item) ? (
            <ul className="list-disc list-inside space-y-1 text-gray-600 dark:text-gray-400">
              {item.slice(0, 3).map((li, i) => (
                <li key={i}>{li}</li>
              ))}
            </ul>
          ) : type === 'badge' ? (
            <Badge variant="outline">{item}</Badge>
          ) : (
            <span className="text-gray-700 dark:text-gray-300">{item || '-'}</span>
          )}
        </td>
      ))}
    </tr>
  );
};

// AI Insights Panel Component
const AIInsightsPanel = ({ insights, loading }: { insights: ComparisonInsights | null; loading: boolean }) => {
  const [isOpen, setIsOpen] = useState(true);

  if (loading) {
    return (
      <Card className="border-violet-200 dark:border-violet-800 bg-gradient-to-r from-violet-50 to-purple-50 dark:from-violet-950/30 dark:to-purple-950/30">
        <CardHeader className="pb-3">
          <CardTitle className="text-lg flex items-center gap-2">
            <Sparkles className="h-5 w-5 text-violet-600 animate-pulse" />
            AI Comparison Insights
            <Loader2 className="h-4 w-4 animate-spin ml-auto" />
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-3">
            <div className="h-4 bg-violet-200/50 rounded animate-pulse w-3/4" />
            <div className="h-4 bg-violet-200/50 rounded animate-pulse w-1/2" />
            <div className="h-4 bg-violet-200/50 rounded animate-pulse w-2/3" />
          </div>
        </CardContent>
      </Card>
    );
  }

  if (!insights) return null;

  return (
    <Collapsible open={isOpen} onOpenChange={setIsOpen}>
      <Card className="border-violet-200 dark:border-violet-800 bg-gradient-to-r from-violet-50 to-purple-50 dark:from-violet-950/30 dark:to-purple-950/30">
        <CollapsibleTrigger asChild>
          <CardHeader className="pb-3 cursor-pointer hover:bg-violet-100/50 dark:hover:bg-violet-900/30 rounded-t-lg transition-colors">
            <CardTitle className="text-lg flex items-center gap-2">
              <Sparkles className="h-5 w-5 text-violet-600" />
              AI Comparison Insights
              {isOpen ? <ChevronUp className="h-4 w-4 ml-auto" /> : <ChevronDown className="h-4 w-4 ml-auto" />}
            </CardTitle>
          </CardHeader>
        </CollapsibleTrigger>
        <CollapsibleContent>
          <CardContent className="pt-0 space-y-6">
            {/* Key Differences - Highlighted */}
            <div>
              <h4 className="font-semibold text-sm text-red-700 dark:text-red-400 mb-3 flex items-center gap-2">
                <GitCompare className="h-4 w-4" />
                Key Differences
              </h4>
              <div className="grid gap-3">
                {insights.key_differences?.map((diff, idx) => (
                  <div key={idx} className="p-3 bg-white dark:bg-gray-900 rounded-lg border border-red-100 dark:border-red-900">
                    <p className="font-medium text-sm text-gray-900 dark:text-gray-100">{diff.title}</p>
                    <p className="text-xs text-gray-600 dark:text-gray-400 mt-1">{diff.description}</p>
                  </div>
                ))}
              </div>
            </div>

            {/* Key Similarities */}
            <div>
              <h4 className="font-semibold text-sm text-green-700 dark:text-green-400 mb-3 flex items-center gap-2">
                <ThumbsUp className="h-4 w-4" />
                Key Similarities
              </h4>
              <div className="grid gap-3">
                {insights.key_similarities?.map((sim, idx) => (
                  <div key={idx} className="p-3 bg-white dark:bg-gray-900 rounded-lg border border-green-100 dark:border-green-900">
                    <p className="font-medium text-sm text-gray-900 dark:text-gray-100">{sim.title}</p>
                    <p className="text-xs text-gray-600 dark:text-gray-400 mt-1">{sim.description}</p>
                  </div>
                ))}
              </div>
            </div>

            {/* Strategic Insights */}
            <div>
              <h4 className="font-semibold text-sm text-violet-700 dark:text-violet-400 mb-3 flex items-center gap-2">
                <Lightbulb className="h-4 w-4" />
                Strategic Insights
              </h4>
              <ul className="space-y-2">
                {insights.strategic_insights?.map((insight, idx) => (
                  <li key={idx} className="text-sm text-gray-700 dark:text-gray-300 flex items-start gap-2">
                    <Zap className="h-3 w-3 text-violet-500 mt-1 shrink-0" />
                    {insight}
                  </li>
                ))}
              </ul>
            </div>
          </CardContent>
        </CollapsibleContent>
      </Card>
    </Collapsible>
  );
};

// Comparative Q&A Component
const ComparativeQA = ({
  personaIds,
  suggestedQuestions
}: {
  personaIds: number[];
  suggestedQuestions: string[];
}) => {
  const [question, setQuestion] = useState('');
  const [conversation, setConversation] = useState<Array<{ role: 'user' | 'assistant'; content: string; reasoning?: string }>>([]);
  const [isAsking, setIsAsking] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  const askQuestion = async (q: string) => {
    if (!q.trim() || isAsking) return;

    setConversation(prev => [...prev, { role: 'user', content: q }]);
    setQuestion('');
    setIsAsking(true);

    try {
      const response: ComparisonAnswer = await PersonasAPI.compareAsk(personaIds, q);
      setConversation(prev => [...prev, {
        role: 'assistant',
        content: response.answer,
        reasoning: response.reasoning
      }]);
    } catch (error) {
      setConversation(prev => [...prev, {
        role: 'assistant',
        content: 'Sorry, I encountered an error analyzing this question. Please try again.',
      }]);
    } finally {
      setIsAsking(false);
    }
  };

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [conversation]);

  return (
    <Card className="border-blue-200 dark:border-blue-800">
      <CardHeader className="pb-3">
        <CardTitle className="text-lg flex items-center gap-2">
          <MessageSquare className="h-5 w-5 text-blue-600" />
          Ask About These Personas
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Suggested Questions */}
        {conversation.length === 0 && (
          <div className="flex flex-wrap gap-2">
            {suggestedQuestions?.slice(0, 4).map((q, idx) => (
              <Button
                key={idx}
                variant="outline"
                size="sm"
                className="text-xs h-8"
                onClick={() => askQuestion(q)}
              >
                {q}
              </Button>
            ))}
          </div>
        )}

        {/* Conversation */}
        {conversation.length > 0 && (
          <ScrollArea className="h-[300px] pr-4" ref={scrollRef}>
            <div className="space-y-4">
              {conversation.map((msg, idx) => (
                <div key={idx} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                  <div className={`max-w-[85%] p-3 rounded-lg ${msg.role === 'user'
                    ? 'bg-blue-600 text-white'
                    : 'bg-gray-100 dark:bg-gray-800 text-gray-900 dark:text-gray-100'
                    }`}>
                    <p className="text-sm">{msg.content}</p>
                    {msg.reasoning && (
                      <p className="text-xs mt-2 pt-2 border-t border-gray-200 dark:border-gray-700 text-gray-500 dark:text-gray-400 italic">
                        {msg.reasoning}
                      </p>
                    )}
                  </div>
                </div>
              ))}
              {isAsking && (
                <div className="flex justify-start">
                  <div className="bg-gray-100 dark:bg-gray-800 p-3 rounded-lg">
                    <Loader2 className="h-4 w-4 animate-spin" />
                  </div>
                </div>
              )}
            </div>
          </ScrollArea>
        )}

        {/* Input */}
        <div className="flex gap-2">
          <Input
            placeholder="Ask a question about these personas..."
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && askQuestion(question)}
            disabled={isAsking}
          />
          <Button onClick={() => askQuestion(question)} disabled={!question.trim() || isAsking}>
            <Send className="h-4 w-4" />
          </Button>
        </div>
      </CardContent>
    </Card>
  );
};

export function ComparePersonas() {
  const location = useLocation();
  const navigate = useNavigate();
  const [personas, setPersonas] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [insights, setInsights] = useState<ComparisonInsights | null>(null);
  const [insightsLoading, setInsightsLoading] = useState(false);

  const personaIds = location.state?.personaIds as number[];

  useEffect(() => {
    console.log("ComparePersonas mounted. State:", location.state);

    if (!personaIds || personaIds.length === 0) {
      console.warn("No persona IDs found in state, redirecting...");
      navigate('/personas');
      return;
    }

    const fetchData = async () => {
      try {
        setLoading(true);
        console.log("Fetching personas:", personaIds);

        // Fetch personas
        const promises = personaIds.map(id => PersonasAPI.get(id));
        const results = await Promise.allSettled(promises);

        const successfulPersonas = results
          .filter(r => r.status === 'fulfilled')
          .map(r => (r as PromiseFulfilledResult<any>).value);

        if (successfulPersonas.length === 0) {
          setError("Failed to load any personas. Please try again.");
        } else {
          setPersonas(successfulPersonas);
        }
      } catch (err) {
        console.error("Critical error loading comparison:", err);
        setError("An unexpected error occurred.");
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, [personaIds, navigate]);

  // Fetch AI insights after personas load
  useEffect(() => {
    if (personas.length >= 2 && !insights) {
      const fetchInsights = async () => {
        setInsightsLoading(true);
        try {
          const result = await PersonasAPI.compareAnalyze(personaIds);
          setInsights(result);
        } catch (error) {
          console.error("Failed to fetch comparison insights:", error);
        } finally {
          setInsightsLoading(false);
        }
      };
      fetchInsights();
    }
  }, [personas, personaIds, insights]);

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 dark:bg-gray-950 p-8 flex items-center justify-center">
        <div className="flex flex-col items-center gap-4">
          <Activity className="h-8 w-8 text-violet-600 animate-pulse" />
          <p className="text-gray-500">Loading comparison...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen bg-gray-50 dark:bg-gray-950 p-8 flex items-center justify-center">
        <div className="text-center space-y-4">
          <AlertCircle className="h-12 w-12 text-red-500 mx-auto" />
          <h2 className="text-xl font-bold">Unable to Compare</h2>
          <p className="text-gray-500">{error}</p>
          <Button onClick={() => navigate('/personas')}>Return to Library</Button>
        </div>
      </div>
    );
  }

  // Helper to extract nested data safely
  const getField = (persona: any, path: string) => {
    try {
      const data = typeof persona.full_persona_json === 'string'
        ? JSON.parse(persona.full_persona_json)
        : persona.full_persona_json;

      return path.split('.').reduce((obj, key) => obj?.[key], data);
    } catch {
      return null;
    }
  };

  // Get attribute score for highlighting
  const getAttrScore = (attrKey: string) => {
    if (!insights?.attribute_scores?.[attrKey]) return {};
    return {
      highlightLevel: insights.attribute_scores[attrKey].highlight_level,
      similarityScore: insights.attribute_scores[attrKey].similarity_score,
    };
  };

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-950 p-8">
      <div className="max-w-[1600px] mx-auto space-y-6">
        {/* Header */}
        <div className="flex items-center gap-4">
          <Button variant="ghost" onClick={() => navigate('/personas')}>
            <ArrowLeft className="h-4 w-4 mr-2" />
            Back to Library
          </Button>
          <h1 className="text-2xl font-bold">Persona Comparison</h1>
          <Badge variant="outline" className="ml-auto">
            {personas.length} personas
          </Badge>
        </div>

        {/* AI Insights Panel */}
        <AIInsightsPanel insights={insights} loading={insightsLoading} />

        {/* Comparison Table with Smart Highlighting */}
        <div className="overflow-x-auto rounded-xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 shadow-sm">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="border-b border-gray-200 dark:border-gray-800">
                <th className="p-4 bg-gray-100/50 dark:bg-gray-800/50 font-semibold text-gray-500 uppercase text-xs tracking-wider w-[200px]">
                  Persona Profile
                </th>
                {personas.map(p => (
                  <th key={p.id} className="p-6 border-r border-gray-200 dark:border-gray-800 last:border-0 align-top min-w-[250px]">
                    <div className="flex flex-col gap-2">
                      <Badge className="w-fit bg-violet-100 text-violet-700 hover:bg-violet-200 border-0">
                        {p.persona_subtype || 'Standard'}
                      </Badge>
                      <div>
                        <h3 className="text-lg font-bold text-gray-900 dark:text-gray-100">{p.name}</h3>
                        <p className="text-sm text-gray-500">{p.age} years • {p.gender}</p>
                      </div>
                      {p.disease_pack && (
                        <Badge variant="outline" className="w-fit text-xs border-blue-200 text-blue-700 bg-blue-50">
                          {p.disease_pack}
                        </Badge>
                      )}
                    </div>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {/* Core Attributes */}
              <ComparisonRow
                label="Condition"
                icon={<Activity className="h-4 w-4" />}
                data={personas.map(p => p.condition)}
                {...getAttrScore('condition')}
              />
              <ComparisonRow
                label="Location"
                icon={<Target className="h-4 w-4" />}
                data={personas.map(p => p.location)}
                {...getAttrScore('location')}
              />
              <ComparisonRow
                label="Specialty"
                icon={<Briefcase className="h-4 w-4 text-teal-500" />}
                data={personas.map(p => p.specialty || '-')}
                {...getAttrScore('specialty')}
              />
              <ComparisonRow
                label="Practice Setup"
                icon={<Building className="h-4 w-4 text-indigo-500" />}
                data={personas.map(p => p.practice_setup || '-')}
                {...getAttrScore('practice_setup')}
              />
              <ComparisonRow
                label="Decision Style"
                icon={<Brain className="h-4 w-4 text-orange-500" />}
                data={personas.map(p => p.decision_style || '-')}
                {...getAttrScore('decision_style')}
              />

              {/* Psychology */}
              <ComparisonRow
                label="Motivations"
                icon={<Brain className="h-4 w-4 text-green-500" />}
                type="list"
                data={personas.map(p => getField(p, 'motivations') || [])}
                {...getAttrScore('motivations')}
              />
              <ComparisonRow
                label="Key Beliefs"
                icon={<Shield className="h-4 w-4 text-blue-500" />}
                type="list"
                data={personas.map(p => getField(p, 'beliefs') || [])}
                {...getAttrScore('beliefs')}
              />
              <ComparisonRow
                label="Pain Points"
                icon={<AlertTriangle className="h-4 w-4 text-red-500" />}
                type="list"
                data={personas.map(p => getField(p, 'pain_points') || [])}
                {...getAttrScore('pain_points')}
              />

              {/* Communication */}
              <ComparisonRow
                label="Communication"
                icon={<MessageSquare className="h-4 w-4 text-purple-500" />}
                data={personas.map(p => {
                  const prefs = getField(p, 'communication_preferences');
                  return prefs?.information_style || prefs?.preferred_channels || p.channel_use || '-';
                })}
              />

              {/* Core Insight */}
              <ComparisonRow
                label="Core Insight"
                icon={<Lightbulb className="h-4 w-4 text-amber-500" />}
                data={personas.map(p => p.core_insight || '-')}
                {...getAttrScore('core_insight')}
              />
            </tbody>
          </table>
        </div>

        {/* Comparative Q&A */}
        <ComparativeQA
          personaIds={personaIds}
          suggestedQuestions={insights?.suggested_questions || []}
        />
      </div>
    </div>
  );
}
