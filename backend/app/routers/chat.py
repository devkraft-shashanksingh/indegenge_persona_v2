from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
import logging

from .. import schemas, crud
from ..chat_engine import ChatEngine
from ..database import get_db

router = APIRouter(
    prefix="/api/chat",
    tags=["chat"]
)

logger = logging.getLogger(__name__)

@router.post("/sessions", response_model=schemas.ChatSession)
async def create_chat_session(
    session_data: schemas.ChatSessionCreate, 
    db: Session = Depends(get_db)
):
    """Start a new chat session with a persona."""
    engine = ChatEngine(db)
    return engine.create_session(session_data.persona_id, session_data.brand_id)

@router.get("/sessions/{session_id}", response_model=schemas.ChatSession)
async def get_chat_session(session_id: int, db: Session = Depends(get_db)):
    """Get chat session details."""
    session = crud.get_chat_session(db, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Chat session not found")
    return session

@router.get("/sessions/{session_id}/messages", response_model=List[schemas.ChatMessage])
async def get_chat_history_endpoint(
    session_id: int, 
    limit: int = 50, 
    db: Session = Depends(get_db)
):
    """Get message history for a session."""
    if not crud.get_chat_session(db, session_id):
        raise HTTPException(status_code=404, detail="Chat session not found")
    return crud.get_chat_history(db, session_id, limit)

@router.post("/sessions/{session_id}/messages", response_model=schemas.ChatMessage)
async def send_chat_message(
    session_id: int,
    message: schemas.ChatMessageCreate,
    db: Session = Depends(get_db)
):
    """Send a message to the persona and get a response."""
    engine = ChatEngine(db)
    
    try:
        # process_message handles saving the user message and generating/saving the assistant response
        response_msg = engine.process_message(session_id, message.content)
        return response_msg
    except ValueError as e:
        # Typically means session or persona not found
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Chat error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to process chat message: {str(e)}")
