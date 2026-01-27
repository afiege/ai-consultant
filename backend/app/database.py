from sqlalchemy import create_engine, event, Engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool
from .config import settings

# Create database engine with SQLite-specific configuration
# Using NullPool for better concurrent request handling - each request gets a fresh connection
engine = create_engine(
    settings.database_url,
    connect_args={
        "check_same_thread": False,  # Allow multiple threads (needed for FastAPI)
        "timeout": 30  # Wait up to 30 seconds for database locks
    },
    poolclass=NullPool,  # Use NullPool for SQLite to avoid connection sharing issues
    echo=settings.debug  # Log SQL queries in debug mode
)


# Configure SQLite for better concurrency
@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_conn, connection_record):
    """Enable WAL mode and set busy timeout for better concurrency."""
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")  # Write-Ahead Logging
    cursor.execute("PRAGMA busy_timeout=30000")  # 30 second timeout
    cursor.execute("PRAGMA foreign_keys=ON")  # Enable foreign key constraints
    cursor.close()


# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class for all models
Base = declarative_base()


def get_db():
    """
    Dependency function to get database session.

    Usage in FastAPI endpoints:
        @app.get("/endpoint")
        def my_endpoint(db: Session = Depends(get_db)):
            ...
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Initialize database tables. Call this on application startup."""
    Base.metadata.create_all(bind=engine)
