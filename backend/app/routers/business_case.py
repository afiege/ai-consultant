"""Business Case router for Step 5 - AI-guided business case calculation using LiteLLM."""

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from typing import Dict, Optional
import json

from ..database import get_db
from ..models import Session as SessionModel, ConsultationMessage, ConsultationFinding
from ..schemas.consultation import ConsultationMessageCreate
from ..services.business_case_service import BusinessCaseService
from ..config import settings

router = APIRouter()


def get_llm_settings(db_session: SessionModel) -> tuple[str, Optional[str], Optional[str]]:
    """
    Get LLM settings from session, falling back to global settings.

    Returns:
        Tuple of (model, api_key, api_base)
    """
    from cryptography.fernet import Fernet

    # Get model (session override or global default)
    model = db_session.llm_model or settings.llm_model

    # Get API key (session-level LLM key, or legacy mistral key, or None for env var)
    api_key = None
    if db_session.llm_api_key_encrypted:
        cipher = Fernet(settings.get_encryption_key.encode())
        api_key = cipher.decrypt(db_session.llm_api_key_encrypted.encode()).decode()
    elif db_session.mistral_api_key_encrypted:
        cipher = Fernet(settings.get_encryption_key.encode())
        api_key = cipher.decrypt(db_session.mistral_api_key_encrypted.encode()).decode()

    # Get API base (session override or global default)
    api_base = db_session.llm_api_base or settings.llm_api_base or None

    return model, api_key, api_base


def _get_expert_settings(db_session: SessionModel) -> tuple[Optional[Dict[str, str]], str]:
    """
    Get expert settings from a session.

    Returns:
        Tuple of (custom_prompts dict or None, language code)
    """
    custom_prompts = None
    if db_session.custom_prompts:
        try:
            custom_prompts = json.loads(db_session.custom_prompts)
        except json.JSONDecodeError:
            pass

    language = db_session.prompt_language or "en"
    return custom_prompts, language


@router.post("/{session_uuid}/business-case/start")
def start_business_case(
    session_uuid: str,
    db: Session = Depends(get_db)
):
    """
    Start the AI business case session.
    Creates initial context and first AI message.
    """
    db_session = db.query(SessionModel).filter(
        SessionModel.session_uuid == session_uuid
    ).first()

    if not db_session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session {session_uuid} not found"
        )

    try:
        custom_prompts, language = _get_expert_settings(db_session)
        model, api_key, api_base = get_llm_settings(db_session)
        service = BusinessCaseService(
            db,
            model=model,
            custom_prompts=custom_prompts,
            language=language,
            api_key=api_key,
            api_base=api_base
        )
        result = service.start_business_case(session_uuid)
        return result
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to start business case: {str(e)}"
        )


@router.post("/{session_uuid}/business-case/start/stream")
def start_business_case_stream(
    session_uuid: str,
    db: Session = Depends(get_db)
):
    """
    Start the AI business case session with streaming response.
    Returns Server-Sent Events (SSE) stream.
    """
    db_session = db.query(SessionModel).filter(
        SessionModel.session_uuid == session_uuid
    ).first()

    if not db_session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session {session_uuid} not found"
        )

    custom_prompts, language = _get_expert_settings(db_session)
    model, api_key, api_base = get_llm_settings(db_session)
    service = BusinessCaseService(
        db,
        model=model,
        custom_prompts=custom_prompts,
        language=language,
        api_key=api_key,
        api_base=api_base
    )

    return StreamingResponse(
        service.start_business_case_stream(session_uuid),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


@router.post("/{session_uuid}/business-case/message/save")
def save_message(
    session_uuid: str,
    message: ConsultationMessageCreate,
    db: Session = Depends(get_db)
):
    """
    Save a user message without generating AI response.
    """
    db_session = db.query(SessionModel).filter(
        SessionModel.session_uuid == session_uuid
    ).first()

    if not db_session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session {session_uuid} not found"
        )

    try:
        service = BusinessCaseService(db)
        result = service.save_user_message(session_uuid, message.content)
        return result
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save message: {str(e)}"
        )


@router.post("/{session_uuid}/business-case/message")
def send_message(
    session_uuid: str,
    message: ConsultationMessageCreate,
    db: Session = Depends(get_db)
):
    """
    Send a user message and receive AI response.
    """
    db_session = db.query(SessionModel).filter(
        SessionModel.session_uuid == session_uuid
    ).first()

    if not db_session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session {session_uuid} not found"
        )

    try:
        custom_prompts, language = _get_expert_settings(db_session)
        model, api_key, api_base = get_llm_settings(db_session)
        service = BusinessCaseService(
            db,
            model=model,
            custom_prompts=custom_prompts,
            language=language,
            api_key=api_key,
            api_base=api_base
        )
        result = service.send_message(session_uuid, message.content)
        return result
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process message: {str(e)}"
        )


@router.post("/{session_uuid}/business-case/message/stream")
def send_message_stream(
    session_uuid: str,
    message: ConsultationMessageCreate,
    db: Session = Depends(get_db)
):
    """
    Send a user message and stream AI response.
    Returns Server-Sent Events (SSE) stream.
    """
    db_session = db.query(SessionModel).filter(
        SessionModel.session_uuid == session_uuid
    ).first()

    if not db_session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session {session_uuid} not found"
        )

    custom_prompts, language = _get_expert_settings(db_session)
    model, api_key, api_base = get_llm_settings(db_session)
    service = BusinessCaseService(
        db,
        model=model,
        custom_prompts=custom_prompts,
        language=language,
        api_key=api_key,
        api_base=api_base
    )

    return StreamingResponse(
        service.send_message_stream(session_uuid, message.content),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


@router.post("/{session_uuid}/business-case/request-response/stream")
def request_ai_response_stream(
    session_uuid: str,
    db: Session = Depends(get_db)
):
    """
    Request AI response based on current conversation (no new user message).
    Returns Server-Sent Events (SSE) stream.
    """
    db_session = db.query(SessionModel).filter(
        SessionModel.session_uuid == session_uuid
    ).first()

    if not db_session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session {session_uuid} not found"
        )

    custom_prompts, language = _get_expert_settings(db_session)
    model, api_key, api_base = get_llm_settings(db_session)
    service = BusinessCaseService(
        db,
        model=model,
        custom_prompts=custom_prompts,
        language=language,
        api_key=api_key,
        api_base=api_base
    )

    return StreamingResponse(
        service.request_ai_response_stream(session_uuid),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


@router.get("/{session_uuid}/business-case/messages")
def get_messages(
    session_uuid: str,
    db: Session = Depends(get_db)
):
    """
    Get all business case messages.
    """
    db_session = db.query(SessionModel).filter(
        SessionModel.session_uuid == session_uuid
    ).first()

    if not db_session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session {session_uuid} not found"
        )

    # Get messages with message_type='business_case'
    messages = db.query(ConsultationMessage).filter(
        ConsultationMessage.session_id == db_session.id,
        ConsultationMessage.message_type == "business_case",
        ConsultationMessage.role != "system"
    ).order_by(ConsultationMessage.created_at).all()

    return [
        {
            "id": m.id,
            "role": m.role,
            "content": m.content,
            "created_at": m.created_at.isoformat()
        }
        for m in messages
        # Filter out the initial trigger message
        if m.content != "Please start the business case analysis."
    ]


@router.get("/{session_uuid}/business-case/findings")
def get_findings(
    session_uuid: str,
    db: Session = Depends(get_db)
):
    """
    Get extracted business case findings.
    """
    db_session = db.query(SessionModel).filter(
        SessionModel.session_uuid == session_uuid
    ).first()

    if not db_session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session {session_uuid} not found"
        )

    findings = db.query(ConsultationFinding).filter(
        ConsultationFinding.session_id == db_session.id,
        ConsultationFinding.factor_type.in_([
            "business_case_classification",
            "business_case_calculation",
            "business_case_validation",
            "business_case_pitch"
        ])
    ).all()

    result = {
        "classification": None,
        "calculation": None,
        "validation_questions": None,
        "management_pitch": None
    }

    type_mapping = {
        "business_case_classification": "classification",
        "business_case_calculation": "calculation",
        "business_case_validation": "validation_questions",
        "business_case_pitch": "management_pitch"
    }

    for f in findings:
        key = type_mapping.get(f.factor_type)
        if key:
            result[key] = f.finding_text

    return result


@router.post("/{session_uuid}/business-case/extract")
def extract_findings(
    session_uuid: str,
    db: Session = Depends(get_db)
):
    """
    Extract business case findings from the conversation.
    """
    db_session = db.query(SessionModel).filter(
        SessionModel.session_uuid == session_uuid
    ).first()

    if not db_session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session {session_uuid} not found"
        )

    try:
        custom_prompts, language = _get_expert_settings(db_session)
        model, api_key, api_base = get_llm_settings(db_session)
        service = BusinessCaseService(
            db,
            model=model,
            custom_prompts=custom_prompts,
            language=language,
            api_key=api_key,
            api_base=api_base
        )
        result = service.extract_findings_now(session_uuid)
        return result
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to extract findings: {str(e)}"
        )
