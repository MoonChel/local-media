"""SQLAlchemy models for the application"""
from datetime import datetime, timezone
from sqlalchemy import Column, Float, ForeignKey, Integer, String, Text, create_engine
from sqlalchemy.orm import declarative_base, relationship, sessionmaker

Base = declarative_base()


class Video(Base):
    __tablename__ = "videos"

    id = Column(String, primary_key=True)
    source_id = Column(String, index=True)
    source_label = Column(String)
    rel_path = Column(String, nullable=False)
    abs_path = Column(String, nullable=False)
    title = Column(String, nullable=False)
    size = Column(Integer, nullable=False)
    mtime = Column(Float, nullable=False)

    # Relationship
    progress = relationship("Progress", back_populates="video", uselist=False, cascade="all, delete-orphan")

    def to_dict(self):
        return {
            "id": self.id,
            "source_id": self.source_id,
            "source_label": self.source_label,
            "rel_path": self.rel_path,
            "abs_path": self.abs_path,
            "title": self.title,
            "size": self.size,
            "mtime": self.mtime,
        }


class Progress(Base):
    __tablename__ = "progress"

    video_id = Column(String, ForeignKey("videos.id", ondelete="CASCADE"), primary_key=True)
    position_seconds = Column(Float, nullable=False)
    updated_at = Column(String, nullable=False)

    # Relationship
    video = relationship("Video", back_populates="progress")

    def to_dict(self):
        return {
            "video_id": self.video_id,
            "position_seconds": self.position_seconds,
            "updated_at": self.updated_at,
        }


class Download(Base):
    __tablename__ = "downloads"

    id = Column(String, primary_key=True)
    source_kind = Column(String, nullable=False)
    source_value = Column(String, nullable=False)
    source_id = Column(String)
    source_label = Column(String)
    target_dir = Column(String, nullable=False)
    status = Column(String, nullable=False)
    error = Column(Text)
    display_name = Column(String)
    progress_percent = Column(Float, default=0)
    created_at = Column(String, nullable=False)
    updated_at = Column(String, nullable=False, index=True)

    def to_dict(self):
        return {
            "id": self.id,
            "source_kind": self.source_kind,
            "source_value": self.source_value,
            "source_id": self.source_id,
            "source_label": self.source_label,
            "target_dir": self.target_dir,
            "status": self.status,
            "error": self.error,
            "display_name": self.display_name,
            "progress_percent": self.progress_percent,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


class YouTubeDownload(Base):
    __tablename__ = "youtube_downloads"

    id = Column(String, primary_key=True)
    url = Column(String, nullable=False)
    source_id = Column(String, nullable=False)
    source_label = Column(String, nullable=False)
    target_dir = Column(String, nullable=False)
    status = Column(String, nullable=False)
    error = Column(Text)
    display_name = Column(String)
    progress_percent = Column(Float, default=0)
    video_id = Column(String)
    created_at = Column(String, nullable=False)
    updated_at = Column(String, nullable=False)

    def to_dict(self):
        return {
            "id": self.id,
            "url": self.url,
            "source_id": self.source_id,
            "source_label": self.source_label,
            "target_dir": self.target_dir,
            "status": self.status,
            "error": self.error,
            "display_name": self.display_name,
            "progress_percent": self.progress_percent,
            "video_id": self.video_id,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


def get_engine(db_path: str):
    """Create SQLAlchemy engine"""
    return create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})


def get_session_maker(engine):
    """Create session maker"""
    return sessionmaker(bind=engine, autocommit=False, autoflush=False)


def init_database(engine):
    """Initialize database tables"""
    Base.metadata.create_all(engine)
