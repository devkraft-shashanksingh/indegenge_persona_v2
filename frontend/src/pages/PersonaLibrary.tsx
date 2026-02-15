"use client"

import React, { useState, useEffect } from "react"
import { useNavigate, useSearchParams } from "react-router-dom"
import { PersonasAPI, BrandsAPI, ChatAPI } from "@/lib/api"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../components/ui/card"
import { Button } from "../components/ui/button"
import { Input } from "../components/ui/input"
import { Label } from "../components/ui/label"
import { Textarea } from "../components/ui/textarea"
import { Badge } from "../components/ui/badge"
import { Separator } from "../components/ui/separator"

import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../components/ui/select"
import { ScrollArea } from "../components/ui/scroll-area"
import { Checkbox } from "../components/ui/checkbox"
import { Slider } from "../components/ui/slider"

import {
  User,
  MapPin,
  Loader2,
  Plus,
  Users,
  Search,
  Brain,
  CheckCircle,
  Settings,
  Wand2,
  X,
  Trash2,
  Library,
  GitCompare,
  PlayCircle,
  Filter,
  LayoutGrid,
  List,
  Eye,
  MessageSquare,
} from "lucide-react"
import { PersonaDetailModal } from "../components/PersonaDetailModal"
import { useToast } from "@/components/ui/use-toast"
import { cn } from "@/lib/utils"

interface Persona {
  id: number
  name: string
  avatar_url?: string
  persona_type: string
  persona_subtype?: string
  disease_pack?: string
  age: number
  gender: string
  condition: string
  location: string
  full_persona_json: string
  created_at: string
  brand_id?: number
  specialty?: string
  practice_setup?: string
  system_context?: string
  decision_influencers?: string
  adherence_to_protocols?: string
  channel_use?: string
  decision_style?: string
  core_insight?: string
}

interface Brand {
  id: number
  name: string
}

interface BulkPersonaTemplate {
  id: string
  age: string
  gender: string
  condition: string
  location: string
  concerns: string
}

const conditionColors: Record<string, string> = {
  Diabetes: "bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200",
  Hypertension: "bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200",
  Asthma: "bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-200",
  Depression: "bg-indigo-100 text-indigo-800 dark:bg-indigo-900 dark:text-indigo-200",
  Arthritis: "bg-amber-100 text-amber-800 dark:bg-amber-900 dark:text-amber-200",
  default: "bg-gray-100 text-gray-800 dark:bg-gray-800 dark:text-gray-200",
}

const DEFAULT_AGE_RANGE: [number, number] = [18, 100]
const PERSONA_TYPES = ["HCP", "Patient"] as const

interface PersonaFilters {
  ageRange: [number, number]
  personaTypes: string[]
  genders: string[]
  conditions: string[]
  locations: string[]
}

export function PersonaLibrary() {
  const { toast } = useToast();
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();

  const [personas, setPersonas] = useState<Persona[]>([]);
  const [brands, setBrands] = useState<Brand[]>([]);
  const [selectedBrandId, setSelectedBrandId] = useState<string>(searchParams.get('brand_id') || "all");
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [bulkGenerating, setBulkGenerating] = useState(false);
  const [generationProgress, setGenerationProgress] = useState({ current: 0, total: 0 });
  const [workspaceMode, setWorkspaceMode] = useState<"browse" | "create">("browse");
  const [creationMode, setCreationMode] = useState<"single" | "bulk" | "prompt">("single");
  const [selectedPersona, setSelectedPersona] = useState<Persona | null>(null);
  const [isDetailModalOpen, setIsDetailModalOpen] = useState(false);
  const [searchTerm, setSearchTerm] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [selectedPersonaIds, setSelectedPersonaIds] = useState<Set<number>>(new Set());
  const [viewMode, setViewMode] = useState<"grid" | "list">("list");

  // Filters
  const [filters, setFilters] = useState<PersonaFilters>({
    ageRange: DEFAULT_AGE_RANGE,
    personaTypes: [],
    genders: [],
    conditions: [],
    locations: [],
  });

  // Form data for single persona creation
  const [formData, setFormData] = useState({
    age: "",
    gender: "",
    condition: "",
    location: "",
    concerns: "",
    count: '1'
  });

  const [bulkTemplates, setBulkTemplates] = useState<BulkPersonaTemplate[]>([
    { id: "1", age: "", gender: "", condition: "", location: "", concerns: "" },
  ]);
  const [bulkPrompt, setBulkPrompt] = useState("")
  const [bulkCount, setBulkCount] = useState(3)
  const [bulkFilters, setBulkFilters] = useState({
    ageRange: { min: 25, max: 75 },
    genders: ["Male", "Female"],
    conditions: [] as string[],
    locations: [] as string[],
  })

  useEffect(() => {
    fetchBrands()
  }, [])

  useEffect(() => {
    fetchPersonas()
  }, [selectedBrandId])

  useEffect(() => {
    setSelectedPersonaIds((prev) => {
      const availableIds = new Set(personas.map((p) => p.id))
      return new Set([...prev].filter((id) => availableIds.has(id)))
    })
  }, [personas])

  const handleBrandFilterChange = (value: string) => {
    setSelectedBrandId(value)
    if (value === "all") {
      searchParams.delete('brand_id')
    } else {
      searchParams.set('brand_id', value)
    }
    setSearchParams(searchParams)
  }

  const handleSimulatePersonas = (personaIds: number[]) => {
    if (personaIds.length === 0) return
    navigate('/simulation', { state: { preselectedPersonaIds: personaIds } })
  }

  const handleComparePersonas = (personaIds: number[]) => {
    if (personaIds.length < 2) {
      alert("Please select at least 2 personas to compare.");
      return;
    }
    navigate('/compare', { state: { personaIds } });
  }

  const togglePersonaSelection = (id: number) => {
    setSelectedPersonaIds((prev) => {
      const updated = new Set(prev)
      if (updated.has(id)) {
        updated.delete(id)
      } else {
        updated.add(id)
      }
      return updated
    })
  }

  const fetchBrands = async () => {
    try {
      const data = await BrandsAPI.list()
      setBrands(data)
    } catch (error) {
      console.error("Failed to fetch brands:", error)
    }
  }

  const fetchPersonas = async () => {
    setLoading(true)
    try {
      const brandId = selectedBrandId !== "all" ? parseInt(selectedBrandId) : undefined
      const data = await PersonasAPI.list(brandId)
      setPersonas(data)
      setError(null)
    } catch (error: any) {
      console.error("PersonaLibrary: Error fetching personas:", error)
      const errorMessage = error?.response?.data?.detail || "Failed to load personas."
      setError(errorMessage)
      toast({ title: "Error loading personas", description: errorMessage, variant: "destructive" })
    } finally {
      setLoading(false)
    }
  }

  const handleDeletePersona = async (personaId: number, personaName: string) => {
    try {
      await PersonasAPI.delete(personaId);
      setPersonas(personas.filter(p => p.id !== personaId));
      setSelectedPersonaIds((prev) => {
        const updated = new Set(prev)
        updated.delete(personaId)
        return updated
      })
      toast({ title: "Deleted", description: `Persona "${personaName}" has been removed.` });
    } catch (error) {
      toast({ title: "Error", description: "Could not delete the persona.", variant: "destructive" });
    }
  };

  const handleChatWithPersona = async (personaId: number) => {
    try {
      const session = await ChatAPI.createSession(personaId);
      navigate(`/chat/${session.id}`);
    } catch (error) {
      toast({ title: "Error", description: "Failed to start chat session", variant: "destructive" });
    }
  };


  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => {
    setFormData({ ...formData, [e.target.name]: e.target.value })
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    const age = parseInt(formData.age);
    if (isNaN(age) || age < 1 || age > 120) {
      setError("Please enter a valid age between 1 and 120.");
      return;
    }

    setGenerating(true);
    try {
      const count = parseInt(formData.count) || 1;
      setGenerationProgress({ current: 0, total: count });

      for (let i = 0; i < count; i++) {
        setGenerationProgress({ current: i + 1, total: count });
        const variations = ['', ' with family history', ' seeking treatment options', ' concerned about side effects'];
        await PersonasAPI.generate({
          age, gender: formData.gender, condition: formData.condition,
          location: formData.location, concerns: formData.concerns + variations[i % variations.length]
        });
      }

      await fetchPersonas();
      setWorkspaceMode("browse");
      setFormData({ age: '', gender: '', condition: '', location: '', concerns: '', count: '1' });
      toast({ title: "Success", description: `Generated ${count} new persona(s).` });
    } catch (error: any) {
      setError(error.response?.data?.detail || "Generation failed.");
    } finally {
      setGenerating(false);
    }
  }

  const handleBulkGenerate = async (e: React.FormEvent) => {
    e.preventDefault();
    setBulkGenerating(true)
    try {
      const promises = bulkTemplates.map((t) =>
        PersonasAPI.generate({ age: parseInt(t.age), gender: t.gender, condition: t.condition, location: t.location, concerns: t.concerns })
      )
      await Promise.allSettled(promises);
      await fetchPersonas();
      setWorkspaceMode("browse");
      toast({ title: "Success", description: `Bulk generation complete.` });
    } catch (error: any) {
      setError(error.response?.data?.detail || "Bulk generation failed.");
    } finally {
      setBulkGenerating(false)
    }
  }

  const handleBulkGenerateFromPrompt = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!bulkPrompt.trim()) return;
    setBulkGenerating(true)
    try {
      const promises = Array.from({ length: bulkCount }, (_, i) => {
        const randomAge = Math.floor(Math.random() * (bulkFilters.ageRange.max - bulkFilters.ageRange.min + 1)) + bulkFilters.ageRange.min
        const randomGender = bulkFilters.genders[Math.floor(Math.random() * bulkFilters.genders.length)]
        return PersonasAPI.generate({
          age: randomAge, gender: randomGender,
          condition: bulkFilters.conditions[0] || "General Health",
          location: bulkFilters.locations[0] || "United States",
          concerns: `${bulkPrompt} (Persona ${i + 1})`,
        })
      })
      await Promise.allSettled(promises);
      await fetchPersonas();
      setWorkspaceMode("browse");
      toast({ title: "Success", description: `Generated ${bulkCount} personas from prompt.` });
    } catch (error: any) {
      setError(error.response?.data?.detail || "Prompt generation failed.");
    } finally {
      setBulkGenerating(false)
    }
  }

  const toggleFilterValue = (key: "personaTypes" | "genders" | "conditions" | "locations", value: string) => {
    setFilters(prev => {
      const current = prev[key]
      return { ...prev, [key]: current.includes(value) ? current.filter(v => v !== value) : [...current, value] }
    })
  }

  const updateAgeRange = (value: number[]) => {
    if (value.length === 2) setFilters(prev => ({ ...prev, ageRange: [value[0], value[1]] }))
  }

  const handleResetFilters = () => {
    setFilters({ ageRange: DEFAULT_AGE_RANGE, personaTypes: [], genders: [], conditions: [], locations: [] })
    setSearchTerm('')
  }

  const filteredPersonas = React.useMemo(() => {
    return personas.filter((persona) => {
      const searchLower = searchTerm.toLowerCase().trim()
      const matchesSearch = searchTerm === "" ||
        persona.name.toLowerCase().includes(searchLower) ||
        (persona.condition || "").toLowerCase().includes(searchLower) ||
        persona.location.toLowerCase().includes(searchLower)

      const [minAge, maxAge] = filters.ageRange
      const matchesAge = persona.age >= minAge && persona.age <= maxAge

      const normalizedType = (persona.persona_type || "Patient").trim().toLowerCase()
      const matchesType = filters.personaTypes.length === 0 ||
        filters.personaTypes.some(t => t.toLowerCase() === normalizedType)

      const matchesGender = filters.genders.length === 0 ||
        filters.genders.some(g => g.toLowerCase() === persona.gender.toLowerCase())

      const matchesCondition = filters.conditions.length === 0 ||
        filters.conditions.some(c => c.toLowerCase() === (persona.condition || "").toLowerCase())

      return matchesSearch && matchesAge && matchesType && matchesGender && matchesCondition
    })
  }, [personas, searchTerm, filters])

  const activeFiltersCount = React.useMemo(() => {
    let count = 0
    if (searchTerm.trim()) count++
    if (filters.personaTypes.length > 0) count++
    if (filters.genders.length > 0) count++
    if (filters.conditions.length > 0) count++
    if (filters.locations.length > 0) count++
    if (filters.ageRange[0] !== DEFAULT_AGE_RANGE[0] || filters.ageRange[1] !== DEFAULT_AGE_RANGE[1]) count++
    return count
  }, [searchTerm, filters])

  const uniqueGenders = React.useMemo(() => {
    const genders = new Set(personas.map(p => p.gender).filter(Boolean))
    return Array.from(genders)
  }, [personas])



  const addBulkTemplate = () => {
    setBulkTemplates([...bulkTemplates, { id: Date.now().toString(), age: "", gender: "", condition: "", location: "", concerns: "" }])
  }

  const removeBulkTemplate = (id: string) => {
    if (bulkTemplates.length > 1) setBulkTemplates(bulkTemplates.filter(t => t.id !== id))
  }

  const handleBulkTemplateChange = (id: string, field: keyof Omit<BulkPersonaTemplate, 'id'>, value: string) => {
    setBulkTemplates(bulkTemplates.map(t => t.id === id ? { ...t, [field]: value } : t))
  }

  return (
    <div className="flex flex-col h-full bg-background overflow-hidden">
      {/* Slim Header */}
      <header className="h-14 border-b bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60 flex items-center justify-between px-4 shrink-0 z-50">
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2 text-primary font-semibold">
            <div className="p-1.5 bg-primary/10 rounded-md">
              <Library className="h-5 w-5" />
            </div>
            <span>Persona Library</span>
          </div>
          <Separator orientation="vertical" className="h-6" />
          <div className="flex bg-muted/50 p-1.5 rounded-xl border shadow-sm">
            <button
              onClick={() => setWorkspaceMode("browse")}
              className={`px-4 py-2 text-sm font-semibold rounded-lg transition-all flex items-center gap-2 ${workspaceMode === "browse"
                ? "bg-background shadow text-primary ring-1 ring-black/5"
                : "text-muted-foreground hover:text-foreground hover:bg-background/50"
                }`}
            >
              <Users className="h-4 w-4" />
              <span>Browse Library</span>
            </button>
            <button
              onClick={() => setWorkspaceMode("create")}
              className={`px-4 py-2 text-sm font-semibold rounded-lg transition-all flex items-center gap-2 ${workspaceMode === "create"
                ? "bg-background shadow text-primary ring-1 ring-black/5"
                : "text-muted-foreground hover:text-foreground hover:bg-background/50"
                }`}
            >
              <Plus className="h-4 w-4" />
              <span>Create Personas</span>
            </button>
          </div>
        </div>

        <div className="flex items-center gap-4">
          <div className="hidden md:flex items-center gap-2 text-sm text-muted-foreground">
            <span className="flex items-center gap-1.5">
              <Users className="h-4 w-4" />
              <span className="font-medium text-foreground">{personas.length}</span> total
            </span>
            <span className="text-border">|</span>
            <span className="flex items-center gap-1.5">
              <CheckCircle className="h-4 w-4" />
              <span className="font-medium text-foreground">{selectedPersonaIds.size}</span> selected
            </span>
          </div>
          <Button
            onClick={() => navigate('/create-persona')}
            className="bg-gradient-to-r from-violet-600 to-purple-600 hover:from-violet-700 hover:to-purple-700 text-white"
          >
            <Brain className="h-4 w-4 mr-2" />
            Persona Builder
          </Button>
        </div>
      </header>

      {/* Main Content Area */}
      <div className="flex-1 overflow-hidden">
        {workspaceMode === "browse" ? (
          <div className="flex h-full w-full">
            {/* LEFT PANE: Filters & Persona List */}
            <aside className="w-[380px] border-r bg-muted/10 flex flex-col shrink-0">
              {/* Filter Controls */}
              <div className="p-4 border-b bg-background/50 backdrop-blur space-y-4">
                <div className="flex items-center justify-between">
                  <h3 className="font-semibold text-base flex items-center gap-2">
                    <Filter className="h-5 w-5 text-primary" />
                    Filters
                  </h3>
                  <div className="flex items-center gap-2">
                    {activeFiltersCount > 0 && (
                      <Button variant="ghost" size="sm" onClick={handleResetFilters} className="h-6 text-[10px] text-muted-foreground hover:text-primary">
                        Reset
                      </Button>
                    )}
                    <Badge variant="secondary" className="font-mono text-xs">{filteredPersonas.length}</Badge>
                  </div>
                </div>

                {/* Search */}
                <div className="relative">
                  <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
                  <Input
                    placeholder="Search by name, condition, location..."
                    className="pl-9 h-9 text-sm bg-background"
                    value={searchTerm}
                    onChange={(e) => setSearchTerm(e.target.value)}
                  />
                </div>

                {/* Brand Filter */}
                <div className="flex items-center gap-2">
                  <span className="text-[10px] font-uppercase tracking-wider text-muted-foreground font-semibold w-14 shrink-0">BRAND</span>
                  <Select value={selectedBrandId} onValueChange={handleBrandFilterChange}>
                    <SelectTrigger className="h-8 text-xs flex-1">
                      <SelectValue placeholder="All Brands" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="all">All Brands</SelectItem>
                      {brands.map(b => <SelectItem key={b.id} value={b.id.toString()}>{b.name}</SelectItem>)}
                    </SelectContent>
                  </Select>
                </div>

                {/* Age Range */}
                <div className="flex items-center gap-2">
                  <span className="text-[10px] font-uppercase tracking-wider text-muted-foreground font-semibold w-14 shrink-0">AGE</span>
                  <Slider value={filters.ageRange} onValueChange={updateAgeRange} min={DEFAULT_AGE_RANGE[0]} max={DEFAULT_AGE_RANGE[1]} step={1} className="flex-1 py-1.5" />
                  <span className="text-[10px] text-muted-foreground font-mono w-16 text-right">{filters.ageRange[0]} - {filters.ageRange[1]}</span>
                </div>

                {/* Type Filters */}
                <div className="flex items-center gap-2">
                  <span className="text-[10px] font-uppercase tracking-wider text-muted-foreground font-semibold w-14 shrink-0">TYPE</span>
                  <div className="flex gap-1 flex-1">
                    {PERSONA_TYPES.map(type => (
                      <button key={type} onClick={() => toggleFilterValue("personaTypes", type)}
                        className={`px-2 py-1 rounded text-[10px] uppercase font-bold border transition-all ${filters.personaTypes.includes(type)
                          ? "bg-primary/10 border-primary text-primary"
                          : "bg-background border-border text-muted-foreground hover:border-primary/50"
                          }`}
                      >{type}</button>
                    ))}
                  </div>
                </div>

                {/* Gender Filters */}
                <div className="flex items-center gap-2">
                  <span className="text-[10px] font-uppercase tracking-wider text-muted-foreground font-semibold w-14 shrink-0">GENDER</span>
                  <div className="flex gap-1 flex-1 flex-wrap">
                    {uniqueGenders.slice(0, 3).map(gender => (
                      <button key={gender} onClick={() => toggleFilterValue("genders", gender)}
                        className={`px-2 py-1 rounded text-[10px] font-bold border transition-all ${filters.genders.includes(gender)
                          ? "bg-primary/10 border-primary text-primary"
                          : "bg-background border-border text-muted-foreground hover:border-primary/50"
                          }`}
                      >{gender}</button>
                    ))}
                  </div>
                </div>
              </div>

              {/* Persona List Header */}
              <div className="bg-muted/5 px-4 py-2 border-b flex justify-between items-center">
                <div className="text-xs text-muted-foreground font-medium">Results ({filteredPersonas.length})</div>
                <div className="flex items-center gap-2">
                  <Button variant="ghost" size="sm" className="h-5 text-[10px] px-1" onClick={() => setSelectedPersonaIds(new Set(filteredPersonas.map(p => p.id)))}>
                    Select All
                  </Button>
                  <Separator orientation="vertical" className="h-3" />
                  <button onClick={() => setViewMode("list")} className={`p-1 rounded ${viewMode === "list" ? "bg-primary/10 text-primary" : "text-muted-foreground"}`}>
                    <List className="h-3.5 w-3.5" />
                  </button>
                  <button onClick={() => setViewMode("grid")} className={`p-1 rounded ${viewMode === "grid" ? "bg-primary/10 text-primary" : "text-muted-foreground"}`}>
                    <LayoutGrid className="h-3.5 w-3.5" />
                  </button>
                </div>
              </div>

              {/* Persona List */}
              <ScrollArea className="flex-1 bg-muted/5">
                <div className="p-4 space-y-2">
                  {loading ? (
                    Array.from({ length: 6 }).map((_, i) => (
                      <div key={i} className="p-3 rounded-xl border bg-background animate-pulse">
                        <div className="flex items-center gap-3">
                          <div className="w-10 h-10 bg-muted rounded-lg" />
                          <div className="flex-1 space-y-2">
                            <div className="h-4 bg-muted rounded w-3/4" />
                            <div className="h-3 bg-muted rounded w-1/2" />
                          </div>
                        </div>
                      </div>
                    ))
                  ) : filteredPersonas.length === 0 ? (
                    <div className="text-center py-8 text-muted-foreground text-sm">
                      No personas match your filters
                    </div>
                  ) : (
                    filteredPersonas.map(persona => {
                      const isSelected = selectedPersonaIds.has(persona.id)
                      const conditionClass = conditionColors[persona.condition] || conditionColors.default
                      return (
                        <div
                          key={persona.id}
                          onClick={() => togglePersonaSelection(persona.id)}
                          className={`group relative p-3 rounded-xl border cursor-pointer transition-all hover:shadow-md ${isSelected
                            ? 'bg-background border-primary shadow-sm ring-1 ring-primary/20'
                            : 'bg-background border-border hover:border-primary/50'}`}
                        >
                          <div className="flex items-start gap-3">
                            <Checkbox checked={isSelected} className="mt-1" onChange={() => togglePersonaSelection(persona.id)} />
                            <div className="flex-1 min-w-0">
                              <div className="flex items-center justify-between mb-0.5">
                                <span className="font-semibold text-sm truncate pr-2">{persona.name}</span>
                                <Badge variant={persona.persona_type === 'HCP' ? 'default' : 'secondary'} className="text-[10px] h-4 px-1 rounded-sm">
                                  {persona.persona_type === 'HCP' ? 'HCP' : 'Pt'}
                                </Badge>
                              </div>
                              <div className="text-xs text-muted-foreground flex flex-wrap gap-x-3 gap-y-1">
                                <span className="flex items-center gap-1"><span className="w-1 h-1 rounded-full bg-muted-foreground/50" /> {persona.age} yrs</span>
                                <span className="flex items-center gap-1"><span className="w-1 h-1 rounded-full bg-muted-foreground/50" /> {persona.gender}</span>
                                {persona.condition && <Badge className={cn("text-[9px] h-4 px-1", conditionClass)}>{persona.condition}</Badge>}
                              </div>
                              {persona.location && (
                                <div className="text-[10px] text-muted-foreground mt-1 flex items-center gap-1">
                                  <MapPin className="h-3 w-3" /> {persona.location}
                                </div>
                              )}
                            </div>
                            <div className="flex flex-col gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                              <Button variant="ghost" size="sm" className="h-6 w-6 p-0" onClick={(e) => { e.stopPropagation(); setSelectedPersona(persona); setIsDetailModalOpen(true); }}>
                                <Eye className="h-3.5 w-3.5" />
                              </Button>
                              <Button variant="ghost" size="sm" className="h-6 w-6 p-0 text-blue-500" onClick={(e) => { e.stopPropagation(); handleChatWithPersona(persona.id); }}>
                                <MessageSquare className="h-3.5 w-3.5" />
                              </Button>
                              <Button variant="ghost" size="sm" className="h-6 w-6 p-0 text-red-500" onClick={(e) => { e.stopPropagation(); if (confirm(`Delete "${persona.name}"?`)) handleDeletePersona(persona.id, persona.name); }}>
                                <Trash2 className="h-3.5 w-3.5" />
                              </Button>
                            </div>
                          </div>
                        </div>
                      )
                    })
                  )}
                </div>
              </ScrollArea>
            </aside>

            {/* RIGHT PANE: Selected Persona Details & Actions */}
            <main className="flex-1 flex flex-col h-full bg-background relative overflow-hidden">
              <ScrollArea className="flex-1">
                <div className="p-8 max-w-5xl mx-auto space-y-8 pb-32">
                  {/* Selection Summary */}
                  {selectedPersonaIds.size > 0 ? (
                    <>
                      <section className="space-y-4">
                        <div className="flex items-center justify-between">
                          <div>
                            <h2 className="text-xl font-bold flex items-center gap-2">
                              <Users className="h-5 w-5 text-primary" />
                              Selected Cohort
                            </h2>
                            <p className="text-sm text-muted-foreground mt-1">{selectedPersonaIds.size} persona(s) selected for testing</p>
                          </div>
                          <Button variant="outline" size="sm" onClick={() => setSelectedPersonaIds(new Set())}>Clear Selection</Button>
                        </div>

                        <Card className="border-primary/20 bg-primary/5">
                          <CardContent className="p-6">
                            <div className="grid grid-cols-4 gap-4 mb-6">
                              <div className="text-center p-3 bg-background rounded-lg">
                                <div className="text-2xl font-bold text-primary">{selectedPersonaIds.size}</div>
                                <div className="text-xs text-muted-foreground">Total</div>
                              </div>
                              <div className="text-center p-3 bg-background rounded-lg">
                                <div className="text-2xl font-bold text-blue-600">
                                  {personas.filter(p => selectedPersonaIds.has(p.id) && p.persona_type === 'HCP').length}
                                </div>
                                <div className="text-xs text-muted-foreground">HCPs</div>
                              </div>
                              <div className="text-center p-3 bg-background rounded-lg">
                                <div className="text-2xl font-bold text-emerald-600">
                                  {personas.filter(p => selectedPersonaIds.has(p.id) && p.persona_type !== 'HCP').length}
                                </div>
                                <div className="text-xs text-muted-foreground">Patients</div>
                              </div>
                              <div className="text-center p-3 bg-background rounded-lg">
                                <div className="text-2xl font-bold text-amber-600">
                                  {Math.round(personas.filter(p => selectedPersonaIds.has(p.id)).reduce((sum, p) => sum + p.age, 0) / selectedPersonaIds.size) || 0}
                                </div>
                                <div className="text-xs text-muted-foreground">Avg Age</div>
                              </div>
                            </div>

                            <div className="flex gap-3">
                              <Button className="flex-1 bg-gradient-to-r from-primary to-violet-600" onClick={() => handleSimulatePersonas(Array.from(selectedPersonaIds))}>
                                <PlayCircle className="h-4 w-4 mr-2" />
                                Test in Simulator
                              </Button>
                              <Button variant="outline" className="flex-1" onClick={() => handleComparePersonas(Array.from(selectedPersonaIds))} disabled={selectedPersonaIds.size < 2}>
                                <GitCompare className="h-4 w-4 mr-2" />
                                Compare Personas
                              </Button>
                              {selectedPersonaIds.size === 1 && (
                                <Button variant="secondary" className="flex-1" onClick={() => handleChatWithPersona(Array.from(selectedPersonaIds)[0])}>
                                  <MessageSquare className="h-4 w-4 mr-2" />
                                  Chat
                                </Button>
                              )}
                            </div>
                          </CardContent>
                        </Card>
                      </section>

                      {/* Selected Personas Grid */}
                      <section className="space-y-4">
                        <h3 className="font-semibold">Selected Personas</h3>
                        <div className="grid grid-cols-2 gap-4">
                          {personas.filter(p => selectedPersonaIds.has(p.id)).map(persona => (
                            <Card key={persona.id} className="overflow-hidden hover:shadow-lg transition-shadow">
                              <CardHeader className="pb-2">
                                <div className="flex items-center justify-between">
                                  <CardTitle className="text-base">{persona.name}</CardTitle>
                                  <Badge variant={persona.persona_type === 'HCP' ? 'default' : 'secondary'}>{persona.persona_type}</Badge>
                                </div>
                                <CardDescription>{persona.age} yrs • {persona.gender} • {persona.location}</CardDescription>
                              </CardHeader>
                              <CardContent>
                                <Badge className={conditionColors[persona.condition] || conditionColors.default}>{persona.condition}</Badge>
                              </CardContent>
                            </Card>
                          ))}
                        </div>
                      </section>
                    </>
                  ) : (
                    /* Empty State */
                    <div className="flex flex-col items-center justify-center h-[60vh] text-center">
                      <div className="p-6 bg-primary/5 rounded-full mb-6">
                        <Users className="h-16 w-16 text-primary/50" />
                      </div>
                      <h2 className="text-2xl font-bold mb-2">Select Personas</h2>
                      <p className="text-muted-foreground max-w-md mb-6">
                        Choose personas from the left panel to build a cohort for testing, comparison, or simulation.
                      </p>
                      <div className="flex gap-3">
                        <Button onClick={() => setWorkspaceMode("create")}>
                          <Plus className="h-4 w-4 mr-2" />
                          Create New Personas
                        </Button>
                        <Button variant="outline" onClick={() => setSelectedPersonaIds(new Set(filteredPersonas.slice(0, 5).map(p => p.id)))}>
                          Quick Select (5)
                        </Button>
                      </div>
                    </div>
                  )}
                </div>
              </ScrollArea>
            </main>
          </div>
        ) : (
          /* CREATE MODE */
          <div className="flex h-full w-full">
            {/* LEFT: Creation Mode Selector */}
            <aside className="w-[280px] border-r bg-muted/10 flex flex-col shrink-0">
              <div className="p-4 border-b">
                <h3 className="font-semibold text-base flex items-center gap-2 mb-4">
                  <Settings className="h-5 w-5 text-primary" />
                  Creation Mode
                </h3>
                <div className="space-y-2">
                  <button onClick={() => setCreationMode("single")}
                    className={`w-full p-3 rounded-lg border text-left transition-all ${creationMode === "single" ? "bg-primary/10 border-primary" : "bg-background border-border hover:border-primary/50"}`}>
                    <div className="flex items-center gap-3">
                      <User className="h-5 w-5 text-primary" />
                      <div>
                        <div className="font-medium text-sm">Single Persona</div>
                        <div className="text-xs text-muted-foreground">Create one detailed persona</div>
                      </div>
                    </div>
                  </button>
                  <button onClick={() => setCreationMode("bulk")}
                    className={`w-full p-3 rounded-lg border text-left transition-all ${creationMode === "bulk" ? "bg-primary/10 border-primary" : "bg-background border-border hover:border-primary/50"}`}>
                    <div className="flex items-center gap-3">
                      <Users className="h-5 w-5 text-emerald-600" />
                      <div>
                        <div className="font-medium text-sm">Bulk Creation</div>
                        <div className="text-xs text-muted-foreground">Create multiple with templates</div>
                      </div>
                    </div>
                  </button>
                  <button onClick={() => setCreationMode("prompt")}
                    className={`w-full p-3 rounded-lg border text-left transition-all ${creationMode === "prompt" ? "bg-primary/10 border-primary" : "bg-background border-border hover:border-primary/50"}`}>
                    <div className="flex items-center gap-3">
                      <Wand2 className="h-5 w-5 text-purple-600" />
                      <div>
                        <div className="font-medium text-sm">Prompt-Based</div>
                        <div className="text-xs text-muted-foreground">AI generates from description</div>
                      </div>
                    </div>
                  </button>
                </div>
              </div>
              <div className="p-4">
              </div>
            </aside>

            {/* RIGHT: Creation Form */}
            <main className="flex-1 flex flex-col h-full bg-background overflow-hidden">
              <ScrollArea className="flex-1">
                <div className="p-8 max-w-3xl mx-auto space-y-6">
                  {creationMode === "single" && (
                    <Card>
                      <CardHeader>
                        <CardTitle className="flex items-center gap-2">
                          <Brain className="h-5 w-5 text-primary" />
                          Create AI-Powered Persona
                        </CardTitle>
                        <CardDescription>Enter basic attributes and let AI generate a comprehensive persona</CardDescription>
                      </CardHeader>
                      <CardContent>
                        <form onSubmit={handleSubmit} className="space-y-4">
                          <div className="grid grid-cols-3 gap-4">
                            <div className="space-y-2">
                              <Label htmlFor="age">Age</Label>
                              <Input id="age" name="age" type="number" placeholder="e.g., 45" value={formData.age} onChange={handleInputChange} required />
                            </div>
                            <div className="space-y-2">
                              <Label htmlFor="gender">Gender</Label>
                              <Input id="gender" name="gender" placeholder="e.g., Female" value={formData.gender} onChange={handleInputChange} required />
                            </div>
                            <div className="space-y-2">
                              <Label htmlFor="count">Count</Label>
                              <Input id="count" name="count" type="number" min="1" max="10" value={formData.count} onChange={handleInputChange} />
                            </div>
                          </div>
                          <div className="grid grid-cols-2 gap-4">
                            <div className="space-y-2">
                              <Label htmlFor="condition">Primary Condition</Label>
                              <Input id="condition" name="condition" placeholder="e.g., Type 2 Diabetes" value={formData.condition} onChange={handleInputChange} required />
                            </div>
                            <div className="space-y-2">
                              <Label htmlFor="location">Location</Label>
                              <Input id="location" name="location" placeholder="e.g., Austin, Texas" value={formData.location} onChange={handleInputChange} required />
                            </div>
                          </div>
                          <div className="space-y-2">
                            <Label htmlFor="concerns">Key Concerns & Context</Label>
                            <Textarea id="concerns" name="concerns" placeholder="e.g., Managing blood sugar levels, medication side effects..." value={formData.concerns} onChange={handleInputChange} className="min-h-[100px]" required />
                          </div>
                          {error && <div className="p-3 bg-red-100 border border-red-400 text-red-700 rounded-lg text-sm">{error}</div>}
                          <Button type="submit" className="w-full" disabled={generating}>
                            {generating ? <><Loader2 className="mr-2 h-4 w-4 animate-spin" />Generating {generationProgress.current}/{generationProgress.total}...</> : <><Brain className="mr-2 h-4 w-4" />Generate Persona(s)</>}
                          </Button>
                        </form>
                      </CardContent>
                    </Card>
                  )}

                  {creationMode === "bulk" && (
                    <Card>
                      <CardHeader>
                        <div className="flex items-center justify-between">
                          <div>
                            <CardTitle className="flex items-center gap-2">
                              <Users className="h-5 w-5 text-emerald-600" />
                              Bulk Persona Creation
                            </CardTitle>
                            <CardDescription>Create multiple personas with individual customization</CardDescription>
                          </div>
                          <Button onClick={addBulkTemplate} size="sm"><Plus className="h-4 w-4 mr-1" />Add Template</Button>
                        </div>
                      </CardHeader>
                      <CardContent>
                        <form onSubmit={handleBulkGenerate} className="space-y-4">
                          {bulkTemplates.map((t, i) => (
                            <Card key={t.id} className="border-muted">
                              <CardHeader className="py-3">
                                <div className="flex items-center justify-between">
                                  <CardTitle className="text-sm">Template {i + 1}</CardTitle>
                                  {bulkTemplates.length > 1 && <Button variant="ghost" size="sm" onClick={() => removeBulkTemplate(t.id)}><X className="h-4 w-4" /></Button>}
                                </div>
                              </CardHeader>
                              <CardContent className="space-y-3">
                                <div className="grid grid-cols-4 gap-3">
                                  <Input placeholder="Age" value={t.age} onChange={e => handleBulkTemplateChange(t.id, "age", e.target.value)} />
                                  <Input placeholder="Gender" value={t.gender} onChange={e => handleBulkTemplateChange(t.id, "gender", e.target.value)} />
                                  <Input placeholder="Condition" value={t.condition} onChange={e => handleBulkTemplateChange(t.id, "condition", e.target.value)} />
                                  <Input placeholder="Location" value={t.location} onChange={e => handleBulkTemplateChange(t.id, "location", e.target.value)} />
                                </div>
                                <Textarea placeholder="Concerns..." value={t.concerns} onChange={e => handleBulkTemplateChange(t.id, "concerns", e.target.value)} className="min-h-[60px]" />
                              </CardContent>
                            </Card>
                          ))}
                          <Button type="submit" className="w-full" disabled={bulkGenerating}>
                            {bulkGenerating ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Users className="mr-2 h-4 w-4" />}
                            Generate {bulkTemplates.length} Personas
                          </Button>
                        </form>
                      </CardContent>
                    </Card>
                  )}

                  {creationMode === "prompt" && (
                    <Card>
                      <CardHeader>
                        <CardTitle className="flex items-center gap-2">
                          <Wand2 className="h-5 w-5 text-purple-600" />
                          Prompt-Based Generation
                        </CardTitle>
                        <CardDescription>Describe your needs and let AI generate diverse personas</CardDescription>
                      </CardHeader>
                      <CardContent>
                        <form onSubmit={handleBulkGenerateFromPrompt} className="space-y-4">
                          <div className="space-y-2">
                            <Label>Generation Prompt</Label>
                            <Textarea placeholder="e.g., Create personas for elderly patients with chronic conditions who prefer traditional healthcare..." value={bulkPrompt} onChange={e => setBulkPrompt(e.target.value)} className="min-h-[120px]" />
                          </div>
                          <div className="grid grid-cols-2 gap-4">
                            <div className="space-y-2">
                              <Label>Number of Personas</Label>
                              <Input type="number" min="1" max="10" value={bulkCount} onChange={e => setBulkCount(parseInt(e.target.value) || 3)} />
                            </div>
                            <div className="space-y-2">
                              <Label>Age Range</Label>
                              <div className="flex items-center gap-2">
                                <Input type="number" value={bulkFilters.ageRange.min} onChange={e => setBulkFilters({ ...bulkFilters, ageRange: { ...bulkFilters.ageRange, min: parseInt(e.target.value) || 25 } })} className="w-20" />
                                <span>to</span>
                                <Input type="number" value={bulkFilters.ageRange.max} onChange={e => setBulkFilters({ ...bulkFilters, ageRange: { ...bulkFilters.ageRange, max: parseInt(e.target.value) || 75 } })} className="w-20" />
                              </div>
                            </div>
                          </div>
                          <Button type="submit" className="w-full bg-gradient-to-r from-purple-500 to-pink-500" disabled={bulkGenerating || !bulkPrompt.trim()}>
                            {bulkGenerating ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Wand2 className="mr-2 h-4 w-4" />}
                            Generate {bulkCount} Personas
                          </Button>
                        </form>
                      </CardContent>
                    </Card>
                  )}
                </div>
              </ScrollArea>
            </main>
          </div>
        )}
      </div>

      <PersonaDetailModal isOpen={isDetailModalOpen} onClose={() => setIsDetailModalOpen(false)} persona={selectedPersona} />
    </div>
  )
}
