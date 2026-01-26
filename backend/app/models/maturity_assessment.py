from sqlalchemy import Column, Integer, String, Float, ForeignKey, DateTime, Text
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from ..database import Base


class MaturityAssessment(Base):
    """Acatech Industry 4.0 Maturity Assessment model.

    Evaluates company across 4 structural dimensions on a scale of 1-6.
    Levels: 1-Computerization, 2-Connectivity, 3-Visibility,
            4-Transparency, 5-Predictive Capacity, 6-Adaptability
    """

    __tablename__ = "maturity_assessments"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("sessions.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), server_default=func.now())

    # Dimension 1: Resources - Digital capability of employees, equipment, materials
    resources_score = Column(Float, nullable=True)
    resources_details = Column(Text, nullable=True)  # JSON with individual question scores

    # Dimension 2: Information Systems - Integration of IT systems, data processing
    information_systems_score = Column(Float, nullable=True)
    information_systems_details = Column(Text, nullable=True)

    # Dimension 3: Culture - Willingness to change, knowledge sharing, openness
    culture_score = Column(Float, nullable=True)
    culture_details = Column(Text, nullable=True)

    # Dimension 4: Organizational Structure - Agility, collaboration, decision-making
    organizational_structure_score = Column(Float, nullable=True)
    organizational_structure_details = Column(Text, nullable=True)

    # Overall maturity level (average of all dimensions)
    overall_score = Column(Float, nullable=True)
    maturity_level = Column(String(50), nullable=True)  # e.g., "Connectivity", "Visibility"

    # Relationship
    session = relationship("Session", back_populates="maturity_assessment")
