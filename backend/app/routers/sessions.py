from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
import uuid

from ..database import get_db
from ..models import Session as SessionModel
from ..schemas import SessionCreate, SessionUpdate, SessionResponse

router = APIRouter()


@router.post("/", response_model=SessionResponse, status_code=status.HTTP_201_CREATED)
def create_session(
    session_data: SessionCreate,
    db: Session = Depends(get_db)
):
    """Create a new consultation session."""
    # Generate unique session UUID
    session_uuid = str(uuid.uuid4())

    # Encrypt API key if provided
    encrypted_key = None
    if session_data.mistral_api_key:
        from cryptography.fernet import Fernet
        from ..config import settings

        cipher = Fernet(settings.get_encryption_key.encode())
        encrypted_key = cipher.encrypt(session_data.mistral_api_key.encode()).decode()

    # Create new session
    db_session = SessionModel(
        session_uuid=session_uuid,
        company_name=session_data.company_name,
        current_step=1,
        status="active",
        mistral_api_key_encrypted=encrypted_key
    )

    db.add(db_session)
    db.commit()
    db.refresh(db_session)

    return db_session


@router.get("/{session_uuid}", response_model=SessionResponse)
def get_session(
    session_uuid: str,
    db: Session = Depends(get_db)
):
    """Get session details by UUID."""
    db_session = db.query(SessionModel).filter(
        SessionModel.session_uuid == session_uuid
    ).first()

    if not db_session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session with UUID {session_uuid} not found"
        )

    return db_session


@router.put("/{session_uuid}", response_model=SessionResponse)
def update_session(
    session_uuid: str,
    session_data: SessionUpdate,
    db: Session = Depends(get_db)
):
    """Update session details."""
    db_session = db.query(SessionModel).filter(
        SessionModel.session_uuid == session_uuid
    ).first()

    if not db_session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session with UUID {session_uuid} not found"
        )

    # Update fields if provided
    if session_data.company_name is not None:
        db_session.company_name = session_data.company_name

    if session_data.current_step is not None:
        db_session.current_step = session_data.current_step

    if session_data.status is not None:
        db_session.status = session_data.status

    if session_data.six_three_five_skipped is not None:
        db_session.six_three_five_skipped = session_data.six_three_five_skipped

    if session_data.mistral_api_key is not None:
        # TODO: Encrypt API key before storing
        from cryptography.fernet import Fernet
        from ..config import settings

        cipher = Fernet(settings.get_encryption_key.encode())
        encrypted_key = cipher.encrypt(session_data.mistral_api_key.encode())
        db_session.mistral_api_key_encrypted = encrypted_key.decode()

    db.commit()
    db.refresh(db_session)

    return db_session


@router.delete("/{session_uuid}", status_code=status.HTTP_204_NO_CONTENT)
def delete_session(
    session_uuid: str,
    db: Session = Depends(get_db)
):
    """Delete a session and all related data."""
    db_session = db.query(SessionModel).filter(
        SessionModel.session_uuid == session_uuid
    ).first()

    if not db_session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session with UUID {session_uuid} not found"
        )

    db.delete(db_session)
    db.commit()

    return None


@router.get("/", response_model=List[SessionResponse])
def list_sessions(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """List all sessions (paginated)."""
    sessions = db.query(SessionModel).offset(skip).limit(limit).all()
    return sessions
