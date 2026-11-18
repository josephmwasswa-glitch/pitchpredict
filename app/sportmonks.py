"""Sportmonks Football API v3 adapter.

Requires SPORTMONKS_API_TOKEN. Prediction probabilities additionally require
the Sportmonks Predictions add-on on the user's subscription.
"""
import os

import httpx
from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/providers/sportmonks", tags=["Prediction Providers"])
BASE_URL = "https://api.sportmonks.com/v3/football"


def _market_from_type(item: dict) -> tuple[str | None, dict | None]:
    prediction = item.get("predictions") or {}
    kind = item.get("type") or {}
    label = " ".join(
        str(kind.get(key, "")) for key in ("developer_name", "name", "code")
    ).lower().replace("_", " ").replace("-", " ")

    if "fulltime result" in label or "full time result" in label or "winner probability" in label:
        values = {
            "HOME": prediction.get("home"),
            "DRAW": prediction.get("draw"),
            "AWAY": prediction.get("away"),
        }
        market = "1X2"
    elif "both teams to score" in label or "btts" in label:
        values = {"YES": prediction.get("yes"), "NO": prediction.get("no")}
        market = "BTTS"
    elif "over" in label and ("2.5" in label or "2 5" in label):
        values = {"OVER": prediction.get("over"), "UNDER": prediction.get("under")}
        market = "OVER_2_5"
    else:
        return None, None

    if any(value is None for value in values.values()):
        return None, None
    try:
        values = {key: float(value) for key, value in values.items()}
    except (TypeError, ValueError):
        return None, None
    if any(value < 0 or value > 100 for value in values.values()):
        return None, None
    if not 98 <= sum(values.values()) <= 102:
        return None, None
    return market, values


@router.get("/fixtures/{fixture_id}/predictions")
async def sportmonks_fixture_predictions(fixture_id: int):
    token = os.getenv("SPORTMONKS_API_TOKEN")
    if not token:
        raise HTTPException(
            status_code=503,
            detail="SPORTMONKS_API_TOKEN is not configured on the service",
        )

    url = f"{BASE_URL}/predictions/probabilities/fixtures/{fixture_id}"
    headers = {"Authorization": token}
    params = {"include": "type;fixture"}

    try:
        async with httpx.AsyncClient(timeout=25) as client:
            response = await client.get(url, headers=headers, params=params)
    except httpx.HTTPError:
        raise HTTPException(status_code=502, detail="Sportmonks request failed")

    if response.status_code in (401, 403):
        raise HTTPException(
            status_code=502,
            detail="Sportmonks rejected the token or this subscription lacks prediction access",
        )
    if response.status_code != 200:
        raise HTTPException(
            status_code=502,
            detail=f"Sportmonks returned HTTP {response.status_code}",
        )

    payload = response.json()
    if payload.get("errors"):
        raise HTTPException(status_code=502, detail="Sportmonks returned an API error")

    normalized = []
    for item in payload.get("data", []):
        market, probabilities = _market_from_type(item)
        if market and probabilities:
            normalized.append({
                "provider": "sportmonks",
                "fixture_id": item.get("fixture_id", fixture_id),
                "market": market,
                "probabilities": probabilities,
            })

    return {
        "provider": "sportmonks",
        "fixture_id": fixture_id,
        "predictions_found": len(normalized),
        "predictions": normalized,
        "source_counted_as_consensus": bool(normalized),
        "note": "An empty result may mean the fixture is not predictable or the subscription does not include prediction data.",
    }
