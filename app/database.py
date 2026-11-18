import os
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker


def normalize_database_url(value: str | None) -> str:
    """Normalize database URLs and provide a stable local SQLite fallback."""
    database_url = (value or "").strip()
    if not database_url:
        database_path = Path(__file__).resolve().parent.parent / "pitchpredict.db"
        return f"sqlite:///{database_path.as_posix()}"

    if database_url.startswith("postgres://"):
        return database_url.replace(
            "postgres://", "postgresql+psycopg://", 1
        )
    if database_url.startswith("postgresql://"):
        return database_url.replace(
            "postgresql://", "postgresql+psycopg://", 1
        )
    return database_url


DATABASE_URL = normalize_database_url(os.getenv("DATABASE_URL"))

engine_options = {"pool_pre_ping": True}
if DATABASE_URL.startswith("sqlite:"):
    engine_options["connect_args"] = {"check_same_thread": False}

engine = create_engine(DATABASE_URL, **engine_options)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)

Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
