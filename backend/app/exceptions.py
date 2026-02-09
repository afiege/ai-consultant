"""
Unified exception handling for the AI Consultant backend.

This module provides:
- Custom exception classes for different error scenarios
- Consistent error response format
- Global exception handlers for FastAPI
"""

from fastapi import HTTPException, status
from fastapi.responses import JSONResponse
from fastapi.requests import Request
from typing import Optional, Dict, Any
import logging

logger = logging.getLogger(__name__)


class APIError(Exception):
    """Base exception for all API errors."""

    def __init__(
        self,
        message: str,
        status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
        error_code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        self.message = message
        self.status_code = status_code
        self.error_code = error_code or "INTERNAL_ERROR"
        self.details = details or {}
        super().__init__(self.message)


class NotFoundError(APIError):
    """Resource not found error."""

    def __init__(self, resource: str, identifier: str):
        super().__init__(
            message=f"{resource} with identifier '{identifier}' not found",
            status_code=status.HTTP_404_NOT_FOUND,
            error_code="NOT_FOUND",
            details={"resource": resource, "identifier": identifier}
        )


class SessionNotFoundError(NotFoundError):
    """Session not found error."""

    def __init__(self, session_uuid: str):
        super().__init__(resource="Session", identifier=session_uuid)


class ValidationError(APIError):
    """Request validation error."""

    def __init__(self, message: str, field: Optional[str] = None):
        details = {"field": field} if field else {}
        super().__init__(
            message=message,
            status_code=status.HTTP_400_BAD_REQUEST,
            error_code="VALIDATION_ERROR",
            details=details
        )


class LLMError(APIError):
    """LLM/AI service error."""

    def __init__(self, message: str, provider: Optional[str] = None):
        details = {"provider": provider} if provider else {}
        super().__init__(
            message=f"AI service error: {message}",
            status_code=status.HTTP_502_BAD_GATEWAY,
            error_code="LLM_ERROR",
            details=details
        )


class LLMAuthenticationError(LLMError):
    """LLM authentication/API key error."""

    def __init__(self, provider: Optional[str] = None):
        super().__init__(
            message="Invalid or missing API key",
            provider=provider
        )
        self.status_code = status.HTTP_401_UNAUTHORIZED
        self.error_code = "LLM_AUTH_ERROR"


class LLMRateLimitError(LLMError):
    """LLM rate limit exceeded error."""

    def __init__(self, provider: Optional[str] = None, retry_after: Optional[int] = None):
        super().__init__(
            message="AI service rate limit exceeded. Please try again later.",
            provider=provider
        )
        self.status_code = status.HTTP_429_TOO_MANY_REQUESTS
        self.error_code = "LLM_RATE_LIMIT"
        if retry_after:
            self.details["retry_after"] = retry_after


class ExportError(APIError):
    """Export/PDF generation error."""

    def __init__(self, message: str, format: Optional[str] = None):
        details = {"format": format} if format else {}
        super().__init__(
            message=f"Export failed: {message}",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            error_code="EXPORT_ERROR",
            details=details
        )


class DatabaseError(APIError):
    """Database operation error."""

    def __init__(self, message: str = "Database operation failed"):
        super().__init__(
            message=message,
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            error_code="DATABASE_ERROR"
        )


def create_error_response(error: APIError) -> Dict[str, Any]:
    """Create a standardized error response dictionary."""
    return {
        "error": error.error_code,
        "message": error.message,
        "details": error.details
    }


async def api_error_handler(request: Request, exc: APIError) -> JSONResponse:
    """Global exception handler for APIError and its subclasses."""
    logger.error(
        f"API Error: {exc.error_code} - {exc.message}",
        extra={
            "status_code": exc.status_code,
            "details": exc.details,
            "path": request.url.path
        }
    )

    return JSONResponse(
        status_code=exc.status_code,
        content=create_error_response(exc)
    )


async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Global exception handler for unhandled exceptions."""
    logger.exception(
        f"Unhandled exception: {str(exc)}",
        extra={"path": request.url.path}
    )

    error = APIError(
        message="An unexpected error occurred",
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        error_code="INTERNAL_ERROR"
    )

    return JSONResponse(
        status_code=error.status_code,
        content=create_error_response(error)
    )
