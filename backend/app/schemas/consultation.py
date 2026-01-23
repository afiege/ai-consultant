from pydantic import BaseModel
from datetime import datetime
from typing import Optional, List


class ConsultationMessageBase(BaseModel):
    """Base schema for ConsultationMessage."""
    role: str  # 'user', 'assistant', 'system'
    content: str


class ConsultationMessageCreate(BaseModel):
    """Schema for creating a consultation message."""
    content: str  # User message only
    participant_uuid: Optional[str] = None  # For collaborative mode


class ConsultationMessageResponse(ConsultationMessageBase):
    """Schema for consultation message response."""
    id: int
    session_id: int
    created_at: datetime
    participant_name: Optional[str] = None  # For collaborative mode

    class Config:
        from_attributes = True


class CollaborativeConsultationStatus(BaseModel):
    """Schema for collaborative consultation status."""
    collaborative_mode: bool
    participants: List[dict] = []
    message_count: int
    consultation_started: bool


class LLMRequest(BaseModel):
    """Schema for requests that need an LLM API key."""
    api_key: str  # API key passed per-request, NOT stored


class ConsultationStartRequest(LLMRequest):
    """Schema for starting consultation with API key."""
    pass


class ConsultationMessageWithKey(LLMRequest):
    """Schema for sending a message with API key."""
    content: str  # User message
    participant_uuid: Optional[str] = None  # For collaborative mode


class ConsultationFindingBase(BaseModel):
    """Base schema for ConsultationFinding."""
    factor_type: str  # 'project', 'risks', 'end_user'
    finding_text: str


class ConsultationFindingCreate(ConsultationFindingBase):
    """Schema for creating a consultation finding."""
    pass


class ConsultationFindingResponse(ConsultationFindingBase):
    """Schema for consultation finding response."""
    id: int
    session_id: int
    created_at: datetime

    class Config:
        from_attributes = True


class ConsultationSummary(BaseModel):
    """Schema for complete consultation summary with 3 factors."""
    project: Optional[str] = None
    risks: Optional[str] = None
    end_user: Optional[str] = None
    messages: List[ConsultationMessageResponse] = []
