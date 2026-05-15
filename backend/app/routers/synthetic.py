from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from .. import schemas, models, synthetic_testing_engine, crud
import json
import urllib.parse
from ..database import get_db
import concurrent.futures

router = APIRouter(
    prefix="/api/synthetic",
    tags=["synthetic"]
)

@router.post("/analyze", response_model=schemas.SyntheticTestingResponse)
async def synthetic_testing_analyze(
    request: schemas.SyntheticTestingRequest,
    db: Session = Depends(get_db)
):
    """
    Run synthetic testing of marketing assets against selected personas.
    """
    assets_data = [
        {
            "id": asset.id,
            "name": asset.name,
            "data": asset.image_data,
            "text": asset.text_content
        }
        for asset in request.assets
    ]
    
    return synthetic_testing_engine.run_synthetic_testing(
        request.persona_ids,
        assets_data,
        db
    )

@router.get("/runs", response_model=List[schemas.SyntheticTestRun])
def list_synthetic_runs(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """
    List all synthetic test runs.
    """
    runs = db.query(models.SyntheticTestRun).order_by(models.SyntheticTestRun.created_at.desc()).offset(skip).limit(limit).all()
    return runs

@router.post("/runs", response_model=schemas.SyntheticTestRun)
def create_synthetic_run(
    run: schemas.SyntheticTestRunCreate,
    db: Session = Depends(get_db)
):
    """
    Save a synthetic test run.
    """
    db_run = models.SyntheticTestRun(
        name=run.name,
        persona_ids=run.persona_ids,
        assets=run.assets,
        results=run.results.dict()
    )
    db.add(db_run)
    db.commit()
    db.refresh(db_run)
    return db_run

@router.get("/runs/{run_id}", response_model=schemas.SyntheticTestRun)
def get_synthetic_run(
    run_id: int,
    db: Session = Depends(get_db)
):
    """
    Get a specific synthetic test run by ID.
    """
    run = db.query(models.SyntheticTestRun).filter(models.SyntheticTestRun.id == run_id).first()
    if run is None:
        raise HTTPException(status_code=404, detail="Synthetic test run not found")
    return run





@router.post("/analyze/v1", response_model=schemas.SyntheticTestingResponseV2)
async def synthetic_testing_analyze(
    request: schemas.SyntheticTestingRequestV2,
    db: Session = Depends(get_db)
):
    """
    Run synthetic testing of marketing assets against selected personas.
    """
    assets_data = [
        {
            "id": asset.id,
            "name": asset.name,
            "data": asset.url,
            "text": asset.text_content,
            "url_image_str":asset.image_url_str,
            "thumbnail_url":asset.thumbnail_url,
            "thumbnail_url_str":asset.thumbnail_url_str,
            "image_descriptor":asset.image_descriptor
        }
        for asset in request.assets
    ]
    
    return synthetic_testing_engine.run_synthetic_testingV2(
        request.campaign_id,
        request.task_id,
        request.persona_ids,
        assets_data,
        request.synthetic_prompt,
        request.emotion_prompt,
        db
    )


@router.post("/emotion-aggregate/v1", response_model=schemas.EmotionResponse)
async def get_emotion_response(request: schemas.EmotionRequestionModel, db: Session = Depends(get_db)):
    # 1. Fetch all personas
    all_personas_db = crud.get_personas(db, limit=1000)
    personas = []
    for p in all_personas_db:
        personas.append({
            "id": p.id,
            "name": p.name,
            "age": p.age,
            "persona_subtype": p.persona_subtype,
            "gender": p.gender,
            "location": p.location,
            "condition": p.condition,
            "full_persona": json.loads(p.full_persona_json) if getattr(p, "full_persona_json", None) else {},
            "additional_context": p.additional_context or {},
        })
        
    if not personas:
        raise HTTPException(status_code=404, detail="No personas found in the database")

    # 2. Create the asset
    assets = []
    url = request.image_url
    parsed_url = urllib.parse.urlparse(url)
    path_name = parsed_url.path.lstrip('/')
    if not path_name:
        path_name = "Asset 1"
        
    assets.append({
        "id": "asset_1",
        "name": path_name,
        "data": url,
        "text": ""
    })
    
    # 3. Generate image descriptors
    try:
        assets = synthetic_testing_engine.generate_asset_image_descriptors_via_url(assets)
        print(f"image descriptors generated: {assets}")
    except Exception as e:
        for i, asset in enumerate(assets):
            if isinstance(asset, dict) and "image_descriptor" not in asset:
                asset["image_descriptor"] = f"Asset {i+1}"
                
    # 4. Generate scores, rationales, and emotions in ONE shot
    try:
        one_shot_result = synthetic_testing_engine.analyze_single_asset_all_personas_one_shot(
            personas,
            assets[0]
        )
        if "error" in one_shot_result:
             raise HTTPException(status_code=500, detail=one_shot_result["error"])
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to analyze asset: {str(e)}")

    aggregated_results = one_shot_result.get("aggregated", {})
    
    asset_1_agg = aggregated_results.get("asset_1")
    emotional_data = None
    
    if asset_1_agg:
        # LLM sometimes nests top-level fields inside average_rationale; hoist them out
        avg_rat = asset_1_agg.get("average_rationale")
        if isinstance(avg_rat, dict):
            for key in ("average_preference", "respondent_count", "average_emotion"):
                if key not in asset_1_agg and key in avg_rat:
                    asset_1_agg[key] = avg_rat.pop(key)

        # Ensure average_preference is rounded to 1 decimal place
        if "average_preference" in asset_1_agg:
            try:
                asset_1_agg["average_preference"] = round(float(asset_1_agg["average_preference"]), 1)
            except (ValueError, TypeError):
                pass

        # Extract average_emotion to emotional_data
        if "average_emotion" in asset_1_agg:
            avg_emotion = asset_1_agg.pop("average_emotion")
            emotional_data = {
                "emotion_response": avg_emotion.get("emotion_response", ""),
                "gut_check": avg_emotion.get("gut_check", "")
            }
            
    emotion_response_data = schemas.EmotionResponse(
        id=request.id,
        image_url=request.image_url,
        emotional_data=emotional_data,
        aggregated=asset_1_agg
    )

    try:
        db_emotion_agg = models.EmotionAggregate(
            image_uuid=request.id,
            image_url=request.image_url,
            input_data=request.dict(),
            output_data=emotion_response_data.dict()
        )
        db.add(db_emotion_agg)
        db.commit()
    except Exception as e:
        print(f"Failed to save EmotionAggregate: {str(e)}")
        db.rollback()

    return emotion_response_data