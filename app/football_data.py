
import os
import httpx
from datetime import datetime
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Fixture as FixtureModel

router = APIRouter(
    prefix="/football-data",
    tags=["Worldwide Football Data"]
)

API_KEY = os.getenv("FOOTBALL_API_KEY")
API_URL = "https://v3.football.api-sports.io/fixtures"


@router.get("/fixtures")
async def worldwide_fixtures(
    date: str,
    db: Session = Depends(get_db)
):
    if not API_KEY:
        raise HTTPException(
            status_code=503,
            detail="Football API key is not configured"
        )

    headers = {
        "x-apisports-key": API_KEY
    }

    params = {
        "date": date
    }

    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.get(
            API_URL,
            headers=headers,
            params=params
        )

    if response.status_code != 200:
        raise HTTPException(
            status_code=502,
            detail="Football data provider error"
        )

    data = response.json()

    if data.get("errors"):
        raise HTTPException(
            status_code=502,
            detail=str(data["errors"])
        )

    saved = 0

    for item in data.get("response", []):
        fixture_data = item["fixture"]
        teams = item["teams"]
        league = item["league"]

        external_id = fixture_data["id"]

        existing = db.query(FixtureModel).filter(
            FixtureModel.external_id == external_id
        ).first()

        if existing:
            continue

        new_fixture = FixtureModel(
            external_id=external_id,
            home_team=teams["home"]["name"],
            away_team=teams["away"]["name"],
            league=league["name"],
            country=league["country"],
            kickoff=datetime.fromisoformat(
                fixture_data["date"].replace("Z", "+00:00")
            ).replace(tzinfo=None),
            status=fixture_data["status"]["short"]
        )

        db.add(new_fixture)
        saved += 1

    db.commit()

    return {
        "date": date,
        "fixtures_received": len(data.get("response", [])),
        "new_fixtures_saved": saved
    }
