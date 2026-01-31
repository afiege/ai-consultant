"""Consultation router for Step 4 - AI-guided interview using LiteLLM."""

from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from typing import List, Dict, Optional
import json
from slowapi import Limiter
from slowapi.util import get_remote_address

from ..database import get_db
from ..models import Session as SessionModel, Participant, ConsultationMessage, ConsultationFinding
from ..schemas.consultation import (
    LLMRequest,
    ConsultationMessageCreate,
    ConsultationMessageResponse,
    ConsultationStartRequest,
    ConsultationMessageWithKey,
    CollaborativeConsultationStatus
)
from ..services.consultation_service import ConsultationService
from ..services.session_settings import get_llm_settings
from ..config import settings
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

# Rate limiter for LLM endpoints to prevent abuse
limiter = Limiter(key_func=get_remote_address)


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
@limiter.limit("30/minute")
def start_consultation_stream(
    request: Request,
    session_uuid: str,
    body: ConsultationStartRequest,
    db: Session = Depends(get_db)
):
    """
    Start the AI consultation session with streaming response.
    Returns Server-Sent Events (SSE) stream.

    Rate limited to 30 requests per minute per IP.
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
        api_key=body.api_key,
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
    # Ensure we see the latest committed data from other connections
    db.expire_all()

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

    Rate limited to 60 requests per minute per IP.
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
@limiter.limit("30/minute")
def request_ai_response_stream(
    request: Request,
    session_uuid: str,
    body: LLMRequest,
    db: Session = Depends(get_db)
):
    """
    Request AI response based on current conversation (no new user message).
    Used when user wants AI feedback after answering questions.
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
    service = ConsultationService(
        db,
        model=model,
        custom_prompts=custom_prompts,
        language=language,
        api_key=body.api_key,
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

    # Filter out context messages (used internally but not for display)
    return [
        {
            "id": m.id,
            "role": m.role,
            "content": m.content,
            "created_at": m.created_at.isoformat()
        }
        for m in messages
        if not m.content.startswith("[SESSION CONTEXT]")
    ]


# Define which message types and findings belong to each step
STEP_MESSAGE_TYPES = {
    4: ["consultation", "business_case", "cost_estimation"],  # Reset from Step 4 clears all
    5: ["business_case", "cost_estimation"],  # Reset from Step 5 keeps Step 4
    6: ["cost_estimation"],  # Reset from Step 6 keeps Step 4 + 5
}

STEP_FINDING_TYPES = {
    4: None,  # None means delete all findings
    5: [
        # Step 5 findings
        "business_case_classification", "business_case_calculation",
        "business_case_validation", "business_case_pitch",
        # Step 6 findings
        "cost_complexity", "cost_initial", "cost_recurring", "cost_maintenance",
        "cost_tco", "cost_drivers", "cost_optimization", "cost_roi",
        # Export findings that depend on Step 5/6
        "swot_analysis", "technical_briefing",
    ],
    6: [
        # Step 6 findings only
        "cost_complexity", "cost_initial", "cost_recurring", "cost_maintenance",
        "cost_tco", "cost_drivers", "cost_optimization", "cost_roi",
        # Export findings that depend on Step 6
        "technical_briefing",
    ],
}


@router.delete("/{session_uuid}/consultation/reset")
def reset_consultation(
    session_uuid: str,
    from_step: int = 4,
    db: Session = Depends(get_db)
):
    """
    Reset consultation messages and findings from a specific step onwards.

    Args:
        from_step: The step to reset from (4, 5, or 6).
                   Resets this step and all subsequent steps.
                   - 4: Resets Step 4 + 5 + 6 (full reset)
                   - 5: Resets Step 5 + 6 (keeps Step 4 conversation)
                   - 6: Resets Step 6 only (keeps Step 4 + 5)
    """
    if from_step not in [4, 5, 6]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="from_step must be 4, 5, or 6"
        )

    db_session = db.query(SessionModel).filter(
        SessionModel.session_uuid == session_uuid
    ).first()

    if not db_session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session {session_uuid} not found"
        )

    # Delete messages for the specified steps
    message_types = STEP_MESSAGE_TYPES[from_step]
    deleted_messages = db.query(ConsultationMessage).filter(
        ConsultationMessage.session_id == db_session.id,
        ConsultationMessage.message_type.in_(message_types)
    ).delete(synchronize_session='fetch')

    # Delete findings for the specified steps
    finding_types = STEP_FINDING_TYPES[from_step]
    if finding_types is None:
        # Delete all findings
        deleted_findings = db.query(ConsultationFinding).filter(
            ConsultationFinding.session_id == db_session.id
        ).delete(synchronize_session='fetch')
    else:
        # Delete specific finding types
        deleted_findings = db.query(ConsultationFinding).filter(
            ConsultationFinding.session_id == db_session.id,
            ConsultationFinding.factor_type.in_(finding_types)
        ).delete(synchronize_session='fetch')

    db.commit()

    step_names = {4: "consultation", 5: "business case", 6: "cost estimation"}
    return {
        "status": "success",
        "from_step": from_step,
        "messages_deleted": deleted_messages,
        "findings_deleted": deleted_findings,
        "message": f"Reset from Step {from_step} ({step_names[from_step]}). You can start over."
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


@router.get("/{session_uuid}/all-findings")
def get_all_findings(
    session_uuid: str,
    db: Session = Depends(get_db)
):
    """
    Get all findings organized by category for the Results page.
    Aggregates findings from all consultation steps.
    """
    from ..models import CompanyInfo, MaturityAssessment

    db_session = db.query(SessionModel).filter(
        SessionModel.session_uuid == session_uuid
    ).first()

    if not db_session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session {session_uuid} not found"
        )

    # Get all findings
    findings = db.query(ConsultationFinding).filter(
        ConsultationFinding.session_id == db_session.id
    ).all()
    findings_dict = {f.factor_type: {"text": f.finding_text, "created_at": f.created_at.isoformat()} for f in findings}

    # Get company info
    company_infos = db.query(CompanyInfo).filter(
        CompanyInfo.session_id == db_session.id
    ).all()
    company_info_data = [
        {"info_type": ci.info_type, "content": ci.content}
        for ci in company_infos
    ]

    # Get structured company profile
    structured_profile = None
    if db_session.company_profile:
        try:
            structured_profile = json.loads(db_session.company_profile)
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse company_profile JSON for session {db_session.id}: {e}")

    # Get maturity assessment
    maturity = db.query(MaturityAssessment).filter(
        MaturityAssessment.session_id == db_session.id
    ).first()
    maturity_data = None
    if maturity:
        maturity_data = {
            "overall_score": maturity.overall_score,
            "maturity_level": maturity.maturity_level,
            "resources_score": maturity.resources_score,
            "information_systems_score": maturity.information_systems_score,
            "culture_score": maturity.culture_score,
            "organizational_structure_score": maturity.organizational_structure_score
        }

    # Organize findings by category
    result = {
        "session": {
            "uuid": db_session.session_uuid,
            "company_name": db_session.company_name
        },
        "company_info": {
            "profile": findings_dict.get("company_profile"),
            "structured_profile": structured_profile,
            "raw_info": company_info_data
        },
        "maturity": maturity_data,
        "crisp_dm": {
            "business_objectives": findings_dict.get("business_objectives"),
            "situation_assessment": findings_dict.get("situation_assessment"),
            "ai_goals": findings_dict.get("ai_goals"),
            "project_plan": findings_dict.get("project_plan")
        },
        "business_case": {
            "classification": findings_dict.get("business_case_classification"),
            "calculation": findings_dict.get("business_case_calculation"),
            "validation_questions": findings_dict.get("business_case_validation"),
            "management_pitch": findings_dict.get("business_case_pitch")
        },
        "costs": {
            "complexity": findings_dict.get("cost_complexity"),
            "initial_investment": findings_dict.get("cost_initial"),
            "recurring_costs": findings_dict.get("cost_recurring"),
            "maintenance": findings_dict.get("cost_maintenance"),
            "tco": findings_dict.get("cost_tco"),
            "cost_drivers": findings_dict.get("cost_drivers"),
            "optimization": findings_dict.get("cost_optimization"),
            "roi_analysis": findings_dict.get("cost_roi")
        },
        "analysis": {
            "swot_analysis": findings_dict.get("swot_analysis"),
            "technical_briefing": findings_dict.get("technical_briefing")
        }
    }

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
    # Ensure we see the latest committed data from other connections
    db.expire_all()

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
        # Skip initial trigger message and context messages
        if m.content == "Please start the consultation." or m.content.startswith("[SESSION CONTEXT]"):
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
