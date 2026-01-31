"""Database utility functions for transaction management and error handling."""

import logging
from functools import wraps
from typing import Generator, TypeVar, Callable, Any
from contextlib import contextmanager
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

logger = logging.getLogger(__name__)

T = TypeVar('T')


@contextmanager
def transaction_scope(db: Session) -> Generator[Session, None, None]:
    """
    Context manager for database transactions with automatic rollback on error.

    Usage:
        with transaction_scope(db) as session:
            session.add(some_object)
            # Commits automatically on successful exit
            # Rolls back automatically on exception

    Args:
        db: SQLAlchemy session

    Yields:
        The session for use within the context

    Raises:
        Re-raises any exception after rolling back
    """
    try:
        yield db
        db.commit()
    except SQLAlchemyError as e:
        logger.error(f"Database error, rolling back transaction: {e}")
        db.rollback()
        raise
    except Exception as e:
        logger.error(f"Error during transaction, rolling back: {e}")
        db.rollback()
        raise


def with_transaction(func: Callable[..., T]) -> Callable[..., T]:
    """
    Decorator for router functions that wraps the entire operation in a transaction.

    The function must have a parameter named 'db' that is the SQLAlchemy session.
    On success, the transaction is committed. On any exception, it's rolled back.

    Usage:
        @router.post("/endpoint")
        @with_transaction
        def create_item(item: ItemCreate, db: Session = Depends(get_db)):
            db.add(Item(**item.dict()))
            return {"status": "created"}

    Note: For FastAPI endpoints, this decorator should be placed AFTER the
    router decorator (closer to the function).
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        # Find the db session in kwargs
        db = kwargs.get('db')
        if db is None:
            # Try to find it in args by looking for Session type
            for arg in args:
                if isinstance(arg, Session):
                    db = arg
                    break

        if db is None:
            logger.warning(f"No db session found in {func.__name__}, skipping transaction wrapper")
            return func(*args, **kwargs)

        try:
            result = func(*args, **kwargs)
            db.commit()
            return result
        except SQLAlchemyError as e:
            logger.error(f"Database error in {func.__name__}, rolling back: {e}")
            db.rollback()
            raise
        except Exception as e:
            logger.error(f"Error in {func.__name__}, rolling back transaction: {e}")
            db.rollback()
            raise

    return wrapper


async def with_transaction_async(func: Callable[..., T]) -> Callable[..., T]:
    """
    Async version of with_transaction decorator for async router functions.

    Usage:
        @router.post("/endpoint")
        @with_transaction_async
        async def create_item(item: ItemCreate, db: Session = Depends(get_db)):
            db.add(Item(**item.dict()))
            return {"status": "created"}
    """
    @wraps(func)
    async def wrapper(*args, **kwargs):
        db = kwargs.get('db')
        if db is None:
            for arg in args:
                if isinstance(arg, Session):
                    db = arg
                    break

        if db is None:
            logger.warning(f"No db session found in {func.__name__}, skipping transaction wrapper")
            return await func(*args, **kwargs)

        try:
            result = await func(*args, **kwargs)
            db.commit()
            return result
        except SQLAlchemyError as e:
            logger.error(f"Database error in {func.__name__}, rolling back: {e}")
            db.rollback()
            raise
        except Exception as e:
            logger.error(f"Error in {func.__name__}, rolling back transaction: {e}")
            db.rollback()
            raise

    return wrapper


def safe_commit(db: Session, error_message: str = "Database commit failed") -> bool:
    """
    Safely commit a transaction with error handling.

    Args:
        db: SQLAlchemy session
        error_message: Message to log if commit fails

    Returns:
        True if commit succeeded, False otherwise
    """
    try:
        db.commit()
        return True
    except SQLAlchemyError as e:
        logger.error(f"{error_message}: {e}")
        db.rollback()
        return False
    except Exception as e:
        logger.error(f"{error_message}: {e}")
        db.rollback()
        return False


def safe_delete(db: Session, obj: Any, error_message: str = "Delete failed") -> bool:
    """
    Safely delete an object with automatic rollback on failure.

    Args:
        db: SQLAlchemy session
        obj: Object to delete
        error_message: Message to log if delete fails

    Returns:
        True if delete succeeded, False otherwise
    """
    try:
        db.delete(obj)
        db.commit()
        return True
    except SQLAlchemyError as e:
        logger.error(f"{error_message}: {e}")
        db.rollback()
        return False
