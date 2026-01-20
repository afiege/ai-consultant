from pydantic import BaseModel
from datetime import datetime
from typing import Optional


class ParticipantBase(BaseModel):
    """Base schema for Participant."""
    name: str


class ParticipantCreate(ParticipantBase):
    """Schema for creating a participant."""
    pass


class ParticipantResponse(ParticipantBase):
    """Schema for participant response."""
    id: int
    participant_uuid: str
    session_id: int
    joined_at: datetime
    connection_status: str

    class Config:
        from_attributes = True


class ParticipantStatus(BaseModel):
    """Schema for participant status update."""
    participant_uuid: str
    name: str
    connection_status: str
    current_sheet_id: Optional[int] = None
