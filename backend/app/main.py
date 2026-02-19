from fastapi import FastAPI, Depends, Request, APIRouter
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
import logging
import uvicorn
import time

from .core.config import settings
from .routers import personas, brands, chat, synthetic, analysis, panel_feedback, simulations, utils
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
    openapi_url=f"/persona-apis{settings.API_V1_STR}/openapi.json",
    docs_url="/persona-apis/docs",
    redoc_url="/persona-apis/redoc"
)

# Set all CORS enabled origins
if settings.BACKEND_CORS_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
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

# Create a global router for the prefix
api_router = APIRouter(prefix="/persona-apis")

# Include Sub-Routers
api_router.include_router(personas.router)
api_router.include_router(brands.router)
api_router.include_router(chat.router)
api_router.include_router(synthetic.router)
api_router.include_router(analysis.router)
api_router.include_router(panel_feedback.router)
api_router.include_router(simulations.router)
api_router.include_router(utils.router)

@api_router.get("/")
async def root():
    return {
        "message": f"Welcome to {settings.PROJECT_NAME} API", 
        "docs": "/persona-apis/docs",
        "environment": settings.ENVIRONMENT
    }

@api_router.get("/health/db")
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

@api_router.get("/stats")
def get_stats(db: Session = Depends(get_db)):
    """
    Get dashboard statistics.
    """
    return crud.get_simulation_stats(db)

@api_router.get(f"{settings.API_V1_STR}/segments")
def list_segments():
    """List all available segments."""
    return segments.SEGMENTS

@api_router.get(f"{settings.API_V1_STR}/disease-packs")
def list_disease_packs():
    """List all available disease packs."""
    # Convert dict values to list
    return list(disease_packs.DISEASE_PACKS.values())

# Include the main router into the app
app.include_router(api_router)

if __name__ == "__main__":
    uvicorn.run("app.main:app", host=settings.BACKEND_HOST, port=settings.BACKEND_PORT, reload=True)
