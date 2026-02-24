from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List, Union, Literal
from datetime import datetime
from enum import Enum
import json


class FieldStatus(str, Enum):
    """Status of a persona field."""
    SUGGESTED = "suggested"
    CONFIRMED = "confirmed"
    EMPTY = "empty"


class EnrichedFieldBase(BaseModel):
    """Base schema for enriched persona fields with status tracking."""
    value: Any
    status: FieldStatus = FieldStatus.EMPTY
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    evidence: List[str] = Field(default_factory=list)


class EnrichedString(EnrichedFieldBase):
    """Enriched string field with status and evidence."""
    value: str = ""


class EnrichedText(EnrichedFieldBase):
    """Enriched text field (longer content) with status and evidence."""
    value: str = ""


class EnrichedList(EnrichedFieldBase):
    """Enriched list field with status and evidence."""
    value: List[str] = Field(default_factory=list)


class PersonaFieldUpdate(BaseModel):
    """Schema for updating a single enriched field."""
    value: Optional[Any] = None
    status: Optional[FieldStatus] = None
    confidence: Optional[float] = None
    evidence: Optional[List[str]] = None

class PersonaBase(BaseModel):
    name: str
    avatar_url: Optional[str] = None  # DALL-E 3 generated avatar image URL
    persona_type: str = "Patient"
    age: Optional[int] = None
    gender: Optional[str] = None
    condition: Optional[str] = None
    location: Optional[str] = None
    full_persona_json: str
    brand_id: Optional[int] = None
    persona_subtype: Optional[str] = None
    disease_pack: Optional[str] = None
    tagline: Optional[str] = None
    specialty: Optional[str] = None
    practice_setup: Optional[str] = None
    system_context: Optional[str] = None
    decision_influencers: Optional[str] = None
    adherence_to_protocols: Optional[str] = None
    channel_use: Optional[str] = None
    decision_style: Optional[str] = None
    core_insight: Optional[str] = None
    additional_context: Optional[Dict[str, Any]] = None  # Flexible bucket for non-schema insights

class PersonaCreate(BaseModel):
    # This schema is for the input data to the generation endpoint
    age: int
    gender: str
    condition: str
    location: str
    concerns: str
    brand_id: Optional[int] = None
    segment: Optional[str] = None
    disease: Optional[str] = None
    additional_context: Optional[Dict[str, Any]] = None

class PersonaUpdate(BaseModel):
    name: Optional[str] = None
    avatar_url: Optional[str] = None
    persona_type: Optional[str] = None
    persona_subtype: Optional[str] = None
    disease_pack: Optional[str] = None
    tagline: Optional[str] = None
    brand_id: Optional[int] = None
    age: Optional[int] = None
    gender: Optional[str] = None
    condition: Optional[str] = None
    location: Optional[str] = None
    specialty: Optional[str] = None
    practice_setup: Optional[str] = None
    system_context: Optional[str] = None
    decision_influencers: Optional[str] = None
    adherence_to_protocols: Optional[str] = None
    channel_use: Optional[str] = None
    decision_style: Optional[str] = None
    core_insight: Optional[str] = None
    additional_context: Optional[Dict[str, Any]] = None
    full_persona_json: Optional[Union[str, Dict[str, Any]]] = None
    # Field-level updates for partial persona JSON updates
    field_updates: Optional[Dict[str, PersonaFieldUpdate]] = None
    # Mark specific fields as confirmed (user edited/approved)
    confirm_fields: Optional[List[str]] = None

class Persona(PersonaBase):
    id: int
    created_at: datetime
    
    # Custom getter to parse the JSON string into a dictionary
    @property
    def full_persona(self) -> Dict[str, Any]:
        return json.loads(self.full_persona_json)

    class Config:
        from_attributes = True

class PersonaSearchRequest(BaseModel):
    prompt: str

class PersonaSearchFilters(BaseModel):
    age_min: Optional[int] = None
    age_max: Optional[int] = None
    gender: Optional[str] = None
    condition: Optional[str] = None
    location: Optional[str] = None
    persona_type: Optional[str] = None
    brand_id: Optional[int] = None
    limit: int = 10

# Cohort Analysis Schemas
class CohortAnalysisRequest(BaseModel):
    persona_ids: List[int]
    stimulus_text: str
    metrics: List[str]
    metric_weights: Optional[Dict[str, float]] = None
    questions: Optional[List[str]] = None

class PersonaResponse(BaseModel):
    persona_id: int
    persona_name: str
    responses: Dict[str, Any]
    reasoning: str
    answers: Optional[List[str]] = None

class CohortAnalysisResponse(BaseModel):
    cohort_size: int
    stimulus_text: str
    metrics_analyzed: List[str]
    questions: Optional[List[str]] = None
    individual_responses: List[PersonaResponse]
    summary_statistics: Dict[str, Any]
    insights: List[str]
    created_at: datetime

# Schemas for Simulation remain unchanged for now, but will be needed later.
class SimulationBase(BaseModel):
    persona_id: int
    scenario: str
    parameters: Dict[str, Any]

class SimulationCreate(SimulationBase):
    pass

class Simulation(SimulationBase):
    id: int
    results: Optional[Dict[str, Any]] = None
    response_rate: Optional[float] = None
    insights: Optional[str] = None
    created_at: datetime
    
    class Config:
        from_attributes = True

class SimulationRequest(BaseModel):
    persona_id: int
    scenario: str
    parameters: Dict[str, Any]

# Schemas for Saved Simulations
class SavedSimulationBase(BaseModel):
    name: str
    simulation_data: Dict[str, Any]

class SavedSimulationCreate(SavedSimulationBase):
    pass


class SavedSimulation(SavedSimulationBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True

# Brand Library Schemas
class BrandBase(BaseModel):
    name: str

class BrandCreate(BrandBase):
    pass

class Brand(BrandBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True

class BrandInsight(BaseModel):
    type: str
    text: str
    segment: Optional[str] = "General"
    source_snippet: Optional[str] = None
    source_document: Optional[str] = None



class BrandDocumentBase(BaseModel):
    brand_id: int
    filename: str
    category: Optional[str] = None  # Document category/classification
    document_type: Optional[str] = None  # DocumentType enum value
    summary: Optional[str] = None
    extracted_insights: Optional[List[BrandInsight]] = None
    vector_store_id: Optional[str] = None
    chunk_size: Optional[int] = None
    chunk_ids: Optional[List[str]] = None

class BrandDocumentCreate(BrandDocumentBase):
    filepath: Optional[str] = None  # Made optional for flexibility

class BrandDocument(BrandDocumentBase):
    id: int
    filepath: Optional[str] = None  # May be None for newer documents
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class BrandContextResponse(BaseModel):
    brand_id: int
    brand_name: str
    motivations: List[BrandInsight]
    beliefs: List[BrandInsight]
    tensions: List[BrandInsight]


class PersonaBrandEnrichmentRequest(BaseModel):
    brand_id: int
    target_segment: Optional[str] = None
    target_fields: Optional[List[str]] = None


class BrandSuggestionRequest(BaseModel):
    target_segment: Optional[str] = None
    persona_type: Optional[str] = "Patient"
    limit_per_category: int = 5


class BrandSuggestionResponse(BaseModel):
    brand_id: int
    brand_name: str
    target_segment: Optional[str] = None
    persona_type: Optional[str] = "Patient"
    motivations: List[str]
    beliefs: List[str]
    tensions: List[str]


# === Chat Schemas ===

class ChatMessageBase(BaseModel):
    role: str
    content: str
    citations: Optional[List[Dict[str, Any]]] = None
    thought_process: Optional[str] = None

class ChatMessageCreate(ChatMessageBase):
    pass

class ChatMessage(ChatMessageBase):
    id: int
    session_id: int
    created_at: datetime
    
    class Config:
        from_attributes = True

class ChatSessionBase(BaseModel):
    persona_id: int
    brand_id: Optional[int] = None
    name: Optional[str] = None

class ChatSessionCreate(ChatSessionBase):
    pass

class ChatSession(ChatSessionBase):
    id: int
    created_at: datetime
    updated_at: Optional[datetime] = None
    # messages list can be populated manually or via ORM if relationships are set
    
    class Config:
        from_attributes = True

# === Synthetic Testing Schemas ===

class SyntheticAsset(BaseModel):
    id: str  # Frontend generated UUID
    name: str
    text_content: Optional[str] = ""
    image_data: Optional[str] = None # Base64

class SyntheticTestingRequest(BaseModel):
    persona_ids: List[int]
    assets: List[SyntheticAsset]

class AssetScores(BaseModel):
    motivation_to_prescribe: int
    connection_to_story: int
    differentiation: int
    believability: int
    stopping_power: int

class QualitativeFeedback(BaseModel):
    does_well: List[str]
    does_not_do_well: List[str]
    considerations: List[str]

class SyntheticResultItem(BaseModel):
    persona_id: int
    persona_name: str
    asset_id: str
    scores: Optional[AssetScores] = None
    overall_preference_score: Optional[int] = None
    feedback: Optional[QualitativeFeedback] = None
    error: Optional[str] = None

class AggregatedAssetResult(BaseModel):
    asset_name: str
    average_scores: Dict[str, float]
    average_preference: int
    respondent_count: int

class SyntheticTestingResponse(BaseModel):
    results: List[SyntheticResultItem]
    aggregated: Dict[str, AggregatedAssetResult]
    metadata: Dict[str, Any]

class SyntheticTestRunCreate(BaseModel):
    name: str
    persona_ids: List[int]
    assets: List[Dict[str, Any]]
    results: SyntheticTestingResponse

class SyntheticTestRun(BaseModel):
    id: int
    name: str
    persona_ids: List[int]
    assets: List[Dict[str, Any]]
    results: SyntheticTestingResponse
    created_at: datetime
    
    class Config:
        from_attributes = True

class GenerationRequest(BaseModel):
    segment_name: str
    segment_description: str
    brand_id: int

class SaveGeneratedPersonaRequest(BaseModel):
    brand_id: int
    segment_name: str
    persona_profile: Dict[str, Any]

# === Panel Feedback Schemas ===

class PanelFeedbackRequest(BaseModel):
    persona_ids: List[int]
    stimulus_text: str
    stimulus_images: Optional[List[Dict[str, Any]]] = None
    content_type: str = "text"

class PanelFeedbackResponse(BaseModel):
    persona_cards: List[Dict[str, Any]]
    summary_by_card: List[Dict[str, Any]]
    summary: Dict[str, Any]
    metadata: Dict[str, Any]


class PanelFeedbackResponseV2(BaseModel):
    images: List[Dict[str, Any]]
    metadata: Dict[str, Any]


class PanelFeedbackRequestV2(BaseModel):
    campaign_id:str
    task_id:str
    persona_ids: List[int]
    stimulus_text: str
    stimulus_images: Optional[List[Dict[str, Any]]] = None
    content_type: str = "text"


class SyntheticAssetV2(BaseModel):
    id: str  # Frontend generated UUID
    name: str
    text_content: Optional[str] = ""
    url:str
    image_url_str:str

class SyntheticTestingRequestV2(BaseModel):
    campaign_id:str
    task_id:str
    persona_ids: List[int]
    assets: List[SyntheticAssetV2]


class SyntheticCardV2(BaseModel):
    persona_id: Optional[int] = None
    persona_name: Optional[str] = None
    role: Optional[str] = None
    segment: Optional[str] = None
    key_characteristics: Optional[List[str]] = None
    avatar_url: Optional[str] = None

    clean_read: Optional[str] = None
    key_themes: Optional[List[str]] = None
    strengths: Optional[List[str]] = None
    weaknesses: Optional[List[str]] = None

    scores: Optional[Dict[str, float]] = None
    overall_preference_score: Optional[float] = None

    card_number: Optional[int] = None
    card_key: Optional[str] = None
    persona_index: Optional[int] = None
    image_index: Optional[int] = None

    image_id: Optional[str] = None
    image_url: Optional[str] = None
    summary: Optional[Dict[str, Any]] = None

    error: Optional[str] = None


class SyntheticImageResultV2(BaseModel):
    image_id: str
    image_url: Optional[str] = None
    image_url_str: Optional[str] = None
    cards: List[SyntheticCardV2] = []


class SyntheticAggregatedMetricsV2(BaseModel):
    motivation_to_prescribe: float = 0.0
    connection_to_story: float = 0.0
    differentiation: float = 0.0
    believability: float = 0.0
    stopping_power: float = 0.0


class SyntheticAggregatedItemV2(BaseModel):
    asset_name: Optional[str] = None
    average_scores: SyntheticAggregatedMetricsV2 = SyntheticAggregatedMetricsV2()
    average_preference: int = 0
    respondent_count: int = 0


class SyntheticTestingMetadataV2(BaseModel):
    campaign_id: str
    task_id: str
    personas_count: int
    assets_count: int
    timestamp: str


class SyntheticTestingResponseV2(BaseModel):
    results: List[SyntheticImageResultV2]
    aggregated: Dict[str, SyntheticAggregatedItemV2]
    metadata: SyntheticTestingMetadataV2
