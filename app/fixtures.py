
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from datetime import datetime

from app.database import get_db
from app.models import Fixture as FixtureModel

router = APIRouter(
    prefix="/fixtures",
    tags=["Football Fixtures"]
)


class FixtureCreate(BaseModel):
    home_team: str
    away_team: str
    league: str
    country: str
    kickoff: datetime


@router.post("/")
def add_fixture(
    fixture: FixtureCreate,
    db: Session = Depends(get_db)
):
    new_fixture = FixtureModel(**fixture.model_dump())

    db.add(new_fixture)
    db.commit()
    db.refresh(new_fixture)

    return {
        "message": "Fixture saved successfully",
        "fixture_id": new_fixture.id,
        "home_team": new_fixture.home_team,
        "away_team": new_fixture.away_team
    }


@router.get("/")
def get_fixtures(db: Session = Depends(get_db)):
    return db.query(FixtureModel).order_by(
        FixtureModel.kickoff
    ).all()


@router.get("/count")
def fixture_count(db: Session = Depends(get_db)):
    total = db.query(FixtureModel).count()
    return {"total_fixtures": total}


@router.get("/{fixture_id}")
def get_fixture(
    fixture_id: int,
    db: Session = Depends(get_db)
):
    fixture = db.query(FixtureModel).filter(
        FixtureModel.id == fixture_id
    ).first()

    if not fixture:
        raise HTTPException(
            status_code=404,
            detail="Fixture not found"
        )

    return fixture
