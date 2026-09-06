"""
ResearchPilot AI - Main FastAPI Application Entry Point

Orchestrates:
- Database initialization
- Middleware setup
- Route registration
- Error handling
- Logging configuration
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.core.logging import setup_logging, get_logger
from app.db.database import engine
from app.db.base import Base
from app.schemas.common import HealthResponse
from app.middleware import (
    RequestIDMiddleware,
    LoggingMiddleware,
    ExceptionMiddleware,
)
from app.api.routes import research

# Setup logging before creating app
setup_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifecycle management.
    
    Startup: Create database tables
    Shutdown: Cleanup resources
    """
    # Startup
    logger.info("=" * 80)
    logger.info("Starting ResearchPilot AI Application")
    logger.info("=" * 80)
    logger.info(f"Debug mode: {settings.debug}")
    logger.info(f"Log level: {settings.log_level}")
    logger.info(f"Database: {settings.database_url.split('@')[1] if '@' in settings.database_url else 'SQLite'}")
    logger.info(f"Max steps: {settings.max_steps}")
    logger.info(f"Research timeout: {settings.research_timeout}s")
    
    # Create all tables
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Database tables created/verified")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}", exc_info=True)
        raise
    
    yield
    
    # Shutdown
    logger.info("=" * 80)
    logger.info("Shutting down ResearchPilot AI Application")
    logger.info("=" * 80)
    
    try:
        await engine.dispose()
        logger.info("Database connections closed")
    except Exception as e:
        logger.error(f"Error closing database: {e}")


# Create FastAPI application
app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    description="AI-Powered Evidence-Based Research Agent",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

# Add middleware (order matters - top to bottom)
# Exceptions must be caught first
app.add_middleware(ExceptionMiddleware)
# Then log requests
app.add_middleware(LoggingMiddleware)
# Then add request IDs
app.add_middleware(RequestIDMiddleware)

# Parse and add CORS middleware
allowed_origins = [
    origin.strip() 
    for origin in settings.allowed_origins.split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

logger.info(f"CORS allowed origins: {allowed_origins}")


# ============================================================================
# Exception Handlers
# ============================================================================

@app.exception_handler(ValueError)
async def value_error_handler(request, exc: ValueError):
    """Handle ValueError exceptions."""
    request_id = getattr(request.state, "request_id", "unknown")
    
    logger.warning(
        f"ValueError: {str(exc)}",
        extra={"request_id": request_id},
    )
    
    return JSONResponse(
        status_code=400,
        content={
            "error": "Invalid value",
            "detail": str(exc),
            "request_id": request_id,
        },
    )


@app.exception_handler(Exception)
async def general_exception_handler(request, exc: Exception):
    """Handle general exceptions."""
    request_id = getattr(request.state, "request_id", "unknown")
    
    logger.error(
        f"Unhandled exception: {exc}",
        extra={"request_id": request_id},
        exc_info=True,
    )
    
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "request_id": request_id,
        },
    )


# ============================================================================
# Health Check Endpoints
# ============================================================================

@app.get(
    "/health",
    response_model=HealthResponse,
    tags=["health"],
    summary="Health check",
)
async def health_check() -> HealthResponse:
    """
    Health check endpoint.
    
    Returns:
        HealthResponse: Status and version
    """
    return HealthResponse(status="healthy", version="1.0.0")


@app.get(
    "/",
    tags=["root"],
    summary="API root",
)
async def root():
    """Root endpoint with API information."""
    return {
        "message": "ResearchPilot AI - Evidence-Based Research Agent",
        "version": "1.0.0",
        "docs": "/docs",
        "redoc": "/redoc",
        "health": "/health",
    }


# ============================================================================
# Route Registration
# ============================================================================

# Include research routes
app.include_router(research.router)

logger.info("Routes registered:")
logger.info("  POST   /api/v1/research")
logger.info("  GET    /api/v1/research/{research_id}")
logger.info("  GET    /api/v1/research/{research_id}/sources")
logger.info("  GET    /api/v1/research/{research_id}/tools")
logger.info("  GET    /api/v1/research/{research_id}/claims")
logger.info("  GET    /health")
logger.info("  GET    /docs")


# ============================================================================
# Startup Event
# ============================================================================

@app.on_event("startup")
async def startup_event():
    """Startup event handler."""
    logger.info("Application startup complete")
    logger.info(f"Listening on http://0.0.0.0:8000")


# ============================================================================
# Shutdown Event
# ============================================================================

@app.on_event("shutdown")
async def shutdown_event():
    """Shutdown event handler."""
    logger.info("Application shutdown initiated")


# ============================================================================
# Entry Point
# ============================================================================

if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.debug,
        log_level=settings.log_level.lower(),
    )
