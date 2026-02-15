from sqlalchemy import Column, Integer, String, Text, DateTime, JSON, Float, ForeignKey, Boolean, Enum
from sqlalchemy.sql import func
from .database import Base
import datetime
import enum


# === Document Type Classification ===
class DocumentType(enum.Enum):
    """Classification of brand documents for knowledge extraction."""
    BRAND_MESSAGING = "brand_messaging"
    DISEASE_LITERATURE = "disease_literature"
    INTERVIEW_TRANSCRIPT = "interview_transcript"
    COMPETITIVE_INTEL = "competitive_intel"


# === Knowledge Graph Node Types (Pharma-specific) ===
class NodeType(enum.Enum):
    """Types of knowledge nodes tailored for pharma marketing."""
    # Brand Pillars
    KEY_MESSAGE = "key_message"
    VALUE_PROPOSITION = "value_proposition"
    DIFFERENTIATOR = "differentiator"
    PROOF_POINT = "proof_point"
    
    # Disease Knowledge
    EPIDEMIOLOGY = "epidemiology"
    SYMPTOM_BURDEN = "symptom_burden"
    TREATMENT_LANDSCAPE = "treatment_landscape"
    UNMET_NEED = "unmet_need"
    
    # Patient Insights
    PATIENT_MOTIVATION = "patient_motivation"
    PATIENT_BELIEF = "patient_belief"
    PATIENT_TENSION = "patient_tension"
    JOURNEY_INSIGHT = "journey_insight"
    
    # HCP Insights
    PRESCRIBING_DRIVER = "prescribing_driver"
    CLINICAL_CONCERN = "clinical_concern"
    PRACTICE_CONSTRAINT = "practice_constraint"
    
    # Market
    COMPETITOR_POSITION = "competitor_position"
    MARKET_BARRIER = "market_barrier"


# === Knowledge Graph Relationship Types ===
class RelationType(enum.Enum):
    """Types of relationships between knowledge nodes."""
    ADDRESSES = "addresses"        # Message addresses a tension
    SUPPORTS = "supports"          # Evidence supports a claim
    CONTRADICTS = "contradicts"    # Insight contradicts messaging
    TRIGGERS = "triggers"          # Symptom triggers emotion
    INFLUENCES = "influences"      # Factor influences decision
    RESONATES_WITH = "resonates"   # Message resonates with motivation


class Persona(Base):
    __tablename__ = "personas"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    avatar_url = Column(String, nullable=True)  # DALL-E 3 generated avatar image URL
    persona_type = Column(String, default="Patient")
    persona_subtype = Column(String, nullable=True)
    disease_pack = Column(String, nullable=True)
    tagline = Column(Text, nullable=True)
    # Brand ownership - optional, allows personas to belong to a specific brand
    brand_id = Column(Integer, ForeignKey("brands.id"), nullable=True, index=True)
    # Store input attributes for filtering
    age = Column(Integer)
    gender = Column(String)
    condition = Column(String)
    location = Column(String)
    specialty = Column(String, nullable=True)
    practice_setup = Column(Text, nullable=True)
    system_context = Column(Text, nullable=True)
    decision_influencers = Column(Text, nullable=True)
    adherence_to_protocols = Column(String, nullable=True)
    channel_use = Column(Text, nullable=True)
    decision_style = Column(String, nullable=True)
    core_insight = Column(Text, nullable=True)
    additional_context = Column(JSON, nullable=True)
    # Store all generated data as a single JSON string for flexibility
    full_persona_json = Column(Text)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

class Simulation(Base):
    __tablename__ = "simulations"
    
    id = Column(Integer, primary_key=True, index=True)
    persona_id = Column(Integer, index=True)
    scenario = Column(Text)
    parameters = Column(JSON)
    results = Column(JSON)
    response_rate = Column(Float)
    insights = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class SavedSimulation(Base):
    __tablename__ = "saved_simulations"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True, unique=True)
    simulation_data = Column(JSON)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class SyntheticTestRun(Base):
    __tablename__ = "synthetic_test_runs"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    persona_ids = Column(JSON) # List of IDs
    assets = Column(JSON) # List of {id, name, preview} (preview is base64 or url)
    results = Column(JSON) # The full API response
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class Brand(Base):
    __tablename__ = "brands"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True, unique=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class BrandDocument(Base):
    __tablename__ = "brand_documents"

    id = Column(Integer, primary_key=True, index=True)
    brand_id = Column(Integer, index=True)
    filename = Column(String)
    filepath = Column(String, nullable=True)  # Path to uploaded file
    category = Column(String, nullable=True)  # Document category/classification
    summary = Column(Text, nullable=True)  # Document summary
    document_type = Column(String, default="brand_messaging")  # DocumentType enum value
    vector_store_id = Column(String, nullable=True) # OpenAI Vector Store ID
    extracted_insights = Column(JSON, nullable=True)
    gemini_document_name = Column(String, nullable=True)
    chunk_size = Column(Integer, nullable=True)
    chunk_ids = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class CachedAssetAnalysis(Base):
    """Caches asset analysis results to avoid redundant API calls."""
    __tablename__ = "cached_asset_analysis"

    id = Column(Integer, primary_key=True, index=True)
    image_hash = Column(String, index=True)  # SHA256 of image bytes
    persona_id = Column(Integer, index=True)
    persona_hash = Column(String, index=True)  # Hash of persona attributes used in prompt
    asset_name = Column(String, nullable=True)  # Original filename
    result_json = Column(JSON)  # Annotated image + text summary
    created_at = Column(DateTime(timezone=True), server_default=func.now())


# === Knowledge Graph Models ===

class KnowledgeNode(Base):
    """Represents a knowledge node extracted from documents."""
    __tablename__ = "knowledge_nodes"
    
    id = Column(String, primary_key=True)  # UUID
    brand_id = Column(Integer, ForeignKey("brands.id"), index=True)
    node_type = Column(String, index=True)  # NodeType enum value
    
    # Content
    text = Column(Text, nullable=False)
    summary = Column(String(200), nullable=True)  # Short version for graph labels
    
    # Targeting (who does this apply to?)
    segment = Column(String, nullable=True)  # "Elderly Patients", "Endocrinologists", "All"
    journey_stage = Column(String, nullable=True)  # "Awareness", "Consideration", "Treatment"
    
    # Provenance
    source_document_id = Column(Integer, ForeignKey("brand_documents.id"), nullable=True)
    source_quote = Column(Text, nullable=True)  # Exact quote from document
    confidence = Column(Float, default=0.7)
    
    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    verified_by_user = Column(Boolean, default=False)


class KnowledgeRelation(Base):
    """Represents a relationship between two knowledge nodes."""
    __tablename__ = "knowledge_relations"
    
    id = Column(Integer, primary_key=True, index=True)
    brand_id = Column(Integer, ForeignKey("brands.id"), index=True)
    
    from_node_id = Column(String, ForeignKey("knowledge_nodes.id"), index=True)
    to_node_id = Column(String, ForeignKey("knowledge_nodes.id"), index=True)
    relation_type = Column(String)  # RelationType enum value
    
    # Strength and context
    strength = Column(Float, default=0.7)  # How strong is this relationship?
    context = Column(Text, nullable=True)  # Why does this relationship exist?
    
    # Provenance
    inferred_by = Column(String, default="llm")  # "llm" or "user"
    created_at = Column(DateTime(timezone=True), server_default=func.now())


# === Chat Models ===

class ChatSession(Base):
    """Represents a conversation session with a persona."""
    __tablename__ = "chat_sessions"
    
    id = Column(Integer, primary_key=True, index=True)
    persona_id = Column(Integer, ForeignKey("personas.id"), index=True)
    brand_id = Column(Integer, ForeignKey("brands.id"), nullable=True)
    
    name = Column(String, nullable=True)  # Optional title for the chat
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class ChatMessage(Base):
    """Individual message in a chat session."""
    __tablename__ = "chat_messages"
    
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("chat_sessions.id"), index=True)
    
    role = Column(String)  # "user" or "assistant" (or "system")
    content = Column(Text)
    
    # Optional metadata for citation/reasoning
    citations = Column(JSON, nullable=True)
    thought_process = Column(Text, nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())

