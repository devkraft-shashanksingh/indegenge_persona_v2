"use client"

import { useState, useEffect, useMemo, useRef } from "react"
import { PersonasAPI, CohortAPI, AssetIntelligenceAPI, PanelFeedbackAPI, type AssetAnalysisResult, type AssetHistoryItem, type PanelFeedbackResponse } from "@/lib/api"
import { metricRegistry } from "@/lib/metricsRegistry"
import { useToast } from "@/components/ui/use-toast"

import { AssetIntelligenceWorkspace } from "@/components/AssetIntelligenceWorkspace"
import { SyntheticTestingWorkspace } from "@/components/SyntheticTestingWorkspace"
import { PersonaFeedbackPanel } from "@/components/PersonaFeedbackPanel"
import { PanelFeedbackSummaryComponent } from "@/components/PanelFeedbackSummary"
import { useNavigate, useLocation } from "react-router-dom"

import { Button } from "@/components/ui/button"
import { Textarea } from "@/components/ui/textarea"
import { Checkbox } from "@/components/ui/checkbox"
import { Label } from "@/components/ui/label"
import { Badge } from "@/components/ui/badge"
import { Card } from "@/components/ui/card"

import { Separator } from "@/components/ui/separator"

import { ScrollArea } from "@/components/ui/scroll-area"
import { Slider } from "@/components/ui/slider"
import {
  Search,
  Sparkles,
  Users,

  MessageSquare,
  PlayCircle,
  Plus,
  Gauge,

  Loader2,
  ImageIcon,
  Upload,
  X,
} from "lucide-react"
import { Input } from "@/components/ui/input"

// API base managed via shared client

interface Persona {
  id: number
  name: string
  age: number
  gender: string
  condition: string
  location: string
  persona_type: string
  specialty?: string | null
  brand_id?: number | null
}

const SAMPLE_MESSAGES = [
  "Introducing our new diabetes management solution with 24/7 glucose monitoring",
  "Experience relief from chronic pain with our breakthrough therapy",
  "Take control of your health journey with personalized treatment plans",
] as const

const DEFAULT_AGE_RANGE: [number, number] = [18, 100]
const PERSONA_TYPES = ["HCP", "Patient"] as const
const MAX_QUESTIONS = 5

type PersonaType = (typeof PERSONA_TYPES)[number]

interface PersonaFilters {
  ageRange: [number, number]
  personaTypes: PersonaType[]
  genders: string[]
  locations: string[]
  conditions: string[]
}

export function SimulationHub() {
  const navigate = useNavigate()
  const [personas, setPersonas] = useState<Persona[]>([])
  const [selectedPersonas, setSelectedPersonas] = useState<Set<number>>(new Set())
  const [metricSelections, setMetricSelections] = useState<Record<string, { selected: boolean; weight?: number }>>(() => {
    return metricRegistry.reduce<Record<string, { selected: boolean; weight?: number }>>((acc, metric) => {
      acc[metric.id] = { selected: !!metric.defaultSelected, weight: metric.defaultWeight ?? 1 }
      return acc
    }, {})
  })
  const selectedMetrics = useMemo(
    () => new Set(Object.entries(metricSelections).filter(([, config]) => config.selected).map(([id]) => id)),
    [metricSelections],
  )
  const [stimulusText, setStimulusText] = useState("")
  const [stimulusImages, setStimulusImages] = useState<File[]>([])
  const [imagePreviews, setImagePreviews] = useState<string[]>([])
  const [contentType, setContentType] = useState<"text" | "image" | "both">("text")
  const [questions, setQuestions] = useState<{ id: string; text: string }[]>([])

  const [analyzing, setAnalyzing] = useState(false)
  const [searchTerm, setSearchTerm] = useState("")

  const [filters, setFilters] = useState<PersonaFilters>({
    ageRange: [...DEFAULT_AGE_RANGE] as [number, number],
    personaTypes: [...PERSONA_TYPES],
    genders: [],
    locations: [],
    conditions: [],
  })

  const [recruitmentMode, setRecruitmentMode] = useState<"manual" | "ai">("manual")
  const [recruitmentPrompt, setRecruitmentPrompt] = useState("")
  const [isRecruiting, setIsRecruiting] = useState(false)
  const { toast } = useToast()

  // Refs
  const stimulusInputRef = useRef<HTMLInputElement>(null)
  const panelInputRef = useRef<HTMLInputElement>(null)



  // Asset Intelligence Mode
  const [simulationMode, setSimulationMode] = useState<"text" | "asset" | "panel" | "synthetic">("text")
  const [assetAnalysisResults, setAssetAnalysisResults] = useState<AssetAnalysisResult[]>([])
  const [assetAnalyzing, setAssetAnalyzing] = useState(false)
  const [assetFile, setAssetFile] = useState<File | null>(null)
  const [assetPreview, setAssetPreview] = useState<string | null>(null)

  // Panel Feedback Mode
  const [panelFeedbackResults, setPanelFeedbackResults] = useState<PanelFeedbackResponse | null>(null)
  const [panelFeedbackLoading, setPanelFeedbackLoading] = useState(false)
  const [panelStimulusText, setPanelStimulusText] = useState("")
  const [panelImages, setPanelImages] = useState<File[]>([])
  const [panelImagePreviews, setPanelImagePreviews] = useState<string[]>([])

  // Asset History
  const [assetHistory, setAssetHistory] = useState<AssetHistoryItem[]>([])
  const [loadingAssetHistory, setLoadingAssetHistory] = useState(false)


  // Handle pre-filled message from Analytics page (for message variants)
  const location = useLocation()
  useEffect(() => {
    const state = location.state as {
      prefillMessage?: string
      isVariant?: boolean
      originalMessage?: string
      preselectedPersonaIds?: number[]
    } | null

    if (state?.prefillMessage) {
      setStimulusText(state.prefillMessage)
    }

    if (state?.preselectedPersonaIds?.length) {
      setSelectedPersonas(new Set(state.preselectedPersonaIds))
    }

    if (state) {
      // Clear the state to prevent re-filling on refresh
      window.history.replaceState({}, document.title)
    }
  }, [location.state])

  // Auto-load asset history when switching to asset mode
  useEffect(() => {
    if (simulationMode === "asset" && assetHistory.length === 0 && !loadingAssetHistory) {
      loadAssetHistory()
    }
  }, [simulationMode])

  // Switch to results view when analysis completes


  const handleRecruit = async () => {
    if (!recruitmentPrompt.trim()) return
    setIsRecruiting(true)
    try {
      const recruitedPersonas = await PersonasAPI.recruit(recruitmentPrompt)

      if (recruitedPersonas.length === 0) {
        toast({
          title: "No Match Found",
          description: `No personas found matching: "${recruitmentPrompt}"`,
          variant: "destructive"
        })
        return
      }

      const newSelected = new Set(selectedPersonas)
      recruitedPersonas.forEach((p: Persona) => newSelected.add(p.id))
      setSelectedPersonas(newSelected)

      // Show detailed summary
      const genders = Array.from(new Set(recruitedPersonas.map((p: Persona) => p.gender)))
      const ageRange = recruitedPersonas.length > 0
        ? `${Math.min(...recruitedPersonas.map((p: Persona) => p.age))}-${Math.max(...recruitedPersonas.map((p: Persona) => p.age))}`
        : 'N/A'

      toast({
        title: "Recruitment Complete",
        description: `Found ${recruitedPersonas.length} personas. Genders: ${genders.join(', ')}. Age range: ${ageRange}.`,
      })

      // Clear the prompt after successful recruitment
      setRecruitmentPrompt("")
    } catch (error) {
      console.error("Recruitment failed", error)
      toast({
        title: "Recruitment Failed",
        description: "Could not recruit personas. Please check your connection and try again.",
        variant: "destructive"
      })
    } finally {
      setIsRecruiting(false)
    }
  }

  const filterOptions = useMemo(() => {
    const genders = new Set<string>()
    const locations = new Set<string>()
    const conditions = new Set<string>()
    const personaTypes = new Set<PersonaType>()

    personas.forEach((persona) => {
      const normalizedType = (persona.persona_type || "Patient").trim() as PersonaType
      if (PERSONA_TYPES.includes(normalizedType)) {
        personaTypes.add(normalizedType)
      }
      if (persona.gender) {
        genders.add(persona.gender)
      }
      if (persona.location) {
        locations.add(persona.location)
      }
      if (persona.condition) {
        conditions.add(persona.condition)
      }
    })

    return {
      personaTypes: PERSONA_TYPES.filter((type) => personaTypes.has(type)),
      genders: Array.from(genders).sort(),
      locations: Array.from(locations).sort(),
      conditions: Array.from(conditions).sort(),
    }
  }, [personas])

  const personaTypeOptions =
    filterOptions.personaTypes.length > 0 ? filterOptions.personaTypes : [...PERSONA_TYPES]











  const isAgeRangeDefault =
    filters.ageRange[0] === DEFAULT_AGE_RANGE[0] && filters.ageRange[1] === DEFAULT_AGE_RANGE[1]

  const activeFiltersCount = useMemo(() => {
    let count = 0
    if (!isAgeRangeDefault) count += 1
    if (filters.personaTypes.length > 0 && filters.personaTypes.length !== personaTypeOptions.length) count += 1
    if (filters.genders.length > 0) count += 1
    if (filters.locations.length > 0) count += 1
    if (filters.conditions.length > 0) count += 1
    return count
  }, [filters, isAgeRangeDefault, personaTypeOptions.length])




  const handleResetFilters = () => {
    setFilters({
      ageRange: [...DEFAULT_AGE_RANGE] as [number, number],
      personaTypes: [...personaTypeOptions],
      genders: [],
      locations: [],
      conditions: [],
    })
  }

  const toggleFilterValue = (
    key: "personaTypes" | "genders" | "locations" | "conditions",
    value: string,
  ) => {
    setFilters((prev) => {
      const currentValues = new Set(prev[key])
      if (currentValues.has(value)) {
        currentValues.delete(value)
      } else {
        currentValues.add(value)
      }

      return {
        ...prev,
        [key]: Array.from(currentValues),
      }
    })
  }

  const updateAgeRange = (value: number[]) => {
    if (value.length !== 2) return
    const [min, max] = value[0] <= value[1] ? value : [value[1], value[0]]
    setFilters((prev) => ({
      ...prev,
      ageRange: [min, max] as [number, number],
    }))
  }





  useEffect(() => {
    fetchPersonas()
  }, [])



  const fetchPersonas = async () => {
    try {
      const data = await PersonasAPI.list()
      setPersonas(data)
    } catch (error) {
      console.error("Error fetching personas:", error)
    }
  }

  const togglePersona = (id: number) => {
    const newSelected = new Set(selectedPersonas)
    if (newSelected.has(id)) {
      newSelected.delete(id)
    } else {
      newSelected.add(id)
    }
    setSelectedPersonas(newSelected)
  }

  const toggleMetric = (id: string) => {
    setMetricSelections((prev) => {
      const current = prev[id] || { selected: false, weight: metricRegistry.find((m) => m.id === id)?.defaultWeight ?? 1 }
      return {
        ...prev,
        [id]: {
          ...current,
          selected: !current.selected,
          weight: current.weight ?? metricRegistry.find((m) => m.id === id)?.defaultWeight ?? 1,
        },
      }
    })
  }

  const updateMetricWeight = (id: string, weight: number) => {
    const defaultWeight = metricRegistry.find((m) => m.id === id)?.defaultWeight ?? 1
    const safeWeight = Number.isFinite(weight) ? weight : defaultWeight
    setMetricSelections((prev) => ({
      ...prev,
      [id]: {
        ...prev[id],
        selected: prev[id]?.selected ?? true,
        weight: safeWeight,
      },
    }))
  }

  const handleImageUpload = (files: FileList | null) => {
    if (!files) return

    const newImages: File[] = []

    Array.from(files).forEach((file) => {
      if (file.type.startsWith("image/")) {
        newImages.push(file)

        // Create preview URL
        const reader = new FileReader()
        reader.onload = (e) => {
          setImagePreviews((prev) => [...prev, e.target?.result as string])
        }
        reader.readAsDataURL(file)
      }
    })

    setStimulusImages((prev) => [...prev, ...newImages])
  }

  const addQuestion = (text: string = "") => {
    if (questions.length >= MAX_QUESTIONS) {
      toast({
        title: "Limit Reached",
        description: `You can add up to ${MAX_QUESTIONS} questions.`,
        variant: "destructive"
      })
      return
    }
    setQuestions((prev) => [...prev, { id: crypto.randomUUID(), text }])
  }

  const removeQuestion = (id: string) => {
    setQuestions((prev) => prev.filter((q) => q.id !== id))
  }

  const removeImage = (index: number) => {
    setStimulusImages((prev) => prev.filter((_, i) => i !== index))
    setImagePreviews((prev) => prev.filter((_, i) => i !== index))
  }

  // Asset Intelligence handlers
  const handleAssetUpload = (files: FileList | null) => {
    if (!files || files.length === 0) return
    const file = files[0]
    if (!file.type.startsWith('image/')) {
      toast({
        title: "Invalid File",
        description: "Please upload an image file",
        variant: "destructive"
      })
      return
    }
    setAssetFile(file)
    const reader = new FileReader()
    reader.onload = (e) => {
      setAssetPreview(e.target?.result as string)
    }
    reader.readAsDataURL(file)
    setAssetAnalysisResults([]) // Clear previous results
  }

  const handleAssetAnalysis = async () => {
    if (!assetFile) {
      toast({
        title: "Missing Asset",
        description: "Please upload an asset image first",
        variant: "destructive"
      })
      return
    }
    if (selectedPersonas.size === 0) {
      toast({
        title: "No Personas Selected",
        description: "Please select at least one persona",
        variant: "destructive"
      })
      return
    }

    setAssetAnalyzing(true)
    setAssetAnalysisResults([])

    try {
      const personaIds = Array.from(selectedPersonas)
      console.log('🎨 Starting Asset Intelligence analysis...', {
        file: assetFile.name,
        personas: personaIds
      })

      const response = await AssetIntelligenceAPI.analyze(assetFile, personaIds)
      console.log('✅ Asset analysis complete:', response)

      // Debug: Log detailed info about each result's annotated_image
      response.results.forEach((result: AssetAnalysisResult, i: number) => {
        const hasImage = !!result.annotated_image
        const imageLength = result.annotated_image?.length || 0
        const imagePrefix = result.annotated_image?.substring(0, 50) || 'null'
        console.log(`📸 Result ${i} (${result.persona_name}):`, {
          hasImage,
          imageLength,
          imagePrefix,
          textSummaryLength: result.text_summary?.length || 0,
          error: result.error
        })
      })

      setAssetAnalysisResults(response.results)
    } catch (error) {
      console.error('❌ Asset analysis failed:', error)
      toast({
        title: "Analysis Failed",
        description: `Asset analysis failed: ${String(error)}`,
        variant: "destructive"
      })
    } finally {
      setAssetAnalyzing(false)
    }
  }



  // Asset History handlers
  const loadAssetHistory = async () => {
    if (loadingAssetHistory) return

    setLoadingAssetHistory(true)
    try {
      const response = await AssetIntelligenceAPI.getHistory()
      setAssetHistory(response.assets)
    } catch (error) {
      console.error('Failed to load asset history:', error)
    } finally {
      setLoadingAssetHistory(false)
    }
  }

  const loadHistoricalAsset = (historyItem: AssetHistoryItem) => {
    // Load historical results into the viewer
    setAssetAnalysisResults(historyItem.results)
    // Clear current upload preview since we're loading from history
    setAssetFile(null)
    setAssetPreview(null)
  }

  const handlePanelImageUpload = (files: FileList | null) => {
    if (!files) return
    const newImages: File[] = []
    Array.from(files).forEach((file) => {
      if (file.type.startsWith("image/")) {
        newImages.push(file)
        const reader = new FileReader()
        reader.onload = (e) => {
          setPanelImagePreviews((prev) => [...prev, e.target?.result as string])
        }
        reader.readAsDataURL(file)
      }
    })
    setPanelImages((prev) => [...prev, ...newImages])
  }

  const removePanelImage = (index: number) => {
    setPanelImages((prev) => prev.filter((_, i) => i !== index))
    setPanelImagePreviews((prev) => prev.filter((_, i) => i !== index))
  }

  // Panel Feedback handler
  const handlePanelFeedback = async () => {
    if (selectedPersonas.size === 0) {
      toast({
        title: "No Personas Selected",
        description: "Please select at least one persona",
        variant: "destructive"
      })
      return
    }

    const hasText = panelStimulusText.trim().length > 0
    const hasImages = panelImages.length > 0

    if (!hasText && !hasImages) {
      toast({
        title: "Missing Content",
        description: "Please enter marketing content or upload an image to analyze",
        variant: "destructive"
      })
      return
    }

    setPanelFeedbackLoading(true)
    setPanelFeedbackResults(null)

    try {
      const personaIds = Array.from(selectedPersonas)

      // Convert images to base64 if present
      let processedImages = undefined
      if (hasImages) {
        processedImages = await Promise.all(
          panelImages.map(async (file) => {
            return new Promise<{ filename: string; content_type: string; data: string }>((resolve, reject) => {
              const reader = new FileReader()
              reader.onload = () => {
                const base64String = (reader.result as string).split(',')[1]
                resolve({
                  filename: file.name,
                  content_type: file.type,
                  data: base64String
                })
              }
              reader.onerror = reject
              reader.readAsDataURL(file)
            })
          })
        )
      }

      // Determine content type
      let panelContentType: 'text' | 'image' | 'both' = 'text'
      if (hasText && hasImages) panelContentType = 'both'
      else if (hasImages) panelContentType = 'image'

      console.log('🎯 Starting Panel Feedback analysis...', {
        personas: personaIds.length,
        contentType: panelContentType,
        textLength: panelStimulusText.length,
        imageCount: panelImages.length
      })

      const response = await PanelFeedbackAPI.analyze(
        personaIds,
        panelStimulusText,
        processedImages,
        panelContentType
      )
      console.log('✅ Panel feedback complete:', response)
      setPanelFeedbackResults(response)
    } catch (error) {
      console.error('❌ Panel feedback failed:', error)
      toast({
        title: "Feedback Failed",
        description: `Panel feedback failed: ${String(error)}`,
        variant: "destructive"
      })
    } finally {
      setPanelFeedbackLoading(false)
    }
  }





  const handleRunAnalysis = async () => {
    if (selectedPersonas.size === 0) {
      toast({
        title: "No Personas",
        description: "Please select at least one persona",
        variant: "destructive"
      })
      return
    }

    const trimmedQuestions = questions.map((q) => q.text.trim()).filter((q) => q.length > 0)

    if (questions.some((q) => q.text.trim().length === 0) && questions.length > 0) {
      toast({
        title: "Empty Questions",
        description: "Please fill in all questions or remove empty ones.",
        variant: "destructive"
      })
      return
    }

    if (trimmedQuestions.length > MAX_QUESTIONS) {
      toast({
        title: "Too Many Questions",
        description: `Please limit qualitative questions to ${MAX_QUESTIONS}.`,
        variant: "destructive"
      })
      return
    }
    if (selectedMetrics.size === 0) {
      toast({
        title: "No Metrics",
        description: "Please select at least one metric",
        variant: "destructive"
      })
      return
    }

    // Validate based on content type
    const hasText = stimulusText.trim() !== ""
    const hasImages = stimulusImages.length > 0

    if (contentType === "text" && !hasText) {
      toast({
        title: "Missing Text",
        description: "Please enter stimulus text",
        variant: "destructive"
      })
      return
    }
    if (contentType === "image" && !hasImages) {
      toast({
        title: "Missing Image",
        description: "Please upload at least one image",
        variant: "destructive"
      })
      return
    }
    if (contentType === "both" && (!hasText || !hasImages)) {
      toast({
        title: "Missing Content",
        description: "Please provide both text and images for analysis",
        variant: "destructive"
      })
      return
    }

    setAnalyzing(true)
    try {
      const selectedMetricIds = Array.from(selectedMetrics)
      const metricWeights = selectedMetricIds.reduce<Record<string, number>>((acc, id) => {
        const selection = metricSelections[id]
        acc[id] = selection?.weight ?? metricRegistry.find((m) => m.id === id)?.defaultWeight ?? 1
        return acc
      }, {})

      let response: any
      const personaIds = Array.from(selectedPersonas)

      if (contentType === "text") {
        const payload = {
          persona_ids: personaIds,
          stimulus_text: stimulusText,
          metrics: selectedMetricIds,
          metric_weights: metricWeights,
          questions: trimmedQuestions.length > 0 ? trimmedQuestions : undefined,
        }

        console.log("🚀 Sending JSON request:", payload)
        response = await CohortAPI.analyze(payload)
      } else {
        // Create FormData for file upload (image-only or multimodal)
        const formData = new FormData()
        formData.append("persona_ids", JSON.stringify(personaIds))
        formData.append("metrics", JSON.stringify(selectedMetricIds))
        formData.append("metric_weights", JSON.stringify(metricWeights))
        formData.append("content_type", contentType)

        if (hasText) {
          formData.append("stimulus_text", stimulusText)
        }
        if (trimmedQuestions.length > 0) {
          formData.append("questions", JSON.stringify(trimmedQuestions))
        }
        stimulusImages.forEach((file) => {
          formData.append("stimulus_images", file)
        })

        console.log("🚀 Sending FormData request:", {
          persona_ids: formData.get("persona_ids"),
          metrics: formData.get("metrics"),
          metric_weights: formData.get("metric_weights"),
          content_type: formData.get("content_type"),
          stimulus_text: formData.get("stimulus_text"),
          questions: formData.get("questions"),
          stimulus_images_count: stimulusImages.length,
        })

        response = await CohortAPI.analyze(formData)
      }

      console.log("✅ Received response:", {
        responseType: typeof response,
        cohort_size: response?.cohort_size,
        individual_responses_count: response?.individual_responses?.length,
        has_summary_statistics: !!response?.summary_statistics,
        responseKeys: response ? Object.keys(response) : null,
      })

      // Validate response structure
      if (!response) {
        throw new Error("Received null/undefined response from server")
      }
      if (!response.individual_responses || !Array.isArray(response.individual_responses)) {
        throw new Error("Response missing individual_responses array")
      }
      if (response.individual_responses.length === 0) {
        throw new Error("Response contains no individual responses")
      }


      console.log("🧭 Navigating to analytics with data:", {
        cohort_size: response.cohort_size,
        responses_count: response.individual_responses.length,
      })

      navigate("/analytics", {
        state: {
          analysisResults: response,
          originalImages: stimulusImages, // Pass original images for improvement
          contentType: contentType
        }
      })

    } catch (error) {
      console.error("❌ Error running analysis:", error)
      const errorStr = String(error)
      toast({
        title: "Analysis Error",
        description: `Error running analysis: ${errorStr}`,
        variant: "destructive"
      })
    } finally {
      setAnalyzing(false)
    }
  }

  const filteredPersonas = useMemo(() => {
    const term = searchTerm.trim().toLowerCase()

    return personas.filter((persona) => {
      const normalizedPersonaType = (persona.persona_type || "Patient").trim().toLowerCase()
      const normalizedGender = (persona.gender || "").trim().toLowerCase()
      const normalizedLocation = (persona.location || "").trim().toLowerCase()
      const normalizedCondition = (persona.condition || "").trim().toLowerCase()

      const matchesSearch =
        term.length === 0 ||
        persona.name.toLowerCase().includes(term) ||
        normalizedCondition.includes(term) ||
        normalizedLocation.includes(term)

      if (!matchesSearch) {
        return false
      }

      const [minAge, maxAge] = filters.ageRange
      const matchesAge = persona.age >= minAge && persona.age <= maxAge

      const matchesPersonaType =
        filters.personaTypes.length === 0 ||
        filters.personaTypes.some((type) => type.toLowerCase() === normalizedPersonaType)

      const matchesGender =
        filters.genders.length === 0 ||
        filters.genders.some((gender) => gender.trim().toLowerCase() === normalizedGender)

      const matchesLocation =
        filters.locations.length === 0 ||
        filters.locations.some((location) => location.trim().toLowerCase() === normalizedLocation)

      const matchesCondition =
        filters.conditions.length === 0 ||
        filters.conditions.some((condition) => condition.trim().toLowerCase() === normalizedCondition)

      return matchesAge && matchesPersonaType && matchesGender && matchesLocation && matchesCondition
    })
  }, [filters, personas, searchTerm])



  return (
    <div className="flex flex-col h-full bg-background overflow-hidden">
      {/* Slim Header */}
      <header className="h-14 border-b bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60 flex items-center justify-between px-4 shrink-0 z-50">
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2 text-primary font-semibold">
            <div className="p-1.5 bg-primary/10 rounded-md">
              <PlayCircle className="h-5 w-5" />
            </div>
            <span>Simulation Hub</span>
          </div>
          <Separator orientation="vertical" className="h-6" />
          <div className="flex bg-muted/50 p-1.5 rounded-xl border shadow-sm">
            <button
              onClick={() => setSimulationMode("text")}
              className={`px-4 py-2 text-sm font-semibold rounded-lg transition-all flex items-center gap-2 ${simulationMode === "text"
                ? "bg-background shadow text-primary ring-1 ring-black/5"
                : "text-muted-foreground hover:text-foreground hover:bg-background/50"
                }`}
            >
              <div className={`p-1 rounded-md ${simulationMode === "text" ? "bg-primary/10 text-primary" : "bg-transparent"}`}>
                <MessageSquare className="h-4 w-4" />
              </div>
              <span className="bg-transparent">Persona Simulation</span>
            </button>
            <button
              onClick={() => setSimulationMode("asset")}
              className={`px-4 py-2 text-sm font-semibold rounded-lg transition-all flex items-center gap-2 ${simulationMode === "asset"
                ? "bg-background shadow text-primary ring-1 ring-black/5"
                : "text-muted-foreground hover:text-foreground hover:bg-background/50"
                }`}
            >
              <div className={`p-1 rounded-md ${simulationMode === "asset" ? "bg-primary/10 text-primary" : "bg-transparent"}`}>
                <ImageIcon className="h-4 w-4" />
              </div>
              <span>Asset Intelligence</span>
            </button>
            <button
              onClick={() => setSimulationMode("panel")}
              className={`px-4 py-2 text-sm font-semibold rounded-lg transition-all flex items-center gap-2 ${simulationMode === "panel"
                ? "bg-background shadow text-primary ring-1 ring-black/5"
                : "text-muted-foreground hover:text-foreground hover:bg-background/50"
                }`}
            >
              <div className={`p-1 rounded-md ${simulationMode === "panel" ? "bg-primary/10 text-primary" : "bg-transparent"}`}>
                <Users className="h-4 w-4" />
              </div>
              <span>Panel Feedback</span>
            </button>
            <button
              onClick={() => setSimulationMode("synthetic")}
              className={`px-4 py-2 text-sm font-semibold rounded-lg transition-all flex items-center gap-2 ${simulationMode === "synthetic"
                ? "bg-background shadow text-primary ring-1 ring-black/5"
                : "text-muted-foreground hover:text-foreground hover:bg-background/50"
                }`}
            >
              <div className={`p-1 rounded-md ${simulationMode === "synthetic" ? "bg-primary/10 text-primary" : "bg-transparent"}`}>
                <Gauge className="h-4 w-4" />
              </div>
              <span>Synthetic Testing</span>
            </button>
          </div>
        </div>

        <div className="flex items-center gap-4">
          {simulationMode === "text" && (
            <div className="hidden md:flex items-center gap-2 text-sm text-muted-foreground">
              <span className="flex items-center gap-1.5">
                <Users className="h-4 w-4" />
                <span className="font-medium text-foreground">{selectedPersonas.size}</span> selected
              </span>
              <span className="text-border">|</span>
              <span className="flex items-center gap-1.5">
                <Gauge className="h-4 w-4" />
                <span className="font-medium text-foreground">{selectedMetrics.size}</span> metrics
              </span>
            </div>
          )}
        </div>
      </header>

      {/* Main Content Area */}
      <div className="flex-1 overflow-hidden">
        {simulationMode === "asset" ? (
          <AssetIntelligenceWorkspace
            results={assetAnalysisResults}
            history={assetHistory}
            isLoading={loadingAssetHistory}
            isAnalyzing={assetAnalyzing}
            onUpload={handleAssetUpload}
            onAnalyze={handleAssetAnalysis}
            onLoadHistory={loadHistoricalAsset}
            onBack={() => setSimulationMode("text")}
            assetPreview={assetPreview}
            selectedPersonasCount={selectedPersonas.size}
            brandId={personas[0]?.brand_id ?? null}
            selectedPersonaIds={Array.from(selectedPersonas)}
            onViewKnowledgeGraph={() => navigate('/knowledge-graph')}
            allPersonas={personas}
            onTogglePersona={togglePersona}
          />
        ) : simulationMode === "synthetic" ? (
          <SyntheticTestingWorkspace
            selectedPersonaIds={Array.from(selectedPersonas)}
            allPersonas={personas}
          />
        ) : simulationMode === "panel" ? (
          <div className="flex h-full">
            {/* LEFT: Input Panel */}
            <aside className="w-[400px] border-r bg-muted/10 flex flex-col shrink-0 p-4 space-y-4">
              <div className="space-y-2">
                <h3 className="font-semibold text-base flex items-center gap-2">
                  <Users className="h-5 w-5 text-primary" />
                  Panel Feedback
                </h3>
                <p className="text-sm text-muted-foreground">
                  Get structured feedback from multiple personas on your marketing content.
                </p>
              </div>

              {/* Persona Selection Summary */}
              <div className="p-3 bg-background rounded-lg border">
                <div className="flex items-center justify-between">
                  <span className="text-sm font-medium">Selected Personas</span>
                  <Badge variant="secondary">{selectedPersonas.size}</Badge>
                </div>
                {selectedPersonas.size === 0 && (
                  <p className="text-xs text-muted-foreground mt-1">
                    Use the Persona Simulation tab to select personas first.
                  </p>
                )}
              </div>

              {/* Marketing Content Input */}
              <div className="flex-1 flex flex-col space-y-4 overflow-hidden">
                <div className="space-y-2">
                  <Label className="text-sm font-medium">Marketing Content (Optional if image provided)</Label>
                  <Textarea
                    placeholder="Enter your marketing message, email copy, or campaign text here..."
                    className="min-h-[150px] resize-none"
                    value={panelStimulusText}
                    onChange={(e) => setPanelStimulusText(e.target.value)}
                  />
                </div>

                <div className="space-y-2 flex-1 flex flex-col overflow-hidden">
                  <div className="flex items-center justify-between">
                    <Label className="text-sm font-medium">Visual Assets (Optional)</Label>
                    <Button
                      variant="outline"
                      size="sm"
                      className="h-8 text-xs"
                      onClick={() => panelInputRef.current?.click()}
                    >
                      <Upload className="h-3 w-3 mr-2" />
                      Add Images
                    </Button>
                    <input
                      ref={panelInputRef}
                      id="panel-image-upload"
                      type="file"
                      multiple
                      accept="image/*"
                      className="hidden"
                      onChange={(e) => handlePanelImageUpload(e.target.files)}
                    />
                  </div>

                  <div className="flex-1 overflow-auto border rounded-lg bg-background/50 p-2">
                    {panelImagePreviews.length > 0 ? (
                      <div className="grid grid-cols-2 gap-2">
                        {panelImagePreviews.map((preview, idx) => (
                          <div key={idx} className="relative group aspect-square rounded-md overflow-hidden border">
                            <img src={preview} alt="Preview" className="w-full h-full object-cover" />
                            <button
                              onClick={() => removePanelImage(idx)}
                              className="absolute top-1 right-1 p-1 bg-background/80 hover:bg-destructive hover:text-destructive-foreground rounded-full opacity-0 group-hover:opacity-100 transition-opacity"
                            >
                              <X className="h-3 w-3" />
                            </button>
                          </div>
                        ))}
                      </div>
                    ) : (
                      <div className="h-full flex flex-col items-center justify-center text-muted-foreground py-8">
                        <ImageIcon className="h-8 w-8 mb-2 opacity-20" />
                        <p className="text-xs">No images uploaded</p>
                      </div>
                    )}
                  </div>
                </div>
              </div>

              {/* Run Analysis Button */}
              <Button
                onClick={handlePanelFeedback}
                disabled={panelFeedbackLoading || selectedPersonas.size === 0 || (!panelStimulusText.trim() && panelImages.length === 0)}
                className="w-full"
              >
                {panelFeedbackLoading ? (
                  <>
                    <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                    Analyzing...
                  </>
                ) : (
                  <>
                    <PlayCircle className="h-4 w-4 mr-2" />
                    Get Panel Feedback
                  </>
                )}
              </Button>
            </aside>

            {/* RIGHT: Results Panel */}
            <main className="flex-1 overflow-auto p-6 space-y-6">
              {panelFeedbackLoading ? (
                <div className="flex items-center justify-center h-full">
                  <div className="text-center space-y-4">
                    <Loader2 className="h-12 w-12 animate-spin text-primary mx-auto" />
                    <p className="text-muted-foreground">Analyzing with {selectedPersonas.size} personas...</p>
                  </div>
                </div>
              ) : panelFeedbackResults ? (
                <div className="space-y-6">
                  <PanelFeedbackSummaryComponent
                    summary={panelFeedbackResults.summary}
                    personaCount={panelFeedbackResults.metadata.persona_count}
                  />
                  <PersonaFeedbackPanel cards={panelFeedbackResults.persona_cards} />
                </div>
              ) : (
                <div className="flex items-center justify-center h-full text-center">
                  <div className="space-y-4 max-w-md">
                    <div className="p-4 bg-primary/5 rounded-full w-fit mx-auto">
                      <Users className="h-12 w-12 text-primary" />
                    </div>
                    <h3 className="text-lg font-semibold">Panel Feedback</h3>
                    <p className="text-muted-foreground">
                      Select personas and enter your marketing content to get structured feedback with Clean Read, Key Themes, Strengths, and Weaknesses from each persona.
                    </p>
                  </div>
                </div>
              )}
            </main>
          </div>
        ) : (
          <div className="flex h-full w-full">
            {/* LEFT PANE: Audience Selection (Wider, Studio Style) */}
            <aside className="w-[420px] border-r bg-muted/10 flex flex-col shrink-0 transition-all">
              <div className="p-4 border-b bg-background/50 backdrop-blur space-y-4">
                <div className="flex items-center justify-between">
                  <h3 className="font-semibold text-base flex items-center gap-2">
                    <Users className="h-5 w-5 text-primary" />
                    Target Audience
                  </h3>
                  <div className="flex items-center gap-2">
                    {activeFiltersCount > 0 && (
                      <Button variant="ghost" size="sm" onClick={handleResetFilters} className="h-6 text-[10px] text-muted-foreground hover:text-primary">
                        Reset Filters
                      </Button>
                    )}
                    <Badge variant="secondary" className="font-mono text-xs">{filteredPersonas.length}</Badge>
                  </div>
                </div>

                {/* Recruitment Mode Tabs */}
                <div className="flex p-1 bg-muted rounded-lg">
                  <button
                    onClick={() => setRecruitmentMode("manual")}
                    className={`flex-1 py-1.5 text-xs font-semibold rounded-md transition-all ${recruitmentMode === "manual" ? "bg-background shadow-sm text-foreground" : "text-muted-foreground hover:text-foreground/80"}`}
                  >
                    Browse Library
                  </button>
                  <button
                    onClick={() => setRecruitmentMode("ai")}
                    className={`flex-1 py-1.5 text-xs font-semibold rounded-md transition-all ${recruitmentMode === "ai" ? "bg-background shadow-sm text-primary" : "text-muted-foreground hover:text-foreground/80"}`}
                  >
                    AI Recruit
                  </button>
                </div>

                {/* Search / AI Input */}
                {recruitmentMode === "ai" ? (
                  <div className="space-y-2 animate-in fade-in slide-in-from-top-2">
                    <Textarea
                      placeholder="Describe your ideal target audience (e.g., 'Diabetic patients over 50 in urban areas')..."
                      className="text-sm h-24 resize-none bg-background focus-visible:ring-primary"
                      value={recruitmentPrompt}
                      onChange={(e) => setRecruitmentPrompt(e.target.value)}
                    />
                    <Button size="sm" className="w-full text-xs" onClick={handleRecruit} disabled={isRecruiting || !recruitmentPrompt.trim()}>
                      {isRecruiting ? <Loader2 className="h-3 w-3 animate-spin mr-2" /> : <Sparkles className="h-3 w-3 mr-2" />}
                      Find Matching Personas
                    </Button>
                  </div>
                ) : (
                  <div className="space-y-3 animate-in fade-in slide-in-from-top-2">
                    <div className="relative">
                      <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
                      <Input
                        placeholder="Search by name, condition, location..."
                        className="pl-9 h-9 text-sm bg-background"
                        value={searchTerm}
                        onChange={(e) => setSearchTerm(e.target.value)}
                      />
                    </div>

                    {/* Horizontal Compact Filters */}
                    <div className="flex flex-col gap-2">
                      <div className="flex items-center gap-2">
                        <span className="text-[10px] font-uppercase tracking-wider text-muted-foreground font-semibold w-12 shrink-0">AGE</span>
                        <Slider
                          value={filters.ageRange}
                          onValueChange={updateAgeRange}
                          min={DEFAULT_AGE_RANGE[0]}
                          max={DEFAULT_AGE_RANGE[1]}
                          step={1}
                          className="flex-1 py-1.5"
                        />
                        <span className="text-[10px] text-muted-foreground font-mono w-16 text-right">{filters.ageRange[0]} - {filters.ageRange[1]}</span>
                      </div>

                      <div className="flex items-center gap-2">
                        <span className="text-[10px] font-uppercase tracking-wider text-muted-foreground font-semibold w-12 shrink-0">TYPE</span>
                        <div className="flex gap-1 flex-1">
                          {personaTypeOptions.map(type => (
                            <button
                              key={type}
                              onClick={() => toggleFilterValue("personaTypes", type)}
                              className={`px-2 py-1 rounded text-[10px] uppercase font-bold border transition-all ${filters.personaTypes.includes(type)
                                ? "bg-primary/10 border-primary text-primary"
                                : "bg-background border-border text-muted-foreground hover:border-primary/50"
                                }`}
                            >
                              {type}
                            </button>
                          ))}
                        </div>
                      </div>
                    </div>
                  </div>
                )}
              </div>

              {/* Persona List */}
              <div className="bg-muted/5 px-4 py-2 border-b flex justify-between items-center">
                <div className="text-xs text-muted-foreground font-medium">Results ({filteredPersonas.length})</div>
                <Button variant="ghost" size="sm" className="h-5 text-[10px] px-1" onClick={() => setSelectedPersonas(new Set(filteredPersonas.map(p => p.id)))}>
                  Select All
                </Button>
              </div>

              <ScrollArea className="flex-1 bg-muted/5">
                <div className="p-4 grid grid-cols-1 gap-3">
                  {filteredPersonas.slice(0, 100).map(persona => (
                    <div
                      key={persona.id}
                      onClick={() => togglePersona(persona.id)}
                      className={`
                          group relative p-3 rounded-xl border cursor-pointer transition-all hover:shadow-md
                          ${selectedPersonas.has(persona.id)
                          ? 'bg-background border-primary shadow-sm ring-1 ring-primary/20'
                          : 'bg-background border-border hover:border-primary/50'}
                      `}
                    >
                      <div className="flex items-start gap-3">
                        <Checkbox
                          checked={selectedPersonas.has(persona.id)}
                          className="mt-1"
                          onChange={() => togglePersona(persona.id)}
                        />
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center justify-between mb-0.5">
                            <span className="font-semibold text-sm truncate pr-2">{persona.name}</span>
                            <Badge variant={persona.persona_type === 'HCP' ? 'default' : 'secondary'} className="text-[10px] h-4 px-1 rounded-sm">
                              {persona.persona_type === 'HCP' ? 'HCP' : 'Pt'}
                            </Badge>
                          </div>
                          <div className="text-xs text-muted-foreground flex flex-wrap gap-x-3 gap-y-1">
                            <span className="flex items-center gap-1"><span className="w-1 h-1 rounded-full bg-muted-foreground/50" /> {persona.age} yrs</span>
                            {persona.condition && <span className="flex items-center gap-1 truncate"><span className="w-1 h-1 rounded-full bg-muted-foreground/50" /> {persona.condition}</span>}
                            {persona.location && <span className="flex items-center gap-1 truncate"><span className="w-1 h-1 rounded-full bg-muted-foreground/50" /> {persona.location}</span>}
                          </div>
                        </div>
                      </div>
                    </div>
                  ))}
                  {filteredPersonas.length === 0 && (
                    <div className="text-center py-8 text-muted-foreground text-sm">
                      No personas match your filters
                    </div>
                  )}
                </div>
              </ScrollArea>
            </aside>

            {/* RIGHT PANE: Workspace / Studio */}
            <main className="flex-1 flex flex-col h-full bg-background relative overflow-hidden">
              <ScrollArea className="flex-1">
                <div className="p-8 max-w-5xl mx-auto space-y-10 pb-32">

                  {/* Section 1: Stimulus */}
                  <section className="space-y-4">
                    <div className="flex items-center justify-between">
                      <div>
                        <h2 className="text-xl font-bold flex items-center gap-2 text-foreground">
                          <MessageSquare className="h-5 w-5 text-primary" />
                          Input Stimulus
                        </h2>
                        <p className="text-sm text-muted-foreground mt-1">Provide the content you want the personas to evaluate.</p>
                      </div>
                      <div className="flex p-1 bg-muted rounded-lg border">
                        <button onClick={() => setContentType("text")} className={`px-3 py-1.5 text-xs font-semibold rounded ${contentType === "text" ? "bg-background shadow text-foreground" : "text-muted-foreground hover:text-foreground"}`}>Text</button>
                        <button onClick={() => setContentType("image")} className={`px-3 py-1.5 text-xs font-semibold rounded ${contentType === "image" ? "bg-background shadow text-foreground" : "text-muted-foreground hover:text-foreground"}`}>Image</button>
                        <button onClick={() => setContentType("both")} className={`px-3 py-1.5 text-xs font-semibold rounded ${contentType === "both" ? "bg-background shadow text-foreground" : "text-muted-foreground hover:text-foreground"}`}>Multi-Modal</button>
                      </div>
                    </div>

                    <Card className="border-muted-foreground/10 shadow-sm overflow-hidden bg-muted/5 group focus-within:ring-2 ring-primary/20 transition-all">
                      {(contentType === "text" || contentType === "both") && (
                        <div className="p-4 space-y-3">
                          <Label className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">Marketing Copy / Message</Label>
                          <Textarea
                            placeholder="Enter marketing copy, email subject lines, or clinical messaging..."
                            className="min-h-[180px] text-base resize-y bg-background border-muted-foreground/10 focus-visible:ring-0"
                            value={stimulusText}
                            onChange={(e) => setStimulusText(e.target.value)}
                          />
                          <div className="flex gap-2 justify-end">
                            {SAMPLE_MESSAGES.map((msg, idx) => (
                              <button key={idx} onClick={() => setStimulusText(msg)} className="text-[10px] text-muted-foreground hover:text-primary transition-colors underline decoration-dotted">
                                Sample {idx + 1}
                              </button>
                            ))}
                          </div>
                        </div>
                      )}

                      {(contentType === "image" || contentType === "both") && (
                        <>
                          {(contentType === "both") && <Separator />}
                          <div className="p-6 bg-muted/20 space-y-4">
                            <div
                              onClick={() => stimulusInputRef.current?.click()}
                              className="border-2 border-dashed border-muted-foreground/20 rounded-xl p-8 text-center hover:bg-background/50 hover:border-primary/40 transition-all cursor-pointer"
                            >
                              <input
                                ref={stimulusInputRef}
                                id="sim-img-upload"
                                type="file"
                                multiple
                                accept="image/*"
                                className="hidden"
                                onChange={(e) => handleImageUpload(e.target.files)}
                              />
                              <div className="mx-auto w-12 h-12 rounded-full bg-primary/10 flex items-center justify-center mb-3 text-primary">
                                <Upload className="h-6 w-6" />
                              </div>
                              <p className="text-sm font-medium">Drag & drop visual assets</p>
                              <p className="text-xs text-muted-foreground mt-1">or click to browse files</p>
                            </div>

                            {/* Previews */}
                            {imagePreviews.length > 0 && (
                              <div className="grid grid-cols-3 gap-4">
                                {imagePreviews.map((src, i) => (
                                  <div key={i} className="relative aspect-video bg-black/5 rounded-lg overflow-hidden border group">
                                    <img src={src} className="w-full h-full object-cover" alt="" />
                                    <button onClick={(e) => { e.stopPropagation(); removeImage(i); }} className="absolute top-1 right-1 p-1 bg-black/50 text-white rounded opacity-0 group-hover:opacity-100 transition-opacity">
                                      <X className="h-3 w-3" />
                                    </button>
                                  </div>
                                ))}
                              </div>
                            )}
                          </div>
                        </>
                      )}
                    </Card>
                  </section>

                  {/* Section 2: Metrics */}
                  <section className="space-y-4">
                    <div className="flex items-center justify-between">
                      <div>
                        <h2 className="text-xl font-bold flex items-center gap-2 text-foreground">
                          <Gauge className="h-5 w-5 text-primary" />
                          Analysis Metrics
                        </h2>
                        <p className="text-sm text-muted-foreground mt-1">Select dimensions for AI evaluation.</p>
                      </div>
                    </div>

                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                      {metricRegistry.map(metric => {
                        const isSelected = metricSelections[metric.id]?.selected
                        const weight = metricSelections[metric.id]?.weight ?? 1
                        return (
                          <div
                            key={metric.id}
                            className={`
                                    relative p-4 rounded-xl border transition-all duration-200
                                    ${isSelected ? 'bg-background border-primary/50 shadow-sm ring-1 ring-primary/10' : 'bg-card border-border hover:border-primary/30'}
                                  `}
                          >
                            <div className="flex items-start gap-3">
                              <Checkbox
                                checked={isSelected}
                                onChange={() => toggleMetric(metric.id)}
                                className="mt-1"
                              />
                              <div className="flex-1">
                                <div className="flex items-center justify-between">
                                  <span className={`font-semibold text-sm ${isSelected ? 'text-foreground' : 'text-muted-foreground'}`}>{metric.label}</span>
                                  {metric.icon && <metric.icon.component className={`h-5 w-5 ${metric.icon.color || 'text-muted-foreground/50'}`} />}
                                </div>
                                <p className="text-xs text-muted-foreground mt-1 line-clamp-2">{metric.description}</p>

                                {isSelected && (
                                  <div className="mt-3 pt-3 border-t flex items-center gap-3 animate-in fade-in">
                                    <span className="text-[10px] font-medium text-muted-foreground w-12">Weight</span>
                                    <Slider
                                      value={[weight]}
                                      max={3}
                                      step={0.5}
                                      className="flex-1"
                                      onValueChange={([v]) => updateMetricWeight(metric.id, v)}
                                    />
                                    <span className="text-[10px] w-4 text-right">{weight}x</span>
                                  </div>
                                )}
                              </div>
                            </div>
                          </div>
                        )
                      })}
                    </div>
                  </section>

                  {/* Section 3: Questions */}
                  <section className="space-y-4 opacity-80 hover:opacity-100 transition-opacity">
                    <div className="flex items-center justify-between">
                      <h2 className="text-lg font-semibold flex items-center gap-2">
                        <MessageSquare className="h-4 w-4" /> Qualitative Questions
                      </h2>
                    </div>
                    <div className="bg-card border rounded-lg p-4 space-y-3">
                      {questions.map((q, idx) => (
                        <div key={q.id} className="flex gap-2">
                          <Input value={q.text} readOnly className="h-9 bg-muted/50" />
                          <Button variant="ghost" size="icon" className="h-9 w-9 text-muted-foreground" onClick={() => removeQuestion(q.id)}>
                            <X className="h-4 w-4" />
                          </Button>
                        </div>
                      ))}
                      <div className="flex gap-2">
                        <Input
                          placeholder="Add a specific question for personas..."
                          className="h-9"
                          onKeyDown={(e) => {
                            if (e.key === 'Enter') {
                              const target = e.target as HTMLInputElement;
                              if (target.value) {
                                addQuestion(target.value);
                                target.value = '';
                              }
                            }
                          }}
                        />
                        <Button size="sm" variant="outline" onClick={() => { /* Triggered via Enter mainly */ }}>
                          <Plus className="h-4 w-4" />
                        </Button>
                      </div>
                    </div>
                  </section>
                </div>
              </ScrollArea>

              {/* Fixed Footer Floating Action */}
              <div className="absolute bottom-6 left-1/2 -translate-x-1/2 w-full max-w-md pointer-events-none">
                <div className="pointer-events-auto shadow-2xl rounded-full p-1 bg-background/50 backdrop-blur-xl border border-white/20">
                  <Button
                    disabled={analyzing || selectedPersonas.size === 0}
                    onClick={handleRunAnalysis}
                    className="w-full h-12 rounded-full text-lg font-semibold bg-gradient-to-r from-primary to-violet-600 hover:opacity-90 transition-all shadow-lg"
                  >
                    {analyzing ? (
                      <>
                        <Loader2 className="mr-2 h-5 w-5 animate-spin" /> Simulating...
                      </>
                    ) : (
                      <>
                        <PlayCircle className="mr-2 h-5 w-5" /> Run Simulation ({selectedPersonas.size})
                      </>
                    )}
                  </Button>
                </div>
              </div>
            </main>
          </div>
        )}
      </div>
    </div>
  )
}
