from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from ..database import Base


class ConsultationMessage(Base):
    """AI consultation interview messages for Step 4 and Step 5."""

    __tablename__ = "consultation_messages"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False)
    participant_id = Column(Integer, ForeignKey("participants.id", ondelete="SET NULL"), nullable=True)  # For collaborative mode
    role = Column(String(50), nullable=False)  # 'user', 'assistant', 'system'
    content = Column(Text, nullable=False)
    message_type = Column(String(20), default="consultation")  # 'consultation' (Step 4) or 'business_case' (Step 5)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    session = relationship("Session", back_populates="consultation_messages")
    participant = relationship("Participant")


class ConsultationFinding(Base):
    """Key findings from consultation (Step 4) and business case (Step 5)."""

    __tablename__ = "consultation_findings"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False)
    # Step 4 types: 'business_objectives', 'situation_assessment', 'ai_goals', 'project_plan'
    # Step 5 types: 'business_case_classification', 'business_case_calculation', 'business_case_validation', 'business_case_pitch'
    factor_type = Column(String(50), nullable=False)
    finding_text = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Ensure one finding per factor type per session
    __table_args__ = (UniqueConstraint('session_id', 'factor_type', name='_session_factor_uc'),)

    # Relationships
    session = relationship("Session", back_populates="consultation_findings")
    cross_references = relationship("FindingCrossReference", back_populates="source_finding", foreign_keys="FindingCrossReference.source_finding_id", cascade="all, delete-orphan")


class FindingCrossReference(Base):
    """Cross-references between findings, extracted by LLM for wiki-style linking."""

    __tablename__ = "finding_cross_references"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False)
    source_finding_id = Column(Integer, ForeignKey("consultation_findings.id", ondelete="CASCADE"), nullable=False)
    target_finding_type = Column(String(50), nullable=False)  # The factor_type of the target finding
    linked_phrase = Column(String(500), nullable=False)  # The exact phrase in source that links to target
    relationship_type = Column(String(50), default="references")  # 'references', 'depends_on', 'supports', 'contradicts'
    confidence = Column(Integer, default=80)  # 0-100, how confident the LLM was
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    session = relationship("Session")
    source_finding = relationship("ConsultationFinding", back_populates="cross_references", foreign_keys=[source_finding_id])
