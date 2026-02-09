from pydantic import BaseModel, HttpUrl
from datetime import datetime
from typing import Optional


class CompanyInfoBase(BaseModel):
    """Base schema for CompanyInfo."""
    info_type: str  # 'text', 'file', 'web_crawl'
    content: Optional[str] = None
    source_url: Optional[str] = None
    file_name: Optional[str] = None


class CompanyInfoCreate(CompanyInfoBase):
    """Schema for creating company info."""
    pass


class CompanyInfoTextCreate(BaseModel):
    """Schema for text-based company info."""
    content: str


class CompanyInfoWebCrawlCreate(BaseModel):
    """Schema for web crawl request."""
    url: str


class CompanyInfoResponse(CompanyInfoBase):
    """Schema for company info response."""
    id: int
    session_id: int
    created_at: datetime

    class Config:
        from_attributes = True
