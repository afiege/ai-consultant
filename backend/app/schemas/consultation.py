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


class FindingItem(BaseModel):
    """Schema for a single finding item."""
    text: Optional[str] = None
    created_at: Optional[str] = None


class SessionInfo(BaseModel):
    """Basic session information."""
    uuid: str
    company_name: Optional[str] = None


class CompanyInfoSection(BaseModel):
    """Company info section in all findings."""
    profile: Optional[FindingItem] = None
    raw_info: List[dict] = []


class MaturitySection(BaseModel):
    """Maturity assessment data."""
    overall_score: Optional[float] = None
    maturity_level: Optional[str] = None
    resources_score: Optional[float] = None
    information_systems_score: Optional[float] = None
    culture_score: Optional[float] = None
    organizational_structure_score: Optional[float] = None


class CrispDmSection(BaseModel):
    """CRISP-DM findings section."""
    business_objectives: Optional[FindingItem] = None
    situation_assessment: Optional[FindingItem] = None
    ai_goals: Optional[FindingItem] = None
    project_plan: Optional[FindingItem] = None


class BusinessCaseSection(BaseModel):
    """Business case findings section."""
    classification: Optional[FindingItem] = None
    calculation: Optional[FindingItem] = None
    validation_questions: Optional[FindingItem] = None
    management_pitch: Optional[FindingItem] = None


class CostsSection(BaseModel):
    """Cost estimation findings section."""
    complexity: Optional[FindingItem] = None
    initial_investment: Optional[FindingItem] = None
    recurring_costs: Optional[FindingItem] = None
    maintenance: Optional[FindingItem] = None
    tco: Optional[FindingItem] = None
    cost_drivers: Optional[FindingItem] = None
    optimization: Optional[FindingItem] = None
    roi_analysis: Optional[FindingItem] = None


class AnalysisSection(BaseModel):
    """Analysis section (SWOT and Technical Briefing)."""
    swot_analysis: Optional[FindingItem] = None
    technical_briefing: Optional[FindingItem] = None


class AllFindingsResponse(BaseModel):
    """Response schema for all findings endpoint."""
    session: SessionInfo
    company_info: CompanyInfoSection
    maturity: Optional[MaturitySection] = None
    crisp_dm: CrispDmSection
    business_case: BusinessCaseSection
    costs: CostsSection
    analysis: AnalysisSection
