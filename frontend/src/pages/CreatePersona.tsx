"use client"

import React, { useEffect, useMemo, useState } from "react"
import { useNavigate, useSearchParams } from "react-router-dom"
import { PersonasAPI, BrandsAPI, DiscoveryAPI } from "@/lib/api"
import type { DiscoveredSegment } from "@/lib/api"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../components/ui/card"
import { Button } from "../components/ui/button"
import { Badge } from "../components/ui/badge"
import { Separator } from "../components/ui/separator"

import {
  Loader2,
  Sparkles,
  Target,
  CheckCircle,
  Settings,
  UserPlus,
  ArrowLeft,
  Search,
  FileText,
  Zap,
} from "lucide-react"


import { LiveGenerationFeed } from "../components/LiveGenerationFeed"
import { useToast } from "../components/ui/use-toast"

interface BrandOption {
  id: number
  name: string
}

interface FieldStatus {
  key: string
  label: string
  complete: boolean
  message?: string
}



export function CreatePersona() {
  const navigate = useNavigate()
  const { toast } = useToast()
  const [searchParams] = useSearchParams()
  const urlBrandId = searchParams.get('brand_id')
  const urlCondition = searchParams.get('condition')

  const [generating, setGenerating] = useState(false)
  const [generationProgress, setGenerationProgress] = useState({ current: 0, total: 0 })
  const [recentlyCreated, setRecentlyCreated] = useState<{ ids: number[]; names: string[] }>({ ids: [], names: [] })
  // Simplified: Only "research" mode remains
  const [creationMode] = useState<"research">("research")

  // === Research Discovery State ===
  const [discoveryBrandId, setDiscoveryBrandId] = useState<number | null>(urlBrandId ? parseInt(urlBrandId) : null)
  const [discoveredSegments, setDiscoveredSegments] = useState<DiscoveredSegment[]>([])
  const [discovering, setDiscovering] = useState(false)
  const [directEntryName, setDirectEntryName] = useState("")
  const [directEntryDescription, setDirectEntryDescription] = useState("")
  const [selectedSegment, setSelectedSegment] = useState<DiscoveredSegment | null>(null)
  const [generatingFromDiscovery, setGeneratingFromDiscovery] = useState(false)
  const [discoveryError, setDiscoveryError] = useState<string | null>(null)
  const [generationTarget, setGenerationTarget] = useState<{ name: string, description: string } | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [reviewPersona, setReviewPersona] = useState<any | null>(null)

  const [brands, setBrands] = useState<BrandOption[]>([])




  // === Research Discovery Handlers ===
  const handleDiscoverSegments = async () => {
    if (!discoveryBrandId) {
      setDiscoveryError("Please select a brand first.")
      return
    }
    setDiscovering(true)
    setDiscoveryError(null)
    setDiscoveredSegments([])
    try {
      const result = await DiscoveryAPI.discoverSegments(discoveryBrandId)
      setDiscoveredSegments(result.segments || [])
      if ((result.segments || []).length === 0) {
        setDiscoveryError("No segments found. Ensure documents have been uploaded and processed for this brand.")
      }
    } catch (err: any) {
      setDiscoveryError(err?.response?.data?.detail || "Discovery failed. Check that brand has documents.")
    } finally {
      setDiscovering(false)
    }
  }

  const handleGenerateFromSegment = async (segmentName: string, segmentDescription: string) => {
    if (!discoveryBrandId) return

    // Set state to trigger the LiveGenerationFeed modal
    setGenerationTarget({ name: segmentName, description: segmentDescription })
    setGeneratingFromDiscovery(true)
  }

  const handleGenerationComplete = (persona: any) => {
    setGeneratingFromDiscovery(false)
    // Set for review instead of auto-finish
    setReviewPersona(persona)
  }

  const handleSavePersona = async () => {
    if (!reviewPersona || !discoveryBrandId) return
    setGenerating(true)
    setError(null)
    try {
      const saved = await DiscoveryAPI.saveGenerated({
        brand_id: discoveryBrandId,
        segment_name: generationTarget?.name || reviewPersona.name,
        persona_profile: reviewPersona
      })
      setReviewPersona(null)
      // Clear generation target as well
      setGenerationTarget(null)

      setRecentlyCreated({ ids: [saved.id], names: [saved.name] })
      toast({
        title: "Persona Saved Successfully",
        description: `${saved.name} has been added to your library.`,
        duration: 5000,
      })
    } catch (err: any) {
      console.error(err)
      toast({
        title: "Save Failed",
        description: err.message || "Could not save persona.",
        variant: "destructive",
      })
      setError(err.message || "Save failed")
    } finally {
      setGenerating(false)
    }
  }

  const handleDiscardPersona = () => {
    setReviewPersona(null)
    setGenerationTarget(null)
    toast({
      title: "Persona Discarded",
      description: "The generated persona was not saved.",
    })
  }

  const handleGenerationError = (error: string) => {
    setGeneratingFromDiscovery(false)
    setGenerationTarget(null)
    setDiscoveryError(error)
    toast({
      title: "Generation Failed",
      description: error,
      variant: "destructive",
      duration: 5000,
    })
  }

  const handleNavigateToSimulator = (personaIds: number[]) => {
    if (personaIds.length === 0) return
    navigate('/simulation', { state: { preselectedPersonaIds: personaIds } })
  }

  const handleDirectEntry = async () => {
    if (!directEntryName.trim()) {
      setDiscoveryError("Please enter a segment name.")
      return
    }
    await handleGenerateFromSegment(
      directEntryName.trim(),
      directEntryDescription.trim() || `A persona segment called "${directEntryName.trim()}"`
    )
  }

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [brandsData] = await Promise.all([
          BrandsAPI.list()
        ])
        setBrands(brandsData)
      } catch (err) {
        console.error("Failed to load initial data", err)
      }
    }
    fetchData()
  }, [])

  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-50 via-white to-violet-50 dark:from-gray-950 dark:via-gray-900 dark:to-violet-950">


      {/* Indegene Purple Header Section */}
      <div className="relative overflow-hidden bg-gradient-to-r from-[hsl(262,60%,38%)] via-[hsl(262,60%,42%)] to-[hsl(280,60%,45%)]">
        {/* Animated Background */}
        <div className="absolute inset-0 overflow-hidden">
          <div className="absolute top-20 left-10 w-72 h-72 bg-white/10 rounded-full blur-3xl animate-pulse"></div>
          <div className="absolute bottom-0 right-20 w-96 h-96 bg-white/10 rounded-full blur-3xl animate-pulse animation-delay-2000"></div>
        </div>

        <div className="relative z-10 px-8 py-8">
          <div className="max-w-7xl mx-auto">
            <div className="flex items-center justify-between">
              <div className="flex items-center space-x-5">
                <div className="relative">
                  <div className="relative p-4 bg-white/20 backdrop-blur-sm rounded-2xl border border-white/20">
                    <UserPlus className="h-10 w-10 text-white" />
                  </div>
                </div>
                <div>
                  <div className="flex items-center gap-3 mb-1">
                    <h1 className="text-4xl font-bold text-white">Create Persona</h1>
                    <Badge className="bg-white/20 backdrop-blur-sm text-white border-white/30 px-3 py-1">
                      <Sparkles className="h-3 w-3 mr-1" />
                      AI-Powered
                    </Badge>
                  </div>
                  <p className="text-white/80 text-base">
                    Generate realistic patient and HCP personas with advanced AI
                  </p>
                </div>
              </div>
              <div className="flex gap-3">
                <Button
                  variant="outline"
                  size="lg"
                  onClick={() => navigate('/personas')}
                  className="bg-white/10 backdrop-blur-sm border-white/20 text-white hover:bg-white/20"
                >
                  <ArrowLeft className="h-5 w-5 mr-2" />
                  Back to Library
                </Button>
                <Button
                  variant="outline"
                  size="lg"
                  onClick={() => navigate('/dashboard')}
                  className="bg-white/10 backdrop-blur-sm border-white/20 text-white hover:bg-white/20"
                >
                  <Settings className="h-5 w-5 mr-2" />
                  Dashboard
                </Button>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Main Content */}
      <div className="max-w-6xl mx-auto px-8 py-12">
        <div className="space-y-8">
          {recentlyCreated.ids.length > 0 && (
            <Card className="border-0 shadow-2xl bg-gradient-to-r from-emerald-50 via-white to-violet-50 dark:from-emerald-950/30 dark:via-gray-900 dark:to-violet-900/30">
              <CardContent className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between py-6">
                <div className="flex items-start gap-3">
                  <div className="mt-1 rounded-full bg-emerald-500/10 p-3 text-emerald-600 dark:text-emerald-300">
                    <CheckCircle className="h-6 w-6" />
                  </div>
                  <div>
                    <p className="text-sm uppercase tracking-wide text-emerald-600 dark:text-emerald-300 font-semibold">
                      Persona Ready
                    </p>
                    <h3 className="text-xl font-semibold text-gray-900 dark:text-gray-100">
                      {recentlyCreated.names.length === 1
                        ? `${recentlyCreated.names[0]} is ready for testing`
                        : `${recentlyCreated.names.length} personas ready for cohort simulation`}
                    </h3>
                    <p className="text-sm text-gray-600 dark:text-gray-400">
                      Jump straight into the simulator to see how this persona responds to your content.
                    </p>
                  </div>
                </div>
                <div className="flex flex-col gap-2 sm:flex-row">
                  <Button
                    onClick={() => handleNavigateToSimulator(recentlyCreated.ids)}
                    className="bg-gradient-to-r from-primary to-secondary text-white shadow-lg"
                  >
                    <Sparkles className="mr-2 h-4 w-4" />
                    {recentlyCreated.ids.length > 1 ? "Test this cohort" : "Test this persona"}
                  </Button>
                  <Button variant="outline" onClick={() => navigate('/personas')}>
                    <ArrowLeft className="mr-2 h-4 w-4" />
                    View in Persona Library
                  </Button>
                  <Button variant="ghost" onClick={() => setRecentlyCreated({ ids: [], names: [] })}>
                    Create another
                  </Button>
                </div>
              </CardContent>
            </Card>
          )}



          {/* === RESEARCH DISCOVERY MODE === */}
          {creationMode === "research" && (
            <div className="space-y-6">
              {/* Live Generation Feed - INLINE */}
              {generatingFromDiscovery && discoveryBrandId && generationTarget && (
                <LiveGenerationFeed
                  isVisible={true}
                  brandId={discoveryBrandId}
                  segmentName={generationTarget.name}
                  segmentDescription={generationTarget.description}
                  onComplete={handleGenerationComplete}
                  onError={handleGenerationError}
                />
              )}
              {/* Step 1: Brand Selection + Discovery */}
              <Card className="border-0 shadow-xl bg-white/80 backdrop-blur-sm">
                <CardHeader>
                  <div className="flex items-center gap-3">
                    <div className="p-2 bg-violet-100 dark:bg-violet-900/50 rounded-lg">
                      <Search className="h-5 w-5 text-violet-600" />
                    </div>
                    <div>
                      <CardTitle>Step 1: Discover Segments</CardTitle>
                      <CardDescription>Select a brand and scan its documents for hidden personas</CardDescription>
                    </div>
                  </div>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="flex gap-4">
                    <div className="flex-1">
                      <label className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-1 block">Brand</label>
                      <select
                        value={discoveryBrandId ?? ""}
                        onChange={(e) => setDiscoveryBrandId(e.target.value ? parseInt(e.target.value) : null)}
                        className="w-full p-2 border rounded-lg bg-white dark:bg-gray-800"
                      >
                        <option value="">Select a brand...</option>
                        {brands.map((b) => (
                          <option key={b.id} value={b.id}>{b.name}</option>
                        ))}
                      </select>
                    </div>
                    <div className="flex items-end">
                      <Button
                        onClick={handleDiscoverSegments}
                        disabled={!discoveryBrandId || discovering}
                        className="bg-violet-600 hover:bg-violet-700"
                      >
                        {discovering ? (
                          <><Loader2 className="h-4 w-4 mr-2 animate-spin" /> Scanning Documents...</>
                        ) : (
                          <><Search className="h-4 w-4 mr-2" /> Discover Segments</>
                        )}
                      </Button>
                    </div>
                  </div>

                  {/* Review Generated Persona UI */}
                  {reviewPersona && (
                    <div className="mb-6 animate-in fade-in zoom-in-95 duration-300">
                      <Card className="border-2 border-indigo-500 shadow-xl overflow-hidden">
                        <CardHeader className="bg-indigo-50 border-b border-indigo-100 dark:bg-indigo-950/30 dark:border-indigo-900">
                          <div className="flex items-center justify-between">
                            <div className="flex items-center gap-3">
                              <div className="p-2 bg-indigo-100 rounded-full dark:bg-indigo-900">
                                <CheckCircle className="h-6 w-6 text-indigo-600 dark:text-indigo-400" />
                              </div>
                              <div>
                                <CardTitle className="text-indigo-900 dark:text-indigo-100">Review Persona</CardTitle>
                                <CardDescription className="text-indigo-700 dark:text-indigo-300">
                                  Review the generated profile before saving to your library.
                                </CardDescription>
                              </div>
                            </div>
                            <Badge variant="outline" className="bg-white text-indigo-700 border-indigo-200">
                              Wait for Approval
                            </Badge>
                          </div>
                        </CardHeader>
                        <CardContent className="p-6 space-y-6">
                          <div className="grid md:grid-cols-2 gap-6">
                            <div className="space-y-4">
                              <div>
                                <label className="text-xs font-semibold text-gray-500 uppercase tracking-wider">Name & Role</label>
                                <div className="font-semibold text-lg text-gray-900 dark:text-gray-100">{reviewPersona.name}</div>
                                <div className="text-sm text-gray-600 dark:text-gray-400">{reviewPersona.persona_type} • {reviewPersona.age} • {reviewPersona.gender}</div>
                              </div>

                              <div>
                                <label className="text-xs font-semibold text-gray-500 uppercase tracking-wider">Bio</label>
                                <div className="text-sm text-gray-700 dark:text-gray-300 italic p-3 bg-gray-50 rounded-lg border dark:bg-gray-900/50 dark:border-gray-800">
                                  "{reviewPersona.bio || reviewPersona.medical_background || "No bio available"}"
                                </div>
                              </div>

                              <div>
                                <label className="text-xs font-semibold text-gray-500 uppercase tracking-wider">Tagline</label>
                                <div className="text-sm font-medium text-indigo-600 dark:text-indigo-400">
                                  {reviewPersona.tagline || "N/A"}
                                </div>
                              </div>
                            </div>

                            <div className="space-y-4">
                              <div>
                                <label className="text-xs font-semibold text-gray-500 uppercase tracking-wider">Psychographics (MBT)</label>
                                <div className="space-y-2 mt-1">
                                  <div className="flex gap-2 text-sm">
                                    <span className="font-medium min-w-[80px] text-gray-600">Motivation:</span>
                                    <span className="text-gray-800 dark:text-gray-200">{(reviewPersona.motivations || [])[0]}</span>
                                  </div>
                                  <div className="flex gap-2 text-sm">
                                    <span className="font-medium min-w-[80px] text-gray-600">Belief:</span>
                                    <span className="text-gray-800 dark:text-gray-200">{(reviewPersona.beliefs || [])[0]}</span>
                                  </div>
                                  <div className="flex gap-2 text-sm">
                                    <span className="font-medium min-w-[80px] text-gray-600">Tension:</span>
                                    <span className="text-gray-800 dark:text-gray-200">{(reviewPersona.pain_points || [])[0]}</span>
                                  </div>
                                </div>
                              </div>

                              {reviewPersona.sources && reviewPersona.sources.length > 0 && (
                                <div>
                                  <label className="text-xs font-semibold text-gray-500 uppercase tracking-wider flex items-center gap-1">
                                    <FileText className="h-3 w-3" /> Key Sources
                                  </label>
                                  <ul className="mt-1 space-y-1">
                                    {reviewPersona.sources.slice(0, 3).map((s: any, i: number) => (
                                      <li key={i} className="text-xs text-gray-600 truncate flex items-center gap-1">
                                        <div className="w-1 h-1 rounded-full bg-indigo-400"></div>
                                        {s.filename}
                                      </li>
                                    ))}
                                  </ul>
                                </div>
                              )}
                            </div>
                          </div>

                          <Separator />

                          <div className="flex items-center justify-end gap-3">
                            <Button variant="ghost" onClick={handleDiscardPersona} disabled={generating}>
                              Discard
                            </Button>
                            <Button
                              onClick={handleSavePersona}
                              className="bg-indigo-600 hover:bg-indigo-700 text-white min-w-[140px]"
                              disabled={generating}
                            >
                              {generating ? (
                                <><Loader2 className="mr-2 h-4 w-4 animate-spin" /> Saving...</>
                              ) : (
                                <><CheckCircle className="mr-2 h-4 w-4" /> Approve & Save</>
                              )}
                            </Button>
                          </div>
                        </CardContent>
                      </Card>
                    </div>
                  )}

                  {/* Discovered Segments List */}
                  {discoveredSegments.length > 0 && (
                    <div className="mt-6">
                      <h3 className="text-lg font-semibold mb-3 flex items-center gap-2">
                        <Sparkles className="h-5 w-5 text-violet-500" />
                        Discovered Segments ({discoveredSegments.length})
                      </h3>
                      <div className="grid gap-3">
                        {discoveredSegments.map((seg, idx) => (
                          <div
                            key={idx}
                            className={`p-4 rounded-xl border-2 cursor-pointer transition-all hover:shadow-md ${selectedSegment?.name === seg.name
                              ? "border-violet-500 bg-violet-50 dark:bg-violet-950/30"
                              : "border-gray-200 dark:border-gray-700 hover:border-violet-300"
                              }`}
                            onClick={() => setSelectedSegment(seg)}
                          >
                            <div className="flex items-start justify-between">
                              <div className="flex-1">
                                <h4 className="font-bold text-gray-900 dark:text-gray-100">{seg.name}</h4>
                                <p className="text-sm text-gray-600 dark:text-gray-400 mt-1">{seg.description}</p>
                                {seg.differentiators && seg.differentiators.length > 0 && (
                                  <div className="flex flex-wrap gap-1.5 mt-2">
                                    {seg.differentiators.map((d, i) => (
                                      <Badge key={i} variant="secondary" className="text-xs">{d}</Badge>
                                    ))}
                                  </div>
                                )}
                              </div>
                              <Button
                                size="sm"
                                variant={selectedSegment?.name === seg.name ? "default" : "outline"}
                                className="ml-3 shrink-0"
                                disabled={generatingFromDiscovery}
                                onClick={(e) => {
                                  e.stopPropagation()
                                  handleGenerateFromSegment(seg.name, seg.description)
                                }}
                              >
                                {generatingFromDiscovery && selectedSegment?.name === seg.name ? (
                                  <Loader2 className="h-4 w-4 animate-spin" />
                                ) : (
                                  <><Zap className="h-4 w-4 mr-1" /> Generate</>
                                )}
                              </Button>
                            </div>
                            {seg.evidence && (
                              <p className="text-xs text-gray-500 mt-2 italic">
                                <FileText className="h-3 w-3 inline mr-1" />{seg.evidence}
                              </p>
                            )}
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {discoveryError && (
                    <div className="p-3 bg-red-50 dark:bg-red-950/30 border border-red-200 dark:border-red-800 rounded-lg text-sm text-red-700 dark:text-red-300">
                      {discoveryError}
                    </div>
                  )}
                </CardContent>
              </Card>

              {/* Step 2: Direct Entry (Always Visible) */}
              <Card className="border-0 shadow-xl bg-white/80 backdrop-blur-sm">
                <CardHeader>
                  <div className="flex items-center gap-3">
                    <div className="p-2 bg-emerald-100 dark:bg-emerald-900/50 rounded-lg">
                      <Target className="h-5 w-5 text-emerald-600" />
                    </div>
                    <div>
                      <CardTitle>Or: Direct Entry</CardTitle>
                      <CardDescription>Already know the segment? Type it directly and we'll build the persona from brand documents.</CardDescription>
                    </div>
                  </div>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div>
                      <label className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-1 block">Segment Name *</label>
                      <input
                        type="text"
                        placeholder='e.g. "The Skeptical Specialist"'
                        value={directEntryName}
                        onChange={(e) => setDirectEntryName(e.target.value)}
                        className="w-full p-2.5 border rounded-lg bg-white dark:bg-gray-800 focus:ring-2 focus:ring-violet-500 focus:border-violet-500"
                      />
                    </div>
                    <div>
                      <label className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-1 block">Brief Description (optional)</label>
                      <input
                        type="text"
                        placeholder='e.g. "An oncologist who questions new treatments"'
                        value={directEntryDescription}
                        onChange={(e) => setDirectEntryDescription(e.target.value)}
                        className="w-full p-2.5 border rounded-lg bg-white dark:bg-gray-800 focus:ring-2 focus:ring-violet-500 focus:border-violet-500"
                      />
                    </div>
                  </div>
                  <Button
                    onClick={handleDirectEntry}
                    disabled={!directEntryName.trim() || !discoveryBrandId || generatingFromDiscovery}
                    className="bg-emerald-600 hover:bg-emerald-700"
                  >
                    {generatingFromDiscovery ? (
                      <><Loader2 className="h-4 w-4 mr-2 animate-spin" /> Generating Persona (Multi-Pass)...</>
                    ) : (
                      <><Zap className="h-4 w-4 mr-2" /> Generate Persona</>
                    )}
                  </Button>
                  {!discoveryBrandId && (
                    <p className="text-xs text-amber-600">⚠️ Select a brand above first — it provides the research documents for extraction.</p>
                  )}
                </CardContent>
              </Card>
            </div>
          )}

        </div >
      </div >
    </div >
  )
}