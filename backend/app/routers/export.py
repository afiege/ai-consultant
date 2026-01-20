"""Export router for generating PDF reports."""

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Session as SessionModel
from ..services.pdf_generator import PDFReportGenerator

router = APIRouter()


@router.post("/{session_uuid}/export/pdf")
def generate_pdf_report(
    session_uuid: str,
    db: Session = Depends(get_db)
):
    """
    Generate a PDF report for the consultation session.

    Returns the PDF file as a downloadable response.
    """
    # Verify session exists
    db_session = db.query(SessionModel).filter(
        SessionModel.session_uuid == session_uuid
    ).first()

    if not db_session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session {session_uuid} not found"
        )

    try:
        generator = PDFReportGenerator(db)
        pdf_bytes = generator.generate_report(session_uuid)

        # Return PDF as downloadable file
        filename = f"consultation-report-{session_uuid[:8]}.pdf"

        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f"attachment; filename={filename}"
            }
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate PDF: {str(e)}"
        )


@router.get("/{session_uuid}/export/data")
def get_export_data(
    session_uuid: str,
    db: Session = Depends(get_db)
):
    """
    Get all session data in JSON format (for alternative export options).
    """
    from ..models import (
        CompanyInfo, Participant, IdeaSheet, Idea,
        Prioritization, ConsultationMessage, ConsultationFinding
    )

    db_session = db.query(SessionModel).filter(
        SessionModel.session_uuid == session_uuid
    ).first()

    if not db_session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session {session_uuid} not found"
        )

    # Gather all data
    company_infos = db.query(CompanyInfo).filter(
        CompanyInfo.session_id == db_session.id
    ).all()

    participants = db.query(Participant).filter(
        Participant.session_id == db_session.id
    ).all()

    sheets = db.query(IdeaSheet).filter(
        IdeaSheet.session_id == db_session.id
    ).all()

    all_ideas = []
    for sheet in sheets:
        ideas = db.query(Idea).filter(Idea.sheet_id == sheet.id).all()
        for idea in ideas:
            votes = db.query(Prioritization).filter(
                Prioritization.idea_id == idea.id
            ).all()
            total_points = sum(v.score or 0 for v in votes)

            participant = db.query(Participant).filter(
                Participant.id == idea.participant_id
            ).first()

            all_ideas.append({
                'id': idea.id,
                'content': idea.content,
                'participant_name': participant.name if participant else 'Unknown',
                'round_number': idea.round_number,
                'total_points': total_points
            })

    # Sort ideas by points
    all_ideas.sort(key=lambda x: x['total_points'], reverse=True)

    messages = db.query(ConsultationMessage).filter(
        ConsultationMessage.session_id == db_session.id,
        ConsultationMessage.role != 'system'
    ).order_by(ConsultationMessage.created_at).all()

    findings = db.query(ConsultationFinding).filter(
        ConsultationFinding.session_id == db_session.id
    ).all()

    return {
        'session': {
            'uuid': db_session.session_uuid,
            'company_name': db_session.company_name,
            'created_at': db_session.created_at.isoformat() if db_session.created_at else None
        },
        'company_info': [
            {
                'info_type': ci.info_type,
                'content': ci.content[:1000] if ci.content else None
            }
            for ci in company_infos
        ],
        'participants': [
            {
                'name': p.name,
                'is_ai': p.connection_status == 'ai_controlled'
            }
            for p in participants
        ],
        'ideas': all_ideas,
        'consultation': {
            'messages': [
                {
                    'role': m.role,
                    'content': m.content,
                    'created_at': m.created_at.isoformat() if m.created_at else None
                }
                for m in messages
            ],
            'findings': {
                f.factor_type: f.finding_text
                for f in findings
            }
        }
    }
