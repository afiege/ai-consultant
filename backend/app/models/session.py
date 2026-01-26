from sqlalchemy import Column, Integer, String, DateTime, Text, Boolean
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from ..database import Base


class Session(Base):
    """Main consultation session model."""

    __tablename__ = "sessions"

    id = Column(Integer, primary_key=True, index=True)
    session_uuid = Column(String(36), unique=True, nullable=False, index=True)
    company_name = Column(String(255), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), server_default=func.now())
    current_step = Column(Integer, default=1)  # 1-4 tracking progress
    status = Column(String(50), default="active")  # active, completed, archived
    six_three_five_skipped = Column(Boolean, default=False)  # Whether 6-3-5 was skipped
    owner_participant_uuid = Column(String(36), nullable=True)  # UUID of session owner (first participant to join)
    collaborative_consultation = Column(Boolean, default=False)  # Enable multi-participant consultation mode

    # Expert mode settings
    expert_mode = Column(Boolean, default=False)  # Enable expert mode features
    prompt_language = Column(String(5), default="en")  # "en" or "de"
    custom_prompts = Column(Text, nullable=True)  # JSON string of custom prompts

    # LLM configuration (per-session)
    llm_model = Column(String(100), nullable=True)  # e.g., "meta-llama-3.1-8b-instruct"
    llm_api_base = Column(String(255), nullable=True)  # e.g., "https://chat-ai.academiccloud.de/v1"

    # Relationships
    company_info = relationship("CompanyInfo", back_populates="session", cascade="all, delete-orphan")
    participants = relationship("Participant", back_populates="session", cascade="all, delete-orphan")
    idea_sheets = relationship("IdeaSheet", back_populates="session", cascade="all, delete-orphan")
    prioritizations = relationship("Prioritization", back_populates="session", cascade="all, delete-orphan")
    consultation_messages = relationship("ConsultationMessage", back_populates="session", cascade="all, delete-orphan")
    consultation_findings = relationship("ConsultationFinding", back_populates="session", cascade="all, delete-orphan")
    maturity_assessment = relationship("MaturityAssessment", back_populates="session", uselist=False, cascade="all, delete-orphan")
