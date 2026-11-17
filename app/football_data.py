
import os
import httpx
from fastapi import APIRouter, HTTPException

router = APIRouter(
    prefix="/football-data",
    tags=["Worldwide Football Data"]
)

API_KEY = os.getenv("FOOTBALL_API_KEY")
API_URL = "https://v3.football.api-sports.io/fixtures"

@router.get("/fixtures")
async def worldwide_fixtures(date: str):
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

    return response.json()
