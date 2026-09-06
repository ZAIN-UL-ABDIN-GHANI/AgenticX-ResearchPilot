"""Common API schemas."""

from typing import Optional, Any
from pydantic import BaseModel


class ErrorResponse(BaseModel):
    """Standard error response."""

    error: str
    detail: Optional[str] = None
    request_id: Optional[str] = None


class SuccessResponse(BaseModel):
    """Standard success response."""

    success: bool
    message: str
    data: Optional[Any] = None


class HealthResponse(BaseModel):
    """Health check response."""

    status: str
    version: str = "1.0.0"
    environment: Optional[str] = None
