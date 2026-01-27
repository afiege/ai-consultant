from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional


class SessionBase(BaseModel):
    """Base schema for Session."""
    company_name: Optional[str] = None


class SessionCreate(SessionBase):
    """Schema for creating a new session."""
    pass


class SessionUpdate(BaseModel):
    """Schema for updating a session."""
    company_name: Optional[str] = None
    current_step: Optional[int] = Field(None, ge=1, le=4)
    status: Optional[str] = None
    six_three_five_skipped: Optional[bool] = None
    selected_cluster_id: Optional[int] = None


class SessionResponse(SessionBase):
    """Schema for session response."""
    id: int
    session_uuid: str
    created_at: datetime
    updated_at: Optional[datetime] = None
    current_step: int
    status: str
    six_three_five_skipped: bool
    idea_clusters: Optional[str] = None  # JSON string
    selected_cluster_id: Optional[int] = None

    class Config:
        from_attributes = True
