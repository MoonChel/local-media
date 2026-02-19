"""Database utility functions for session management"""
from contextlib import contextmanager
from typing import Generator

from sqlalchemy.orm import Session


@contextmanager
def get_session(session_maker) -> Generator[Session, None, None]:
    """Context manager for database sessions with automatic cleanup"""
    session = session_maker()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def with_session(session_maker):
    """Decorator for functions that need a database session"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            with get_session(session_maker) as session:
                return func(*args, session=session, **kwargs)
        return wrapper
    return decorator
