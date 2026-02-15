import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Input } from "@/components/ui/input";
import { Avatar, AvatarImage, AvatarFallback } from "@/components/ui/avatar";
import {
  Upload, FileText, Plus, Loader2, Sparkles,
  Library, Users, UserPlus, Search, MoreVertical,
  ChevronRight, ExternalLink, Calendar
} from 'lucide-react';
import { useToast } from "@/components/ui/use-toast";
import { BrandsAPI } from "@/lib/api";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"

interface Brand {
  id: number;
  name: string;
}

interface BrandDocument {
  id: number;
  filename: string;
  category: string;
  summary: string;
  created_at: string;
}

interface Persona {
  id: number;
  name: string;
  avatar_url?: string;
  persona_type: string;
  condition: string;
  created_at: string;
  tagline?: string;
}

const BrandLibrary = () => {
  const navigate = useNavigate();
  const [brands, setBrands] = useState<Brand[]>([]);
  const [selectedBrandId, setSelectedBrandId] = useState<string>("");
  const [newBrandName, setNewBrandName] = useState("");
  const [documents, setDocuments] = useState<BrandDocument[]>([]);
  const [personas, setPersonas] = useState<Persona[]>([]);
  const [isUploading, setIsUploading] = useState(false);
  const [isCreatingBrand, setIsCreatingBrand] = useState(false);
  const [isSeeding, setIsSeeding] = useState(false);
  const [isIngesting, setIsIngesting] = useState(false);
  const [personaCount, setPersonaCount] = useState<number>(0);
  const [searchTerm, setSearchTerm] = useState("");
  const [selectedDoc, setSelectedDoc] = useState<BrandDocument | null>(null);
  const [isPreviewLoading, setIsPreviewLoading] = useState(false);
  const [docContent, setDocContent] = useState<string>("");
  const [bulkIngestPath, setBulkIngestPath] = useState("");
  const [isIngestModalOpen, setIsIngestModalOpen] = useState(false);
  const { toast } = useToast();

  useEffect(() => {
    fetchBrands();
  }, []);

  useEffect(() => {
    if (selectedBrandId) {
      const brandId = parseInt(selectedBrandId);
      fetchDocuments(brandId);
      fetchPersonaCount(brandId);
      fetchPersonas(brandId);
    } else {
      setDocuments([]);
      setPersonas([]);
      setPersonaCount(0);
    }
  }, [selectedBrandId]);

  const fetchPersonaCount = async (brandId: number) => {
    try {
      const data = await BrandsAPI.getPersonasCount(brandId);
      setPersonaCount(data.persona_count);
    } catch (error) {
      console.error("Failed to fetch persona count", error);
      setPersonaCount(0);
    }
  };

  const fetchPersonas = async (brandId: number) => {
    try {
      const data = await BrandsAPI.getPersonas(brandId);
      setPersonas(data);
    } catch (error) {
      console.error("Failed to fetch personas", error);
    }
  };

  const fetchBrands = async () => {
    try {
      const data = await BrandsAPI.list();
      setBrands(data);
    } catch (error) {
      console.error("Failed to fetch brands", error);
      toast({ title: "Error", description: "Failed to load brands.", variant: "destructive" });
    }
  };

  const fetchDocuments = async (brandId: number) => {
    try {
      const data = await BrandsAPI.getDocuments(brandId);
      setDocuments(data);
    } catch (error) {
      console.error("Failed to fetch documents", error);
      toast({ title: "Error", description: "Failed to load documents.", variant: "destructive" });
    }
  };

  const handleCreateBrand = async () => {
    if (!newBrandName.trim()) return;
    setIsCreatingBrand(true);
    try {
      const newBrand = await BrandsAPI.create(newBrandName);
      setBrands([...brands, newBrand]);
      setSelectedBrandId(newBrand.id.toString());
      setNewBrandName("");
      toast({ title: "Brand created", description: `${newBrand.name} has been created.` });
    } catch (error: any) {
      console.error("Failed to create brand", error);
      const errorMessage = error?.response?.data?.detail || "Failed to create brand.";
      toast({ title: "Error", description: errorMessage, variant: "destructive" });
    } finally {
      setIsCreatingBrand(false);
    }
  };

  const handleSeedData = async () => {
    if (!selectedBrandId) return;
    setIsSeeding(true);
    try {
      const newDocs = await BrandsAPI.seed(parseInt(selectedBrandId));
      fetchDocuments(parseInt(selectedBrandId));
      toast({
        title: "Demo Data Populated",
        description: `Added ${newDocs.length} mock documents.`
      });
    } catch (error: any) {
      console.error("Failed to seed data", error);
      const errorMessage = error?.response?.data?.detail || "Failed to seed data.";
      toast({ title: "Error", description: errorMessage, variant: "destructive" });
    } finally {
      setIsSeeding(false);
    }
  };

  const handleBulkIngest = async () => {
    if (!selectedBrandId || !bulkIngestPath.trim()) return;

    setIsIngesting(true);
    try {
      const result = await BrandsAPI.ingestFolder(parseInt(selectedBrandId), bulkIngestPath);
      fetchDocuments(parseInt(selectedBrandId));
      setIsIngestModalOpen(false);
      setBulkIngestPath("");
      toast({
        title: "Ingestion Complete",
        description: `Processed ${result.total_files} files. Created ${result.total_nodes_created} knowledge nodes.`
      });
    } catch (error: any) {
      console.error("Failed to ingest folder", error);
      const errorMessage = error?.response?.data?.detail || "Failed to ingest folder.";
      toast({ title: "Ingestion Failed", description: errorMessage, variant: "destructive" });
    } finally {
      setIsIngesting(false);
    }
  };

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    if (!e.target.files || !e.target.files[0] || !selectedBrandId) return;

    const file = e.target.files[0];
    setIsUploading(true);
    try {
      const newDoc = await BrandsAPI.upload(parseInt(selectedBrandId), file);
      setDocuments(prev => [...prev, newDoc]);
      toast({
        title: "File uploaded",
        description: `Classified as: ${newDoc.category}`
      });
    } catch (error: any) {
      console.error("Failed to upload file", error);
      const errorMessage = error?.response?.data?.detail || "Could not upload file.";
      toast({ title: "Upload failed", description: errorMessage, variant: "destructive" });
    } finally {
      setIsUploading(false);
    }
  };

  const handleDocClick = async (doc: BrandDocument) => {
    setSelectedDoc(doc);
    setDocContent("");
    setIsPreviewLoading(true);
    try {
      const data = await BrandsAPI.getDocumentContent(parseInt(selectedBrandId), doc.id);
      setDocContent(data.content);
    } catch (error) {
      console.error("Failed to fetch document content", error);
      toast({ title: "Error", description: "Failed to load document content.", variant: "destructive" });
    } finally {
      setIsPreviewLoading(false);
    }
  };

  const filteredBrands = brands.filter(b =>
    b.name.toLowerCase().includes(searchTerm.toLowerCase())
  );

  const selectedBrand = brands.find(b => b.id.toString() === selectedBrandId);

  return (
    <div className="flex w-full h-full bg-[#FAFAFE] overflow-hidden">

      {/* 1. LEFT SIDEBAR: Brand List */}
      <div className="w-80 flex-shrink-0 border-r bg-white/50 backdrop-blur-xl flex flex-col shadow-sm relative z-10">
        <div className="p-6 border-b bg-white/90 sticky top-0">
          <div className="flex items-center gap-3 mb-6">
            <div className="bg-violet-600 p-2 rounded-xl shadow-lg shadow-violet-200">
              <Library className="h-5 w-5 text-white" />
            </div>
            <div>
              <h1 className="text-xl font-bold text-slate-900 tracking-tight">Brand Library</h1>
              <p className="text-[10px] text-slate-400 font-medium uppercase tracking-wider">Knowledge Repository</p>
            </div>
          </div>

          <div className="relative mb-4">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
            <Input
              placeholder="Search brands..."
              className="pl-9 h-11 bg-slate-50 border-slate-100 rounded-xl focus-visible:ring-violet-500 transition-all duration-200"
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
            />
          </div>

          <div className="flex gap-2">
            <Input
              placeholder="New Brand Name"
              className="h-10 bg-slate-50 border-slate-100 rounded-xl text-sm"
              value={newBrandName}
              onChange={(e) => setNewBrandName(e.target.value)}
            />
            <Button
              size="icon"
              onClick={handleCreateBrand}
              disabled={!newBrandName || isCreatingBrand}
              className="h-10 w-10 shrink-0 bg-violet-600 hover:bg-violet-700 rounded-xl shadow-md transition-all active:scale-95"
            >
              {isCreatingBrand ? <Loader2 className="h-4 w-4 animate-spin" /> : <Plus className="h-5 w-5" />}
            </Button>
          </div>
        </div>

        <ScrollArea className="flex-1 px-4 py-4">
          <div className="space-y-2">
            {filteredBrands.map(brand => (
              <button
                key={brand.id}
                onClick={() => setSelectedBrandId(brand.id.toString())}
                className={`w-full text-left px-4 py-3.5 rounded-2xl text-sm font-semibold transition-all duration-300 flex items-center justify-between group relative overflow-hidden ${selectedBrandId === brand.id.toString()
                  ? 'bg-violet-600 text-white shadow-lg shadow-violet-100 translate-x-1'
                  : 'hover:bg-violet-50 text-slate-600 hover:text-violet-600'
                  }`}
              >
                <div className="flex items-center gap-3 relative z-10">
                  <div className={`w-2 h-2 rounded-full transition-all duration-300 ${selectedBrandId === brand.id.toString() ? 'bg-white' : 'bg-slate-200 group-hover:bg-violet-300'}`} />
                  <span className="truncate">{brand.name}</span>
                </div>
                {selectedBrandId === brand.id.toString() && (
                  <ChevronRight className="h-4 w-4 text-white animate-in slide-in-from-left-2 duration-300" />
                )}
              </button>
            ))}
            {filteredBrands.length === 0 && (
              <div className="text-center py-12">
                <div className="bg-slate-50 w-12 h-12 rounded-full flex items-center justify-center mx-auto mb-3">
                  <Search className="h-5 w-5 text-slate-300" />
                </div>
                <p className="text-xs text-slate-400 font-medium">No results found</p>
              </div>
            )}
          </div>
        </ScrollArea>
      </div>

      {/* 2. CENTER: Knowledge Assets */}
      <div className="flex-1 flex flex-col min-w-0 bg-[#FAFAFE] overflow-hidden relative">

        {!selectedBrandId ? (
          <div className="flex flex-col items-center justify-center h-full text-center p-8 bg-white/40">
            <div className="relative mb-8">
              <div className="absolute inset-0 bg-violet-500/10 blur-3xl rounded-full scale-150" />
              <div className="bg-white p-8 rounded-[2.5rem] shadow-2xl relative">
                <Library className="h-16 w-16 text-violet-600/20" />
              </div>
            </div>
            <h2 className="text-2xl font-bold text-slate-900 mb-3 tracking-tight">Select a Brand Context</h2>
            <p className="max-w-xs text-slate-500 text-sm leading-relaxed font-medium">
              Choose a pharmaceutical brand to manage its clinical documents, market research, and persona library.
            </p>
          </div>
        ) : (
          <>
            {/* Main Header / Toolbar */}
            <div className="h-20 flex items-center justify-between px-8 bg-white/60 backdrop-blur-md border-b border-slate-100 sticky top-0 z-20">
              <div className="flex items-center gap-4">
                <div className="flex flex-col">
                  <div className="flex items-center gap-2">
                    <h2 className="text-xl font-extrabold text-slate-900 tracking-tight">{selectedBrand?.name}</h2>
                    <Badge className="bg-emerald-50 text-emerald-600 border-none hover:bg-emerald-100 rounded-full px-3 py-0 h-6 text-[10px] font-bold">
                      ACTIVE
                    </Badge>
                  </div>
                  <p className="text-xs text-slate-400 font-medium">
                    {documents.length} Curated Knowledge Assets
                  </p>
                </div>
              </div>

              <div className="flex items-center gap-3">
                <label className="cursor-pointer">
                  <Button size="sm" className="bg-violet-600 hover:bg-violet-700 text-white shadow-lg shadow-violet-100 px-5 rounded-xl h-11 font-bold pointer-events-none">
                    <Upload className="h-4 w-4 mr-2" />
                    {isUploading ? "Processing..." : "Secure Upload"}
                  </Button>
                  <input
                    type="file"
                    className="hidden"
                    onChange={handleFileUpload}
                    disabled={isUploading || isIngesting}
                    accept=".pdf,.txt,.docx,.md"
                  />
                </label>

                <DropdownMenu>
                  <DropdownMenuTrigger asChild>
                    <Button size="icon" variant="ghost" className="h-11 w-11 rounded-xl border border-slate-100 bg-white hover:bg-slate-50">
                      <MoreVertical className="h-5 w-5 text-slate-400" />
                    </Button>
                  </DropdownMenuTrigger>
                  <DropdownMenuContent align="end" className="w-56 p-2 rounded-2xl shadow-2xl border-slate-100">
                    <DropdownMenuItem
                      onClick={handleSeedData}
                      disabled={isSeeding || isIngesting}
                      className="rounded-xl py-3 cursor-pointer"
                    >
                      <Sparkles className="h-4 w-4 mr-2 text-amber-500" />
                      <span className="font-semibold text-slate-700">Seed Demo Data</span>
                    </DropdownMenuItem>
                    <DropdownMenuItem
                      onClick={() => setIsIngestModalOpen(true)}
                      disabled={isSeeding || isIngesting}
                      className="rounded-xl py-3 cursor-pointer"
                    >
                      {isIngesting ? <Loader2 className="h-4 w-4 mr-2 animate-spin text-violet-600" /> : <Library className="h-4 w-4 mr-2 text-violet-600" />}
                      <span className="font-semibold text-slate-700">Bulk Directory Ingest</span>
                    </DropdownMenuItem>
                  </DropdownMenuContent>
                </DropdownMenu>
              </div>
            </div>

            {/* Scrollable Content Area */}
            <ScrollArea className="flex-1 p-8">
              <div className="grid grid-cols-1 xl:grid-cols-2 2xl:grid-cols-3 gap-6">
                {documents.length === 0 ? (
                  <div className="col-span-full py-24 flex flex-col items-center justify-center text-center opacity-80">
                    <div className="bg-white/80 w-24 h-24 rounded-[2rem] shadow-xl flex items-center justify-center mb-6 relative">
                      <div className="absolute inset-0 bg-violet-500/5 animate-pulse rounded-[2rem]" />
                      <FileText className="h-10 w-10 text-violet-200" />
                    </div>
                    <h3 className="font-bold text-xl text-slate-900">Repository Empty</h3>
                    <p className="text-slate-400 text-sm max-w-xs mt-2 mb-8 font-medium">
                      Upload medical communications, brand storyboards, or patient journey maps to start grounding your AI.
                    </p>
                    <Button
                      variant="secondary"
                      onClick={handleSeedData}
                      disabled={isSeeding}
                      className="border-none bg-violet-50 text-violet-600 px-8 py-6 rounded-2xl font-bold hover:bg-violet-100"
                    >
                      Initialize with Samples
                    </Button>
                  </div>
                ) : (
                  documents.map((doc) => (
                    <Card
                      key={doc.id}
                      onClick={() => handleDocClick(doc)}
                      className="group cursor-pointer hover:border-violet-300 hover:shadow-2xl transition-all duration-500 border-white bg-white/80 backdrop-blur-sm rounded-3xl overflow-hidden shadow-sm flex flex-col relative h-[180px]"
                    >
                      <div className="absolute top-0 right-0 w-32 h-32 bg-violet-50 rounded-full blur-3xl -mr-16 -mt-16 opacity-0 group-hover:opacity-100 transition-opacity duration-500" />

                      <CardHeader className="py-5 px-6 pb-2 relative z-10">
                        <div className="flex items-start justify-between">
                          <div className="p-3 bg-slate-50 border border-slate-100 text-violet-600 rounded-2xl group-hover:bg-violet-600 group-hover:text-white group-hover:border-violet-600 transition-all duration-500 shadow-sm">
                            <FileText className="h-5 w-5" />
                          </div>
                          <Badge variant="secondary" className="bg-slate-100 text-slate-500 border-none rounded-lg px-2 py-0.5 text-[9px] font-bold group-hover:bg-violet-100 group-hover:text-violet-600 transition-colors">
                            {doc.category || 'RESOURCES'}
                          </Badge>
                        </div>
                      </CardHeader>

                      <CardContent className="px-6 py-2 relative z-10 flex-1">
                        <CardTitle className="text-sm font-bold text-slate-800 line-clamp-1 mb-2 group-hover:text-violet-900">{doc.filename}</CardTitle>
                        <p className="text-[11px] text-slate-400 font-medium line-clamp-2 leading-relaxed mb-4">
                          {doc.summary || "Deep knowledge node extracted from clinical literature and brand strategy assets."}
                        </p>

                        <div className="flex items-center justify-between pt-2 border-t border-slate-50 group-hover:border-violet-50">
                          <div className="flex items-center gap-1.5 text-[10px] text-slate-400 font-bold">
                            <Calendar className="h-3 w-3" />
                            {new Date(doc.created_at).toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' })}
                          </div>
                          <Button variant="ghost" className="h-6 w-6 p-0 rounded-lg hover:bg-slate-100 opacity-0 group-hover:opacity-100 transition-all">
                            <ExternalLink className="h-3 w-3 text-slate-400" />
                          </Button>
                        </div>
                      </CardContent>
                    </Card>
                  ))
                )}
              </div>
            </ScrollArea>
          </>
        )}
      </div>

      {/* 3. RIGHT SIDEBAR: Brand Personas */}
      {selectedBrandId && (
        <div className="w-[380px] flex-shrink-0 bg-white border-l border-slate-100 flex flex-col relative z-20 shadow-2xl shadow-slate-200">
          <div className="p-8 pb-4">
            <div className="flex items-center justify-between mb-8">
              <div className="flex items-center gap-3">
                <div className="p-2.5 bg-indigo-50 rounded-2xl">
                  <Users className="h-6 w-6 text-indigo-600" />
                </div>
                <div>
                  <h3 className="font-extrabold text-slate-900 tracking-tight">Brand Personas</h3>
                  <p className="text-[10px] text-slate-400 font-bold uppercase tracking-widest leading-none mt-1">Grounded Fleet</p>
                </div>
              </div>
              <Badge className="bg-indigo-600 text-white rounded-xl px-2.5 h-6 font-bold text-xs ring-4 ring-indigo-50 border-none">
                {personaCount}
              </Badge>
            </div>

            <div className="grid grid-cols-2 gap-3 mb-8">
              <Button
                className="bg-indigo-600 hover:bg-indigo-700 text-white font-bold h-12 rounded-2xl shadow-lg shadow-indigo-100 transition-all active:scale-95 text-xs flex-1"
                onClick={() => navigate(`/create-persona?brand_id=${selectedBrandId}`)}
              >
                <UserPlus className="h-4 w-4 mr-2" />
                New Persona
              </Button>
              <Button
                className="bg-white hover:bg-slate-50 text-indigo-600 border-2 border-slate-50 font-bold h-12 rounded-2xl text-xs flex-1 transition-all active:scale-95 shadow-sm"
                onClick={() => navigate(`/personas?brand_id=${selectedBrandId}`)}
              >
                Library View
              </Button>
            </div>

            <div className="flex items-center justify-between mb-4 px-1">
              <h4 className="text-[11px] font-black text-slate-400 uppercase tracking-[0.2em]">Recently Created</h4>
              <div className="h-[2px] w-12 bg-indigo-50 rounded-full" />
            </div>
          </div>

          <ScrollArea className="flex-1 px-8">
            <div className="space-y-4 pb-12">
              {personas.length === 0 ? (
                <div className="py-12 px-4 rounded-[2rem] bg-indigo-50/30 border border-dashed border-indigo-100 flex flex-col items-center text-center">
                  <div className="bg-white w-14 h-14 rounded-2xl flex items-center justify-center shadow-lg shadow-indigo-100 mb-4">
                    <Sparkles className="h-6 w-6 text-indigo-300" />
                  </div>
                  <p className="text-sm font-bold text-indigo-900/40">No personas found for this brand context.</p>
                </div>
              ) : (
                personas.map((p) => (
                  <div
                    key={p.id}
                    onClick={() => navigate(`/personas?id=${p.id}`)}
                    className="group cursor-pointer bg-slate-50 hover:bg-white hover:shadow-2xl hover:shadow-slate-200 hover:-translate-y-1 p-4 rounded-3xl border border-transparent hover:border-slate-50 transition-all duration-500 flex items-center gap-4 relative overflow-hidden"
                  >
                    <Avatar className="h-14 w-14 border-4 border-white shadow-xl rounded-2xl shrink-0 group-hover:scale-105 transition-transform duration-500">
                      <AvatarImage src={p.avatar_url} alt={p.name} className="object-cover" />
                      <AvatarFallback className="bg-gradient-to-br from-indigo-500 to-indigo-700 text-white font-bold text-lg rounded-2xl">
                        {p.name.charAt(0)}
                      </AvatarFallback>
                    </Avatar>

                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-2 mb-1">
                        <span className="font-bold text-slate-800 text-sm truncate group-hover:text-indigo-600 transition-colors uppercase tracking-tight">{p.name}</span>
                        {p.persona_type === 'HCP' && (
                          <div className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
                        )}
                      </div>
                      <p className="text-[11px] font-bold text-slate-400 line-clamp-1 mb-1">{p.condition}</p>
                      <Badge className="bg-white text-[9px] text-slate-500 border-none shadow-sm rounded-lg px-2 py-0 h-5 font-black uppercase tracking-tighter">
                        {p.persona_type}
                      </Badge>
                    </div>

                    <div className="shrink-0 transition-all duration-500 group-hover:translate-x-1 opacity-0 group-hover:opacity-100">
                      <ChevronRight className="h-5 w-5 text-indigo-400" />
                    </div>
                  </div>
                ))
              )}
            </div>
          </ScrollArea>
        </div>
      )}

      {/* 4. Document Preview Modal */}
      <Dialog open={!!selectedDoc} onOpenChange={(open) => !open && setSelectedDoc(null)}>
        <DialogContent className="max-w-4xl max-h-[85vh] flex flex-col p-0 overflow-hidden border-none rounded-[2.5rem] bg-white shadow-2xl">
          <DialogHeader className="p-8 pb-4 border-b border-slate-50 relative z-10">
            <div className="flex items-center gap-4">
              <div className="p-4 bg-violet-50 text-violet-600 rounded-2xl">
                <FileText className="h-6 w-6" />
              </div>
              <div className="flex-1 min-w-0">
                <DialogTitle className="text-xl font-extrabold text-slate-900 tracking-tight truncate">
                  {selectedDoc?.filename}
                </DialogTitle>
                <div className="flex items-center gap-2 mt-1">
                  <Badge variant="outline" className="text-[10px] font-bold border-slate-200 text-slate-500 uppercase px-2 py-0 h-5">
                    {selectedDoc?.category || 'General Document'}
                  </Badge>
                  <span className="text-[10px] text-slate-400 font-bold">•</span>
                  <span className="text-[10px] text-slate-400 font-bold uppercase tracking-wider">
                    Knowledge Asset
                  </span>
                </div>
              </div>
            </div>
          </DialogHeader>

          <ScrollArea className="flex-1 p-8 pt-6">
            <div className="prose prose-slate max-w-none">
              {isPreviewLoading ? (
                <div className="flex flex-col items-center justify-center py-24 gap-4">
                  <div className="relative">
                    <div className="absolute inset-0 bg-violet-500/10 blur-xl rounded-full scale-150 animate-pulse" />
                    <Loader2 className="h-10 w-10 text-violet-600 animate-spin relative z-10" />
                  </div>
                  <p className="text-sm font-bold text-slate-400 animate-pulse tracking-wide uppercase">Extracting Intelligence...</p>
                </div>
              ) : (
                <div className="bg-slate-50/50 p-8 rounded-[2rem] border border-slate-100/50 relative overflow-hidden group">
                  <div className="absolute top-0 left-0 w-full h-1 bg-gradient-to-r from-violet-500/20 via-indigo-500/20 to-violet-500/20" />
                  <pre className="whitespace-pre-wrap font-sans text-sm text-slate-600 leading-relaxed tracking-tight selection:bg-violet-200/50">
                    {docContent || "No content found for this document."}
                  </pre>
                </div>
              )}
            </div>
            <div className="h-8" />
          </ScrollArea>

          <div className="p-6 border-t border-slate-50 bg-slate-50/30 flex justify-end gap-3 rounded-b-[2.5rem]">
            <Button
              variant="outline"
              onClick={() => setSelectedDoc(null)}
              className="rounded-xl px-6 h-11 font-bold border-slate-200 text-slate-600 hover:bg-white"
            >
              Close
            </Button>
            <Button
              className="rounded-xl px-6 h-11 font-bold bg-violet-600 hover:bg-violet-700 shadow-lg shadow-violet-100"
            >
              Download PDF
            </Button>
          </div>
        </DialogContent>
      </Dialog>

      {/* 5. Ingest Path Modal */}
      <Dialog open={isIngestModalOpen} onOpenChange={setIsIngestModalOpen}>
        <DialogContent className="sm:max-w-md rounded-2xl">
          <DialogHeader>
            <DialogTitle>Bulk Directory Ingest</DialogTitle>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <label className="text-sm font-medium text-slate-700">Server Folder Path</label>
              <Input
                placeholder="e.g. data/resources"
                value={bulkIngestPath}
                onChange={(e) => setBulkIngestPath(e.target.value)}
                className="rounded-xl"
              />
              <p className="text-[11px] text-slate-400">
                Provide an absolute or relative path accessible by the backend server.
              </p>
            </div>
          </div>
          <div className="flex justify-end gap-3">
            <Button variant="outline" onClick={() => setIsIngestModalOpen(false)} className="rounded-xl">
              Cancel
            </Button>
            <Button
              onClick={handleBulkIngest}
              disabled={!bulkIngestPath || isIngesting}
              className="bg-violet-600 hover:bg-violet-700 text-white rounded-xl"
            >
              {isIngesting && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}
              Start Ingestion
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default BrandLibrary;
