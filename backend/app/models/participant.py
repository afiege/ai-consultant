from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from ..database import Base


class Participant(Base):
    """Participants in 6-3-5 brainstorming session."""

    __tablename__ = "participants"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False)
    participant_uuid = Column(String(36), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=False)
    joined_at = Column(DateTime(timezone=True), server_default=func.now())
    connection_status = Column(String(50), default="connected")  # connected, disconnected

    # Relationships
    session = relationship("Session", back_populates="participants")
    ideas = relationship("Idea", back_populates="participant")
    prioritizations = relationship("Prioritization", back_populates="participant")
