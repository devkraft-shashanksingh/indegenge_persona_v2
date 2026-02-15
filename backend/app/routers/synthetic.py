from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from .. import schemas, synthetic_testing_engine
from ..database import get_db

router = APIRouter(
    prefix="/api/synthetic-testing",
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
