import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

Base = declarative_base()
engine = None
SessionLocal = None


def _path_to_sqlite_url(path: str) -> str:
    # Normalize filesystem path to SQLAlchemy sqlite URL
    if path.startswith('sqlite://') or '://' in path:
        return path
    # On Windows, replace backslashes
    path = os.path.abspath(path)
    path = path.replace('\\', '/')
    return f'sqlite:///{path}'


def init_engine(database_url: str):
    global engine, SessionLocal
    if not database_url:
        raise RuntimeError('No database URL provided to init_engine')

    # If a plain file path was supplied, convert to sqlite URL
    if not any(database_url.startswith(s) for s in ('sqlite://', 'postgresql://', 'postgres://', 'mysql://')):
        database_url = _path_to_sqlite_url(database_url)

    # Create engine with pool_pre_ping for robustness
    engine = create_engine(
        database_url,
        pool_pre_ping=True,
        pool_recycle=300
    )
    
    SessionLocal = sessionmaker(bind=engine)
    return engine


def get_engine():
    return engine


def get_session():
    if SessionLocal is None:
        raise RuntimeError('Engine not initialized. Call init_engine(database_url) first.')
    return SessionLocal()
