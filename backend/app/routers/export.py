"""Export router for generating PDF reports and transition briefings."""

import logging
from fastapi import APIRouter, Depends, HTTPException, status, Header, BackgroundTasks
from fastapi.responses import Response
from sqlalchemy.orm import Session
from typing import Optional
from pydantic import BaseModel
from litellm import completion
from ..utils.llm import apply_model_params

from ..database import get_db

logger = logging.getLogger(__name__)
from ..models import Session as SessionModel, ConsultationFinding, CompanyInfo, MaturityAssessment
from ..services.pdf_generator import PDFReportGenerator
from ..services.default_prompts import get_prompt
from ..services.session_settings import get_llm_settings, get_temperature_config
from ..config import settings

router = APIRouter()


class AutoUpdateRequest(BaseModel):
    """Request body for auto-update analysis."""
    api_key: Optional[str] = None
    api_base: Optional[str] = None
    language: Optional[str] = "en"


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
        import traceback
        logger.error(f"PDF generation failed: {str(e)}")
        logger.error(traceback.format_exc())
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
                'content': ci.content if ci.content else None
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

    # Get LLM settings from session (same as other steps)
    session_model, session_api_base = get_llm_settings(db_session)
    temps = get_temperature_config(db_session)

    # Use request overrides if provided, otherwise use session settings
    api_key = x_api_key or request.api_key
    model = request.model or session_model
    api_base = request.api_base or session_api_base

    # Build the context for the prompt
    context = _build_transition_context(db, db_session)

    # Get the prompt template - use session language setting if available
    language = request.language or db_session.prompt_language or "en"
    prompt_template = get_prompt("transition_briefing_system", language)

    # Fill in the template
    filled_prompt = prompt_template.format(
        company_profile=context["company_profile"],
        executive_summary=context["executive_summary"],
        business_case_summary=context["business_case_summary"],
        cost_estimation_summary=context["cost_estimation_summary"]
    )

    try:
        completion_kwargs = {
            "model": model,
            "messages": [
                {"role": "system", "content": filled_prompt},
                {"role": "user", "content": "Please generate the Technical Transition Briefing based on the provided context."}
            ],
            "temperature": temps.get('export', 0.4),
            "max_tokens": 4096
        }

        if api_key:
            completion_kwargs["api_key"] = api_key
        if api_base:
            completion_kwargs["api_base"] = api_base
        apply_model_params(completion_kwargs)

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
        for info in company_infos:
            if info.content:
                company_profile_parts.append(f"\n**{info.info_type.upper()}:**\n{info.content}")

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

    # Get LLM settings from session (same as other steps)
    session_model, session_api_base = get_llm_settings(db_session)
    temps = get_temperature_config(db_session)

    # Use request overrides if provided, otherwise use session settings
    api_key = x_api_key or request.api_key
    model = request.model or session_model
    api_base = request.api_base or session_api_base

    # Build the context (reuse the transition context builder)
    context = _build_transition_context(db, db_session)

    # Get the prompt template - use session language setting if available
    language = request.language or db_session.prompt_language or "en"
    prompt_template = get_prompt("swot_analysis_system", language)

    # Fill in the template
    filled_prompt = prompt_template.format(
        company_profile=context["company_profile"],
        executive_summary=context["executive_summary"],
        business_case_summary=context["business_case_summary"],
        cost_estimation_summary=context["cost_estimation_summary"]
    )

    try:
        completion_kwargs = {
            "model": model,
            "messages": [
                {"role": "system", "content": filled_prompt},
                {"role": "user", "content": "Please generate the SWOT analysis based on the provided context."}
            ],
            "temperature": temps.get('export', 0.4),
            "max_tokens": 4096
        }

        if api_key:
            completion_kwargs["api_key"] = api_key
        if api_base:
            completion_kwargs["api_base"] = api_base
        apply_model_params(completion_kwargs)

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


def _trigger_analysis_update_sync(
    session_id: int,
    model: str,
    api_key: Optional[str],
    api_base: Optional[str],
    language: str
):
    """
    Background task to regenerate SWOT and Technical Briefing.
    This runs after findings are extracted from consultation steps.
    """
    from ..database import SessionLocal

    db = SessionLocal()
    try:
        db_session = db.query(SessionModel).filter(
            SessionModel.id == session_id
        ).first()

        if not db_session:
            logger.warning(f"Session {session_id} not found for analysis update")
            return

        # Get temperature config for export step
        temps = get_temperature_config(db_session)

        # Build context
        context = _build_transition_context(db, db_session)

        # Check if we have enough findings to generate analysis
        has_crisp_dm = "No executive summary available" not in context["executive_summary"]

        if not has_crisp_dm:
            logger.info(f"Skipping analysis update - insufficient findings for session {session_id}")
            return

        # Regenerate SWOT Analysis
        try:
            swot_prompt_template = get_prompt("swot_analysis_system", language)
            swot_filled_prompt = swot_prompt_template.format(
                company_profile=context["company_profile"],
                executive_summary=context["executive_summary"],
                business_case_summary=context["business_case_summary"],
                cost_estimation_summary=context["cost_estimation_summary"]
            )

            completion_kwargs = {
                "model": model,
                "messages": [
                    {"role": "system", "content": swot_filled_prompt},
                    {"role": "user", "content": "Please generate the SWOT analysis based on the provided context."}
                ],
                "temperature": temps.get('export', 0.4),
                "max_tokens": 4096
            }

            if api_key:
                completion_kwargs["api_key"] = api_key
            if api_base:
                completion_kwargs["api_base"] = api_base
            apply_model_params(completion_kwargs)

            response = completion(**completion_kwargs)
            swot_content = response.choices[0].message.content

            _save_finding(db, db_session.id, "swot_analysis", swot_content)
            logger.info(f"Auto-updated SWOT analysis for session {session_id}")
        except Exception as e:
            logger.error(f"Failed to auto-update SWOT analysis: {str(e)}")

        # Regenerate Technical Briefing
        try:
            briefing_prompt_template = get_prompt("transition_briefing_system", language)
            briefing_filled_prompt = briefing_prompt_template.format(
                company_profile=context["company_profile"],
                executive_summary=context["executive_summary"],
                business_case_summary=context["business_case_summary"],
                cost_estimation_summary=context["cost_estimation_summary"]
            )

            completion_kwargs = {
                "model": model,
                "messages": [
                    {"role": "system", "content": briefing_filled_prompt},
                    {"role": "user", "content": "Please generate the Technical Transition Briefing based on the provided context."}
                ],
                "temperature": temps.get('export', 0.4),
                "max_tokens": 4096
            }

            if api_key:
                completion_kwargs["api_key"] = api_key
            if api_base:
                completion_kwargs["api_base"] = api_base
            apply_model_params(completion_kwargs)

            response = completion(**completion_kwargs)
            briefing_content = response.choices[0].message.content

            _save_finding(db, db_session.id, "technical_briefing", briefing_content)
            logger.info(f"Auto-updated Technical Briefing for session {session_id}")
        except Exception as e:
            logger.error(f"Failed to auto-update Technical Briefing: {str(e)}")

        db.commit()

    except Exception as e:
        logger.error(f"Error in analysis update task: {str(e)}")
    finally:
        db.close()


@router.post("/{session_uuid}/analysis/auto-update")
def auto_update_analysis(
    session_uuid: str,
    request: AutoUpdateRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    x_api_key: Optional[str] = Header(None)
):
    """
    Trigger regeneration of SWOT Analysis and Technical Briefing.
    Called automatically after findings extraction in consultation steps.
    Runs in background to not block the user.
    """
    db_session = db.query(SessionModel).filter(
        SessionModel.session_uuid == session_uuid
    ).first()

    if not db_session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session {session_uuid} not found"
        )

    # Get LLM settings
    session_model, session_api_base = get_llm_settings(db_session)

    api_key = x_api_key or request.api_key
    model = session_model
    api_base = request.api_base or session_api_base
    language = request.language or db_session.prompt_language or "en"

    # Schedule background task
    background_tasks.add_task(
        _trigger_analysis_update_sync,
        db_session.id,
        model,
        api_key,
        api_base,
        language
    )

    return {
        "status": "scheduled",
        "message": "SWOT Analysis and Technical Briefing regeneration scheduled"
    }


# ============== Cross-Reference Endpoints ==============

class CrossReferenceRequest(BaseModel):
    """Request body for cross-reference extraction."""
    api_key: Optional[str] = None
    api_base: Optional[str] = None
    language: Optional[str] = "en"


@router.post("/{session_uuid}/cross-references/extract")
def extract_cross_references(
    session_uuid: str,
    request: CrossReferenceRequest,
    db: Session = Depends(get_db),
    x_api_key: Optional[str] = Header(None)
):
    """
    Extract cross-references between all findings using LLM.

    This identifies semantic links between different findings
    for wiki-style cross-referencing in the Results page.
    """
    from ..services.cross_reference_service import extract_all_cross_references

    db_session = db.query(SessionModel).filter(
        SessionModel.session_uuid == session_uuid
    ).first()

    if not db_session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session {session_uuid} not found"
        )

    # Get LLM settings
    session_model, session_api_base = get_llm_settings(db_session)

    api_key = x_api_key or request.api_key
    model = session_model
    api_base = request.api_base or session_api_base
    language = request.language or db_session.prompt_language or "en"

    try:
        total_refs = extract_all_cross_references(
            db=db,
            session_id=db_session.id,
            model=model,
            api_key=api_key,
            api_base=api_base,
            language=language
        )

        return {
            "status": "success",
            "cross_references_created": total_refs
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to extract cross-references: {str(e)}"
        )


@router.get("/{session_uuid}/cross-references")
def get_cross_references(
    session_uuid: str,
    db: Session = Depends(get_db)
):
    """
    Get all cross-references for a session.

    Returns cross-references organized by source finding type.
    """
    from ..services.cross_reference_service import get_cross_references_for_session

    db_session = db.query(SessionModel).filter(
        SessionModel.session_uuid == session_uuid
    ).first()

    if not db_session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session {session_uuid} not found"
        )

    cross_refs = get_cross_references_for_session(db, db_session.id)

    return {
        "session_uuid": session_uuid,
        "cross_references": cross_refs
    }
