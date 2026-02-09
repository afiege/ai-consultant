"""
Pytest fixtures shared across all test modules.

Uses an in-memory SQLite database for fast, isolated testing.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, Engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app

# Disable ALL rate limiters during tests
from app.main import limiter as main_limiter
from app.routers.sessions import limiter as sessions_limiter
from app.routers.consultation import limiter as consultation_limiter
from app.routers.business_case import limiter as business_case_limiter
from app.routers.cost_estimation import limiter as cost_estimation_limiter

for _lim in (main_limiter, sessions_limiter, consultation_limiter, business_case_limiter, cost_estimation_limiter):
    _lim.enabled = False


# ---------- Database fixtures ----------

@pytest.fixture(scope="function")
def db_engine():
    """Create an in-memory SQLite engine per test."""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_conn, _):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def db_session(db_engine):
    """Yield a fresh DB session; rolls back after each test."""
    TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=db_engine)
    session = TestingSession()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture(scope="function")
def client(db_session):
    """
    FastAPI TestClient with the DB dependency overridden to
    use the in-memory test database.  Rate limiter storage is
    reset so tests are not throttled.
    """
    def _override_get_db():
        try:
            yield db_session
        finally:
            pass  # session cleanup handled by the db_session fixture

    app.dependency_overrides[get_db] = _override_get_db

    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


# ---------- Helper fixtures ----------

@pytest.fixture
def create_session(client):
    """Helper: create a session and return (session_uuid, token, response_json)."""
    def _create(company_name="Test Corp", **kwargs):
        payload = {"company_name": company_name, **kwargs}
        res = client.post("/api/sessions/", json=payload)
        assert res.status_code == 201, res.text
        data = res.json()
        return data["session_uuid"], data.get("access_token"), data
    return _create


@pytest.fixture
def auth_headers():
    """Build headers dict from a raw token."""
    def _headers(token):
        if token:
            return {"X-Session-Token": token}
        return {}
    return _headers
