from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy import inspect, text

from app.database import Base, engine
from app import models

from app.auth import router as auth_router
from app.users import router as users_router
from app.fixtures import router as fixtures_router
from app.predictions import router as predictions_router
from app.football_data import router as football_data_router
from app.consensus import router as consensus_router


def migrate_fixtures_table() -> None:
    """Incrementally migrate fixtures from releases predating external_id."""
    with engine.begin() as connection:
        inspector = inspect(connection)
        if not inspector.has_table("fixtures"):
            return

        column_names = {
            column["name"]
            for column in inspector.get_columns("fixtures")
        }

        if "external_id" not in column_names:
            connection.execute(
                text("ALTER TABLE fixtures ADD COLUMN external_id INTEGER")
            )

        inspector = inspect(connection)
        index = next(
            (
                item
                for item in inspector.get_indexes("fixtures")
                if item["name"] == "ix_fixtures_external_id"
            ),
            None,
        )

        if index is not None:
            if index.get("unique"):
                return

            connection.execute(
                text("DROP INDEX IF EXISTS ix_fixtures_external_id")
            )

        connection.execute(
            text(
                "CREATE UNIQUE INDEX IF NOT EXISTS "
                "ix_fixtures_external_id "
                "ON fixtures (external_id)"
            )
        )


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create all current tables, then migrate existing fixtures incrementally.
    Base.metadata.create_all(bind=engine)
    migrate_fixtures_table()
    yield


app = FastAPI(
    title="PitchPredict API",
    description="Worldwide AI-powered football predictions platform",
    version="1.1.0",
    lifespan=lifespan,
)

app.include_router(auth_router)
app.include_router(users_router)
app.include_router(fixtures_router)
app.include_router(predictions_router)
app.include_router(football_data_router)
app.include_router(consensus_router)


@app.get("/")
def home():
    return {
        "message": "Welcome to PitchPredict",
        "status": "Running",
    }


@app.get("/health")
def health():
    return {"status": "healthy"}
