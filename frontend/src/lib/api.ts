import axios from 'axios';
import type { AnalysisResults } from '@/types/analytics';

// API configuration - prefer Vite dev proxy for Codespaces compatibility
const envBase = (import.meta as any).env?.VITE_API_URL as string | undefined;

let baseURL = '';

if (envBase && envBase.trim()) {
  baseURL = envBase.trim();
}

console.log('🔧 API baseURL configured as:', baseURL || 'Vite proxy (relative)');

export const api = axios.create({
  baseURL,
  timeout: 0  // Remove timeout - allow long-running LLM requests
});

// Add request logging
api.interceptors.request.use(
  (config) => {
    console.log('📤 API Request:', {
      method: config.method?.toUpperCase(),
      url: config.url,
      baseURL: config.baseURL,
      fullURL: `${config.baseURL}${config.url}`,
      headers: config.headers,
      dataType: config.data instanceof FormData ? 'FormData' : typeof config.data,
      timestamp: new Date().toISOString()
    });

    if (config.data instanceof FormData) {
      console.log('📤 FormData contents:');
      for (const [key, value] of config.data.entries()) {
        if (value instanceof File) {
          console.log(`  ${key}: File(${value.name}, ${value.size} bytes, ${value.type})`);
        } else {
          console.log(`  ${key}: ${value}`);
        }
      }
    } else if (config.data) {
      console.log('📤 Request body:', config.data);
    }

    return config;
  },
  (error) => {
    console.error('❌ Request error:', error);
    return Promise.reject(error);
  }
);

// Add response logging with retry logic
api.interceptors.response.use(
  (response) => {
    console.log('📥 API Response:', {
      status: response.status,
      url: response.config.url,
      dataType: typeof response.data,
      dataLength: Array.isArray(response.data) ? response.data.length : 'N/A'
    });

    if (response.data) {
      console.log('📥 Response data keys:', Object.keys(response.data));
      if (response.data.individual_responses) {
        console.log('📥 Individual responses count:', response.data.individual_responses.length);
      }
    }
    return response;
  },
  async (error) => {
    console.error('❌ API Response Error:', {
      message: error.message,
      status: error.response?.status,
      statusText: error.response?.statusText,
      url: error.config?.url,
      responseData: error.response?.data,
      timestamp: new Date().toISOString()
    });

    // Simple exponential backoff retry for idempotent GET requests only
    const config: any = error.config;
    if (config && config.method === 'get') {
      config.__retryCount = config.__retryCount || 0;
      if (config.__retryCount < 3) {
        config.__retryCount += 1;
        const delay = Math.pow(2, config.__retryCount) * 200; // 200,400,800 ms
        console.log(`🔄 Retrying GET request (attempt ${config.__retryCount}/3) after ${delay}ms`);
        await new Promise(res => setTimeout(res, delay));
        return api(config);
      }
    }

    return Promise.reject(error);
  }
);

export function getApiBaseUrl() { return baseURL; }

export async function checkHealth(): Promise<{ ok: boolean; personas?: number }> {
  try {
    const r = await api.get('/health/db');
    return { ok: r.data.status === 'ok', personas: r.data.personas };
  } catch {
    return { ok: false };
  }
}

// Helper wrappers
// Field status types for enriched persona fields
export type FieldStatus = 'suggested' | 'confirmed' | 'empty';

export interface EnrichedField<T = string> {
  value: T;
  status: FieldStatus;
  confidence: number;
  evidence: string[];
  evidence_verified?: number;
}

export interface PersonaFieldUpdate {
  value?: any;
  status?: FieldStatus;
  confidence?: number;
  evidence?: string[];
}

export interface PersonaUpdatePayload {
  name?: string;
  avatar_url?: string;
  persona_type?: string;
  age?: number;
  gender?: string;
  condition?: string;
  location?: string;
  full_persona_json?: string | Record<string, any>;
  field_updates?: Record<string, PersonaFieldUpdate>;
  confirm_fields?: string[];
}

export interface TranscriptExtractionOptions {
  use_llm?: boolean;
  verify_quotes?: boolean;
}

export interface ExtractionSummary {
  motivations_count: number;
  beliefs_count: number;
  tensions_count: number;
  extraction_method: string;
  confidence_score?: number;
}

export interface TranscriptSuggestions {
  schema_version: string;
  extraction_method?: string;
  summary: string;
  source: {
    character_count: number;
    sentence_count: number;
    excerpt: string;
    filename?: string;
    received_via?: string;
  };
  demographics: {
    age: EnrichedField;
    gender: EnrichedField;
    location: EnrichedField;
    condition?: EnrichedField;
  };
  legacy: {
    motivations: string[];
    beliefs: string[];
    tensions: string[];
  };
  core: Record<string, any>;
  extraction_summary?: ExtractionSummary;
  missing_info?: string[];
}

export interface PersonaExport {
  id: number;
  name: string;
  persona_type: string;
  demographics: {
    age: number;
    gender: string;
    condition: string;
    location: string;
  };
  full_persona: Record<string, any>;
  motivations: string[];
  beliefs: string[];
  pain_points: string[];
  medical_background: string;
  lifestyle_and_values: string;
  communication_preferences: Record<string, any>;
  mbt?: Record<string, any>;
  decision_drivers?: Record<string, any>;
  messaging?: Record<string, any>;
  barriers_objections?: Record<string, any>;
  channel_behavior?: Record<string, any>;
  hcp_context?: Record<string, any>;
  export_metadata: {
    exported_at: string;
    schema_version: string;
    includes_evidence: boolean;
  };
}

// Persona Comparison Types
export interface ComparisonInsightItem {
  title: string;
  description: string;
}

export interface AttributeDifferentiation {
  similarity_score: number;
  highlight_level: 'high' | 'medium' | 'low';
  values: any[];
}

export interface ComparisonInsights {
  key_similarities: ComparisonInsightItem[];
  key_differences: ComparisonInsightItem[];
  strategic_insights: string[];
  attribute_scores: Record<string, AttributeDifferentiation>;
  suggested_questions: string[];
  personas_compared: Array<{ id: number; name: string }>;
}

export interface ComparisonAnswer {
  answer: string;
  reasoning: string;
  relevant_attributes: string[];
}

export const PersonasAPI = {
  list: (brandId?: number) => {
    const params = brandId !== undefined ? { brand_id: brandId } : {};
    return api.get('/api/personas/', { params }).then(r => r.data);
  },
  get: (id: number) => api.get(`/api/personas/${id}`).then(r => r.data),
  generate: (payload: any) => api.post('/api/personas/generate', payload).then(r => r.data),
  createManual: (payload: any) => api.post('/api/personas/manual', payload).then(r => r.data),
  delete: (id: number) => api.delete(`/api/personas/${id}`),
  recruit: (prompt: string) => api.post('/api/personas/recruit', { prompt }).then(r => r.data),
  update: (id: number, payload: PersonaUpdatePayload) =>
    api.put(`/api/personas/${id}`, payload).then(r => r.data),

  // Save with field confirmation - marks edited fields as confirmed
  saveWithConfirmation: (id: number, payload: PersonaUpdatePayload, confirmedFields: string[]) =>
    api.put(`/api/personas/${id}`, {
      ...payload,
      confirm_fields: confirmedFields,
    }).then(r => r.data),

  // Update specific fields with status tracking
  updateFields: (id: number, fieldUpdates: Record<string, PersonaFieldUpdate>, confirmFields?: string[]) =>
    api.put(`/api/personas/${id}`, {
      field_updates: fieldUpdates,
      confirm_fields: confirmFields,
    }).then(r => r.data),

  enrichFromBrand: (id: number, payload: { brand_id: number; target_segment?: string; target_fields?: string[] }) =>
    api.post(`/api/personas/${id}/enrich-from-brand`, payload).then(r => r.data),
  regenerateAvatar: (id: number) => api.post(`/api/personas/${id}/regenerate-avatar`).then(r => r.data),

  // Enhanced transcript extraction with LLM and quote verification
  extractFromTranscript: (
    payload: FormData | { transcript_text: string },
    options: TranscriptExtractionOptions = { use_llm: true, verify_quotes: true }
  ): Promise<TranscriptSuggestions> => {
    const formData = payload instanceof FormData ? payload : new FormData();

    if (!(payload instanceof FormData)) {
      formData.append('transcript_text', payload.transcript_text);
    }

    // Add extraction options
    formData.append('use_llm', String(options.use_llm ?? true));
    formData.append('verify_quotes', String(options.verify_quotes ?? true));

    return api.post('/api/personas/from-transcript', formData).then(r => r.data);
  },

  // Export persona for simulation
  exportForSimulation: (id: number, includeEvidence: boolean = true): Promise<PersonaExport> =>
    api.get(`/api/personas/${id}/export`, {
      params: { include_evidence: includeEvidence }
    }).then(r => r.data),

  // Check similarity before creating a new persona
  checkSimilarity: (payload: {
    persona_attrs: Record<string, any>;
    brand_id?: number;
    threshold?: number;
  }): Promise<{
    has_similar: boolean;
    most_similar: { id: number; name: string } | null;
    similarity_score: number;
    overlapping_traits: string[];
    key_differences?: string[];
    recommendation: 'use_existing' | 'proceed_with_caution' | 'safe_to_create';
  }> => api.post('/api/personas/check-similarity', payload).then(r => r.data),

  // Persona Comparison APIs
  compareAnalyze: (personaIds: number[]): Promise<ComparisonInsights> =>
    api.post('/api/personas/compare/analyze', { persona_ids: personaIds }).then(r => r.data),

  compareAsk: (personaIds: number[], question: string): Promise<ComparisonAnswer> =>
    api.post('/api/personas/compare/ask', { persona_ids: personaIds, question }).then(r => r.data),
};

// Persona Discovery API - Research-driven persona creation
export interface DiscoveredSegment {
  name: string;
  description: string;
  differentiators: string[];
  evidence: string;
}

export interface DiscoveryResponse {
  segments: DiscoveredSegment[];
}

export interface GeneratedPersonaProfile {
  name: string;
  age: number;
  gender: string;
  condition: string;
  location: string;
  persona_type: string;
  tagline?: string;
  core_insight?: string;
  core?: Record<string, any>;
  additional_context?: Record<string, any>;
  [key: string]: any;
}

export const DiscoveryAPI = {
  // Step 1: Discover segments from brand documents
  discoverSegments: (brandId: number, limit: number = 5): Promise<DiscoveryResponse> =>
    api.post('/api/personas/discover-from-docs', { brand_id: brandId, limit }).then(r => r.data),

  // Step 2: Generate a full persona from a discovered or manually entered segment
  generateFromSegment: (brandId: number, segmentName: string, segmentDescription: string): Promise<any> =>
    api.post('/api/personas/generate-from-discovery', {
      brand_id: brandId,
      segment_name: segmentName,
      segment_description: segmentDescription,
    }).then(r => r.data),

  // Step 3: Save a reviewed persona
  saveGenerated: (payload: { brand_id: number; segment_name: string; persona_profile: any }): Promise<any> =>
    api.post('/api/personas/save-generated', payload).then(r => r.data),
};

export interface BrandInsight {
  type: "Motivation" | "Belief" | "Tension";
  text: string;
  segment?: string;
  source_snippet?: string;
  source_document?: string;
}

export interface BrandContextResponse {
  brand_id: number;
  brand_name: string;
  motivations: BrandInsight[];
  beliefs: BrandInsight[];
  tensions: BrandInsight[];
}

export interface BrandSuggestionResponse {
  brand_id: number;
  brand_name: string;
  target_segment?: string;
  persona_type?: string;
  motivations: string[];
  beliefs: string[];
  tensions: string[];
}

export const BrandsAPI = {
  list: () => api.get('/api/brands').then(r => r.data),
  create: (name: string) => api.post('/api/brands', { name }).then(r => r.data),
  getDocuments: (brandId: number) => api.get(`/api/brands/${brandId}/documents`).then(r => r.data),
  getPersonas: (brandId: number) => api.get(`/api/brands/${brandId}/personas`).then(r => r.data),
  getPersonasCount: (brandId: number): Promise<{ brand_id: number; brand_name: string; persona_count: number }> =>
    api.get(`/api/brands/${brandId}/personas/count`).then(r => r.data),
  upload: (brandId: number, file: File) => {
    const formData = new FormData();
    formData.append('file', file);
    return api.post(`/api/brands/${brandId}/upload`, formData).then(r => r.data);
  },
  ingestFolder: (brandId: number, folderPath: string) =>
    api.post(`/api/brands/${brandId}/ingest-folder`, { folder_path: folderPath, recursive: true }).then(r => r.data),
  seed: (brandId: number) => api.post(`/api/brands/${brandId}/seed`).then(r => r.data),
  getContext: (brandId: number, params?: { target_segment?: string; limit_per_category?: number }) =>
    api.get<BrandContextResponse>(`/api/brands/${brandId}/context`, { params }).then(r => r.data),
  getSuggestions: (brandId: number, payload: { target_segment?: string; persona_type?: string; limit_per_category?: number }) =>
    api.post<BrandSuggestionResponse>(`/api/brands/${brandId}/persona-suggestions`, payload).then(r => r.data),
  enrichPersona: (personaId: number, payload: { brand_id: number; target_segment?: string; target_fields?: string[] }) =>
    api.post(`/api/personas/${personaId}/enrich-from-brand`, payload).then(r => r.data),
  getDocumentContent: (brandId: number, documentId: number): Promise<{ content: string }> =>
    api.get(`/api/brands/${brandId}/documents/${documentId}/content`).then(r => r.data)
};

export interface Segment {
  name: string;
  persona_type: string;
  description: string;
  motivations: string[];
  beliefs: string[];
  pain_points: string[];
}

export interface DiseasePack {
  name: string;
  condition: string;
}

export const SegmentsAPI = {
  list: () => api.get<Segment[]>('/api/segments').then(r => r.data)
};

export const DiseasePacksAPI = {
  list: () => api.get<DiseasePack[]>('/api/disease-packs').then(r => r.data)
};

export const CohortAPI = {
  analyze: (payload: any) => {
    // Check if payload is FormData (multimodal) or regular object (text-only)
    if (payload instanceof FormData) {
      // Always use multimodal endpoint for FormData requests
      console.log('📤 Using multimodal endpoint for FormData request');
      return api.post('/cohorts/analyze-multimodal', payload).then(r => r.data);
    } else {
      // Regular JSON payload for text-only
      console.log('📤 Using regular endpoint for JSON request');
      return api.post('/cohorts/analyze', payload).then(r => r.data);
    }
  },
  improveImage: (analysisResults: any, originalImage: File) => {
    const formData = new FormData();
    formData.append('analysis_results', JSON.stringify(analysisResults));
    formData.append('original_image', originalImage);
    return api.post('/cohorts/improve-image', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    }).then(r => r.data);
  }
};

export const StatsAPI = {
  stats: () => api.get('/stats').then(r => r.data)
};

export interface SavedSimulation {
  id: number;
  name: string;
  created_at: string;
  simulation_data: AnalysisResults;
}

export const SavedSimulationsAPI = {
  list: () => api.get<SavedSimulation[]>('/simulations/saved'),
  get: (id: number) => api.get<SavedSimulation>(`/simulations/saved/${id}`),
  save: (data: { name: string; simulation_data: AnalysisResults }) => api.post<SavedSimulation>('/simulations/save', data),
  delete: (id: number) => api.delete(`/simulations/saved/${id}`),
};

// Veeva CRM Integration API
export interface HCPProfile {
  npi: string;
  name: string;
  specialty: string;
  institution: string;
  location: string;
  tier: string;
  interaction_history: {
    last_call: string;
    call_frequency: string;
    engagement_score: number;
    preferred_topics: string[];
    objections: string[];
    call_notes: string;
  };
  prescribing_patterns: {
    preferred_brands: string[];
    patient_volume: string;
    adoption_rate: string;
    therapeutic_areas: string[];
  };
  patient_demographics: {
    avg_age: number;
    gender_split: { male: number; female: number };
    insurance_mix: { commercial: number; medicare: number; medicaid: number };
    comorbidities: string[];
  };
}

export interface CRMConnectionStatus {
  status: string;
  last_sync: string;
  sync_status: string;
  total_hcp_profiles: number;
  data_freshness: string;
  environment: string;
  vault_instance: string;
}

export interface CRMImportResult {
  success: boolean;
  created_personas: Array<{
    id: number;
    name: string;
    source_hcp: string;
    specialty: string;
    condition: string;
  }>;
  total_created: number;
  processing_time: string;
  import_summary: {
    source: string;
    hcp_profiles_processed: number;
    personas_generated: number;
  };
}

export const VeevaCRMAPI = {
  getConnectionStatus: (): Promise<CRMConnectionStatus> =>
    api.get('/crm/connection-status').then(r => r.data),

  getHCPProfiles: (specialty?: string, tier?: string): Promise<{
    profiles: HCPProfile[];
    total_count: number;
    filtered_by: { specialty?: string; tier?: string };
    sync_timestamp: string;
  }> => {
    const params = new URLSearchParams();
    if (specialty) params.append('specialty', specialty);
    if (tier) params.append('tier', tier);
    const query = params.toString();
    return api.get(`/crm/hcp-profiles${query ? `?${query}` : ''}`).then(r => r.data);
  },

  importPersonas: (selectedNPIs: string[], options: any = {}): Promise<CRMImportResult> =>
    api.post('/crm/import-personas', {
      selected_npis: selectedNPIs,
      options
    }).then(r => r.data)
};

// Asset Intelligence API - Nano Banana Pro integration
export interface AssetAnalysisResult {
  persona_id: number;
  persona_name: string;
  id?: number; // Optional as older records might not have it attached in frontend types immediately
  annotated_image: string | null; // Base64 encoded
  text_summary: string;
  error: string | null;
  // Knowledge Graph fields
  citations?: Array<{
    id: string;
    text: string;
    source_quote?: string;
    confidence?: number;
  }>;
  research_alignment_score?: number;
  alignment_summary?: string;
  knowledge_enabled?: boolean;
}

export interface AssetAnalysisResponse {
  success: boolean;
  asset_filename: string;
  personas_analyzed: number;
  results: AssetAnalysisResult[];
}

export interface AssetHistoryItem {
  image_hash: string;
  asset_name: string;
  created_at: string;
  results: AssetAnalysisResult[];
}

export interface AssetHistoryResponse {
  total_assets: number;
  assets: AssetHistoryItem[];
}

export const AssetIntelligenceAPI = {
  analyze: (file: File, personaIds: number[]): Promise<AssetAnalysisResponse> => {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('persona_ids', personaIds.join(','));
    return api.post('/api/assets/analyze', formData).then(r => r.data);
  },
  getHistory: (): Promise<AssetHistoryResponse> => {
    return api.get('/api/assets/history/full').then(r => r.data);
  },
  deleteHistory: (analysisId: number): Promise<{ success: boolean; message: string }> => {
    return api.delete(`/api/assets/history/${analysisId}`).then(r => r.data);
  },
  clearCache: (): Promise<{ success: boolean; deleted_count: number }> => {
    return api.delete('/api/assets/cache/clear').then(r => r.data);
  }
};

// Knowledge Graph API
export type KnowledgeNode = {
  id: string;
  text: string;
  source_quote?: string;
  segment?: string;
  verified: boolean;
  node_type: string;
  confidence: number;
  source_document_id?: number | string;
  summary?: string;
  journey_stage?: string;
  created_at?: string;
  [key: string]: any;
};

export interface KnowledgeRelation {
  id: number;
  from_node_id: string;
  to_node_id: string;
  relation_type: string;
  strength: number;
  context?: string;
  inferred_by: string;
  created_at?: string;
}

export interface KnowledgeGraph {
  brand_id: number;
  nodes: Array<{
    id: string;
    type: string;
    data: any;
    position: { x: number; y: number };
  }>;
  edges: Array<{
    id: string;
    source: string;
    target: string;
    type: string;
    data: any;
    label: string;
    animated: boolean;
  }>;
  stats: {
    total_nodes: number;
    total_edges: number;
    node_types: Record<string, number>;
    contradictions: number;
  };
}


export const KnowledgeGraphAPI = {
  // Get nodes for a brand
  getNodes: (brandId: number, options?: { node_type?: string; segment?: string }): Promise<{ total: number; nodes: KnowledgeNode[] }> =>
    api.get(`/api/knowledge/brands/${brandId}/nodes`, { params: options }).then(r => r.data),

  // Get relations for a brand
  getRelations: (brandId: number, options?: { relation_type?: string }): Promise<{ total: number; relations: KnowledgeRelation[] }> =>
    api.get(`/api/knowledge/brands/${brandId}/relations`, { params: options }).then(r => r.data),

  // Get full graph for visualization
  getGraph: (brandId: number): Promise<KnowledgeGraph> =>
    api.get(`/api/knowledge/brands/${brandId}/graph`).then(r => r.data),

  // Extract knowledge from a document
  extractFromDocument: (documentId: number): Promise<{
    success: boolean;
    document_id: number;
    document_type: string;
    nodes_extracted: number;
    relationships_inferred: number;
    node_ids: string[];
  }> => api.post(`/api/knowledge/documents/${documentId}/extract`).then(r => r.data),

  // Enrich a persona from the knowledge graph
  enrichPersona: (brandId: number, personaId: number): Promise<{
    success: boolean;
    persona_id: number;
    enriched: boolean;
    nodes_applied: number;
  }> => api.post(`/api/knowledge/brands/${brandId}/personas/${personaId}/enrich`).then(r => r.data),

  // Delete a node
  deleteNode: (nodeId: string): Promise<{ success: boolean; deleted_node_id: string }> =>
    api.delete(`/api/knowledge/nodes/${nodeId}`).then(r => r.data),

  // Verify a node
  verifyNode: (nodeId: string, verified: boolean = true): Promise<{ success: boolean; node_id: string; verified: boolean }> =>
    api.put(`/api/knowledge/nodes/${nodeId}/verify`, null, { params: { verified } }).then(r => r.data),
};



// Chat API
export interface ChatSession {
  id: number;
  persona_id: number;
  brand_id?: number;
  name: string;
  created_at: string;
  updated_at: string;
}

export interface ChatMessage {
  id: number;
  session_id: number;
  role: 'user' | 'assistant' | 'system';
  content: string;
  created_at: string;
  citations?: any;
  thought_process?: string;
}

export const ChatAPI = {
  createSession: (personaId: number, brandId?: number) =>
    api.post<ChatSession>('/api/chat/sessions', { persona_id: personaId, brand_id: brandId }).then(r => r.data),

  getSession: (sessionId: number) =>
    api.get<ChatSession>(`/api/chat/sessions/${sessionId}`).then(r => r.data),

  getHistory: (sessionId: number) =>
    api.get<ChatMessage[]>(`/api/chat/sessions/${sessionId}/messages`).then(r => r.data),

  sendMessage: (sessionId: number, content: string) =>
    api.post<ChatMessage>(`/api/chat/sessions/${sessionId}/messages`, { content, role: 'user' }).then(r => r.data),
};

// Panel Feedback API - Structured persona feedback for marketing assets
export interface PersonaFeedbackCard {
  persona_id: number;
  persona_name: string;
  role: string;
  segment: string;
  key_characteristics: string[];
  avatar_url?: string;
  clean_read: string;
  key_themes: string[];
  strengths: string[];
  weaknesses: string[];
  error?: string;
}

export interface PanelFeedbackSummary {
  aggregated_themes: string[];
  dissent_highlights: string[];
  recommendations: Array<{
    suggestion: string;
    reasoning: string;
  }>;
}

export interface PanelFeedbackResponse {
  persona_cards: PersonaFeedbackCard[];
  summary: PanelFeedbackSummary;
  metadata: {
    persona_count: number;
    content_type: string;
    created_at: string;
  };
}

export const PanelFeedbackAPI = {
  analyze: (
    personaIds: number[],
    stimulusText: string,
    stimulusImages?: Array<{ filename: string; content_type: string; data: string }>,
    contentType: string = 'text'
  ): Promise<PanelFeedbackResponse> =>
    api.post('/api/panel-feedback', {
      persona_ids: personaIds,
      stimulus_text: stimulusText,
      stimulus_images: stimulusImages,
      content_type: contentType
    }).then(r => r.data),
};

// Synthetic Testing API
export interface AssetScores {
  motivation_to_prescribe: number;
  connection_to_story: number;
  differentiation: number;
  believability: number;
  stopping_power: number;
}

export interface QualitativeFeedback {
  does_well: string[];
  does_not_do_well: string[];
  considerations: string[];
}

export interface SyntheticResultItem {
  persona_id: number;
  persona_name: string;
  asset_id: string;
  scores: AssetScores;
  overall_preference_score: number;
  feedback: QualitativeFeedback;
  error?: string;
}

export interface AggregatedAssetResult {
  asset_name: string;
  average_scores: Record<string, number>;
  average_preference: number;
  respondent_count: number;
}

export interface SyntheticTestingResponse {
  results: SyntheticResultItem[];
  aggregated: Record<string, AggregatedAssetResult>;
  metadata: {
    personas_count: number;
    assets_count: number;
    timestamp: string;
  };
}

export interface SyntheticTestRun {
  id: number;
  name: string;
  persona_ids: number[];
  assets: any[];
  results: SyntheticTestingResponse;
  created_at: string;
}

export const SyntheticTestingAPI = {
  analyze: (
    personaIds: number[],
    assets: Array<{ id: string; name: string; image_data?: string; text_content: string }>
  ): Promise<SyntheticTestingResponse> =>
    api.post('/api/synthetic-testing/analyze', {
      persona_ids: personaIds,
      assets: assets
    }).then(r => r.data),

  listRuns: (): Promise<SyntheticTestRun[]> =>
    api.get('/api/synthetic/runs').then(r => r.data),

  saveRun: (payload: { name: string; persona_ids: number[]; assets: any[]; results: SyntheticTestingResponse }): Promise<SyntheticTestRun> =>
    api.post('/api/synthetic/runs', payload).then(r => r.data),

  getRun: (id: number): Promise<SyntheticTestRun> =>
    api.get(`/api/synthetic/runs/${id}`).then(r => r.data),
};

