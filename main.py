
from contextlib import asynccontextmanager
from fastapi import FastAPI

from app.database import Base, engine
from app import models

from app.auth import router as auth_router
from app.users import router as users_router
from app.fixtures import router as fixtures_router
from app.predictions import router as predictions_router
from app.football_data import router as football_data_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    title="PitchPredict API",
    description="Worldwide AI-powered football predictions platform",
    version="1.0.0",
    lifespan=lifespan
)

app.include_router(auth_router)
app.include_router(users_router)
app.include_router(fixtures_router)
app.include_router(predictions_router)
app.include_router(football_data_router)


@app.get("/")
def home():
    return {
        "message": "Welcome to PitchPredict",
        "status": "Running"
    }


@app.get("/health")
def health():
    return {"status": "healthy"}
