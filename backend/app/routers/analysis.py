from fastapi import APIRouter, Depends, HTTPException, File, UploadFile, Form
from sqlalchemy.orm import Session
from typing import List, Optional
import hashlib
import logging

from .. import models, schemas, crud, asset_analyzer, knowledge_alignment
from ..database import get_db

router = APIRouter(
    prefix="/api/assets",
    tags=["analysis"]
)

logger = logging.getLogger(__name__)

@router.post("/analyze")
async def analyze_asset_with_personas(
    file: UploadFile = File(...),
    persona_ids: str = Form(...),
    brand_id: Optional[int] = Form(None),
    db: Session = Depends(get_db)
):
    """
    Analyze a marketing asset from the perspective of selected personas.
    
    Uses Nano Banana Pro (Gemini 3.0 Pro Image) to generate annotated images
    with professional red-lining feedback for each persona.
    
    Now includes Knowledge Graph integration for research-backed, attributable feedback.
    
    Results are cached based on image hash + persona hash. If a persona's
    attributes change, the cache is automatically invalidated.
    """
    
    # Parse persona IDs
    try:
        ids = [int(id.strip()) for id in persona_ids.split(",") if id.strip()]
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid persona_ids format. Expected comma-separated integers.")
    
    if not ids:
        raise HTTPException(status_code=400, detail="At least one persona_id is required.")
    
    # Fetch personas from database
    personas = []
    for persona_id in ids:
        persona = db.query(models.Persona).filter(models.Persona.id == persona_id).first()
        if persona:
            personas.append({
                "id": persona.id,
                "name": persona.name,
                "persona_type": persona.persona_type,
                "persona_subtype": persona.persona_subtype,
                "decision_style": persona.decision_style,
                "full_persona_json": persona.full_persona_json,
                "brand_id": persona.brand_id  # Include brand_id from persona
            })
        else:
            logger.warning(f"Persona with id {persona_id} not found, skipping.")
    
    if not personas:
        raise HTTPException(status_code=404, detail="No valid personas found for the provided IDs.")
    
    # Determine brand_id (from parameter or from first persona)
    effective_brand_id = brand_id
    if not effective_brand_id and personas:
        effective_brand_id = personas[0].get("brand_id")
    
    # Fetch knowledge graph context if brand_id is available
    knowledge_section = None
    knowledge_context = None
    if effective_brand_id:
        knowledge_context = knowledge_alignment.get_brand_knowledge_context(
            brand_id=effective_brand_id,
            persona_type=personas[0].get("persona_type", "patient"),
            db=db
        )
        if knowledge_context.get("has_knowledge"):
            knowledge_section = knowledge_alignment.build_knowledge_enriched_prompt_section(
                knowledge_context=knowledge_context,
                persona_type=personas[0].get("persona_type", "patient")
            )
            logger.info(f"📚 Knowledge context loaded for brand {effective_brand_id}: {len(knowledge_context.get('key_messages', []))} messages, {len(knowledge_context.get('patient_tensions', []))} tensions")
    
    # Read the uploaded file
    try:
        image_bytes = await file.read()
        mime_type = file.content_type or "image/png"
    except Exception as e:
        logger.error(f"Failed to read uploaded file: {e}")
        raise HTTPException(status_code=400, detail="Failed to read uploaded file.")
    
    # Compute image hash for caching
    image_hash = hashlib.sha256(image_bytes).hexdigest()
    asset_name = file.filename
    
    logger.info(f"🎨 Analyzing asset '{asset_name}' (hash: {image_hash[:12]}...) for {len(personas)} personas, with_knowledge={bool(knowledge_section)}")
    
    results = []
    cache_hits = 0
    cache_misses = 0
    
    for persona in personas:
        # Compute persona hash for cache key
        persona_hash = asset_analyzer.compute_persona_hash(persona)
        
        # Check cache first
        cached = crud.get_cached_analysis(
            db=db,
            image_hash=image_hash,
            persona_id=persona["id"],
            persona_hash=persona_hash
        )
        
        if cached:
            logger.info(f"✅ Cache HIT for persona {persona['id']} ({persona['name']})")
            cache_hits += 1
            result = cached.result_json
            result["cached"] = True
            results.append(result)
        else:
            logger.info(f"❌ Cache MISS for persona {persona['id']} ({persona['name']}) - running analysis")
            cache_misses += 1
            
            # Run analysis with knowledge context
            result = await asset_analyzer.analyze_image_with_nano_banana(
                image_bytes=image_bytes,
                persona=persona,
                mime_type=mime_type,
                knowledge_section=knowledge_section
            )
            result["cached"] = False
            
            # Analyze response for citations if we have knowledge context
            if knowledge_context and knowledge_context.get("has_knowledge"):
                citation_analysis = knowledge_alignment.analyze_response_for_citations(
                    text_summary=result.get("text_summary", ""),
                    knowledge_context=knowledge_context
                )
                result["citations"] = citation_analysis.get("citations", [])
                result["research_alignment_score"] = citation_analysis.get("research_alignment_score")
                result["alignment_summary"] = knowledge_alignment.generate_alignment_summary(
                    citations=citation_analysis.get("citations", []),
                    knowledge_context=knowledge_context
                )
            
            # Save to cache
            crud.create_cached_analysis(
                db=db,
                image_hash=image_hash,
                persona_id=persona["id"],
                persona_hash=persona_hash,
                asset_name=asset_name,
                result_json=result
            )
            
            results.append(result)
    
    # Log response details before returning
    for i, result in enumerate(results):
        img = result.get('annotated_image')
        citations = result.get('citations', [])
        logger.info(f"📸 Result {i} ({result.get('persona_name')}): has_image={bool(img)}, citations={len(citations)}, cached={result.get('cached')}")
    
    return {
        "success": True,
        "asset_filename": file.filename,
        "image_hash": image_hash,
        "brand_id": effective_brand_id,
        "knowledge_enabled": bool(knowledge_section),
        "personas_analyzed": len(results),
        "cache_hits": cache_hits,
        "cache_misses": cache_misses,
        "results": results
    }


@router.get("/history")
async def get_asset_analysis_history(
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db)
):
    """
    Retrieve the history of asset analyses for the dashboard.
    Returns a list of past analyses with metadata, grouped by asset.
    """
    cached_results = crud.get_asset_history(db=db, skip=skip, limit=limit)
    
    # Group by image_hash and asset_name for cleaner display
    history = []
    seen_assets = {}
    
    for cached in cached_results:
        asset_key = cached.image_hash
        if asset_key not in seen_assets:
            seen_assets[asset_key] = {
                "image_hash": cached.image_hash,
                "asset_name": cached.asset_name,
                "first_analyzed": cached.created_at.isoformat() if cached.created_at else None,
                "personas": []
            }
            history.append(seen_assets[asset_key])
        
        seen_assets[asset_key]["personas"].append({
            "persona_id": cached.persona_id,
            "persona_hash": cached.persona_hash[:12] + "..." if cached.persona_hash else None,
            "analyzed_at": cached.created_at.isoformat() if cached.created_at else None
        })
    
    return {
        "total_entries": len(cached_results),
        "unique_assets": len(history),
        "history": history
    }


@router.get("/history/full")
async def get_full_asset_history(
    skip: int = 0,
    limit: int = 20,
    db: Session = Depends(get_db)
):
    """
    Get full asset analysis history including annotated images and results.
    Groups by image_hash and includes all persona analysis results.
    """
    cached_results = crud.get_asset_history(db=db, skip=skip, limit=limit)
    
    # Group by image_hash with full results
    assets = {}
    for cached in cached_results:
        asset_key = cached.image_hash
        if asset_key not in assets:
            assets[asset_key] = {
                "image_hash": cached.image_hash,
                "asset_name": cached.asset_name,
                "created_at": cached.created_at.isoformat() if cached.created_at else None,
                "results": []
            }
        
        # Include full result_json with annotated image
        result = cached.result_json.copy() if cached.result_json else {}
        result["persona_id"] = cached.persona_id
        result["id"] = cached.id  # Include analysis record ID
        result["analyzed_at"] = cached.created_at.isoformat() if cached.created_at else None
        assets[asset_key]["results"].append(result)
    
    return {
        "total_assets": len(assets),
        "assets": list(assets.values())
    }


@router.delete("/cache/clear")
async def clear_asset_analysis_cache(
    db: Session = Depends(get_db)
):
    """
    Clear all cached asset analysis results.
    Useful when API keys change or for testing fresh analyses.
    """
    try:
        # Delete all cached analysis records
        deleted_count = db.query(models.CachedAssetAnalysis).delete()
        db.commit()
        logger.info(f"🗑️ Cleared {deleted_count} cached asset analysis records")
        return {
            "success": True,
            "message": f"Cleared {deleted_count} cached analysis records",
            "deleted_count": deleted_count
        }
    except Exception as e:
        db.rollback()
        logger.error(f"Error clearing cache: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to clear cache: {str(e)}")


@router.delete("/history/{analysis_id}")
async def delete_asset_analysis_history(
    analysis_id: int,
    db: Session = Depends(get_db)
):
    """
    Delete a specific asset analysis result by ID
    """
    try:
        analysis = db.query(models.CachedAssetAnalysis).filter(models.CachedAssetAnalysis.id == analysis_id).first()
        if not analysis:
            raise HTTPException(status_code=404, detail="Analysis result not found")
        
        db.delete(analysis)
        db.commit()
        return {"success": True, "message": "Analysis result deleted"}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error deleting analysis: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to delete analysis: {str(e)}")
