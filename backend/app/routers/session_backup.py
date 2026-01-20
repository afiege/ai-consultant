"""Session backup/restore router for saving and loading sessions as JSON."""

from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from typing import Dict, Any
import uuid
import json
from datetime import datetime

from ..database import get_db
from ..models import (
    Session as SessionModel,
    CompanyInfo,
    Participant,
    IdeaSheet,
    Idea,
    Prioritization,
    ConsultationMessage,
    ConsultationFinding
)

router = APIRouter()


@router.get("/{session_uuid}/backup")
def export_session_backup(
    session_uuid: str,
    db: Session = Depends(get_db)
):
    """
    Export complete session data as JSON for backup/restore.

    This includes all data needed to fully restore the session later.
    """
    db_session = db.query(SessionModel).filter(
        SessionModel.session_uuid == session_uuid
    ).first()

    if not db_session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session {session_uuid} not found"
        )

    # Export session metadata (excluding encrypted keys for security)
    session_data = {
        'session_uuid': db_session.session_uuid,
        'company_name': db_session.company_name,
        'current_step': db_session.current_step,
        'status': db_session.status,
        'six_three_five_skipped': db_session.six_three_five_skipped,
        'expert_mode': db_session.expert_mode,
        'prompt_language': db_session.prompt_language,
        'custom_prompts': db_session.custom_prompts,
        'llm_model': db_session.llm_model,
        'llm_api_base': db_session.llm_api_base,
        'created_at': db_session.created_at.isoformat() if db_session.created_at else None,
    }

    # Export company info
    company_infos = db.query(CompanyInfo).filter(
        CompanyInfo.session_id == db_session.id
    ).all()

    company_info_data = [
        {
            'info_type': ci.info_type,
            'content': ci.content,
            'source_url': ci.source_url,
            'file_name': ci.file_name,
            'created_at': ci.created_at.isoformat() if ci.created_at else None,
        }
        for ci in company_infos
    ]

    # Export participants
    participants = db.query(Participant).filter(
        Participant.session_id == db_session.id
    ).all()

    # Create mapping from participant ID to UUID for reference
    participant_id_map = {p.id: p.participant_uuid for p in participants}

    participants_data = [
        {
            'participant_uuid': p.participant_uuid,
            'name': p.name,
            'connection_status': p.connection_status,
            'joined_at': p.joined_at.isoformat() if p.joined_at else None,
        }
        for p in participants
    ]

    # Export idea sheets and ideas
    sheets = db.query(IdeaSheet).filter(
        IdeaSheet.session_id == db_session.id
    ).all()

    sheets_data = []
    for sheet in sheets:
        ideas = db.query(Idea).filter(Idea.sheet_id == sheet.id).all()

        ideas_data = [
            {
                'participant_uuid': participant_id_map.get(idea.participant_id),
                'round_number': idea.round_number,
                'idea_number': idea.idea_number,
                'content': idea.content,
                'created_at': idea.created_at.isoformat() if idea.created_at else None,
            }
            for idea in ideas
        ]

        sheets_data.append({
            'sheet_number': sheet.sheet_number,
            'current_round': sheet.current_round,
            'current_participant_uuid': participant_id_map.get(sheet.current_participant_id),
            'ideas': ideas_data,
        })

    # Export prioritizations
    prioritizations = db.query(Prioritization).filter(
        Prioritization.session_id == db_session.id
    ).all()

    # Build idea reference map (idea_id -> sheet_number, round, idea_number)
    idea_ref_map = {}
    for sheet in sheets:
        ideas = db.query(Idea).filter(Idea.sheet_id == sheet.id).all()
        for idea in ideas:
            idea_ref_map[idea.id] = {
                'sheet_number': sheet.sheet_number,
                'round_number': idea.round_number,
                'idea_number': idea.idea_number,
            }

    prioritizations_data = [
        {
            'idea_ref': idea_ref_map.get(p.idea_id),
            'participant_uuid': participant_id_map.get(p.participant_id),
            'vote_type': p.vote_type,
            'score': p.score,
            'rank_position': p.rank_position,
            'created_at': p.created_at.isoformat() if p.created_at else None,
        }
        for p in prioritizations
    ]

    # Export consultation messages
    messages = db.query(ConsultationMessage).filter(
        ConsultationMessage.session_id == db_session.id
    ).order_by(ConsultationMessage.created_at).all()

    messages_data = [
        {
            'role': m.role,
            'content': m.content,
            'message_type': m.message_type,
            'created_at': m.created_at.isoformat() if m.created_at else None,
        }
        for m in messages
    ]

    # Export consultation findings
    findings = db.query(ConsultationFinding).filter(
        ConsultationFinding.session_id == db_session.id
    ).all()

    findings_data = [
        {
            'factor_type': f.factor_type,
            'finding_text': f.finding_text,
            'created_at': f.created_at.isoformat() if f.created_at else None,
        }
        for f in findings
    ]

    # Build complete backup
    backup = {
        'version': '1.0',
        'exported_at': datetime.utcnow().isoformat(),
        'session': session_data,
        'company_info': company_info_data,
        'participants': participants_data,
        'idea_sheets': sheets_data,
        'prioritizations': prioritizations_data,
        'consultation_messages': messages_data,
        'consultation_findings': findings_data,
    }

    return JSONResponse(
        content=backup,
        headers={
            'Content-Disposition': f'attachment; filename="session-backup-{session_uuid[:8]}.json"'
        }
    )


@router.post("/restore")
async def restore_session_backup(
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """
    Restore a session from a JSON backup file.

    Creates a new session with a new UUID but restores all data.
    Returns the new session UUID.
    """
    try:
        content = await file.read()
        backup = json.loads(content.decode('utf-8'))
    except json.JSONDecodeError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid JSON file: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to read file: {str(e)}"
        )

    # Validate backup structure
    required_keys = ['version', 'session', 'company_info', 'participants',
                     'idea_sheets', 'consultation_messages', 'consultation_findings']
    for key in required_keys:
        if key not in backup:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid backup file: missing '{key}'"
            )

    session_data = backup['session']

    # Create new session with new UUID
    new_session_uuid = str(uuid.uuid4())

    new_session = SessionModel(
        session_uuid=new_session_uuid,
        company_name=session_data.get('company_name'),
        current_step=session_data.get('current_step', 1),
        status=session_data.get('status', 'active'),
        six_three_five_skipped=session_data.get('six_three_five_skipped', False),
        expert_mode=session_data.get('expert_mode', False),
        prompt_language=session_data.get('prompt_language', 'en'),
        custom_prompts=session_data.get('custom_prompts'),
        llm_model=session_data.get('llm_model'),
        llm_api_base=session_data.get('llm_api_base'),
    )

    db.add(new_session)
    db.flush()  # Get the new session ID

    # Restore company info
    for ci_data in backup.get('company_info', []):
        company_info = CompanyInfo(
            session_id=new_session.id,
            info_type=ci_data['info_type'],
            content=ci_data.get('content'),
            source_url=ci_data.get('source_url'),
            file_name=ci_data.get('file_name'),
        )
        db.add(company_info)

    # Restore participants and build UUID mapping
    participant_uuid_to_id = {}
    for p_data in backup.get('participants', []):
        # Generate new UUID for restored participant
        new_participant_uuid = str(uuid.uuid4())

        participant = Participant(
            session_id=new_session.id,
            participant_uuid=new_participant_uuid,
            name=p_data['name'],
            connection_status=p_data.get('connection_status', 'disconnected'),
        )
        db.add(participant)
        db.flush()

        # Map old UUID to new ID
        if p_data.get('participant_uuid'):
            participant_uuid_to_id[p_data['participant_uuid']] = participant.id

    # Restore idea sheets and ideas
    # Build mapping for prioritization restoration
    idea_ref_to_id = {}

    for sheet_data in backup.get('idea_sheets', []):
        # Determine current participant
        current_participant_id = None
        if sheet_data.get('current_participant_uuid'):
            current_participant_id = participant_uuid_to_id.get(
                sheet_data['current_participant_uuid']
            )

        sheet = IdeaSheet(
            session_id=new_session.id,
            sheet_number=sheet_data['sheet_number'],
            current_participant_id=current_participant_id,
            current_round=sheet_data.get('current_round', 1),
        )
        db.add(sheet)
        db.flush()

        # Restore ideas for this sheet
        for idea_data in sheet_data.get('ideas', []):
            participant_id = None
            if idea_data.get('participant_uuid'):
                participant_id = participant_uuid_to_id.get(idea_data['participant_uuid'])

            if participant_id is None:
                # Skip ideas without valid participant
                continue

            idea = Idea(
                sheet_id=sheet.id,
                participant_id=participant_id,
                round_number=idea_data['round_number'],
                idea_number=idea_data['idea_number'],
                content=idea_data['content'],
            )
            db.add(idea)
            db.flush()

            # Build reference key for prioritization mapping
            ref_key = (
                sheet_data['sheet_number'],
                idea_data['round_number'],
                idea_data['idea_number']
            )
            idea_ref_to_id[ref_key] = idea.id

    # Restore prioritizations
    for p_data in backup.get('prioritizations', []):
        idea_ref = p_data.get('idea_ref')
        if not idea_ref:
            continue

        ref_key = (
            idea_ref.get('sheet_number'),
            idea_ref.get('round_number'),
            idea_ref.get('idea_number')
        )
        idea_id = idea_ref_to_id.get(ref_key)

        if not idea_id:
            continue

        participant_id = None
        if p_data.get('participant_uuid'):
            participant_id = participant_uuid_to_id.get(p_data['participant_uuid'])

        prioritization = Prioritization(
            session_id=new_session.id,
            idea_id=idea_id,
            participant_id=participant_id,
            vote_type=p_data.get('vote_type'),
            score=p_data.get('score'),
            rank_position=p_data.get('rank_position'),
        )
        db.add(prioritization)

    # Restore consultation messages
    for m_data in backup.get('consultation_messages', []):
        message = ConsultationMessage(
            session_id=new_session.id,
            role=m_data['role'],
            content=m_data['content'],
            message_type=m_data.get('message_type', 'consultation'),
        )
        db.add(message)

    # Restore consultation findings
    for f_data in backup.get('consultation_findings', []):
        finding = ConsultationFinding(
            session_id=new_session.id,
            factor_type=f_data['factor_type'],
            finding_text=f_data['finding_text'],
        )
        db.add(finding)

    db.commit()

    return {
        'success': True,
        'message': 'Session restored successfully',
        'new_session_uuid': new_session_uuid,
        'original_session_uuid': session_data.get('session_uuid'),
        'original_company_name': session_data.get('company_name'),
    }
