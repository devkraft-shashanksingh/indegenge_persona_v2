"use client"

import { useState, useEffect } from "react"
import { BrandsAPI } from "@/lib/api"
import { KnowledgeGraphWorkspace } from "@/components/KnowledgeGraphWorkspace"
import { KnowledgeFactsView } from "@/components/KnowledgeFactsView"
import { NodeMergePanel } from "@/components/NodeMergePanel"
import { Network, AlertCircle, Settings2, BookOpen, ChevronRight, Loader2, Library } from "lucide-react"
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@/components/ui/select"
import { Card, CardContent } from "@/components/ui/card"
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Button } from "@/components/ui/button"

interface Brand {
    id: number
    name: string
}

export function KnowledgeGraphPage() {
    const [brands, setBrands] = useState<Brand[]>([])
    const [selectedBrandId, setSelectedBrandId] = useState<string>("")
    const [loading, setLoading] = useState(true)
    const [activeTab, setActiveTab] = useState<'facts' | 'graph' | 'admin'>('facts')

    useEffect(() => {
        fetchBrands()
    }, [])

    const fetchBrands = async () => {
        try {
            const data = await BrandsAPI.list()
            setBrands(data)
            if (data.length > 0) {
                // If we have a stored preference or parameter, use it? For now defaulting to first.
                setSelectedBrandId(data[0].id.toString())
            }
        } catch (err) {
            console.error("Failed to fetch brands", err)
        } finally {
            setLoading(false)
        }
    }

    const selectedBrand = brands.find(b => b.id.toString() === selectedBrandId)

    // Empty State
    if (!loading && brands.length === 0) {
        return (
            <div className="min-h-screen bg-gray-50 flex items-center justify-center p-4">
                <Card className="max-w-md w-full border-dashed border-2 shadow-sm bg-white/50">
                    <CardContent className="flex flex-col items-center justify-center py-12 text-center">
                        <div className="w-16 h-16 bg-muted rounded-full flex items-center justify-center mb-4">
                            <AlertCircle className="h-8 w-8 text-muted-foreground" />
                        </div>
                        <h3 className="text-xl font-semibold mb-2">No Brands Available</h3>
                        <p className="text-muted-foreground mb-6">
                            Get started by creating your first brand persona in the Brand Library.
                        </p>
                        <Button variant="outline">Go to Brand Library</Button>
                    </CardContent>
                </Card>
            </div>
        )
    }

    return (
        <div className="flex flex-col h-screen w-full bg-background overflow-hidden relative animate-in fade-in duration-500">
            {/* Slim Application Header */}
            <div className="h-14 border-b bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60 flex items-center justify-between px-4 shrink-0 z-30 shadow-sm">
                <div className="flex items-center gap-4">
                    <div className="flex items-center gap-2 text-violet-600 font-semibold text-lg">
                        <div className="bg-violet-100 p-1.5 rounded-lg">
                            <BookOpen className="h-4 w-4" />
                        </div>
                        Evidence Bank
                    </div>

                    <div className="h-6 w-px bg-border/60" />

                    <div className="flex items-center gap-2">
                        <span className="text-sm text-muted-foreground hidden sm:inline">Active Brand:</span>
                        <Select value={selectedBrandId} onValueChange={setSelectedBrandId}>
                            <SelectTrigger className="w-[200px] h-9 bg-muted/30 border-muted-foreground/20 hover:bg-muted/50 transition-colors focus:ring-violet-500">
                                <SelectValue placeholder="Select Brand" />
                            </SelectTrigger>
                            <SelectContent>
                                {brands.map(b => (
                                    <SelectItem key={b.id} value={b.id.toString()}>{b.name}</SelectItem>
                                ))}
                            </SelectContent>
                        </Select>
                    </div>
                </div>

                <div className="flex items-center gap-4">
                    <Tabs value={activeTab} onValueChange={(v) => setActiveTab(v as 'facts' | 'graph' | 'admin')} className="h-9">
                        <TabsList className="h-9 bg-muted/50 p-1">
                            <TabsTrigger value="facts" className="h-7 text-xs px-3 data-[state=active]:bg-white data-[state=active]:text-violet-700 data-[state=active]:shadow-sm">
                                <Library className="h-3 w-3 mr-1.5" />
                                Facts & Evidence
                            </TabsTrigger>
                            <TabsTrigger value="graph" className="h-7 text-xs px-3 data-[state=active]:bg-white data-[state=active]:text-violet-700 data-[state=active]:shadow-sm">
                                <Network className="h-3 w-3 mr-1.5" />
                                Graph Explorer
                            </TabsTrigger>
                            <TabsTrigger value="admin" className="h-7 text-xs px-3 data-[state=active]:bg-white data-[state=active]:text-indigo-700 data-[state=active]:shadow-sm">
                                <Settings2 className="h-3 w-3 mr-1.5" />
                                Data Management
                            </TabsTrigger>
                        </TabsList>
                    </Tabs>
                </div>
            </div>

            {/* Main Content Area */}
            <div className="flex-1 overflow-hidden relative">
                {selectedBrandId ? (
                    <>
                        <div className={`h-full w-full ${activeTab === 'facts' ? 'block' : 'hidden'}`}>
                            <KnowledgeFactsView
                                brandId={parseInt(selectedBrandId)}
                                brandName={selectedBrand?.name}
                            />
                        </div>

                        {activeTab === 'graph' && (
                            <div className="h-full w-full">
                                <KnowledgeGraphWorkspace
                                    brandId={parseInt(selectedBrandId)}
                                    brandName={selectedBrand?.name}
                                />
                            </div>
                        )}

                        {activeTab === 'admin' && (
                            <div className="h-full w-full overflow-y-auto bg-slate-50/50 dark:bg-slate-950/50 p-6">
                                <div className="max-w-6xl mx-auto space-y-6">
                                    <div className="flex items-center justify-between">
                                        <div>
                                            <h2 className="text-2xl font-bold tracking-tight">Graph Data Management</h2>
                                            <p className="text-muted-foreground">Review duplicate insights and optimize graph topology</p>
                                        </div>
                                    </div>
                                    <NodeMergePanel brandId={parseInt(selectedBrandId)} />
                                </div>
                            </div>
                        )}
                    </>
                ) : (
                    <div className="flex items-center justify-center h-full text-muted-foreground">
                        <Loader2 className="h-8 w-8 animate-spin" />
                    </div>
                )}
            </div>
        </div>
    )
}
