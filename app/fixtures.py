
from fastapi import APIRouter
from pydantic import BaseModel
from datetime import datetime

router = APIRouter(
    prefix="/fixtures",
    tags=["Football Fixtures"]
)

class Fixture(BaseModel):
    home_team: str
    away_team: str
    league: str
    country: str
    kickoff: datetime

fixtures = []

@router.post("/")
def add_fixture(fixture: Fixture):
    fixtures.append(fixture)
    return {
        "message": "Fixture added successfully",
        "fixture": fixture
    }

@router.get("/")
def get_fixtures():
    return fixtures

@router.get("/count")
def fixture_count():
    return {"total_fixtures": len(fixtures)}
