import json
import logging
from typing import Optional, Dict, Any, List

from sqlalchemy.orm import Session

from . import models, schemas, persona_engine

logger = logging.getLogger(__name__)


def _is_enriched_field(field_data: Any) -> bool:
    """Check if a field follows the enriched field structure."""
    if not isinstance(field_data, dict):
        return False
    return "value" in field_data and "status" in field_data


def _merge_enriched_field(
    existing: Dict[str, Any],
    update: Dict[str, Any],
    confirm: bool = False
) -> Dict[str, Any]:
    """Merge an enriched field update while preserving evidence.
    
    Args:
        existing: The existing field data
        update: The update to apply
        confirm: If True, mark the field as confirmed
    
    Returns:
        Merged field data with preserved evidence
    """
    result = {**existing}
    
    # Update value if provided
    if "value" in update:
        result["value"] = update["value"]
    
    # Update confidence if provided
    if "confidence" in update:
        result["confidence"] = update["confidence"]
    
    # Preserve or extend evidence - never lose it
    existing_evidence = existing.get("evidence", [])
    new_evidence = update.get("evidence", [])
    if new_evidence:
        # Combine and deduplicate evidence
        combined_evidence = list(existing_evidence)
        for ev in new_evidence:
            if ev not in combined_evidence:
                combined_evidence.append(ev)
        result["evidence"] = combined_evidence
    else:
        result["evidence"] = existing_evidence
    
    # Update status
    if confirm:
        result["status"] = "confirmed"
    elif "status" in update:
        result["status"] = update["status"]
    
    return result


def _deep_merge_persona_json(
    existing: Dict[str, Any],
    updates: Dict[str, Any],
    confirm_fields: Optional[List[str]] = None
) -> Dict[str, Any]:
    """Deep merge persona JSON with field-level status tracking.
    
    Args:
        existing: The existing persona JSON
        updates: Updates to apply
        confirm_fields: List of field paths to mark as confirmed
    
    Returns:
        Merged persona JSON with preserved evidence and updated statuses
    """
    confirm_fields = confirm_fields or []
    result = json.loads(json.dumps(existing))  # Deep copy
    
    def merge_recursive(target: Dict, source: Dict, path: str = ""):
        for key, value in source.items():
            current_path = f"{path}.{key}" if path else key
            should_confirm = current_path in confirm_fields
            
            if key not in target:
                # New field - add it
                if _is_enriched_field(value) and should_confirm:
                    value = {**value, "status": "confirmed"}
                target[key] = value
            elif _is_enriched_field(target[key]) and isinstance(value, dict):
                # Both are enriched fields - merge them
                target[key] = _merge_enriched_field(
                    target[key],
                    value,
                    confirm=should_confirm
                )
            elif isinstance(target[key], dict) and isinstance(value, dict):
                # Both are dicts but not enriched fields - recurse
                merge_recursive(target[key], value, current_path)
            else:
                # Simple replacement
                target[key] = value
                
        # Also mark fields as confirmed even if not in updates
        for field_path in confirm_fields:
            # Determine if this field_path belongs to the current merge level
            if path:
                # At nested level: field_path must start with path + "."
                if not field_path.startswith(path + "."):
                    continue
                # Extract the key at this level (next segment after path)
                path_prefix_len = len(path) + 1  # +1 for the dot
                remaining_path = field_path[path_prefix_len:]
                current_key = remaining_path.split(".")[0]
            else:
                # At top level: field_path must not contain dots (top-level field only)
                if "." in field_path:
                    continue
                current_key = field_path
            
            if current_key in target and _is_enriched_field(target[current_key]):
                target[current_key]["status"] = "confirmed"
    
    merge_recursive(result, updates)
    return result


def apply_field_updates(
    persona_json: Dict[str, Any],
    field_updates: Dict[str, schemas.PersonaFieldUpdate],
    confirm_fields: Optional[List[str]] = None
) -> Dict[str, Any]:
    """Apply field-level updates to persona JSON.
    
    Args:
        persona_json: The existing persona JSON
        field_updates: Dict mapping field paths to updates
        confirm_fields: List of field paths to mark as confirmed
    
    Returns:
        Updated persona JSON
    """
    result = json.loads(json.dumps(persona_json))  # Deep copy
    confirm_fields = confirm_fields or []
    
    for field_path, update in field_updates.items():
        # Navigate to the field
        parts = field_path.split(".")
        target = result
        
        for i, part in enumerate(parts[:-1]):
            if part not in target:
                target[part] = {}
            target = target[part]
        
        final_key = parts[-1]
        existing = target.get(final_key, {
            "value": "",
            "status": "empty",
            "confidence": 0.5,
            "evidence": []
        })
        
        # Build update dict from PersonaFieldUpdate
        update_dict = {}
        if update.value is not None:
            update_dict["value"] = update.value
        if update.status is not None:
            update_dict["status"] = update.status.value
        if update.confidence is not None:
            update_dict["confidence"] = update.confidence
        if update.evidence is not None:
            update_dict["evidence"] = update.evidence
        
        should_confirm = field_path in confirm_fields
        
        if _is_enriched_field(existing):
            target[final_key] = _merge_enriched_field(
                existing,
                update_dict,
                confirm=should_confirm
            )
        else:
            # Create new enriched field
            target[final_key] = {
                "value": update_dict.get("value", existing),
                "status": "confirmed" if should_confirm else update_dict.get("status", "suggested"),
                "confidence": update_dict.get("confidence", 0.7),
                "evidence": update_dict.get("evidence", [])
            }
    
    return result

def get_personas(db: Session, skip: int = 0, limit: int = 100):
    """Retrieve all personas from the database."""
    return db.query(models.Persona).offset(skip).limit(limit).all()

def search_personas(db: Session, filters: schemas.PersonaSearchFilters):
    """Search personas based on structured filters."""
    print(f"🔍 Searching with filters: {filters.dict()}")
    query = db.query(models.Persona)
    
    if filters.age_min is not None:
        query = query.filter(models.Persona.age >= filters.age_min)
    if filters.age_max is not None:
        query = query.filter(models.Persona.age <= filters.age_max)
    if filters.gender:
        query = query.filter(models.Persona.gender.ilike(filters.gender))
    if filters.condition:
        query = query.filter(models.Persona.condition.ilike(f"%{filters.condition}%"))
    if filters.location:
        query = query.filter(models.Persona.location.ilike(f"%{filters.location}%"))
    if filters.persona_type:
        query = query.filter(models.Persona.persona_type.ilike(filters.persona_type))
    if filters.brand_id is not None:
        query = query.filter(models.Persona.brand_id == filters.brand_id)
        
    return query.limit(filters.limit).all()

def create_persona(db: Session, persona_data: schemas.PersonaCreate, persona_json: str):
    """
    Create a new persona entry in the database.
    
    Args:
        db: The database session.
        persona_data: The input data used for generation (age, gender, etc.).
        persona_json: The full JSON string generated by the LLM.
    """
    # The persona_json string might contain the name, let's parse it to be safe
    generated_data = json.loads(persona_json)
    
    db_persona = models.Persona(
        name=generated_data.get("name", "Unnamed Persona"),
        age=persona_data.age,
        gender=persona_data.gender,
        condition=persona_data.condition,
        location=persona_data.location,
        brand_id=persona_data.brand_id,
        full_persona_json=persona_json
    )
    try:
        db.add(db_persona)
        db.commit()
        db.refresh(db_persona)
        return db_persona
    except Exception:
        db.rollback()
        raise

def get_persona(db: Session, persona_id: int):
    return db.query(models.Persona).filter(models.Persona.id == persona_id).first()

def get_personas_by_brand(db: Session, brand_id: int, skip: int = 0, limit: int = 100):
    """Get all personas belonging to a specific brand."""
    return db.query(models.Persona).filter(
        models.Persona.brand_id == brand_id
    ).offset(skip).limit(limit).all()

def get_personas_count_by_brand(db: Session, brand_id: int) -> int:
    """Get the count of personas for a specific brand."""
    return db.query(models.Persona).filter(
        models.Persona.brand_id == brand_id
    ).count()

def update_persona(db: Session, persona_id: int, persona: schemas.PersonaUpdate):
    """Update persona with support for field-level updates and confirmation.
    
    Supports three update modes:
    1. Direct full_persona_json replacement
    2. Field-level updates via field_updates dict
    3. Confirming fields via confirm_fields list
    """
    db_persona = db.query(models.Persona).filter(models.Persona.id == persona_id).first()
    if not db_persona:
        return None
    
    update_data = persona.dict(exclude_unset=True)
    
    # Extract special fields
    field_updates = update_data.pop("field_updates", None)
    confirm_fields = update_data.pop("confirm_fields", None)
    full_payload = update_data.get("full_persona_json")
    
    # Parse existing persona JSON
    try:
        existing_json = json.loads(db_persona.full_persona_json or "{}")
    except json.JSONDecodeError:
        existing_json = {}
    
    # Handle full_persona_json update with merge
    if isinstance(full_payload, dict):
        # Merge with existing, preserving evidence
        merged_json = _deep_merge_persona_json(
            existing_json,
            full_payload,
            confirm_fields=confirm_fields
        )
        update_data["full_persona_json"] = json.dumps(merged_json, ensure_ascii=False)
    elif isinstance(full_payload, str):
        try:
            payload_dict = json.loads(full_payload)
            merged_json = _deep_merge_persona_json(
                existing_json,
                payload_dict,
                confirm_fields=confirm_fields
            )
            update_data["full_persona_json"] = json.dumps(merged_json, ensure_ascii=False)
        except json.JSONDecodeError:
            # If parsing fails, use as-is
            pass
    
    # Apply field-level updates if provided
    if field_updates:
        try:
            current_json = json.loads(update_data.get("full_persona_json", db_persona.full_persona_json or "{}"))
        except json.JSONDecodeError:
            current_json = existing_json
        
        updated_json = apply_field_updates(
            current_json,
            field_updates,
            confirm_fields=confirm_fields
        )
        update_data["full_persona_json"] = json.dumps(updated_json, ensure_ascii=False)
    
    # Apply confirm_fields even without other updates
    if confirm_fields and not full_payload and not field_updates:
        merged_json = _deep_merge_persona_json(
            existing_json,
            {},
            confirm_fields=confirm_fields
        )
        update_data["full_persona_json"] = json.dumps(merged_json, ensure_ascii=False)
    
    # Apply all updates to the model
    for key, value in update_data.items():
        setattr(db_persona, key, value)
    
    db.commit()
    db.refresh(db_persona)
    return db_persona

def delete_persona(db: Session, persona_id: int):
    db_persona = db.query(models.Persona).filter(models.Persona.id == persona_id).first()
    if db_persona:
        db.delete(db_persona)
        db.commit()
        return True
    return False

def create_simulation(db: Session, simulation: schemas.SimulationCreate):
    db_simulation = models.Simulation(**simulation.dict())
    db.add(db_simulation)
    db.commit()
    db.refresh(db_simulation)
    return db_simulation

def get_simulation(db: Session, simulation_id: int):
    return db.query(models.Simulation).filter(models.Simulation.id == simulation_id).first()

def get_simulations(db: Session, skip: int = 0, limit: int = 100):
    return db.query(models.Simulation).offset(skip).limit(limit).all()

def update_simulation_results(db: Session, simulation_id: int, results: dict, response_rate: float, insights: str):
    db_simulation = db.query(models.Simulation).filter(models.Simulation.id == simulation_id).first()
    if db_simulation:
        db_simulation.results = results
        db_simulation.response_rate = response_rate
        db_simulation.insights = insights
        db.commit()
        db.refresh(db_simulation)
    return db_simulation

def create_cohort_simulation(db: Session, persona_ids: list, stimulus_text: str, results: dict, insights: list):
    """Create simulation records for cohort analysis"""
    # Calculate average response rate from results
    response_rates = []
    for response in results.get('individual_responses', []):
        # Calculate a response rate based on purchase intent (normalized to 0-100)
        if 'intent_to_action' in response.get('responses', {}):
            response_rates.append(response['responses']['intent_to_action'] * 10)  # Convert 1-10 to 10-100
    
    avg_response_rate = sum(response_rates) / len(response_rates) if response_rates else 0
    
    # Store simulation for each persona
    for persona_id in persona_ids:
        db_simulation = models.Simulation(
            persona_id=persona_id,
            scenario=stimulus_text,
            parameters={"metrics": results.get('metrics_analyzed', [])},
            results=results,
            response_rate=avg_response_rate,
            insights=json.dumps(insights)
        )
        db.add(db_simulation)
    
    db.commit()
    return avg_response_rate

def get_simulation_stats(db: Session):
    """Get statistics about simulations"""
    from sqlalchemy import func
    from datetime import datetime, timedelta
    
    # Count total simulations
    total_simulations = db.query(models.Simulation).count()
    
    # Count simulations this month
    start_of_month = datetime.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    monthly_simulations = db.query(models.Simulation).filter(
        models.Simulation.created_at >= start_of_month
    ).count()
    
    # Calculate average response rate
    avg_response_rate = db.query(func.avg(models.Simulation.response_rate)).scalar()
    
    # Count total insights (each simulation can have multiple insights)
    total_insights = 0
    simulations = db.query(models.Simulation).all()
    for sim in simulations:
        if sim.insights:
            try:
                insights_list = json.loads(sim.insights)
                total_insights += len(insights_list)
            except:
                pass
    
    return {
        "total_simulations": total_simulations,
        "monthly_simulations": monthly_simulations,
        "avg_response_rate": avg_response_rate or 0,
        "total_insights": total_insights
    }

# CRUD for Saved Simulations
def create_saved_simulation(db: Session, simulation_data: schemas.SavedSimulationCreate):
    db_saved_simulation = models.SavedSimulation(**simulation_data.dict())
    db.add(db_saved_simulation)
    db.commit()
    db.refresh(db_saved_simulation)
    return db_saved_simulation

def get_saved_simulation(db: Session, simulation_id: int):
    return db.query(models.SavedSimulation).filter(models.SavedSimulation.id == simulation_id).first()

def get_saved_simulations(db: Session, skip: int = 0, limit: int = 100):
    return db.query(models.SavedSimulation).order_by(models.SavedSimulation.created_at.desc()).offset(skip).limit(limit).all()

def delete_saved_simulation(db: Session, simulation_id: int):
    db_saved_simulation = db.query(models.SavedSimulation).filter(models.SavedSimulation.id == simulation_id).first()
    if db_saved_simulation:
        db.delete(db_saved_simulation)
        db.commit()
        return True
    return False

# CRUD for Brand Library
def create_brand(db: Session, brand: schemas.BrandCreate):
    db_brand = models.Brand(name=brand.name)
    db.add(db_brand)
    db.commit()
    db.refresh(db_brand)
    return db_brand

def get_brands(db: Session, skip: int = 0, limit: int = 100):
    return db.query(models.Brand).offset(skip).limit(limit).all()

def create_brand_document(db: Session, document: schemas.BrandDocumentCreate):
    data = document.dict()
    # Remove fields not in the model
    data = document.dict()
    # Remove fields not in the model
    data.pop('summary', None)
    
    db_document = models.BrandDocument(**data)
    db.add(db_document)
    db.commit()
    db.refresh(db_document)
    return db_document


def _delete_vector_store(vector_store_id: Optional[str]) -> None:
    """Best-effort cleanup of remote OpenAI Vector Stores."""
    if not vector_store_id:
        return
    
    try:
        from .document_processor import _get_openai_client
        client = _get_openai_client()
        if client:
            client.beta.vector_stores.delete(vector_store_id)
            logger.info("Deleted OpenAI Vector Store %s", vector_store_id)
    except Exception as exc:
        logger.warning("Vector store cleanup failed for %s: %s", vector_store_id, exc)


def upsert_brand_document(db: Session, document: schemas.BrandDocumentCreate):
    """Create or replace a brand document while cleaning up stale vectors.

    If a document with the same brand and filename exists, it will be updated
    with the new payload. When a replacement includes a new vector_store_id,
    the previous store is removed on a best-effort basis.
    """

    logger.info(f"🔍 Upserting document: Brand {document.brand_id}, Filename '{document.filename}'")
    
    existing = db.query(models.BrandDocument).filter(
        models.BrandDocument.brand_id == document.brand_id,
        models.BrandDocument.filename == document.filename,
    ).first()
    
    if existing:
        logger.info(f"✅ Found existing document ID {existing.id} for filename '{document.filename}'")
    else:
        logger.info(f"⚠️ No existing document found for filename '{document.filename}'. checking similar...")
        # Debug: list all docs for this brand to see what's there
        all_docs = db.query(models.BrandDocument).filter(models.BrandDocument.brand_id == document.brand_id).all()
        doc_names = [d.filename for d in all_docs]
        logger.info(f"   Current docs for brand {document.brand_id}: {doc_names}")

    if existing:
        previous_vs_id = existing.vector_store_id
        for key, value in document.dict().items():
            setattr(existing, key, value)

        db.commit()
        db.refresh(existing)

        # If vector store ID changed (and wasn't None), delete the old one to avoid garbage
        if previous_vs_id and previous_vs_id != existing.vector_store_id:
             _delete_vector_store(previous_vs_id)

        return existing

    return create_brand_document(db, document)


def delete_brand_document(db: Session, document_id: int, *, brand_id: Optional[int] = None) -> bool:
    query = db.query(models.BrandDocument).filter(models.BrandDocument.id == document_id)
    if brand_id is not None:
        query = query.filter(models.BrandDocument.brand_id == brand_id)

    db_document = query.first()
    if db_document:
        vs_id = db_document.vector_store_id
        db.delete(db_document)
        db.commit()
        _delete_vector_store(vs_id)
        return True

    return False

def get_brand_documents(db: Session, brand_id: int):
    return db.query(models.BrandDocument).filter(models.BrandDocument.brand_id == brand_id).all()


# CRUD for Cached Asset Analysis
def get_cached_analysis(
    db: Session,
    image_hash: str,
    persona_id: int,
    persona_hash: str
) -> Optional[models.CachedAssetAnalysis]:
    """Retrieve a cached analysis if it exists for the given keys."""
    return db.query(models.CachedAssetAnalysis).filter(
        models.CachedAssetAnalysis.image_hash == image_hash,
        models.CachedAssetAnalysis.persona_id == persona_id,
        models.CachedAssetAnalysis.persona_hash == persona_hash
    ).first()


def create_cached_analysis(
    db: Session,
    image_hash: str,
    persona_id: int,
    persona_hash: str,
    asset_name: Optional[str],
    result_json: Dict[str, Any]
) -> models.CachedAssetAnalysis:
    """Create a new cached analysis entry."""
    db_cached = models.CachedAssetAnalysis(
        image_hash=image_hash,
        persona_id=persona_id,
        persona_hash=persona_hash,
        asset_name=asset_name,
        result_json=result_json
    )
    db.add(db_cached)
    db.commit()
    db.refresh(db_cached)
    return db_cached


def get_asset_history(
    db: Session,
    skip: int = 0,
    limit: int = 50
) -> List[models.CachedAssetAnalysis]:
    """Retrieve asset analysis history for the dashboard, newest first."""
    return db.query(models.CachedAssetAnalysis).order_by(
        models.CachedAssetAnalysis.created_at.desc()
    ).offset(skip).limit(limit).all()


def delete_cached_analysis(db: Session, analysis_id: int) -> bool:
    """Delete a cached analysis record by ID."""
    record = db.query(models.CachedAssetAnalysis).filter(
        models.CachedAssetAnalysis.id == analysis_id
    ).first()
    if record:
        db.delete(record)
        db.commit()
        return True
    return False


# CRUD for Chat Sessions
def create_chat_session(db: Session, session: schemas.ChatSessionCreate):
    db_session = models.ChatSession(**session.dict())
    db.add(db_session)
    db.commit()
    db.refresh(db_session)
    return db_session

def get_chat_session(db: Session, session_id: int):
    return db.query(models.ChatSession).filter(models.ChatSession.id == session_id).first()

def get_chat_sessions_by_persona(db: Session, persona_id: int, skip: int = 0, limit: int = 50):
    return db.query(models.ChatSession).filter(
        models.ChatSession.persona_id == persona_id
    ).order_by(models.ChatSession.updated_at.desc()).offset(skip).limit(limit).all()

def create_chat_message(db: Session, message: schemas.ChatMessageCreate, session_id: int):
    db_message = models.ChatMessage(**message.dict(), session_id=session_id)
    db.add(db_message)
    
    # Update parent session "updated_at"
    session = get_chat_session(db, session_id)
    if session:
        from datetime import datetime
        session.updated_at = datetime.utcnow()
        
    db.commit()
    db.refresh(db_message)
    return db_message

def get_chat_history(db: Session, session_id: int, limit: int = 50):
    return db.query(models.ChatMessage).filter(
        models.ChatMessage.session_id == session_id
    ).order_by(models.ChatMessage.created_at.asc()).limit(limit).all()

def delete_chat_session(db: Session, session_id: int):
    session = get_chat_session(db, session_id)
    if session:
        # Delete messages first (manual cascade)
        db.query(models.ChatMessage).filter(models.ChatMessage.session_id == session_id).delete()
        db.delete(session)
        db.commit()
        return True
    return False
