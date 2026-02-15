from fastapi import FastAPI, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
import logging
import uvicorn
import time

from .core.config import settings
from .routers import personas, brands, chat, synthetic, analysis
from .database import get_db
from . import models, segments, disease_packs, crud
from sqlalchemy.orm import Session

# Configure logging - write to both console and file for debugging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(name)s %(levelname)s %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('debug_server.log', mode='w'),
    ]
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json"
)

# Set all CORS enabled origins
if settings.BACKEND_CORS_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[str(origin) for origin in settings.BACKEND_CORS_ORIGINS],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    response.headers["X-Process-Time"] = str(process_time)
    return response

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request, exc):
    logger.error(f"Validation error: {exc}")
    return JSONResponse(
        status_code=422,
        content={"detail": exc.errors(), "body": exc.body},
    )

# Include Routers
app.include_router(personas.router)
app.include_router(brands.router)
app.include_router(chat.router)
app.include_router(synthetic.router)
app.include_router(analysis.router)

@app.get("/")
async def root():
    return {
        "message": f"Welcome to {settings.PROJECT_NAME} API", 
        "docs": "/docs",
        "environment": settings.ENVIRONMENT
    }

@app.get("/health/db")
def health_check_db(db: Session = Depends(get_db)):
    """
    Check database connectivity and return simple stats.
    Used by frontend to verify API is online.
    """
    try:
        # Check simple query
        count = db.query(models.Persona).count()
        return {"status": "ok", "personas": count}
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return JSONResponse(status_code=500, content={"status": "error", "detail": str(e)})

@app.get("/stats")
def get_stats(db: Session = Depends(get_db)):
    """
    Get dashboard statistics.
    """
    return crud.get_simulation_stats(db)

@app.get(f"{settings.API_V1_STR}/segments")
def list_segments():
    """List all available segments."""
    return segments.SEGMENTS

@app.get(f"{settings.API_V1_STR}/disease-packs")
def list_disease_packs():
    """List all available disease packs."""
    # Convert dict values to list
    return list(disease_packs.DISEASE_PACKS.values())

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
