from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from .. import schemas, models, synthetic_testing_engine, crud
import json
import urllib.parse
from ..database import get_db
from ..synthetic_testing_engine import DEFAULT_EMOTION_PROMPT

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


@router.post("/emotion/v1", response_model=schemas.EmotionResponse)
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

    # 2. Create the assets
    assets = []
    for i, url in enumerate(request.image_urls):
        parsed_url = urllib.parse.urlparse(url)
        path_name = parsed_url.path.lstrip('/')
        if not path_name:
            path_name = f"Asset {i+1}"
            
        assets.append({
            "id": f"asset_{i+1}",
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
                
    # 4. Generate emotion data
    emotion_prompt_echo = ""
    try:
        emotion_data = synthetic_testing_engine.generate_emotion_data(personas, assets, emotion_prompt_echo)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate emotion data: {str(e)}")
        
    return schemas.EmotionResponse(emotion_data=emotion_data)