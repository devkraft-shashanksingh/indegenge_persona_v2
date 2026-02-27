from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Any

from .. import crud, schemas, panel_feedback_engine
from ..database import get_db

router = APIRouter(
    prefix="/api/panel-feedback",
    tags=["panel-feedback"],
    responses={404: {"description": "Not found"}},
)

@router.post("", response_model=schemas.PanelFeedbackResponse)
def create_panel_feedback(
    request: schemas.PanelFeedbackRequest,
    db: Session = Depends(get_db)
) -> Any:
    """
    Run a panel feedback analysis for the given personas.
    """
    try:
        result = panel_feedback_engine.run_panel_feedback_analysis(
            persona_ids=request.persona_ids,
            stimulus_text=request.stimulus_text,
            stimulus_images=request.stimulus_images,
            content_type=request.content_type,
            db=db
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    

@router.post("/v2", response_model=schemas.PanelFeedbackResponseV2)
def create_panel_feedback(
    request: schemas.PanelFeedbackRequestV2,
    db: Session = Depends(get_db)
) -> Any:
    """
    Run a panel feedback analysis for the given personas.
    """
    try:
        result = panel_feedback_engine.run_panel_feedback_analysis_v2(
            campaign_id=request.campaign_id,
            task_id=request.task_id,
            persona_ids=request.persona_ids,
            stimulus_text=request.stimulus_text,
            stimulus_images=request.stimulus_images,
            content_type=request.content_type,
            panel_feedback_prompt=request.panel_feedback_prompt,
            panel_summary_prompt=request.panel_summary_prompt,
            db=db,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

