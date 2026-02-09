"""Session-scoped authentication utilities."""

import hashlib
import secrets
import logging
from typing import Optional

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session as DBSession

from ..database import get_db
from ..models import Session as SessionModel

logger = logging.getLogger(__name__)

TOKEN_HEADER = "X-Session-Token"


def generate_session_token() -> tuple[str, str]:
    """Generate a random session token and its SHA-256 hash.

    Returns:
        (raw_token, token_hash) — the raw token is returned to the client once,
        the hash is stored in the database.
    """
    raw_token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
    return raw_token, token_hash


def hash_token(raw_token: str) -> str:
    """Hash a raw token for comparison."""
    return hashlib.sha256(raw_token.encode()).hexdigest()


def validate_session_token(
    session_uuid: str,
    db: DBSession,
    token: Optional[str],
) -> SessionModel:
    """Look up a session by UUID and validate the access token.

    If the session has no stored hash (legacy/migrated sessions) the request
    is allowed through so that existing sessions keep working.
    """
    db_session = db.query(SessionModel).filter(
        SessionModel.session_uuid == session_uuid
    ).first()

    if not db_session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session {session_uuid} not found",
        )

    # Legacy sessions without a token hash — allow access
    if not db_session.access_token_hash:
        return db_session

    # If the session has a token hash, require a valid token
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session token required. Provide it via the X-Session-Token header.",
        )

    if hash_token(token) != db_session.access_token_hash:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid session token.",
        )

    return db_session


def get_session_token(x_session_token: Optional[str] = Header(None)) -> Optional[str]:
    """FastAPI dependency to extract the session token from the request header."""
    return x_session_token
