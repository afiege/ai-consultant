from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from ..database import Base


class IdeaSheet(Base):
    """Idea sheets that rotate between participants in 6-3-5 method."""

    __tablename__ = "idea_sheets"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False)
    sheet_number = Column(Integer, nullable=False)  # 1-6 for up to 6 participants
    current_participant_id = Column(Integer, ForeignKey("participants.id"), nullable=True)
    current_round = Column(Integer, default=1)  # 1-6 rounds max
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Ensure unique sheet number per session
    __table_args__ = (UniqueConstraint('session_id', 'sheet_number', name='_session_sheet_uc'),)

    # Relationships
    session = relationship("Session", back_populates="idea_sheets")
    ideas = relationship("Idea", back_populates="sheet", cascade="all, delete-orphan")


class Idea(Base):
    """Individual ideas in the 6-3-5 method."""

    __tablename__ = "ideas"

    id = Column(Integer, primary_key=True, index=True)
    sheet_id = Column(Integer, ForeignKey("idea_sheets.id", ondelete="CASCADE"), nullable=False)
    participant_id = Column(Integer, ForeignKey("participants.id"), nullable=False)
    round_number = Column(Integer, nullable=False)  # Which round (1-6)
    idea_number = Column(Integer, nullable=False)  # 1, 2, or 3 (three ideas per round)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    sheet = relationship("IdeaSheet", back_populates="ideas")
    participant = relationship("Participant", back_populates="ideas")
    prioritizations = relationship("Prioritization", back_populates="idea", cascade="all, delete-orphan")
