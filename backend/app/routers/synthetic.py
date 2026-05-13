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
                
    # 4. Generate scores and rationales
    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = []
        for persona in personas:
            futures.append(
                executor.submit(
                    synthetic_testing_engine.analyze_single_asset_persona_via_url,
                    persona,
                    assets[0],
                    ""
                )
            )
        for future in concurrent.futures.as_completed(futures):
            try:
                res = future.result()
                if "error" not in res:
                    results.append(res)
            except Exception as e:
                print(f"Failed to analyze asset for persona: {e}")

    # 5. Generate emotion data
    emotion_prompt_echo = ""
    try:
        emotion_data = synthetic_testing_engine.generate_emotion_data(personas, assets, emotion_prompt_echo)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate emotion data: {str(e)}")

    # 6. Aggregate results
    aggregated_results = {}
    for asset in assets:
        a_id = asset["id"]
        asset_responses = [r for r in results if r.get("asset_id") == a_id and "error" not in r]
        if not asset_responses:
            continue

        sums = {
            "motivation_to_prescribe": 0.0,
            "connection_to_story": 0.0,
            "differentiation": 0.0,
            "believability": 0.0,
            "stopping_power": 0.0,
        }
        counts = {k: 0 for k in sums}
        pref_sum, pref_count = 0.0, 0
        individual_rationales = []

        for r in asset_responses:
            s = r.get("scores", {}) or {}
            if isinstance(s, dict):
                for k in sums.keys():
                    v = s.get(k, 0)
                    if isinstance(v, (int, float)) and 1.0 <= float(v) <= 7.0:
                        sums[k] += float(v)
                        counts[k] += 1

            op = r.get("overall_preference_score", None)
            if isinstance(op, (int, float)):
                pref_sum += float(op)
                pref_count += 1

            sr = r.get("score_rationale", {})
            if isinstance(sr, dict) and any(sr.values()):
                individual_rationales.append(sr)

        avg_scores = {k: (round(sums[k] / counts[k], 1) if counts[k] > 0 else 0.0) for k in sums.keys()}

        avg_rationale = synthetic_testing_engine._synthesize_average_rationale(
            asset_name=asset.get("name", a_id),
            avg_scores=avg_scores,
            individual_rationales=individual_rationales,
        )

        # Filter emotion_data for this asset to synthesize average emotion
        asset_emotions = [e for e in emotion_data if e.get("concept_name") == asset.get("name")]
        avg_emotion = synthetic_testing_engine._synthesize_average_emotion(
            asset_name=asset.get("name", a_id),
            individual_emotions=asset_emotions,
        )

        aggregated_results[a_id] = {
            "asset_name": asset.get("name"),
            "average_scores": avg_scores,
            "average_rationale": avg_rationale,
            "average_preference": round(pref_sum / pref_count, 1) if pref_count > 0 else 0.0,
            "respondent_count": len(asset_responses),
            "average_emotion": avg_emotion
        }
        
    # User requested emotion_data to only contain concept_name, emotion_response, gut_check
    filtered_emotion_data = []
    for ed in emotion_data:
        filtered_emotion_data.append({
            "concept_name": ed.get("concept_name", ""),
            "emotion_response": ed.get("emotion_response", ""),
            "gut_check": ed.get("gut_check", "")
        })

    return schemas.EmotionResponse(results=None, aggregated=aggregated_results, emotion_data=None)