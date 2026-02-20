from __future__ import annotations

from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from .models import Base


def get_engine(db_path: str):
    """Create SQLAlchemy engine"""
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    return create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False},
        echo=False  # Set to True for SQL debugging
    )


def get_session_maker(engine):
    """Create session maker"""
    return sessionmaker(bind=engine, autocommit=False, autoflush=False)


def init_db(engine) -> None:
    """Initialize database tables"""
    Base.metadata.create_all(engine)


def get_session(session_maker) -> Session:
    """Get a new database session"""
    return session_maker()
