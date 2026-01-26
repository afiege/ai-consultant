"""Export router for generating PDF reports and transition briefings."""

from fastapi import APIRouter, Depends, HTTPException, status, Header
from fastapi.responses import Response
from sqlalchemy.orm import Session
from typing import Optional
from pydantic import BaseModel
from litellm import completion

from ..database import get_db
from ..models import Session as SessionModel, ConsultationFinding, CompanyInfo, MaturityAssessment
from ..services.pdf_generator import PDFReportGenerator
from ..services.default_prompts import get_prompt
from ..config import get_settings

router = APIRouter()


class TransitionBriefingRequest(BaseModel):
    """Request body for transition briefing generation."""
    model: Optional[str] = None
    api_key: Optional[str] = None
    api_base: Optional[str] = None
    language: Optional[str] = "en"


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


@router.post("/{session_uuid}/transition-briefing/generate")
def generate_transition_briefing(
    session_uuid: str,
    request: TransitionBriefingRequest,
    db: Session = Depends(get_db),
    x_api_key: Optional[str] = Header(None)
):
    """
    Generate a Technical Transition Briefing for the DMME handover.

    This creates a structured document that bridges Business Understanding
    to Technical Understanding & Conceptualization phase.
    """
    # Get session
    db_session = db.query(SessionModel).filter(
        SessionModel.session_uuid == session_uuid
    ).first()

    if not db_session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session {session_uuid} not found"
        )

    # Get API key from header or request body
    api_key = x_api_key or request.api_key
    if not api_key:
        settings = get_settings()
        api_key = getattr(settings, 'openai_api_key', None)

    # Build the context for the prompt
    context = _build_transition_context(db, db_session)

    # Get the prompt template
    language = request.language or "en"
    prompt_template = get_prompt("transition_briefing_system", language)

    # Fill in the template
    filled_prompt = prompt_template.format(
        company_profile=context["company_profile"],
        executive_summary=context["executive_summary"],
        business_case_summary=context["business_case_summary"],
        cost_estimation_summary=context["cost_estimation_summary"]
    )

    # Call the LLM
    model = request.model or "mistral/mistral-small-latest"

    try:
        completion_kwargs = {
            "model": model,
            "messages": [
                {"role": "system", "content": filled_prompt},
                {"role": "user", "content": "Please generate the Technical Transition Briefing based on the provided context."}
            ],
            "temperature": 0.4,
            "max_tokens": 3000
        }

        if api_key:
            completion_kwargs["api_key"] = api_key
        if request.api_base:
            completion_kwargs["api_base"] = request.api_base

        response = completion(**completion_kwargs)
        briefing_content = response.choices[0].message.content

        # Save the briefing as a finding
        _save_finding(db, db_session.id, "technical_briefing", briefing_content)
        db.commit()

        return {
            "status": "success",
            "briefing": briefing_content
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate transition briefing: {str(e)}"
        )


@router.get("/{session_uuid}/transition-briefing")
def get_transition_briefing(
    session_uuid: str,
    db: Session = Depends(get_db)
):
    """
    Get the existing Technical Transition Briefing if one has been generated.
    """
    db_session = db.query(SessionModel).filter(
        SessionModel.session_uuid == session_uuid
    ).first()

    if not db_session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session {session_uuid} not found"
        )

    # Get the briefing from findings
    finding = db.query(ConsultationFinding).filter(
        ConsultationFinding.session_id == db_session.id,
        ConsultationFinding.factor_type == "technical_briefing"
    ).first()

    if not finding:
        return {"briefing": None, "exists": False}

    return {"briefing": finding.finding_text, "exists": True}


def _build_transition_context(db: Session, db_session: SessionModel) -> dict:
    """Build context for the transition briefing prompt."""

    # Get all findings
    findings = db.query(ConsultationFinding).filter(
        ConsultationFinding.session_id == db_session.id
    ).all()
    findings_dict = {f.factor_type: f.finding_text for f in findings}

    # Build company profile with maturity
    company_infos = db.query(CompanyInfo).filter(
        CompanyInfo.session_id == db_session.id
    ).all()

    maturity = db.query(MaturityAssessment).filter(
        MaturityAssessment.session_id == db_session.id
    ).first()

    company_profile_parts = []
    company_profile_parts.append(f"**Company:** {db_session.company_name or 'Unknown'}")

    # Add maturity info
    if maturity:
        company_profile_parts.append(f"\n**Digital Maturity Level:** {maturity.overall_score:.1f}/6 ({maturity.maturity_level})")
        company_profile_parts.append(f"- Resources: {maturity.resources_score}/6")
        company_profile_parts.append(f"- Information Systems: {maturity.information_systems_score}/6")
        company_profile_parts.append(f"- Culture: {maturity.culture_score}/6")
        company_profile_parts.append(f"- Organizational Structure: {maturity.organizational_structure_score}/6")

    # Add company info summary
    if findings_dict.get("company_profile"):
        company_profile_parts.append(f"\n**Profile Summary:**\n{findings_dict['company_profile']}")
    elif company_infos:
        for info in company_infos[:2]:
            if info.content:
                company_profile_parts.append(f"\n**{info.info_type.upper()}:**\n{info.content[:500]}...")

    company_profile = "\n".join(company_profile_parts)

    # Build executive summary (CRISP-DM findings)
    exec_summary_parts = []
    if findings_dict.get("business_objectives"):
        exec_summary_parts.append(f"**Business Objectives:**\n{findings_dict['business_objectives']}")
    if findings_dict.get("situation_assessment"):
        exec_summary_parts.append(f"\n**Situation Assessment:**\n{findings_dict['situation_assessment']}")
    if findings_dict.get("ai_goals"):
        exec_summary_parts.append(f"\n**AI/Data Mining Goals:**\n{findings_dict['ai_goals']}")
    if findings_dict.get("project_plan"):
        exec_summary_parts.append(f"\n**Project Plan:**\n{findings_dict['project_plan']}")

    executive_summary = "\n".join(exec_summary_parts) if exec_summary_parts else "No executive summary available. Complete Step 4 consultation first."

    # Build business case summary
    bc_parts = []
    if findings_dict.get("business_case_classification"):
        bc_parts.append(f"**Value Classification:**\n{findings_dict['business_case_classification']}")
    if findings_dict.get("business_case_calculation"):
        bc_parts.append(f"\n**Financial Projection:**\n{findings_dict['business_case_calculation']}")
    if findings_dict.get("business_case_pitch"):
        bc_parts.append(f"\n**Management Pitch:**\n{findings_dict['business_case_pitch']}")

    business_case_summary = "\n".join(bc_parts) if bc_parts else "No business case available. Complete Step 5a first."

    # Build cost estimation summary
    cost_parts = []
    if findings_dict.get("cost_complexity"):
        cost_parts.append(f"**Complexity Assessment:**\n{findings_dict['cost_complexity']}")
    if findings_dict.get("cost_initial"):
        cost_parts.append(f"\n**Initial Investment:**\n{findings_dict['cost_initial']}")
    if findings_dict.get("cost_tco"):
        cost_parts.append(f"\n**3-Year TCO:**\n{findings_dict['cost_tco']}")
    if findings_dict.get("cost_roi"):
        cost_parts.append(f"\n**ROI Analysis:**\n{findings_dict['cost_roi']}")

    cost_estimation_summary = "\n".join(cost_parts) if cost_parts else "No cost estimation available. Complete Step 5b first."

    return {
        "company_profile": company_profile,
        "executive_summary": executive_summary,
        "business_case_summary": business_case_summary,
        "cost_estimation_summary": cost_estimation_summary
    }


def _save_finding(db: Session, session_id: int, factor_type: str, text: str):
    """Save or update a finding."""
    if not text or text.strip() == "":
        return

    existing = db.query(ConsultationFinding).filter(
        ConsultationFinding.session_id == session_id,
        ConsultationFinding.factor_type == factor_type
    ).first()

    if existing:
        existing.finding_text = text.strip()
    else:
        db.add(ConsultationFinding(
            session_id=session_id,
            factor_type=factor_type,
            finding_text=text.strip()
        ))


@router.post("/{session_uuid}/swot-analysis/generate")
def generate_swot_analysis(
    session_uuid: str,
    request: TransitionBriefingRequest,
    db: Session = Depends(get_db),
    x_api_key: Optional[str] = Header(None)
):
    """
    Generate a SWOT analysis based on the gathered session data.

    Analyzes strengths, weaknesses, opportunities, and threats
    for the proposed AI/digitalization project.
    """
    # Get session
    db_session = db.query(SessionModel).filter(
        SessionModel.session_uuid == session_uuid
    ).first()

    if not db_session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session {session_uuid} not found"
        )

    # Get API key from header or request body
    api_key = x_api_key or request.api_key
    if not api_key:
        settings = get_settings()
        api_key = getattr(settings, 'openai_api_key', None)

    # Build the context (reuse the transition context builder)
    context = _build_transition_context(db, db_session)

    # Get the prompt template
    language = request.language or "en"
    prompt_template = get_prompt("swot_analysis_system", language)

    # Fill in the template
    filled_prompt = prompt_template.format(
        company_profile=context["company_profile"],
        executive_summary=context["executive_summary"],
        business_case_summary=context["business_case_summary"],
        cost_estimation_summary=context["cost_estimation_summary"]
    )

    # Call the LLM
    model = request.model or "mistral/mistral-small-latest"

    try:
        completion_kwargs = {
            "model": model,
            "messages": [
                {"role": "system", "content": filled_prompt},
                {"role": "user", "content": "Please generate the SWOT analysis based on the provided context."}
            ],
            "temperature": 0.4,
            "max_tokens": 2500
        }

        if api_key:
            completion_kwargs["api_key"] = api_key
        if request.api_base:
            completion_kwargs["api_base"] = request.api_base

        response = completion(**completion_kwargs)
        swot_content = response.choices[0].message.content

        # Save the SWOT as a finding
        _save_finding(db, db_session.id, "swot_analysis", swot_content)
        db.commit()

        return {
            "status": "success",
            "swot": swot_content
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate SWOT analysis: {str(e)}"
        )


@router.get("/{session_uuid}/swot-analysis")
def get_swot_analysis(
    session_uuid: str,
    db: Session = Depends(get_db)
):
    """
    Get the existing SWOT analysis if one has been generated.
    """
    db_session = db.query(SessionModel).filter(
        SessionModel.session_uuid == session_uuid
    ).first()

    if not db_session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session {session_uuid} not found"
        )

    # Get the SWOT from findings
    finding = db.query(ConsultationFinding).filter(
        ConsultationFinding.session_id == db_session.id,
        ConsultationFinding.factor_type == "swot_analysis"
    ).first()

    if not finding:
        return {"swot": None, "exists": False}

    return {"swot": finding.finding_text, "exists": True}
