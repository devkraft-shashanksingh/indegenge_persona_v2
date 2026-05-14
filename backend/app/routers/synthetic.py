from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session
from typing import List, Optional
from .. import schemas, models, synthetic_testing_engine, crud
import json
import urllib.parse
import uuid
import logging
from datetime import datetime
from ..database import get_db
import boto3
from botocore.exceptions import ClientError, BotoCoreError
from ..core.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/synthetic",
    tags=["synthetic"]
)

def _get_s3_client():
    """Create and return a boto3 S3 client using app settings."""
    return boto3.client(
        "s3",
        aws_access_key_id=settings.AWS_SECRET_KEY,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        region_name=settings.REGION,
    )


def _upload_file_to_s3(
    file_bytes: bytes,
    s3_key: str,
    content_type: str,
    bucket: str,
) -> str:
    """Upload raw bytes to S3 and return the S3 key."""
    s3 = _get_s3_client()
    s3.put_object(
        Bucket=bucket,
        Key=s3_key,
        Body=file_bytes,
        ContentType=content_type,
    )
    return s3_key


def _build_s3_url(s3_key: str, bucket: str) -> str:
    region = settings.REGION or "us-east-1"
    # us-east-1 uses a slightly different hostname
    if region == "us-east-1":
        return f"https://{bucket}.s3.amazonaws.com/{s3_key}"
    return f"https://{bucket}.s3.{region}.amazonaws.com/{s3_key}"


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



@router.post("/upload-image", response_model=schemas.UploadImageResponse)
async def upload_images(
    images: List[UploadFile] = File(..., description="Upload 1 to 4 images"),
    db: Session = Depends(get_db),
):

    # ---- 1. Validate ----
    if len(images) == 0:
        raise HTTPException(status_code=400, detail="At least 1 image is required.")
    if len(images) > 4:
        raise HTTPException(status_code=400, detail="Maximum 4 images allowed per upload.")

    missing = []
    if not settings.AWS_SECRET_KEY:
        missing.append("AWS_SECRET_KEY")
    if not settings.AWS_SECRET_ACCESS_KEY:
        missing.append("AWS_SECRET_ACCESS_KEY")
    if not settings.REGION:
        missing.append("REGION")
    if not settings.S3_BUCKET:
        missing.append("S3_BUCKET")
    if missing:
        raise HTTPException(
            status_code=500,
            detail=f"Missing AWS configuration: {', '.join(missing)}"
        )

    bucket = settings.S3_BUCKET
    base_folder = (settings.S3_SERVICE_BASE_FOLDER or "").rstrip("/")
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")

    # ---- 2. Auto-generate IDs ----
    new_campaign_id = str(uuid.uuid4())
    new_id = str(uuid.uuid4())

    logger.info(f"[upload] Auto-generated campaign id={new_id} campaign_id={new_campaign_id}")

    # ---- 3. Upload images to S3 ----
    uploaded: List[dict] = []
    for idx, upload_file in enumerate(images):
        file_bytes = await upload_file.read()

        content_type = upload_file.content_type or "image/jpeg"
        raw_name = upload_file.filename or f"file_{idx}"
        ext = raw_name.rsplit(".", 1)[-1].lower() if "." in raw_name else "jpg"
        safe_filename = f"image_{timestamp}_{idx}.{ext}"
        thumb_filename = f"thumb_{timestamp}_{idx}.{ext}"

        # S3 key layout: <base_folder>/<campaign_id>/image_... and .../thumbnails/thumb_...
        if base_folder:
            image_s3_key = f"{base_folder}/{new_campaign_id}/{safe_filename}"
            thumb_s3_key  = f"{base_folder}/{new_campaign_id}/thumbnails/{thumb_filename}"
        else:
            image_s3_key = f"{new_campaign_id}/{safe_filename}"
            thumb_s3_key  = f"{new_campaign_id}/thumbnails/{thumb_filename}"

        try:
            _upload_file_to_s3(file_bytes, image_s3_key, content_type, bucket)
            logger.info(f"[upload] image {idx+1} uploaded: {image_s3_key}")
        except (ClientError, BotoCoreError) as exc:
            logger.error(f"[upload] S3 upload failed image {idx+1}: {exc}")
            raise HTTPException(status_code=500, detail=f"S3 upload failed for image {idx+1}: {exc}")

        try:
            _upload_file_to_s3(file_bytes, thumb_s3_key, content_type, bucket)
        except (ClientError, BotoCoreError) as exc:
            logger.error(f"[upload] S3 thumbnail upload failed image {idx+1}: {exc}")
            raise HTTPException(status_code=500, detail=f"S3 thumbnail upload failed for image {idx+1}: {exc}")

        image_url = _build_s3_url(image_s3_key, bucket)
        thumb_url  = _build_s3_url(thumb_s3_key, bucket)

        uploaded.append({
            "image_url": image_url,
            "thumbnail_url": thumb_url,
            "image_url_str": image_s3_key,
            "thumbnail_url_str": thumb_s3_key,
            "original_filename": raw_name,
        })

    # ---- 4. Persist Campaign + ConceptImage rows (descriptor = null) ----
    campaign_row = models.Campaign(
        id=uuid.UUID(new_id),
        campaign_id=new_campaign_id,
        type="self",
        status="pending",
    )
    db.add(campaign_row)
    db.flush()

    concept_image_rows: List[models.ConceptImage] = []
    for u in uploaded:
        row = models.ConceptImage(
            id=uuid.uuid4(),
            campaign_id=new_campaign_id,
            url=u["image_url"],
            thumbnail_url=u["thumbnail_url"],
            image_url_str=u["image_url_str"],
            thumbnail_url_str=u["thumbnail_url_str"],
            image_descriptor=None,          # filled after LLM call
        )
        db.add(row)
        concept_image_rows.append(row)

    db.commit()
    for row in concept_image_rows:
        db.refresh(row)
    db.refresh(campaign_row)

    logger.info(
        f"[upload] DB rows saved — campaign_id={new_campaign_id} "
        f"images={len(concept_image_rows)}"
    )

    # ---- 5. ONE LLM call: generate 3-word descriptor for every image ----
    assets_for_llm = [
        {
            "id":   str(row.id),
            "name": uploaded[i]["original_filename"],
            "data": row.url,
            "text": "",
        }
        for i, row in enumerate(concept_image_rows)
    ]

    try:
        logger.info(f"[upload] Calling LLM for descriptors on {len(assets_for_llm)} image(s)...")
        enriched = synthetic_testing_engine.generate_asset_image_descriptors_via_url(assets_for_llm)
    except Exception as exc:
        logger.warning(f"[upload] LLM descriptor call failed: {exc}. Using fallback labels.")
        enriched = assets_for_llm
        for i, a in enumerate(enriched):
            a.setdefault("image_descriptor", f"Asset {i+1}")

    # ---- 6. Update image_descriptor for each ConceptImage ----
    for i, row in enumerate(concept_image_rows):
        descriptor = (
            enriched[i].get("image_descriptor") if i < len(enriched) else None
        ) or f"Asset {i+1}"
        row.image_descriptor = descriptor
        db.add(row)

    db.commit()
    for row in concept_image_rows:
        db.refresh(row)
    db.refresh(campaign_row)

    logger.info(f"[upload] Descriptors updated for campaign_id={new_campaign_id}")

    # ---- Build and return response ----
    concept_image_details = [
        schemas.ConceptImageResponse(
            id=str(row.id),
            url=row.url,
            thumbnail_url=row.thumbnail_url,
            image_descriptor=row.image_descriptor,
            image_url_str=row.image_url_str,
            thumbnail_url_str=row.thumbnail_url_str,
        )
        for row in concept_image_rows
    ]

    return schemas.UploadImageResponse(
        message=f"Successfully uploaded {len(images)} image(s).",
        campaign=schemas.CampaignResponse(
            id=new_id,
            campaign_id=new_campaign_id,
            type=campaign_row.type,
            status=campaign_row.status,
            concept_image_details=concept_image_details,
            response_received=campaign_row.response_received,
            error_message=campaign_row.error_message,
            created_at=campaign_row.created_at,
            updated_at=campaign_row.updated_at,
        ),
    )


@router.get("/preview-image", response_model=List[schemas.CampaignResponse])
def get_campaign_preview(
    campaign_id: Optional[str] = None,
    db: Session = Depends(get_db),
):
    query = db.query(models.Campaign).order_by(models.Campaign.created_at.desc())

    if campaign_id:
        campaign_rows = query.filter(models.Campaign.campaign_id == campaign_id).all()
        if not campaign_rows:
            raise HTTPException(
                status_code=404,
                detail=f"No campaigns found for campaign_id={campaign_id}"
            )
    else:
        campaign_rows = query.limit(5).all()
        if not campaign_rows:
            raise HTTPException(status_code=404, detail="No campaigns found.")

    bucket = settings.S3_BUCKET
    results: List[schemas.CampaignResponse] = []

    for campaign_row in campaign_rows:
        image_rows = (
            db.query(models.ConceptImage)
            .filter(models.ConceptImage.campaign_id == campaign_row.campaign_id)
            .all()
        )

        concept_image_details = []
        for img in image_rows:
            # Build permanent public URL from the stored S3 key
            fresh_url = (
                _build_s3_url(img.image_url_str, bucket)
                if bucket and img.image_url_str
                else img.url
            )
            fresh_thumb_url = (
                _build_s3_url(img.thumbnail_url_str, bucket)
                if bucket and img.thumbnail_url_str
                else img.thumbnail_url
            )

            concept_image_details.append(
                schemas.ConceptImageResponse(
                    id=str(img.id),
                    url=fresh_url,
                    thumbnail_url=fresh_thumb_url,
                    image_descriptor=img.image_descriptor,
                    image_url_str=img.image_url_str,
                    thumbnail_url_str=img.thumbnail_url_str,
                )
            )

        results.append(
            schemas.CampaignResponse(
                id=str(campaign_row.id),
                campaign_id=campaign_row.campaign_id,
                type=campaign_row.type,
                status=campaign_row.status,
                concept_image_details=concept_image_details,
                response_received=campaign_row.response_received,
                error_message=campaign_row.error_message,
                created_at=campaign_row.created_at,
                updated_at=campaign_row.updated_at,
            )
        )

    return results


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
            
    return schemas.EmotionResponse(
        emotional_data=emotional_data,
        aggregated=asset_1_agg
    )