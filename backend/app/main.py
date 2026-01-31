from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
import os
import logging

from .config import settings
from .exceptions import APIError, api_error_handler, generic_exception_handler

# Configure logging
logging.basicConfig(
    level=logging.DEBUG if settings.debug else logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)
from .database import init_db

# Import routers
from .routers import sessions, company_info, six_three_five, prioritization, consultation, export, expert_settings, business_case, cost_estimation, session_backup, maturity_assessment, test_mode
# from .routers import websocket

# Rate limiter configuration
# Uses client IP address for rate limiting
limiter = Limiter(key_func=get_remote_address)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Modern lifespan context manager for FastAPI.
    Replaces deprecated @app.on_event("startup") and @app.on_event("shutdown").
    """
    # Startup
    os.makedirs("./database", exist_ok=True)
    os.makedirs(settings.upload_dir, exist_ok=True)
    os.makedirs("./exports", exist_ok=True)

    # Initialize database tables
    init_db()
    logger.info("Database initialized successfully")

    yield  # Application runs here

    # Shutdown
    logger.info("Application shutting down")


app = FastAPI(
    title="AI & Digitalization Consultant",
    description="AI-powered digitalization consultant for SMEs with 4-step consultation process",
    version="1.0.0",
    lifespan=lifespan,
)

# Add rate limiter to app state
app.state.limiter = limiter

# Rate limit exceeded handler
@app.exception_handler(RateLimitExceeded)
async def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded):
    """Handle rate limit exceeded errors with a friendly message."""
    return JSONResponse(
        status_code=429,
        content={
            "error": "RATE_LIMIT_EXCEEDED",
            "message": "Too many requests. Please wait before making more requests.",
            "details": {"retry_after": exc.detail}
        }
    )

# Register custom exception handlers
app.add_exception_handler(APIError, api_error_handler)
app.add_exception_handler(Exception, generic_exception_handler)

# CORS middleware configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Health check endpoint
@app.get("/")
async def root():
    """Root endpoint - health check."""
    return {
        "message": "AI & Digitalization Consultant API",
        "status": "running",
        "version": "1.0.0"
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}


# Include routers
app.include_router(sessions.router, prefix="/api/sessions", tags=["sessions"])
app.include_router(company_info.router, prefix="/api/sessions", tags=["company-info"])
app.include_router(six_three_five.router, prefix="/api/sessions", tags=["6-3-5"])
app.include_router(prioritization.router, prefix="/api/sessions", tags=["prioritization"])
app.include_router(consultation.router, prefix="/api/sessions", tags=["consultation"])
app.include_router(export.router, prefix="/api/sessions", tags=["export"])
app.include_router(expert_settings.router, prefix="/api/sessions", tags=["expert-settings"])
app.include_router(business_case.router, prefix="/api/sessions", tags=["business-case"])
app.include_router(cost_estimation.router, prefix="/api/sessions", tags=["cost-estimation"])
app.include_router(session_backup.router, prefix="/api/sessions", tags=["session-backup"])
app.include_router(maturity_assessment.router, prefix="/api/sessions", tags=["maturity-assessment"])
app.include_router(test_mode.router, tags=["test-mode"])
# app.include_router(websocket.router, prefix="/ws", tags=["websocket"])


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug
    )
