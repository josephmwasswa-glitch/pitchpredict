import os
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

DATABASE_URL = (os.getenv("DATABASE_URL") or "").strip()

if DATABASE_URL:
    # Normalize legacy PostgreSQL URL schemes for SQLAlchemy/psycopg 3.
    if DATABASE_URL.startswith("postgres://"):
        DATABASE_URL = DATABASE_URL.replace(
            "postgres://",
            "postgresql+psycopg://",
            1,
        )
    elif DATABASE_URL.startswith("postgresql://"):
        DATABASE_URL = DATABASE_URL.replace(
            "postgresql://",
            "postgresql+psycopg://",
            1,
        )
else:
    # Keep local development and initial deployments runnable without a
    # provisioned PostgreSQL database. Production can still set DATABASE_URL.
    DATABASE_PATH = Path(__file__).resolve().parent.parent / "pitchpredict.db"
    DATABASE_URL = f"sqlite:///{DATABASE_PATH.as_posix()}"

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
