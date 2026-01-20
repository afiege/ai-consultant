from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, List


class IdeaBase(BaseModel):
    """Base schema for Idea."""
    content: str


class IdeaCreate(IdeaBase):
    """Schema for creating an idea."""
    sheet_id: int
    round_number: int
    idea_number: int = Field(..., ge=1, le=3)


class IdeaBatchCreate(BaseModel):
    """Schema for creating multiple ideas at once (3 per round)."""
    sheet_id: int
    round_number: int
    ideas: List[str] = Field(..., min_length=3, max_length=3)


class IdeaResponse(IdeaBase):
    """Schema for idea response."""
    id: int
    sheet_id: int
    participant_id: int
    round_number: int
    idea_number: int
    created_at: datetime

    class Config:
        from_attributes = True


class IdeaSheetResponse(BaseModel):
    """Schema for idea sheet response."""
    id: int
    session_id: int
    sheet_number: int
    current_participant_id: Optional[int] = None
    current_round: int
    created_at: datetime
    ideas: List[IdeaResponse] = []

    class Config:
        from_attributes = True


class IdeaWithParticipant(IdeaResponse):
    """Schema for idea with participant info."""
    participant_name: str


class IdeaSheetWithIdeas(IdeaSheetResponse):
    """Schema for idea sheet with all ideas and participant info."""
    ideas: List[IdeaWithParticipant] = []
