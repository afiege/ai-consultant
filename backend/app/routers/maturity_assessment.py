"""Router for maturity assessment (acatech Industry 4.0 Maturity Index)."""

import json
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Session as SessionModel, MaturityAssessment
from ..schemas.maturity_assessment import (
    MaturityAssessmentCreate,
    MaturityAssessmentResponse,
    MATURITY_LEVELS,
    get_maturity_level_name,
)

router = APIRouter(prefix="/sessions/{session_uuid}/maturity", tags=["maturity"])


def get_session(db: Session, session_uuid: str) -> SessionModel:
    """Get session by UUID or raise 404."""
    session = db.query(SessionModel).filter(
        SessionModel.session_uuid == session_uuid
    ).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session


@router.get("", response_model=MaturityAssessmentResponse | None)
async def get_maturity_assessment(session_uuid: str, db: Session = Depends(get_db)):
    """Get the maturity assessment for a session."""
    session = get_session(db, session_uuid)

    assessment = db.query(MaturityAssessment).filter(
        MaturityAssessment.session_id == session.id
    ).first()

    if not assessment:
        return None

    # Parse JSON details back to dict
    response_data = {
        "id": assessment.id,
        "session_id": assessment.session_id,
        "created_at": assessment.created_at,
        "updated_at": assessment.updated_at,
        "resources_score": assessment.resources_score,
        "resources_details": json.loads(assessment.resources_details) if assessment.resources_details else None,
        "information_systems_score": assessment.information_systems_score,
        "information_systems_details": json.loads(assessment.information_systems_details) if assessment.information_systems_details else None,
        "culture_score": assessment.culture_score,
        "culture_details": json.loads(assessment.culture_details) if assessment.culture_details else None,
        "organizational_structure_score": assessment.organizational_structure_score,
        "organizational_structure_details": json.loads(assessment.organizational_structure_details) if assessment.organizational_structure_details else None,
        "overall_score": assessment.overall_score,
        "maturity_level": assessment.maturity_level,
    }

    return MaturityAssessmentResponse(**response_data)


@router.post("", response_model=MaturityAssessmentResponse)
async def create_or_update_maturity_assessment(
    session_uuid: str,
    assessment_data: MaturityAssessmentCreate,
    db: Session = Depends(get_db)
):
    """Create or update the maturity assessment for a session."""
    session = get_session(db, session_uuid)

    # Calculate overall score
    scores = [
        assessment_data.resources_score,
        assessment_data.information_systems_score,
        assessment_data.culture_score,
        assessment_data.organizational_structure_score,
    ]
    overall_score = sum(scores) / len(scores)
    maturity_level = get_maturity_level_name(overall_score)

    # Check if assessment already exists
    existing = db.query(MaturityAssessment).filter(
        MaturityAssessment.session_id == session.id
    ).first()

    if existing:
        # Update existing
        existing.resources_score = assessment_data.resources_score
        existing.resources_details = json.dumps(assessment_data.resources_details) if assessment_data.resources_details else None
        existing.information_systems_score = assessment_data.information_systems_score
        existing.information_systems_details = json.dumps(assessment_data.information_systems_details) if assessment_data.information_systems_details else None
        existing.culture_score = assessment_data.culture_score
        existing.culture_details = json.dumps(assessment_data.culture_details) if assessment_data.culture_details else None
        existing.organizational_structure_score = assessment_data.organizational_structure_score
        existing.organizational_structure_details = json.dumps(assessment_data.organizational_structure_details) if assessment_data.organizational_structure_details else None
        existing.overall_score = overall_score
        existing.maturity_level = maturity_level
        assessment = existing
    else:
        # Create new
        assessment = MaturityAssessment(
            session_id=session.id,
            resources_score=assessment_data.resources_score,
            resources_details=json.dumps(assessment_data.resources_details) if assessment_data.resources_details else None,
            information_systems_score=assessment_data.information_systems_score,
            information_systems_details=json.dumps(assessment_data.information_systems_details) if assessment_data.information_systems_details else None,
            culture_score=assessment_data.culture_score,
            culture_details=json.dumps(assessment_data.culture_details) if assessment_data.culture_details else None,
            organizational_structure_score=assessment_data.organizational_structure_score,
            organizational_structure_details=json.dumps(assessment_data.organizational_structure_details) if assessment_data.organizational_structure_details else None,
            overall_score=overall_score,
            maturity_level=maturity_level,
        )
        db.add(assessment)

    db.commit()
    db.refresh(assessment)

    # Return response with parsed JSON
    response_data = {
        "id": assessment.id,
        "session_id": assessment.session_id,
        "created_at": assessment.created_at,
        "updated_at": assessment.updated_at,
        "resources_score": assessment.resources_score,
        "resources_details": json.loads(assessment.resources_details) if assessment.resources_details else None,
        "information_systems_score": assessment.information_systems_score,
        "information_systems_details": json.loads(assessment.information_systems_details) if assessment.information_systems_details else None,
        "culture_score": assessment.culture_score,
        "culture_details": json.loads(assessment.culture_details) if assessment.culture_details else None,
        "organizational_structure_score": assessment.organizational_structure_score,
        "organizational_structure_details": json.loads(assessment.organizational_structure_details) if assessment.organizational_structure_details else None,
        "overall_score": assessment.overall_score,
        "maturity_level": assessment.maturity_level,
    }

    return MaturityAssessmentResponse(**response_data)


@router.get("/levels")
async def get_maturity_levels():
    """Get information about all maturity levels."""
    return [level.model_dump() for level in MATURITY_LEVELS]
