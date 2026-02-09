from sqlalchemy import create_engine, event, Engine
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.pool import NullPool, QueuePool
from .config import settings

_is_sqlite = settings.database_url.startswith("sqlite")

# Build engine kwargs based on database type
_engine_kwargs: dict = {"echo": settings.debug}

if _is_sqlite:
    # SQLite: NullPool + thread safety overrides
    _engine_kwargs.update(
        connect_args={
            "check_same_thread": False,
            "timeout": 30,
        },
        poolclass=NullPool,
    )
else:
    # PostgreSQL / other RDBMS: connection pooling
    _engine_kwargs.update(
        poolclass=QueuePool,
        pool_size=5,
        max_overflow=10,
        pool_pre_ping=True,  # verify connections before checkout
    )

engine = create_engine(settings.database_url, **_engine_kwargs)


# SQLite-specific pragmas (no-op for other databases)
if _is_sqlite:
    @event.listens_for(Engine, "connect")
    def set_sqlite_pragma(dbapi_conn, connection_record):
        """Configure SQLite pragmas for better concurrency and performance.

        WAL mode allows concurrent reads during writes.
        busy_timeout prevents immediate failure on lock contention.
        synchronous=NORMAL is safe with WAL mode and improves write performance.
        cache_size improves read performance with larger page cache.
        wal_autocheckpoint controls when WAL file is checkpointed.
        """
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA busy_timeout=30000")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.execute("PRAGMA cache_size=-64000")
        cursor.execute("PRAGMA wal_autocheckpoint=1000")
        cursor.execute("PRAGMA temp_store=MEMORY")
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
