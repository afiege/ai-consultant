from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
import uuid
import json
from datetime import datetime, timedelta, timezone
from slowapi import Limiter
from slowapi.util import get_remote_address

from ..config import settings
from ..database import get_db
from ..models import Session as SessionModel
from ..schemas import SessionCreate, SessionUpdate, SessionResponse
from ..utils.auth import generate_session_token, validate_session_token, get_session_token

router = APIRouter()

# Create a limiter instance for this router
limiter = Limiter(key_func=get_remote_address)


@router.post("/", response_model=SessionResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("10/minute")
def create_session(
    request: Request,
    session_data: SessionCreate,
    db: Session = Depends(get_db)
):
    """Create a new consultation session.

    Rate limited to 10 sessions per minute per IP to prevent abuse.
    """
    # Generate unique session UUID
    session_uuid = str(uuid.uuid4())

    # Generate access token
    raw_token, token_hash = generate_session_token()

    # Create new session
    db_session = SessionModel(
        session_uuid=session_uuid,
        access_token_hash=token_hash,
        company_name=session_data.company_name,
        user_role=session_data.user_role or "consultant",
        current_step=1,
        status="active"
    )

    db.add(db_session)
    db.commit()
    db.refresh(db_session)

    # Return json with the access_token included (only time it is exposed)
    response_data = SessionResponse.model_validate(db_session).model_dump(mode="json")
    response_data["access_token"] = raw_token
    return JSONResponse(content=response_data, status_code=status.HTTP_201_CREATED)


@router.get("/{session_uuid}", response_model=SessionResponse)
def get_session(
    session_uuid: str,
    db: Session = Depends(get_db),
    token: Optional[str] = Depends(get_session_token),
):
    """Get session details by UUID."""
    db_session = validate_session_token(session_uuid, db, token)
    return db_session


@router.put("/{session_uuid}", response_model=SessionResponse)
def update_session(
    session_uuid: str,
    session_data: SessionUpdate,
    db: Session = Depends(get_db),
    token: Optional[str] = Depends(get_session_token),
):
    """Update session details."""
    db_session = validate_session_token(session_uuid, db, token)

    # Update fields if provided
    if session_data.company_name is not None:
        db_session.company_name = session_data.company_name

    if session_data.current_step is not None:
        db_session.current_step = session_data.current_step

    if session_data.status is not None:
        db_session.status = session_data.status

    if session_data.six_three_five_skipped is not None:
        db_session.six_three_five_skipped = session_data.six_three_five_skipped

    if session_data.user_role is not None:
        db_session.user_role = session_data.user_role

    db.commit()
    db.refresh(db_session)

    return db_session


@router.delete("/{session_uuid}", status_code=status.HTTP_204_NO_CONTENT)
def delete_session(
    session_uuid: str,
    db: Session = Depends(get_db),
    token: Optional[str] = Depends(get_session_token),
):
    """Delete a session and all related data."""
    db_session = validate_session_token(session_uuid, db, token)

    db.delete(db_session)
    db.commit()

    return None


# --- Reflection endpoints (P6 / DP8) ---

@router.get("/{session_uuid}/reflections")
def get_reflections(
    session_uuid: str,
    db: Session = Depends(get_db),
    token: Optional[str] = Depends(get_session_token),
):
    """Get all reflection responses for a session."""
    db_session = validate_session_token(session_uuid, db, token)
    try:
        return json.loads(db_session.reflections) if db_session.reflections else {}
    except (json.JSONDecodeError, TypeError):
        return {}


@router.put("/{session_uuid}/reflections/{step_key}")
def save_reflection(
    session_uuid: str,
    step_key: str,
    body: Dict[str, Any],
    db: Session = Depends(get_db),
    token: Optional[str] = Depends(get_session_token),
):
    """Save or update reflection for a specific step (e.g. 'step3', 'step4')."""
    db_session = validate_session_token(session_uuid, db, token)
    try:
        reflections = json.loads(db_session.reflections) if db_session.reflections else {}
    except (json.JSONDecodeError, TypeError):
        reflections = {}
    reflections[step_key] = body
    db_session.reflections = json.dumps(reflections)
    db.commit()
    return {"status": "saved", "step": step_key}


@router.get("/", response_model=List[SessionResponse])
def list_sessions(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """List all sessions (paginated)."""
    sessions = db.query(SessionModel).offset(skip).limit(limit).all()
    return sessions


@router.delete("/cleanup/expired")
@limiter.limit("2/minute")
def cleanup_expired_sessions(request: Request, db: Session = Depends(get_db)):
    """Manually trigger cleanup of expired sessions.

    Uses SESSION_EXPIRY_DAYS from server config.
    Returns count of deleted sessions.
    """
    expiry_days = settings.session_expiry_days
    if expiry_days <= 0:
        return {"deleted": 0, "message": "Session expiry is disabled (SESSION_EXPIRY_DAYS=0)"}
    cutoff = datetime.now(timezone.utc) - timedelta(days=expiry_days)
    stale = db.query(SessionModel).filter(SessionModel.updated_at < cutoff).all()
    count = len(stale)
    for s in stale:
        db.delete(s)
    db.commit()
    return {"deleted": count, "cutoff": cutoff.isoformat()}
