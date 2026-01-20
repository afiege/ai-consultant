from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from ..database import Base


class Prioritization(Base):
    """Idea prioritization/voting in Step 3."""

    __tablename__ = "prioritizations"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False)
    idea_id = Column(Integer, ForeignKey("ideas.id", ondelete="CASCADE"), nullable=False)
    participant_id = Column(Integer, ForeignKey("participants.id"), nullable=True)  # NULL if collective ranking
    vote_type = Column(String(50), nullable=True)  # 'score', 'rank', 'vote'
    score = Column(Integer, nullable=True)  # Numerical score
    rank_position = Column(Integer, nullable=True)  # Ranking position
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    session = relationship("Session", back_populates="prioritizations")
    idea = relationship("Idea", back_populates="prioritizations")
    participant = relationship("Participant", back_populates="prioritizations")
