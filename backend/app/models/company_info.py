from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from ..database import Base


class CompanyInfo(Base):
    """Company information collected in Step 1."""

    __tablename__ = "company_info"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False)
    info_type = Column(String(50), nullable=False)  # 'text', 'file', 'web_crawl'
    content = Column(Text, nullable=True)  # Free text or extracted content
    source_url = Column(String(500), nullable=True)  # If from web crawl
    file_path = Column(String(500), nullable=True)  # If from file upload
    file_name = Column(String(255), nullable=True)  # Original filename
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    session = relationship("Session", back_populates="company_info")
