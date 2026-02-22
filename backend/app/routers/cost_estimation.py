"""Cost Estimation router for Step 5b - AI-guided cost estimation using LiteLLM."""

from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from typing import Dict, Optional
from slowapi import Limiter
from slowapi.util import get_remote_address

from ..database import get_db
from ..models import Session as SessionModel, ConsultationMessage, ConsultationFinding
from ..schemas.consultation import (
    LLMRequest,
    ConsultationMessageCreate,
    ConsultationMessageWithKey
)
from ..services.cost_estimation_service import CostEstimationService
from ..services.session_settings import get_llm_settings, get_temperature_config, get_custom_prompts, get_prompt_language
from ..config import settings

router = APIRouter()

# Rate limiter for LLM endpoints to prevent abuse
limiter = Limiter(key_func=get_remote_address)


def _get_expert_settings(db_session: SessionModel) -> tuple[Optional[Dict[str, str]], str]:
    """
    Get expert settings from a session.

    Returns:
        Tuple of (custom_prompts dict or None, language code)
    """
    return get_custom_prompts(db_session), get_prompt_language(db_session)


@router.post("/{session_uuid}/cost-estimation/start")
def start_cost_estimation(
    session_uuid: str,
    request: LLMRequest,
    db: Session = Depends(get_db)
):
    """
    Start the AI cost estimation session.
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
        model, api_base = get_llm_settings(db_session)
        temps = get_temperature_config(db_session)
        service = CostEstimationService(
            db,
            model=model,
            custom_prompts=custom_prompts,
            language=language,
            api_key=request.api_key,
            api_base=api_base,
            chat_temperature=temps.get('cost_estimation'),
            extraction_temperature=temps.get('extraction')
        )
        result = service.start_cost_estimation(session_uuid)
        return result
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to start cost estimation: {str(e)}"
        )


@router.post("/{session_uuid}/cost-estimation/start/stream")
@limiter.limit("30/minute")
def start_cost_estimation_stream(
    request: Request,
    session_uuid: str,
    body: LLMRequest,
    db: Session = Depends(get_db)
):
    """
    Start the AI cost estimation session with streaming response.
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
    model, api_base = get_llm_settings(db_session)
    temps = get_temperature_config(db_session)
    service = CostEstimationService(
        db,
        model=model,
        custom_prompts=custom_prompts,
        language=language,
        api_key=body.api_key,
        api_base=api_base,
        chat_temperature=temps.get('cost_estimation'),
        extraction_temperature=temps.get('extraction')
    )

    return StreamingResponse(
        service.start_cost_estimation_stream(session_uuid),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


@router.post("/{session_uuid}/cost-estimation/message/save")
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
        service = CostEstimationService(db)
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


@router.post("/{session_uuid}/cost-estimation/message")
def send_message(
    session_uuid: str,
    message: ConsultationMessageWithKey,
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
        model, api_base = get_llm_settings(db_session)
        temps = get_temperature_config(db_session)
        service = CostEstimationService(
            db,
            model=model,
            custom_prompts=custom_prompts,
            language=language,
            api_key=message.api_key,
            api_base=api_base,
            chat_temperature=temps.get('cost_estimation'),
            extraction_temperature=temps.get('extraction')
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


@router.post("/{session_uuid}/cost-estimation/message/stream")
@limiter.limit("60/minute")
def send_message_stream(
    request: Request,
    session_uuid: str,
    message: ConsultationMessageWithKey,
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
    model, api_base = get_llm_settings(db_session)
    temps = get_temperature_config(db_session)
    service = CostEstimationService(
        db,
        model=model,
        custom_prompts=custom_prompts,
        language=language,
        api_key=message.api_key,
        api_base=api_base,
        chat_temperature=temps.get('cost_estimation'),
        extraction_temperature=temps.get('extraction')
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


@router.post("/{session_uuid}/cost-estimation/request-response/stream")
@limiter.limit("30/minute")
def request_ai_response_stream(
    request: Request,
    session_uuid: str,
    body: LLMRequest,
    db: Session = Depends(get_db)
):
    """
    Request AI response based on current conversation (no new user message).
    Returns Server-Sent Events (SSE) stream.
    """
    # Ensure we see the latest committed data (important for test mode flow)
    db.expire_all()

    db_session = db.query(SessionModel).filter(
        SessionModel.session_uuid == session_uuid
    ).first()

    if not db_session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session {session_uuid} not found"
        )

    custom_prompts, language = _get_expert_settings(db_session)
    model, api_base = get_llm_settings(db_session)
    temps = get_temperature_config(db_session)
    service = CostEstimationService(
        db,
        model=model,
        custom_prompts=custom_prompts,
        language=language,
        api_key=body.api_key,
        api_base=api_base,
        chat_temperature=temps.get('cost_estimation'),
        extraction_temperature=temps.get('extraction')
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


@router.get("/{session_uuid}/cost-estimation/messages")
def get_messages(
    session_uuid: str,
    db: Session = Depends(get_db)
):
    """
    Get all cost estimation messages.
    """
    db_session = db.query(SessionModel).filter(
        SessionModel.session_uuid == session_uuid
    ).first()

    if not db_session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session {session_uuid} not found"
        )

    # Get messages with message_type='cost_estimation'
    messages = db.query(ConsultationMessage).filter(
        ConsultationMessage.session_id == db_session.id,
        ConsultationMessage.message_type == "cost_estimation",
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
        if m.content != "Please start the cost estimation analysis."
    ]


@router.get("/{session_uuid}/cost-estimation/findings")
def get_findings(
    session_uuid: str,
    db: Session = Depends(get_db)
):
    """
    Get extracted cost estimation findings.
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
            "cost_complexity",
            "cost_initial",
            "cost_recurring",
            "cost_maintenance",
            "cost_tco",
            "cost_drivers",
            "cost_optimization",
            "cost_roi"
        ])
    ).all()

    result = {
        "complexity": None,
        "initial_investment": None,
        "recurring_costs": None,
        "maintenance": None,
        "tco": None,
        "cost_drivers": None,
        "optimization": None,
        "roi_analysis": None
    }

    type_mapping = {
        "cost_complexity": "complexity",
        "cost_initial": "initial_investment",
        "cost_recurring": "recurring_costs",
        "cost_maintenance": "maintenance",
        "cost_tco": "tco",
        "cost_drivers": "cost_drivers",
        "cost_optimization": "optimization",
        "cost_roi": "roi_analysis"
    }

    for f in findings:
        key = type_mapping.get(f.factor_type)
        if key:
            result[key] = f.finding_text

    return result


@router.post("/{session_uuid}/cost-estimation/extract")
def extract_findings(
    session_uuid: str,
    request: LLMRequest,
    db: Session = Depends(get_db)
):
    """
    Extract cost estimation findings from the conversation.
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
        model, api_base = get_llm_settings(db_session)
        temps = get_temperature_config(db_session)
        service = CostEstimationService(
            db,
            model=model,
            custom_prompts=custom_prompts,
            language=language,
            api_key=request.api_key,
            api_base=api_base,
            chat_temperature=temps.get('cost_estimation'),
            extraction_temperature=temps.get('extraction')
        )
        result = service.extract_findings_now(session_uuid)
        return result
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to extract findings: {str(e)}"
        )
