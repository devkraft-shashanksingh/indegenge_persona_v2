from fastapi import APIRouter, Depends, HTTPException, status, File, UploadFile, Form, Response, Body
from sqlalchemy.orm import Session
from typing import List, Optional, Dict
import json
import logging
from datetime import datetime
from fastapi.responses import StreamingResponse

from .. import models, schemas, crud, persona_engine, similarity_service
from ..database import get_db
from .. import comparison_engine, persona_discovery, avatar_engine
from ..services import brand_service

router = APIRouter(
    prefix="/api/personas",
    tags=["personas"]
)

logger = logging.getLogger(__name__)

# --- Helper Functions ---

def _strip_evidence_from_export(data: dict) -> dict:
    """Remove evidence arrays from export data to reduce payload size."""
    if isinstance(data, dict):
        result = {}
        for key, value in data.items():
            if key == "evidence":
                continue  # Skip evidence arrays
            result[key] = _strip_evidence_from_export(value)
        return result
    elif isinstance(data, list):
        return [_strip_evidence_from_export(item) for item in data]
    return data

# --- Endpoints ---

@router.post("/generate", response_model=schemas.Persona)
async def generate_and_create_persona(persona_data: schemas.PersonaCreate, db: Session = Depends(get_db)):
    """
    Receives user input, calls the persona_engine, saves the result to the database,
    and returns the new persona.
    
    If brand_id is provided, the persona will be automatically grounded in that brand's MBT insights.
    Also generates a DALL-E 3 avatar for the persona.
    """
    # Fetch brand MBT insights if brand_id is provided
    brand_insights = None
    if persona_data.brand_id:
        brand = db.query(models.Brand).filter(models.Brand.id == persona_data.brand_id).first()
        if not brand:
            raise HTTPException(status_code=404, detail="Brand not found")
        
        documents = crud.get_brand_documents(db, persona_data.brand_id)
        aggregated = brand_service.aggregate_brand_insights(documents, target_segment=None, limit_per_category=5)
        brand_insights = brand_service.flatten_insights(aggregated)
    
    # 1. Get Segment and Disease Context if provided
    segment_data = None
    if persona_data.segment:
        from .. import segments
        segment_data = segments.get_segment_by_name(persona_data.segment)

    disease_data = None
    if persona_data.disease:
        from .. import disease_packs
        disease_data = disease_packs.get_disease_pack(persona_data.disease)

    # 2. Call the persona engine to generate the full persona JSON
    # If brand insights exist, include them in generation
    full_persona_json = persona_engine.generate_persona_from_attributes(
        age=persona_data.age,
        gender=persona_data.gender,
        condition=persona_data.condition,
        location=persona_data.location,
        concerns=persona_data.concerns,
        segment=segment_data,
        disease_context=disease_data,
        brand_insights=brand_insights
    )
    
    if not full_persona_json or full_persona_json == "{}":
        raise HTTPException(status_code=500, detail="Failed to generate persona from LLM.")

    # 2. Save the result to the database
    new_persona = crud.create_persona(
        db=db, 
        persona_data=persona_data, 
        persona_json=full_persona_json
    )
    
    # 3. Post-creation updates (Segment tagging and Avatar)
    updates_needed = False
    
    if segment_data:
        new_persona.persona_subtype = segment_data.get("name")
        # Ensure correct type is set if segment dictates it
        if segment_data.get("persona_type"):
            new_persona.persona_type = segment_data.get("persona_type")
        updates_needed = True

    if disease_data:
        new_persona.disease_pack = disease_data.get("condition_name")
        updates_needed = True

    # Generate avatar using fallback (DALL-E 3 generation removed)
    try:
        # Parse the persona JSON to extract additional attributes
        persona_json_parsed = json.loads(full_persona_json)
        persona_type_raw = persona_json_parsed.get("persona_type", "Patient")
        persona_type = "HCP" if str(persona_type_raw).lower() == "hcp" else "Patient"
        
        avatar_url = avatar_engine.get_fallback_avatar(
            persona_type=persona_type,
            gender=persona_data.gender
        )
        
        if avatar_url:
            # Update the persona with the avatar URL
            new_persona.avatar_url = avatar_url
            updates_needed = True
            logger.info(f"✅ Fallback avatar generated for persona {new_persona.id}")
            
    except Exception as avatar_error:
        logger.warning(f"⚠️ Avatar generation failed for persona {new_persona.id}: {avatar_error}")
        # Don't fail the request if avatar generation fails - persona is still created
    
    if updates_needed:
        db.commit()
        db.refresh(new_persona)
    
    return new_persona

@router.post("/manual", response_model=schemas.Persona)
async def create_manual_persona(manual_data: dict, db: Session = Depends(get_db)):
    """
    Create a persona manually with detailed attributes provided by the user.
    
    If brand_id is provided, the persona will be associated with that brand.
    """
    try:
        # Extract brand_id if provided
        brand_id = manual_data.get("brand_id")
        brand_insights = None

        # Validate brand exists if provided
        if brand_id:
            brand = db.query(models.Brand).filter(models.Brand.id == brand_id).first()
            if not brand:
                raise HTTPException(status_code=404, detail="Brand not found")

            documents = crud.get_brand_documents(db, brand_id)
            aggregated = brand_service.aggregate_brand_insights(documents, target_segment=None, limit_per_category=5)
            brand_insights = brand_service.flatten_insights(aggregated)

        location = manual_data.get("location") or manual_data.get("region", "")
        demographics = manual_data.get("demographics", {})
        motivations = [motivation for motivation in manual_data.get("motivations", []) if str(motivation).strip()]
        beliefs = [belief for belief in manual_data.get("beliefs", []) if str(belief).strip()]
        pain_points = [point for point in manual_data.get("pain_points", []) if str(point).strip()]
        communication_preferences = manual_data.get("communication_preferences", {})
        medical_background = manual_data.get("medical_background", "") or f"Managing {manual_data.get('condition', '').lower()} with support from local clinicians."
        lifestyle = manual_data.get("lifestyle_and_values") or manual_data.get("lifestyle") or f"Lives in {location} and balances health goals with daily responsibilities."
        occupation = demographics.get("occupation") or manual_data.get("occupation") or "Professional"

        schema_payload = persona_engine._build_schema_persona(
            name=manual_data.get("name", ""),
            age=manual_data.get("age", 0),
            gender=manual_data.get("gender", ""),
            condition=manual_data.get("condition", ""),
            location=location,
            concerns=manual_data.get("concerns", ""),
            occupation=occupation,
            motivations=motivations,
            beliefs=beliefs,
            pain_points=pain_points,
            lifestyle=lifestyle,
            medical_background=medical_background,
            communication_preferences=communication_preferences,
            persona_type=manual_data.get("persona_type", "patient"),
            brand_insights=brand_insights,
            existing_persona=manual_data,
        )

        # Create a PersonaCreate object for database insertion
        persona_create_data = schemas.PersonaCreate(
            age=manual_data.get("age", 0),
            gender=manual_data.get("gender", ""),
            condition=manual_data.get("condition", ""),
            location=location,  # Map region/location into database location field
            concerns="",  # Manual personas don't have concerns field
            brand_id=brand_id
        )

        # Save to database
        new_persona = crud.create_persona(
            db=db,
            persona_data=persona_create_data,
            persona_json=json.dumps(schema_payload, ensure_ascii=False)
        )
        
        return new_persona
        
    except Exception as e:
        logger.error(f"Error creating manual persona: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create manual persona: {str(e)}")

@router.get("/", response_model=List[schemas.Persona])
async def get_all_personas(
    skip: int = 0, 
    limit: int = 100, 
    brand_id: Optional[int] = None,
    db: Session = Depends(get_db)
):
    """
    Returns a list of personas from the database.
    
    If brand_id is provided, returns only personas belonging to that brand.
    """
    if brand_id is not None:
        personas = crud.get_personas_by_brand(db, brand_id=brand_id, skip=skip, limit=limit)
    else:
        personas = crud.get_personas(db, skip=skip, limit=limit)
    return personas

@router.get("/stream-generation")
async def stream_persona_generation_endpoint(
    brand_id: int,
    segment_name: str,
    segment_description: str,
    db: Session = Depends(get_db)
):
    """
    Stream the persona generation process using Server-Sent Events (SSE).
    Frontend listens to this endpoint to show real-time progress.
    """
    
    async def event_generator():
        try:
            async for event_json in persona_discovery.stream_persona_generation(
                segment_name, segment_description, brand_id, db
            ):
                yield f"data: {event_json}\n\n"
        except Exception as e:
            logger.error(f"Stream error: {e}")
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")

@router.post("/discover-from-docs")
async def discover_segments_endpoint(
    request: dict,
    db: Session = Depends(get_db)
):
    """
    Discover segments from brand documents using LLM.
    """
    brand_id = request.get("brand_id")
    limit = request.get("limit", 5)
    
    if not brand_id:
        raise HTTPException(status_code=400, detail="brand_id is required")
        
    documents = crud.get_brand_documents(db, brand_id)
    if not documents:
        # Return empty list instead of error if no docs found, 
        # or minimal mock segments to unblock UI
        return {"segments": []}
        
    try:
        segments = persona_discovery.discover_segments_from_documents(documents, limit=limit)
        return {"segments": segments}
    except Exception as e:
        logger.error(f"Discovery endpoint failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/generate-from-discovery")
async def generate_persona_from_discovery_endpoint(
    request: schemas.GenerationRequest,
    db: Session = Depends(get_db)
):
    """
    Generates a full persona profile for a discovered segment using Multi-Pass Extraction.
    """
    try:
        # 1. Extract Profile (Multi-Pass)
        persona_profile = persona_discovery.extract_persona_from_segment(
            segment_name=request.segment_name,
            segment_description=request.segment_description,
            brand_id=request.brand_id,
            db_session=db
        )
        
        if not persona_profile:
             raise HTTPException(status_code=500, detail="Failed to extract persona profile")

        # 2. Save as new Persona
        # Map additional_context correctly
        additional_ctx = persona_profile.get("additional_context", {})
        
        db_persona = models.Persona(
            name=persona_profile.get("name", request.segment_name)[0:50], # Limit name length
            age=persona_profile.get("age", 40),
            gender=persona_profile.get("gender", "Unknown"),
            condition=persona_profile.get("condition", "Unknown"),
            location=persona_profile.get("location", "Unknown"),
            brand_id=request.brand_id,
            persona_type="Patient",
            persona_subtype=request.segment_name,
            full_persona_json=json.dumps(persona_profile),
            additional_context=additional_ctx
        )
        
        db.add(db_persona)
        db.commit()
        db.refresh(db_persona)
        
        return db_persona

    except Exception as e:
        logger.error(f"Generation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/save-generated", response_model=schemas.Persona)
async def save_generated_persona_endpoint(
    request: schemas.SaveGeneratedPersonaRequest,
    db: Session = Depends(get_db)
):
    """
    Saves a persona that was generated and reviewed by the user.
    """
    try:
        persona_profile = request.persona_profile
        brand_id = request.brand_id
        segment_name = request.segment_name
        
        # Validate profile minimally
        if not persona_profile or not isinstance(persona_profile, dict):
            raise HTTPException(status_code=400, detail="Invalid persona profile data")

        # Map additional_context correctly
        additional_ctx = persona_profile.get("additional_context", {})
        
        db_persona = models.Persona(
            name=persona_profile.get("name", segment_name)[0:50], # Limit name length
            age=persona_profile.get("age", 40),
            gender=persona_profile.get("gender", "Unknown"),
            condition=persona_profile.get("condition", "Unknown"),
            location=persona_profile.get("location", "Unknown"),
            brand_id=brand_id,
            persona_type=persona_profile.get("persona_type", "Patient"),
            persona_subtype=segment_name,
            full_persona_json=json.dumps(persona_profile),
            additional_context=additional_ctx
        )
        
        db.add(db_persona)
        db.commit()
        db.refresh(db_persona)
        logger.info(f"✅ Saved generated persona '{db_persona.name}' (ID: {db_persona.id})")
        
        return db_persona

    except Exception as e:
        logger.error(f"Save generated persona failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{persona_id}", response_model=schemas.Persona)
def get_persona(persona_id: int, db: Session = Depends(get_db)):
    """Get a single persona by ID"""
    persona = db.query(models.Persona).filter(models.Persona.id == persona_id).first()
    if not persona:
        raise HTTPException(status_code=404, detail="Persona not found")
    return persona

@router.put("/{persona_id}", response_model=schemas.Persona)
async def update_persona_endpoint(
    persona_id: int,
    persona_update: schemas.PersonaUpdate,
    db: Session = Depends(get_db)
):
    """Update persona attributes or enriched JSON."""
    updated = crud.update_persona(db, persona_id, persona_update)
    if not updated:
        raise HTTPException(status_code=404, detail="Persona not found")
    return updated

@router.post("/{persona_id}/enrich-from-brand", response_model=schemas.Persona)
async def enrich_persona_from_brand(
    persona_id: int,
    request: schemas.PersonaBrandEnrichmentRequest,
    db: Session = Depends(get_db)
):
    persona = crud.get_persona(db, persona_id)
    if not persona:
        raise HTTPException(status_code=404, detail="Persona not found")

    brand = db.query(models.Brand).filter(models.Brand.id == request.brand_id).first()
    if not brand:
        raise HTTPException(status_code=404, detail="Brand not found")

    documents = crud.get_brand_documents(db, request.brand_id)
    aggregated = brand_service.aggregate_brand_insights(documents, request.target_segment, limit_per_category=8)
    flattened = brand_service.flatten_insights(aggregated)

    try:
        persona_json = json.loads(persona.full_persona_json or "{}")
    except json.JSONDecodeError:
        persona_json = {}

    enriched = persona_engine.enrich_persona_from_brand_context(
        persona_json,
        flattened,
        target_fields=request.target_fields
    )

    updated = crud.update_persona(
        db,
        persona_id,
        schemas.PersonaUpdate(full_persona_json=enriched)
    )

    if not updated:
        raise HTTPException(status_code=500, detail="Failed to persist enriched persona")

    return updated


@router.post("/{persona_id}/enrich", response_model=schemas.Persona)
async def enrich_persona(
    persona_id: int,
    db: Session = Depends(get_db)
):
    """
    Enrich an existing persona to match the full schema depth using LLM.
    
    This endpoint takes an existing persona and fills in any missing schema fields 
    such as core.mbt (motivations, beliefs, tensions), decision_drivers, messaging,
    channel_behavior, etc. It uses LLM when available and falls back to sensible
    defaults when OpenAI is unavailable.
    
    No brand_id is required - enrichment is based on existing persona data.
    """
    persona = crud.get_persona(db, persona_id)
    if not persona:
        raise HTTPException(status_code=404, detail="Persona not found")

    try:
        persona_json = json.loads(persona.full_persona_json or "{}")
    except json.JSONDecodeError:
        persona_json = {}

    # Enrich the persona using the new function
    enriched = persona_engine.enrich_existing_persona(persona_json)

    # Update the database with the enriched persona
    updated = crud.update_persona(
        db,
        persona_id,
        schemas.PersonaUpdate(full_persona_json=enriched)
    )

    if not updated:
        raise HTTPException(status_code=500, detail="Failed to persist enriched persona")

    logger.info(f"✅ Enriched persona {persona_id} with full schema depth")
    return updated


@router.post("/recruit", response_model=List[schemas.Persona])
async def recruit_personas(request: schemas.PersonaSearchRequest, db: Session = Depends(get_db)):
    """
    Recruit personas based on a natural language prompt.
    """
    # 1. Parse the prompt into structured filters
    filters_dict = persona_engine.parse_recruitment_prompt(request.prompt)
    
    # 2. Convert to Pydantic model
    try:
        filters = schemas.PersonaSearchFilters(**filters_dict)
    except Exception as e:
        # If parsing fails or returns empty, default to basic search or empty
        logger.warning(f"Failed to parse filters from prompt: {e}")
        filters = schemas.PersonaSearchFilters()

    # 3. Search the database
    personas = crud.search_personas(db, filters)

    return personas


@router.post("/check-similarity")
async def check_persona_similarity_endpoint(
    request: dict,
    db: Session = Depends(get_db)
):
    """
    Check if a new persona is similar to existing personas.
    
    Returns similarity analysis to help users avoid creating duplicates.
    If similar personas exist, suggests using existing ones instead.
    """
    
    new_persona_attrs = request.get("persona_attrs", {})
    brand_id = request.get("brand_id")
    threshold = request.get("threshold", 0.7)
    
    if not new_persona_attrs:
        raise HTTPException(status_code=400, detail="persona_attrs is required")
    
    # Get existing personas (optionally filtered by brand)
    if brand_id:
        existing_personas = crud.get_personas_by_brand(db, brand_id=brand_id, limit=50)
    else:
        existing_personas = crud.get_personas(db, limit=50)
    
    # Convert to dicts for the similarity service
    existing_dicts = []
    for p in existing_personas:
        persona_dict = {
            "id": p.id,
            "name": p.name,
            "age": p.age,
            "gender": p.gender,
            "condition": p.condition,
            "persona_type": p.persona_type,
            "persona_subtype": p.persona_subtype,
            "decision_style": p.decision_style,
            "full_persona_json": p.full_persona_json
        }
        existing_dicts.append(persona_dict)
    
    # Check similarity
    result = similarity_service.check_persona_similarity_sync(
        new_persona_attrs=new_persona_attrs,
        existing_personas=existing_dicts,
        brand_id=brand_id,
        threshold=threshold
    )
    
    return result


@router.post("/from-transcript")
async def extract_persona_from_transcript(
    file: Optional[UploadFile] = File(None),
    transcript_text: Optional[str] = Form(None),
    use_llm: Optional[bool] = Form(True),
    verify_quotes: Optional[bool] = Form(True),
):
    """Accept a transcript file or raw text and return persona suggestions.
    
    Args:
        file: Optional transcript file (PDF, TXT, MD, DOCX)
        transcript_text: Optional raw transcript text
        use_llm: If True, use LLM for comprehensive extraction (default True)
        verify_quotes: If True, validate extracted quotes against source (default True)
    """

    text_content = (transcript_text or "").strip()

    if file:
        try:
            raw_bytes = await file.read()
            text_content = raw_bytes.decode("utf-8", errors="ignore")
        except Exception as exc:
            logger.error("Failed to read transcript file: %s", exc)
            raise HTTPException(status_code=400, detail="Could not read transcript file")

    if not text_content:
        raise HTTPException(status_code=400, detail="Transcript text is required")

    # Use comprehensive LLM extraction if enabled, otherwise fall back to heuristics
    if use_llm:
        suggestions = persona_engine.extract_comprehensive_persona_from_transcript(
            text_content,
            verify_quotes=verify_quotes
        )
    else:
        suggestions = persona_engine.extract_persona_from_transcript(text_content)

    if not suggestions:
        raise HTTPException(status_code=500, detail="Failed to extract suggestions from transcript")

    suggestions["source"] = suggestions.get("source", {})
    suggestions["source"].update({
        "filename": getattr(file, "filename", None),
        "received_via": "file" if file else "text",
    })
    
    # Count extracted items for summary
    legacy = suggestions.get("legacy", {})
    extraction_summary = {
        "motivations_count": len(legacy.get("motivations", [])),
        "beliefs_count": len(legacy.get("beliefs", [])),
        "tensions_count": len(legacy.get("tensions", [])),
        "extraction_method": suggestions.get("extraction_method", "heuristics"),
    }
    suggestions["extraction_summary"] = extraction_summary

    return suggestions


@router.get("/{persona_id}/export")
async def export_persona_for_simulation(
    persona_id: int,
    include_evidence: bool = True,
    db: Session = Depends(get_db)
):
    """Export a persona in a format ready for simulation.
    
    Returns the enriched persona JSON structured for the cohort analysis engine.
    This endpoint provides the same data as the standard GET but in a format
    optimized for simulation payloads.
    
    Args:
        persona_id: The ID of the persona to export
        include_evidence: Whether to include evidence metadata (default True)
    """
    persona = crud.get_persona(db, persona_id)
    if not persona:
        raise HTTPException(status_code=404, detail="Persona not found")
    
    try:
        persona_json = json.loads(persona.full_persona_json or "{}")
    except json.JSONDecodeError:
        persona_json = {}
    
    # Build simulation-ready export
    export_data = {
        "id": persona.id,
        "name": persona.name,
        "persona_type": persona.persona_type or "Patient",
        "demographics": {
            "age": persona.age,
            "gender": persona.gender,
            "condition": persona.condition,
            "location": persona.location,
        },
        # Include full persona data for rich simulation context
        "full_persona": persona_json,
        # Extract key fields for quick access
        "motivations": persona_json.get("motivations", []),
        "beliefs": persona_json.get("beliefs", []),
        "pain_points": persona_json.get("pain_points", []),
        "medical_background": persona_json.get("medical_background", ""),
        "lifestyle_and_values": persona_json.get("lifestyle_and_values", ""),
        "communication_preferences": persona_json.get("communication_preferences", {}),
    }
    
    # Include HCP-specific fields if applicable
    if persona.persona_type and persona.persona_type.lower() == "hcp":
        export_data["hcp_context"] = {
            "specialty": persona.specialty,
            "practice_setup": persona.practice_setup,
            "decision_influencers": persona.decision_influencers,
            "adherence_to_protocols": persona.adherence_to_protocols,
            "decision_style": persona.decision_style,
        }
    
    # Include enriched schema fields if available
    core = persona_json.get("core", {})
    if core:
        export_data["mbt"] = core.get("mbt", {})
        export_data["decision_drivers"] = core.get("decision_drivers", {})
        export_data["messaging"] = core.get("messaging", {})
        export_data["barriers_objections"] = core.get("barriers_objections", {})
        export_data["channel_behavior"] = core.get("channel_behavior", {})
    
    # Strip evidence if not requested (for smaller payloads)
    if not include_evidence:
        export_data = _strip_evidence_from_export(export_data)
    
    export_data["export_metadata"] = {
        "exported_at": datetime.now().isoformat(),
        "schema_version": persona_json.get("schema_version", "1.0.0"),
        "includes_evidence": include_evidence,
    }
    
    return export_data


@router.head("/")
async def head_personas(db: Session = Depends(get_db)):
    """Lightweight HEAD endpoint to allow health probes without transferring payload."""
    count = db.query(models.Persona).count()
    return Response(status_code=200, headers={"X-Total-Personas": str(count)})


@router.delete("/{persona_id}", status_code=204)
async def delete_persona(persona_id: int, db: Session = Depends(get_db)):
    """Delete a persona by ID."""
    success = crud.delete_persona(db, persona_id=persona_id)
    if not success:
        raise HTTPException(status_code=404, detail="Persona not found")
    return Response(status_code=204)


# --- Persona Comparison Endpoints ---

class CompareAnalyzeRequest(schemas.BaseModel):
    persona_ids: List[int]

class CompareAskRequest(schemas.BaseModel):
    persona_ids: List[int]
    question: str

@router.post("/compare/analyze")
async def analyze_persona_comparison_endpoint(
    request: CompareAnalyzeRequest,
    db: Session = Depends(get_db)
):
    """
    Analyze personas and generate AI-powered comparison insights.
    """
    if len(request.persona_ids) < 2:
        raise HTTPException(status_code=400, detail="Need at least 2 personas to compare")
    
    # Fetch personas from database
    personas = []
    for persona_id in request.persona_ids:
        persona = crud.get_persona(db, persona_id)
        if not persona:
            raise HTTPException(status_code=404, detail=f"Persona with ID {persona_id} not found")
        # Convert to dict for engine
        persona_dict = {
            "id": persona.id,
            "name": persona.name,
            "age": persona.age,
            "gender": persona.gender,
            "condition": persona.condition,
            "location": persona.location,
            "persona_type": persona.persona_type,
            "persona_subtype": persona.persona_subtype,
            "specialty": persona.specialty,
            "practice_setup": persona.practice_setup,
            "decision_influencers": persona.decision_influencers,
            "adherence_to_protocols": persona.adherence_to_protocols,
            "channel_use": persona.channel_use,
            "decision_style": persona.decision_style,
            "core_insight": persona.core_insight,
            "tagline": persona.tagline,
            "full_persona_json": persona.full_persona_json,
        }
        personas.append(persona_dict)
    
    try:
        result = comparison_engine.analyze_persona_comparison(personas)
        return result
    except Exception as e:
        logger.error(f"Error in persona comparison analysis: {e}")
        raise HTTPException(status_code=500, detail=f"Comparison analysis failed: {str(e)}")


@router.post("/compare/ask")
async def answer_comparison_question_endpoint(
    request: CompareAskRequest,
    db: Session = Depends(get_db)
):
    """
    Answer a natural language question about compared personas.
    """
    if len(request.persona_ids) < 2:
        raise HTTPException(status_code=400, detail="Need at least 2 personas to compare")
    
    if not request.question or not request.question.strip():
        raise HTTPException(status_code=400, detail="Question is required")
    
    # Fetch personas from database
    personas = []
    for persona_id in request.persona_ids:
        persona = crud.get_persona(db, persona_id)
        if not persona:
            raise HTTPException(status_code=404, detail=f"Persona with ID {persona_id} not found")
        persona_dict = {
            "id": persona.id,
            "name": persona.name,
            "age": persona.age,
            "gender": persona.gender,
            "condition": persona.condition,
            "location": persona.location,
            "persona_type": persona.persona_type,
            "persona_subtype": persona.persona_subtype,
            "specialty": persona.specialty,
            "practice_setup": persona.practice_setup,
            "decision_influencers": persona.decision_influencers,
            "adherence_to_protocols": persona.adherence_to_protocols,
            "channel_use": persona.channel_use,
            "decision_style": persona.decision_style,
            "core_insight": persona.core_insight,
            "tagline": persona.tagline,
            "full_persona_json": persona.full_persona_json,
        }
        personas.append(persona_dict)
    
    try:
        result = comparison_engine.answer_comparison_question(personas, request.question)
        return result
    except Exception as e:
        logger.error(f"Error in comparison Q&A: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to answer question: {str(e)}")
