import logging
from fastapi import Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError

logger = logging.getLogger(__name__)

async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """
    Log raw request details to help debug 422s (validation errors)
    """
    try:
        body = await request.body()
    except Exception:
        body = b""
    
    logger.error("🔴 Request validation error: %s", exc)
    logger.error("🔴 Request method: %s", request.method)
    logger.error("🔴 Request URL: %s", request.url)
    logger.error("🔴 Request headers: %s", dict(request.headers))
    logger.error("🔴 Request body size: %d", len(body))
    logger.error("🔴 Error details: %s", exc.errors())
    
    if body:
        try:
            preview = body[:2000].decode('utf-8', errors='replace')
            logger.error("🔴 Request body preview (first 2000 chars): %s", preview)
        except (UnicodeDecodeError, AttributeError) as e:
            logger.error("🔴 Request body preview unavailable: %s", e)
    
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "detail": "Request validation failed. See server logs for raw request preview.",
            "errors": exc.errors()
        }
    )

async def general_exception_handler(request: Request, exc: Exception):
    """
    Log all unhandled exceptions
    """
    logger.error("🔥 Unhandled server exception: %s", str(exc))
    logger.error("🔥 Request method: %s", request.method)
    logger.error("🔥 Request URL: %s", request.url)
    logger.error("🔥 Exception type: %s", type(exc).__name__)
    logger.error("🔥 Full traceback:", exc_info=True)
    
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "detail": "Internal server error occurred. Check server logs for details.",
            "error_type": type(exc).__name__
        }
    )
