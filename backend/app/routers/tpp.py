from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
import logging
from ..database import get_db
from .. import models, schemas

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/tpp",
    tags=["tpp"],
)


def _tpp_to_response(row: models.TPP) -> schemas.TPPResponse:
    return schemas.TPPResponse(
        id=str(row.id),
        brand_id=row.brand_id,
        name=row.name,
        text=row.text,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


@router.get("", response_model=List[schemas.TPPResponse])
def list_tpp(
    brand_id: Optional[int] = Query(None, description="Filter by brand_id"),
    db: Session = Depends(get_db),
):

    query = db.query(models.TPP).order_by(models.TPP.updated_at.desc())

    if brand_id is not None:
        query = query.filter(models.TPP.brand_id == brand_id)

    rows = query.all()
    return [_tpp_to_response(r) for r in rows]

