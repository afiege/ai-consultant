from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List, Dict, Optional
import uuid
import asyncio
import json
import logging

logger = logging.getLogger(__name__)

from ..database import get_db, SessionLocal
from ..models import (
    Session as SessionModel,
    Participant,
    IdeaSheet,
    Idea,
    CompanyInfo
)
from ..schemas import (
    ParticipantCreate,
    ParticipantResponse,
    IdeaBatchCreate,
    IdeaResponse,
    IdeaSheetWithIdeas
)
from ..services.six_three_five_manager import SixThreeFiveSession
from ..services.ai_participant import AIParticipant, get_company_context_summary
from ..services.session_settings import get_llm_settings, get_custom_prompts, get_prompt_language
from ..schemas import LLMRequest
from ..config import settings


def _get_expert_settings(db_session: SessionModel) -> tuple[Optional[Dict[str, str]], str]:
    """
    Get expert settings from a session.

    Returns:
        Tuple of (custom_prompts dict or None, language code)
    """
    return get_custom_prompts(db_session), get_prompt_language(db_session)


router = APIRouter()


def generate_ai_ideas_background(
    session_uuid: str,
    model: str,
    api_key: Optional[str],
    api_base: Optional[str],
    custom_prompts: Optional[Dict[str, str]],
    language: str
):
    """Background task to generate AI ideas in parallel."""
    # Create a new database session for background task
    db = SessionLocal()
    try:
        manager = SixThreeFiveSession(db, custom_prompts=custom_prompts, language=language)
        manager.model = model
        manager.api_key = api_key
        manager.api_base = api_base
        manager._generate_ai_ideas_for_round(session_uuid)
    except Exception as e:
        logger.error(f"Background AI generation error: {e}")
    finally:
        db.close()


@router.post("/{session_uuid}/six-three-five/start")
def start_six_three_five(
    session_uuid: str,
    request: LLMRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Start a 6-3-5 brainstorming session with AI participants filling empty slots."""
    # Get session
    db_session = db.query(SessionModel).filter(
        SessionModel.session_uuid == session_uuid
    ).first()

    if not db_session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session {session_uuid} not found"
        )

    # Get LLM settings (model and api_base from session, api_key from request)
    model, api_base = get_llm_settings(db_session)
    api_key = request.api_key

    # Get expert settings
    custom_prompts, language = _get_expert_settings(db_session)

    manager = SixThreeFiveSession(db, custom_prompts=custom_prompts, language=language)

    try:
        # Start session WITHOUT generating AI ideas (we'll do that in background)
        result = manager.start_session(
            session_uuid,
            model=model,
            api_key=api_key,
            api_base=api_base,
            generate_ai_ideas=False  # Don't block on AI generation
        )

        # Generate AI ideas in background if there are AI participants
        if result.get('ai_participants', 0) > 0:
            background_tasks.add_task(
                generate_ai_ideas_background,
                session_uuid,
                model,
                api_key,
                api_base,
                custom_prompts,
                language
            )
            result['ai_generation_status'] = 'in_progress'

        return result
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/{session_uuid}/six-three-five/skip")
def skip_six_three_five(
    session_uuid: str,
    db: Session = Depends(get_db)
):
    """Skip the 6-3-5 brainstorming session, maintaining any ideas created so far."""
    # Get session
    db_session = db.query(SessionModel).filter(
        SessionModel.session_uuid == session_uuid
    ).first()

    if not db_session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session {session_uuid} not found"
        )

    # Mark as skipped
    db_session.six_three_five_skipped = True

    # Count existing ideas (if any were created before skipping)
    idea_count = 0
    sheets = db.query(IdeaSheet).filter(IdeaSheet.session_id == db_session.id).all()
    for sheet in sheets:
        idea_count += db.query(Idea).filter(Idea.sheet_id == sheet.id).count()

    db.commit()

    return {
        "status": "skipped",
        "ideas_created": idea_count,
        "message": f"6-3-5 session skipped. {idea_count} ideas preserved."
    }


@router.post("/{session_uuid}/six-three-five/join", response_model=ParticipantResponse)
def join_six_three_five(
    session_uuid: str,
    participant_data: ParticipantCreate,
    db: Session = Depends(get_db)
):
    """Join as a human participant."""
    # Get session
    db_session = db.query(SessionModel).filter(
        SessionModel.session_uuid == session_uuid
    ).first()

    if not db_session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session {session_uuid} not found"
        )

    # Check if session already started
    sheets = db.query(IdeaSheet).filter(IdeaSheet.session_id == db_session.id).first()
    if sheets:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Session already started. Cannot join after session has begun."
        )

    # Check participant limit
    participant_count = db.query(Participant).filter(
        Participant.session_id == db_session.id
    ).count()

    if participant_count >= SixThreeFiveSession.MAX_PARTICIPANTS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Session is full (maximum 6 participants)"
        )

    # Create participant
    participant_uuid = str(uuid.uuid4())
    participant = Participant(
        session_id=db_session.id,
        participant_uuid=participant_uuid,
        name=participant_data.name,
        connection_status="connected"
    )

    db.add(participant)

    # Set first participant as the session owner
    if not db_session.owner_participant_uuid:
        db_session.owner_participant_uuid = participant_uuid

    db.commit()
    db.refresh(participant)

    return participant


@router.get("/{session_uuid}/six-three-five/status")
def get_six_three_five_status(
    session_uuid: str,
    db: Session = Depends(get_db)
):
    """Get current session status."""
    manager = SixThreeFiveSession(db)

    try:
        status_info = manager.get_session_status(session_uuid)

        # Add participant details
        db_session = db.query(SessionModel).filter(
            SessionModel.session_uuid == session_uuid
        ).first()

        participants = db.query(Participant).filter(
            Participant.session_id == db_session.id
        ).all()

        status_info['participants'] = [
            {
                'id': p.id,
                'uuid': p.participant_uuid,
                'name': p.name,
                'is_ai': p.connection_status == 'ai_controlled'
            }
            for p in participants
        ]

        # Include owner information
        status_info['owner_participant_uuid'] = db_session.owner_participant_uuid

        return status_info
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get("/{session_uuid}/six-three-five/my-sheet/{participant_uuid}")
def get_my_current_sheet(
    session_uuid: str,
    participant_uuid: str,
    db: Session = Depends(get_db)
):
    """Get the current sheet assigned to this participant."""
    # Get session
    db_session = db.query(SessionModel).filter(
        SessionModel.session_uuid == session_uuid
    ).first()

    if not db_session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

    # Get participant
    participant = db.query(Participant).filter(
        Participant.participant_uuid == participant_uuid
    ).first()

    if not participant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Participant not found")

    # Find sheet assigned to this participant
    sheet = db.query(IdeaSheet).filter(
        IdeaSheet.session_id == db_session.id,
        IdeaSheet.current_participant_id == participant.id
    ).first()

    if not sheet:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No sheet assigned")

    # Get all ideas on this sheet
    ideas = db.query(Idea).filter(
        Idea.sheet_id == sheet.id
    ).order_by(Idea.round_number, Idea.idea_number).all()

    # Get participant names for ideas
    idea_list = []
    for idea in ideas:
        idea_participant = db.query(Participant).filter(Participant.id == idea.participant_id).first()
        idea_list.append({
            'id': idea.id,
            'content': idea.content,
            'round_number': idea.round_number,
            'idea_number': idea.idea_number,
            'participant_name': idea_participant.name if idea_participant else 'Unknown',
            'created_at': idea.created_at
        })

    # Check if current participant has submitted for current round
    current_round_ideas = [i for i in idea_list if i['round_number'] == sheet.current_round]
    my_current_ideas = [i for i in current_round_ideas if db.query(Idea).filter(
        Idea.id == i['id'],
        Idea.participant_id == participant.id
    ).first()]

    return {
        'sheet_id': sheet.id,
        'sheet_number': sheet.sheet_number,
        'current_round': sheet.current_round,
        'all_ideas': idea_list,
        'has_submitted_current_round': len(my_current_ideas) >= 3
    }


@router.post("/{session_uuid}/six-three-five/ideas")
def submit_ideas(
    session_uuid: str,
    participant_uuid: str,
    ideas_data: IdeaBatchCreate,
    db: Session = Depends(get_db)
):
    """Submit 3 ideas for the current round."""
    manager = SixThreeFiveSession(db)

    try:
        result = manager.submit_ideas(
            session_uuid,
            participant_uuid,
            ideas_data.sheet_id,
            ideas_data.ideas
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/{session_uuid}/six-three-five/advance-round")
async def advance_round(
    session_uuid: str,
    request: LLMRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    Advance to the next round.
    This will:
    1. Rotate sheets to next participants
    2. Automatically generate AI ideas for the new round (in background)
    """
    # Get session
    db_session = db.query(SessionModel).filter(
        SessionModel.session_uuid == session_uuid
    ).first()

    if not db_session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

    # Get LLM settings (model and api_base from session, api_key from request)
    model, api_base = get_llm_settings(db_session)
    api_key = request.api_key

    # Get all sheets
    sheets = db.query(IdeaSheet).filter(
        IdeaSheet.session_id == db_session.id
    ).all()

    if not sheets:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Session not started")

    # Get expert settings
    custom_prompts, language = _get_expert_settings(db_session)

    # Rotate sheets WITHOUT generating AI ideas (we'll do that in background)
    manager = SixThreeFiveSession(db, custom_prompts=custom_prompts, language=language)
    manager.model = model
    manager.api_key = api_key
    manager.api_base = api_base
    result = manager.rotate_sheets(session_uuid, generate_ai_ideas=False)

    # Check if there are AI participants
    ai_count = db.query(Participant).filter(
        Participant.session_id == db_session.id,
        Participant.connection_status == 'ai_controlled'
    ).count()

    # Generate AI ideas in background if there are AI participants
    if ai_count > 0 and result.get('status') != 'complete':
        background_tasks.add_task(
            generate_ai_ideas_background,
            session_uuid,
            model,
            api_key,
            api_base,
            custom_prompts,
            language
        )
        result['ai_generation_status'] = 'in_progress'

    return result


@router.get("/{session_uuid}/six-three-five/ideas", response_model=List[Dict])
def get_all_ideas(
    session_uuid: str,
    db: Session = Depends(get_db)
):
    """Get all ideas from the session (for Step 3 prioritization)."""
    # Get session
    db_session = db.query(SessionModel).filter(
        SessionModel.session_uuid == session_uuid
    ).first()

    if not db_session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

    # Get all sheets
    sheets = db.query(IdeaSheet).filter(
        IdeaSheet.session_id == db_session.id
    ).all()

    all_ideas = []
    for sheet in sheets:
        ideas = db.query(Idea).filter(Idea.sheet_id == sheet.id).all()
        for idea in ideas:
            participant = db.query(Participant).filter(Participant.id == idea.participant_id).first()
            all_ideas.append({
                'id': idea.id,
                'content': idea.content,
                'round_number': idea.round_number,
                'idea_number': idea.idea_number,
                'sheet_number': sheet.sheet_number,
                'participant_name': participant.name if participant else 'Unknown',
                'is_ai': participant.connection_status == 'ai_controlled' if participant else False,
                'created_at': idea.created_at
            })

    return all_ideas


@router.post("/{session_uuid}/six-three-five/manual-ideas")
def submit_manual_ideas(
    session_uuid: str,
    ideas: List[str],
    db: Session = Depends(get_db)
):
    """
    Manually add ideas without going through 6-3-5 session.
    Used when user skips 6-3-5 but still needs ideas for consultation.
    """
    # Get session
    db_session = db.query(SessionModel).filter(
        SessionModel.session_uuid == session_uuid
    ).first()

    if not db_session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

    if not ideas or len(ideas) == 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="At least one idea is required")

    # Create a "Manual Entry" participant if it doesn't exist
    manual_participant = db.query(Participant).filter(
        Participant.session_id == db_session.id,
        Participant.name == "Manual Entry"
    ).first()

    if not manual_participant:
        manual_participant = Participant(
            session_id=db_session.id,
            participant_uuid=str(uuid.uuid4()),
            name="Manual Entry",
            connection_status="manual"
        )
        db.add(manual_participant)
        db.commit()
        db.refresh(manual_participant)

    # Create a sheet for manual ideas if it doesn't exist
    manual_sheet = db.query(IdeaSheet).filter(
        IdeaSheet.session_id == db_session.id,
        IdeaSheet.sheet_number == 0  # Use 0 for manual sheet
    ).first()

    if not manual_sheet:
        manual_sheet = IdeaSheet(
            session_id=db_session.id,
            sheet_number=0,
            current_participant_id=manual_participant.id,
            current_round=1
        )
        db.add(manual_sheet)
        db.commit()
        db.refresh(manual_sheet)

    # Add ideas
    created_ideas = []
    for i, idea_content in enumerate(ideas):
        idea = Idea(
            sheet_id=manual_sheet.id,
            participant_id=manual_participant.id,
            round_number=1,
            idea_number=i + 1,
            content=idea_content.strip()
        )
        db.add(idea)
        created_ideas.append(idea_content.strip())

    db.commit()

    return {
        "status": "success",
        "ideas_created": len(created_ideas),
        "ideas": created_ideas
    }
