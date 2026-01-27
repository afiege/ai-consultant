"""Consultation router for Step 4 - AI-guided interview using LiteLLM."""

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from typing import List, Dict, Optional
import json

from ..database import get_db
from ..models import Session as SessionModel, Participant, ConsultationMessage
from ..schemas.consultation import (
    LLMRequest,
    ConsultationMessageCreate,
    ConsultationMessageResponse,
    ConsultationStartRequest,
    ConsultationMessageWithKey,
    CollaborativeConsultationStatus
)
from ..services.consultation_service import ConsultationService
from ..config import settings

router = APIRouter()


def get_llm_settings(db_session: SessionModel) -> tuple[str, Optional[str]]:
    """
    Get LLM settings from session, falling back to global settings.
    Note: API key is NOT stored - it must be passed per-request.

    Returns:
        Tuple of (model, api_base)
    """
    # Get model (session override or global default)
    model = db_session.llm_model or settings.llm_model

    # Get API base (session override or global default)
    api_base = db_session.llm_api_base or settings.llm_api_base or None

    return model, api_base


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


@router.post("/{session_uuid}/consultation/start")
def start_consultation(
    session_uuid: str,
    request: ConsultationStartRequest,
    db: Session = Depends(get_db)
):
    """
    Start the AI consultation session.
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
        service = ConsultationService(
            db,
            model=model,
            custom_prompts=custom_prompts,
            language=language,
            api_key=request.api_key,
            api_base=api_base
        )
        result = service.start_consultation(session_uuid)
        return result
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to start consultation: {str(e)}"
        )


@router.post("/{session_uuid}/consultation/start/stream")
def start_consultation_stream(
    session_uuid: str,
    request: ConsultationStartRequest,
    db: Session = Depends(get_db)
):
    """
    Start the AI consultation session with streaming response.
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
    service = ConsultationService(
        db,
        model=model,
        custom_prompts=custom_prompts,
        language=language,
        api_key=request.api_key,
        api_base=api_base
    )

    return StreamingResponse(
        service.start_consultation_stream(session_uuid),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


@router.post("/{session_uuid}/consultation/message/save")
def save_message(
    session_uuid: str,
    message: ConsultationMessageCreate,
    db: Session = Depends(get_db)
):
    """
    Save a user message without generating AI response.
    Used when user is answering questions (no auto-reply needed).
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
        service = ConsultationService(db)
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


@router.post("/{session_uuid}/consultation/message")
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
        service = ConsultationService(
            db,
            model=model,
            custom_prompts=custom_prompts,
            language=language,
            api_key=message.api_key,
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


@router.post("/{session_uuid}/consultation/message/stream")
def send_message_stream(
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
    service = ConsultationService(
        db,
        model=model,
        custom_prompts=custom_prompts,
        language=language,
        api_key=message.api_key,
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


@router.post("/{session_uuid}/consultation/request-response/stream")
def request_ai_response_stream(
    session_uuid: str,
    request: LLMRequest,
    db: Session = Depends(get_db)
):
    """
    Request AI response based on current conversation (no new user message).
    Used when user wants AI feedback after answering questions.
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
    service = ConsultationService(
        db,
        model=model,
        custom_prompts=custom_prompts,
        language=language,
        api_key=request.api_key,
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


@router.get("/{session_uuid}/consultation/messages")
def get_messages(
    session_uuid: str,
    db: Session = Depends(get_db)
):
    """
    Get all consultation messages.
    """
    db_session = db.query(SessionModel).filter(
        SessionModel.session_uuid == session_uuid
    ).first()

    if not db_session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session {session_uuid} not found"
        )

    # Get messages without needing Mistral key
    from ..models import ConsultationMessage

    messages = db.query(ConsultationMessage).filter(
        ConsultationMessage.session_id == db_session.id,
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
    ]


@router.delete("/{session_uuid}/consultation/reset")
def reset_consultation(
    session_uuid: str,
    db: Session = Depends(get_db)
):
    """
    Reset/clear all consultation messages to start over.
    """
    db_session = db.query(SessionModel).filter(
        SessionModel.session_uuid == session_uuid
    ).first()

    if not db_session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session {session_uuid} not found"
        )

    # Delete all consultation messages for this session
    deleted_count = db.query(ConsultationMessage).filter(
        ConsultationMessage.session_id == db_session.id
    ).delete()

    db.commit()

    return {
        "status": "success",
        "messages_deleted": deleted_count,
        "message": "Consultation has been reset. You can start over."
    }


@router.get("/{session_uuid}/consultation/findings")
def get_findings(
    session_uuid: str,
    db: Session = Depends(get_db)
):
    """
    Get extracted consultation findings.
    """
    db_session = db.query(SessionModel).filter(
        SessionModel.session_uuid == session_uuid
    ).first()

    if not db_session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session {session_uuid} not found"
        )

    from ..models import ConsultationFinding

    findings = db.query(ConsultationFinding).filter(
        ConsultationFinding.session_id == db_session.id
    ).all()

    result = {
        "project": None,
        "risks": None,
        "end_user": None,
        "implementation": None
    }

    for f in findings:
        result[f.factor_type] = f.finding_text

    return result


@router.post("/{session_uuid}/consultation/summarize")
def summarize_consultation(
    session_uuid: str,
    request: LLMRequest,
    db: Session = Depends(get_db)
):
    """
    Generate a summary of the consultation with extracted findings.
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
        service = ConsultationService(
            db,
            model=model,
            custom_prompts=custom_prompts,
            language=language,
            api_key=request.api_key,
            api_base=api_base
        )
        result = service.extract_findings_now(session_uuid)
        return result
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate summary: {str(e)}"
        )


@router.post("/{session_uuid}/consultation/extract-incremental")
def extract_findings_incremental(
    session_uuid: str,
    request: LLMRequest,
    db: Session = Depends(get_db)
):
    """
    Extract findings incrementally from the current conversation.
    Lighter weight than full summarize - suitable for periodic updates.
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
        service = ConsultationService(
            db,
            model=model,
            custom_prompts=custom_prompts,
            language=language,
            api_key=request.api_key,
            api_base=api_base
        )
        result = service.extract_findings_incremental(session_uuid)
        return result
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to extract findings: {str(e)}"
        )


# ============== Collaborative Consultation Endpoints ==============

@router.get("/{session_uuid}/consultation/collaborative-status")
def get_collaborative_status(
    session_uuid: str,
    db: Session = Depends(get_db)
):
    """
    Get the collaborative consultation status including participants and message count.
    """
    db_session = db.query(SessionModel).filter(
        SessionModel.session_uuid == session_uuid
    ).first()

    if not db_session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session {session_uuid} not found"
        )

    # Get participants (reuse from 6-3-5)
    participants = db.query(Participant).filter(
        Participant.session_id == db_session.id,
        Participant.connection_status != 'ai_controlled'  # Only human participants
    ).all()

    # Get message count
    message_count = db.query(ConsultationMessage).filter(
        ConsultationMessage.session_id == db_session.id,
        ConsultationMessage.role != "system"
    ).count()

    # Check if consultation has started
    consultation_started = message_count > 0

    return {
        "collaborative_mode": db_session.collaborative_consultation or False,
        "participants": [
            {
                "uuid": p.participant_uuid,
                "name": p.name,
                "is_owner": p.participant_uuid == db_session.owner_participant_uuid
            }
            for p in participants
        ],
        "message_count": message_count,
        "consultation_started": consultation_started,
        "owner_participant_uuid": db_session.owner_participant_uuid
    }


@router.post("/{session_uuid}/consultation/collaborative-mode")
def set_collaborative_mode(
    session_uuid: str,
    enabled: bool,
    db: Session = Depends(get_db)
):
    """
    Enable or disable collaborative consultation mode.
    Only the session owner can toggle this.
    """
    db_session = db.query(SessionModel).filter(
        SessionModel.session_uuid == session_uuid
    ).first()

    if not db_session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session {session_uuid} not found"
        )

    db_session.collaborative_consultation = enabled
    db.commit()

    return {
        "collaborative_mode": enabled,
        "message": f"Collaborative mode {'enabled' if enabled else 'disabled'}"
    }


@router.post("/{session_uuid}/consultation/message/save-collaborative")
def save_collaborative_message(
    session_uuid: str,
    message: ConsultationMessageCreate,
    db: Session = Depends(get_db)
):
    """
    Save a user message in collaborative mode with participant info.
    """
    db_session = db.query(SessionModel).filter(
        SessionModel.session_uuid == session_uuid
    ).first()

    if not db_session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session {session_uuid} not found"
        )

    # Get participant if provided
    participant = None
    participant_name = None
    if message.participant_uuid:
        participant = db.query(Participant).filter(
            Participant.participant_uuid == message.participant_uuid
        ).first()
        if participant:
            participant_name = participant.name

    # Format message content with participant name for collaborative mode
    if db_session.collaborative_consultation and participant_name:
        formatted_content = f"[{participant_name}]: {message.content}"
    else:
        formatted_content = message.content

    # Save message
    new_message = ConsultationMessage(
        session_id=db_session.id,
        participant_id=participant.id if participant else None,
        role="user",
        content=formatted_content,
        message_type="consultation"
    )
    db.add(new_message)
    db.commit()
    db.refresh(new_message)

    return {
        "message_id": new_message.id,
        "content": formatted_content,
        "role": "user",
        "participant_name": participant_name
    }


@router.get("/{session_uuid}/consultation/messages-collaborative")
def get_collaborative_messages(
    session_uuid: str,
    since_id: Optional[int] = None,
    db: Session = Depends(get_db)
):
    """
    Get consultation messages with participant info.
    Optionally filter to messages after a specific ID (for polling).
    """
    db_session = db.query(SessionModel).filter(
        SessionModel.session_uuid == session_uuid
    ).first()

    if not db_session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session {session_uuid} not found"
        )

    # Build query
    query = db.query(ConsultationMessage).filter(
        ConsultationMessage.session_id == db_session.id,
        ConsultationMessage.role != "system"
    )

    # Filter by since_id if provided (for polling new messages)
    if since_id:
        query = query.filter(ConsultationMessage.id > since_id)

    messages = query.order_by(ConsultationMessage.created_at).all()

    result = []
    for m in messages:
        # Skip initial trigger message
        if m.content == "Please start the consultation.":
            continue

        # Get participant name if available
        participant_name = None
        if m.participant_id:
            participant = db.query(Participant).filter(
                Participant.id == m.participant_id
            ).first()
            if participant:
                participant_name = participant.name

        result.append({
            "id": m.id,
            "role": m.role,
            "content": m.content,
            "created_at": m.created_at.isoformat(),
            "participant_name": participant_name
        })

    return result
