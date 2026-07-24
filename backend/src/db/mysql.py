"""SQLAlchemy engine and session factory for MySQL."""

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker, Session, DeclarativeBase

_engine: Engine | None = None
_SessionLocal = None


def _get_engine() -> Engine:
    global _engine
    if _engine is None:
        from src.config import get_settings
        settings = get_settings()
        _engine = create_engine(
            settings.mysql_url,
            pool_pre_ping=True,
            pool_size=5,
            max_overflow=10,
        )
    return _engine


def _get_session_factory():
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(
            bind=_get_engine(), autocommit=False, autoflush=False
        )
    return _SessionLocal


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models."""
    pass


def get_session() -> Session:
    """Yield a database session, closing it after use."""
    factory = _get_session_factory()
    session = factory()
    try:
        yield session
    finally:
        session.close()
