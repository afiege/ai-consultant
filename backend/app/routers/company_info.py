from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Request
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel
import uuid
import os
from slowapi import Limiter
from slowapi.util import get_remote_address

from ..database import get_db
from ..models import Session as SessionModel, CompanyInfo
from ..schemas import (
    CompanyInfoTextCreate,
    CompanyInfoWebCrawlCreate,
    CompanyInfoResponse,
    CompanyProfile,
    CompanyProfileResponse,
)
from ..services.file_processor import FileProcessor
from ..services.web_crawler import WebCrawler
from ..services.company_profile_service import (
    extract_company_profile,
    get_company_profile,
    get_profile_as_context,
)
from ..config import settings


class ProfileExtractionRequest(BaseModel):
    """Request model for profile extraction."""
    api_key: Optional[str] = None
    model: Optional[str] = None
    api_base: Optional[str] = None

router = APIRouter()
limiter = Limiter(key_func=get_remote_address)


@router.post("/{session_uuid}/company-info/text", response_model=CompanyInfoResponse)
def submit_company_text(
    session_uuid: str,
    data: CompanyInfoTextCreate,
    db: Session = Depends(get_db)
):
    """Submit free text company information."""
    # Verify session exists
    db_session = db.query(SessionModel).filter(
        SessionModel.session_uuid == session_uuid
    ).first()

    if not db_session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session with UUID {session_uuid} not found"
        )

    # Create company info entry
    company_info = CompanyInfo(
        session_id=db_session.id,
        info_type="text",
        content=data.content
    )

    db.add(company_info)
    db.commit()
    db.refresh(company_info)

    return company_info


@router.post("/{session_uuid}/company-info/upload", response_model=CompanyInfoResponse)
async def upload_company_file(
    session_uuid: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """Upload and process a company document (PDF, DOCX, TXT)."""
    # Verify session exists
    db_session = db.query(SessionModel).filter(
        SessionModel.session_uuid == session_uuid
    ).first()

    if not db_session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session with UUID {session_uuid} not found"
        )

    # Read file
    content = await file.read()
    file_size = len(content)

    # Validate file
    is_valid, error_msg = FileProcessor.validate_file(
        file.filename,
        file_size,
        settings.max_file_size
    )

    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_msg
        )

    # Save file with UUID filename
    sanitized_filename = FileProcessor.sanitize_filename(file.filename)
    file_ext = os.path.splitext(sanitized_filename)[1]
    unique_filename = f"{uuid.uuid4()}{file_ext}"
    file_path = os.path.join(settings.upload_dir, unique_filename)

    os.makedirs(settings.upload_dir, exist_ok=True)

    with open(file_path, 'wb') as f:
        f.write(content)

    # Extract text
    try:
        extracted_text = FileProcessor.process_file(file_path)
    except Exception as e:
        # Clean up file if extraction fails
        if os.path.exists(file_path):
            os.remove(file_path)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing file: {str(e)}"
        )

    # Create company info entry
    company_info = CompanyInfo(
        session_id=db_session.id,
        info_type="file",
        content=extracted_text,
        file_path=file_path,
        file_name=sanitized_filename
    )

    db.add(company_info)
    db.commit()
    db.refresh(company_info)

    return company_info


@router.post("/{session_uuid}/company-info/crawl", response_model=CompanyInfoResponse)
@limiter.limit("10/minute")
def crawl_company_website(
    request: Request,
    session_uuid: str,
    data: CompanyInfoWebCrawlCreate,
    db: Session = Depends(get_db)
):
    """Crawl a website and extract company information."""
    # Verify session exists
    db_session = db.query(SessionModel).filter(
        SessionModel.session_uuid == session_uuid
    ).first()

    if not db_session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session with UUID {session_uuid} not found"
        )

    # Crawl website
    try:
        crawled_data = WebCrawler.crawl_website(data.url)
        formatted_content = WebCrawler.format_extracted_info(crawled_data)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error crawling website: {str(e)}"
        )

    # Create company info entry
    company_info = CompanyInfo(
        session_id=db_session.id,
        info_type="web_crawl",
        content=formatted_content,
        source_url=data.url
    )

    db.add(company_info)
    db.commit()
    db.refresh(company_info)

    return company_info


@router.get("/{session_uuid}/company-info", response_model=List[CompanyInfoResponse])
def get_company_info(
    session_uuid: str,
    db: Session = Depends(get_db)
):
    """Get all company information for a session."""
    # Verify session exists
    db_session = db.query(SessionModel).filter(
        SessionModel.session_uuid == session_uuid
    ).first()

    if not db_session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session with UUID {session_uuid} not found"
        )

    # Get all company info
    company_infos = db.query(CompanyInfo).filter(
        CompanyInfo.session_id == db_session.id
    ).order_by(CompanyInfo.created_at).all()

    return company_infos


@router.delete("/{session_uuid}/company-info/{info_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_company_info(
    session_uuid: str,
    info_id: int,
    db: Session = Depends(get_db)
):
    """Delete a specific company info entry."""
    # Verify session exists
    db_session = db.query(SessionModel).filter(
        SessionModel.session_uuid == session_uuid
    ).first()

    if not db_session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session with UUID {session_uuid} not found"
        )

    # Get company info
    company_info = db.query(CompanyInfo).filter(
        CompanyInfo.id == info_id,
        CompanyInfo.session_id == db_session.id
    ).first()

    if not company_info:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Company info with ID {info_id} not found"
        )

    # Delete file if exists
    if company_info.file_path and os.path.exists(company_info.file_path):
        os.remove(company_info.file_path)

    # Delete from database
    db.delete(company_info)
    db.commit()

    return None


@router.post("/{session_uuid}/company-profile/extract", response_model=CompanyProfileResponse)
@limiter.limit("10/minute")
def extract_profile(
    request: Request,
    session_uuid: str,
    body: ProfileExtractionRequest,
    db: Session = Depends(get_db)
):
    """
    Extract a structured company profile from raw company information.

    This uses an LLM to analyze all company info entries and create a
    condensed, structured profile. The profile is stored in the session
    and used by subsequent steps to reduce token usage.

    The LLM is instructed to ONLY extract explicitly stated information
    and return null for any fields not mentioned in the source material.
    """
    # Verify session exists
    db_session = db.query(SessionModel).filter(
        SessionModel.session_uuid == session_uuid
    ).first()

    if not db_session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session with UUID {session_uuid} not found"
        )

    # Get model settings from session or body
    model = body.model or db_session.llm_model or "mistral/mistral-small-latest"
    api_base = body.api_base or db_session.llm_api_base
    language = db_session.prompt_language or "en"

    try:
        result = extract_company_profile(
            db=db,
            session_uuid=session_uuid,
            model=model,
            api_key=body.api_key,
            api_base=api_base,
            language=language
        )
        return result
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error extracting profile: {str(e)}"
        )


@router.get("/{session_uuid}/company-profile", response_model=Optional[CompanyProfile])
def get_profile(
    session_uuid: str,
    db: Session = Depends(get_db)
):
    """
    Get the extracted company profile for a session.

    Returns null if no profile has been extracted yet.
    """
    # Verify session exists
    db_session = db.query(SessionModel).filter(
        SessionModel.session_uuid == session_uuid
    ).first()

    if not db_session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session with UUID {session_uuid} not found"
        )

    return get_company_profile(db, session_uuid)


@router.get("/{session_uuid}/company-profile/context")
def get_profile_context(
    session_uuid: str,
    db: Session = Depends(get_db)
):
    """
    Get the company profile formatted as context text.

    This returns a token-efficient text representation suitable for
    inclusion in LLM prompts.
    """
    # Verify session exists
    db_session = db.query(SessionModel).filter(
        SessionModel.session_uuid == session_uuid
    ).first()

    if not db_session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session with UUID {session_uuid} not found"
        )

    language = db_session.prompt_language or "en"
    context = get_profile_as_context(db, session_uuid, language)

    return {"context": context}


@router.delete("/{session_uuid}/company-profile", status_code=status.HTTP_204_NO_CONTENT)
def delete_profile(
    session_uuid: str,
    db: Session = Depends(get_db)
):
    """
    Delete the extracted company profile.

    This allows re-extraction after updating company information.
    """
    # Verify session exists
    db_session = db.query(SessionModel).filter(
        SessionModel.session_uuid == session_uuid
    ).first()

    if not db_session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session with UUID {session_uuid} not found"
        )

    db_session.company_profile = None
    db.commit()

    return None


@router.put("/{session_uuid}/company-profile", response_model=CompanyProfile)
def update_profile(
    session_uuid: str,
    profile: CompanyProfile,
    db: Session = Depends(get_db)
):
    """
    Update/save the company profile.

    This allows users to correct or augment the extracted profile.
    """
    # Verify session exists
    db_session = db.query(SessionModel).filter(
        SessionModel.session_uuid == session_uuid
    ).first()

    if not db_session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session with UUID {session_uuid} not found"
        )

    # Save the profile
    db_session.company_profile = profile.model_dump_json()
    db.commit()

    return profile
