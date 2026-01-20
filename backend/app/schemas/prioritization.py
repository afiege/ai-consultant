from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional


class PrioritizationBase(BaseModel):
    """Base schema for Prioritization."""
    idea_id: int
    vote_type: str = "score"  # 'score', 'rank', 'vote'
    score: Optional[int] = Field(None, ge=1, le=10)
    rank_position: Optional[int] = None


class PrioritizationCreate(PrioritizationBase):
    """Schema for creating a prioritization vote."""
    pass


class PrioritizationResponse(PrioritizationBase):
    """Schema for prioritization response."""
    id: int
    session_id: int
    participant_id: Optional[int] = None
    created_at: datetime

    class Config:
        from_attributes = True


class IdeaWithScore(BaseModel):
    """Schema for idea with aggregated score."""
    idea_id: int
    idea_content: str
    participant_name: str
    round_number: int
    average_score: float
    total_votes: int
    rank: int
