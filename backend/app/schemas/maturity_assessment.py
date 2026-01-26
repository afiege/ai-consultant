from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, Dict, List


class DimensionScores(BaseModel):
    """Individual question scores for a dimension."""
    question_scores: Dict[str, float] = Field(default_factory=dict)


class MaturityAssessmentCreate(BaseModel):
    """Schema for creating/updating a maturity assessment."""
    resources_score: float = Field(ge=1, le=6)
    resources_details: Optional[Dict[str, float]] = None

    information_systems_score: float = Field(ge=1, le=6)
    information_systems_details: Optional[Dict[str, float]] = None

    culture_score: float = Field(ge=1, le=6)
    culture_details: Optional[Dict[str, float]] = None

    organizational_structure_score: float = Field(ge=1, le=6)
    organizational_structure_details: Optional[Dict[str, float]] = None


class MaturityAssessmentResponse(BaseModel):
    """Schema for maturity assessment response."""
    id: int
    session_id: int
    created_at: datetime
    updated_at: Optional[datetime] = None

    resources_score: Optional[float] = None
    resources_details: Optional[Dict[str, float]] = None

    information_systems_score: Optional[float] = None
    information_systems_details: Optional[Dict[str, float]] = None

    culture_score: Optional[float] = None
    culture_details: Optional[Dict[str, float]] = None

    organizational_structure_score: Optional[float] = None
    organizational_structure_details: Optional[Dict[str, float]] = None

    overall_score: Optional[float] = None
    maturity_level: Optional[str] = None

    class Config:
        from_attributes = True


class MaturityLevelInfo(BaseModel):
    """Information about maturity levels."""
    level: int
    name: str
    description: str


# Define the maturity levels for reference
MATURITY_LEVELS = [
    MaturityLevelInfo(
        level=1,
        name="Computerization",
        description="Basic IT systems exist but operate in isolation"
    ),
    MaturityLevelInfo(
        level=2,
        name="Connectivity",
        description="IT systems are connected and can exchange data"
    ),
    MaturityLevelInfo(
        level=3,
        name="Visibility",
        description="Real-time data is available across the organization"
    ),
    MaturityLevelInfo(
        level=4,
        name="Transparency",
        description="Data is analyzed to understand why things happen"
    ),
    MaturityLevelInfo(
        level=5,
        name="Predictive Capacity",
        description="Data is used to forecast future scenarios"
    ),
    MaturityLevelInfo(
        level=6,
        name="Adaptability",
        description="Systems can autonomously optimize and adapt"
    ),
]


def get_maturity_level_name(score: float) -> str:
    """Convert a score to a maturity level name."""
    if score < 1.5:
        return "Computerization"
    elif score < 2.5:
        return "Connectivity"
    elif score < 3.5:
        return "Visibility"
    elif score < 4.5:
        return "Transparency"
    elif score < 5.5:
        return "Predictive Capacity"
    else:
        return "Adaptability"
