from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from .. import schemas, models, synthetic_testing_engine, crud
from ..database import get_db

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


@router.post("/analyze/emotion-summary", response_model=schemas.SyntheticTestingResponseLite)
async def synthetic_testing_analyze_lite(
    request: schemas.SyntheticTestingRequestLite,
    db: Session = Depends(get_db)
):
    """
    Lightweight analysis returning only emotion responses and aggregated rationale.
    Accepts presigned image URLs and auto-maps all personas from the database.
    """
    all_personas = crud.get_personas(db)
    if not all_personas:
        raise HTTPException(status_code=404, detail="No personas found")

    persona_ids = [p.id for p in all_personas]

    assets_data = [
        {
            "id": f"asset_{i}",
            "name": f"Asset {i + 1}",
            "data": url,
            "text": None,
            "url_image_str": None,
            "thumbnail_url": None,
            "thumbnail_url_str": None,
            "image_descriptor": None,
        }
        for i, url in enumerate(request.image_urls)
    ]

    full_result = synthetic_testing_engine.run_synthetic_testingV2(
        "",
        "",
        persona_ids,
        assets_data,
        "",
        "",
        db
    )

    return {
        "aggregated": full_result["aggregated"],
        "emotion_data": full_result.get("emotion_data"),
    }
