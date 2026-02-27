from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Any, Dict, Optional
import logging

from ..database import get_db
from .. import models

router = APIRouter(tags=["task-history"])
logger = logging.getLogger(__name__)

# =========================================================
# Pydantic Schema (keep in this file or move to schemas.py)
# =========================================================
from pydantic import BaseModel
from typing import Dict, Any, Optional


class TaskHistoryUpsertRequest(BaseModel):
    task_id: str
    type_test: str          # ✅ column name is type_test
    status: str
    response_stored: Optional[Dict[str, Any]] = None


# =========================================================
# 1) GET: List task_ids (limit/offset + optional type_test filter)
# =========================================================
@router.get("/task-history/tasks", response_model=Dict[str, Any])
def list_task_ids(
    limit: int = Query(20, ge=1, le=200),
    offset: int = Query(0, ge=0),
    type_test: Optional[str] = Query(None, description="Optional filter by type_test (e.g., qual/quant)"),
    db: Session = Depends(get_db),
):
    try:
        q = db.query(models.TaskHistory)

        if type_test:
            q = q.filter(models.TaskHistory.type_test == type_test)

        total = q.count()

        if hasattr(models.TaskHistory, "created_at"):
            q = q.order_by(models.TaskHistory.created_at.desc())
        else:
            q = q.order_by(models.TaskHistory.task_id.desc())

        rows = q.offset(offset).limit(limit).all()

        items = []
        for r in rows:
            items.append({
                "task_id": str(getattr(r, "task_id", "")),
                "type_test": getattr(r, "type_test", None),
                "status": getattr(r, "status", None),
                "created_at": getattr(r, "created_at", None) if hasattr(r, "created_at") else None,
            })

        return {
            "total": total,
            "limit": limit,
            "offset": offset,
            "items": items,
        }

    except Exception as e:
        logger.exception("Failed to list task ids")
        raise HTTPException(status_code=500, detail=f"Failed to list task ids: {str(e)}")


# =========================================================
# 2) GET: Fetch full task record by task_id (+ optional type_test)
# =========================================================
@router.get("/task-history/tasks/{task_id}", response_model=Dict[str, Any])
def get_task(
    task_id: str,
    type_test: Optional[str] = Query(
        None,
        description="Optional type_test to disambiguate if same task_id exists multiple times"
    ),
    db: Session = Depends(get_db),
):
    try:
        q = db.query(models.TaskHistory).filter(models.TaskHistory.task_id == task_id)
        if type_test:
            q = q.filter(models.TaskHistory.type_test == type_test)

        row = q.first()
        if not row:
            raise HTTPException(status_code=404, detail="Task not found")

        data = {c.name: getattr(row, c.name) for c in row.__table__.columns}
        if "task_id" in data and data["task_id"] is not None:
            data["task_id"] = str(data["task_id"])

        return data

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to fetch task")
        raise HTTPException(status_code=500, detail=f"Failed to fetch task: {str(e)}")


# =========================================================
# 3) POST: Upsert by (task_id + type_test), store status + response_stored (JSON/JSONB)
# =========================================================
@router.post("/task-history/upsert", response_model=Dict[str, Any])
def upsert_task_history(
    payload: TaskHistoryUpsertRequest,
    db: Session = Depends(get_db),
):
    try:
        row = (
            db.query(models.TaskHistory)
            .filter(
                models.TaskHistory.task_id == payload.task_id,
                models.TaskHistory.type_test == payload.type_test,
            )
            .first()
        )

        # create if missing
        if not row:
            row = models.TaskHistory(
                task_id=payload.task_id,
                type_test=payload.type_test,
            )
            db.add(row)

        row.status = payload.status

        if payload.response_stored is not None:
            row.response_stored = payload.response_stored

        db.commit()
        db.refresh(row)

        return {
            "message": "Task history upserted successfully",
            "task_id": str(row.task_id),
            "type_test": row.type_test,
            "status": row.status,
        }

    except Exception as e:
        db.rollback()
        logger.exception("Failed to upsert task history")
        raise HTTPException(status_code=500, detail=f"Upsert failed: {str(e)}")