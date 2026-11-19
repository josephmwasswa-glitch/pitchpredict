"""Kataka's independent football prediction model.

Uses recent, completed team results from API-Football and a transparent
attack/defence Poisson model. It is a statistical baseline, not a trained
machine-learning model. No predictions are returned when the provider data
is unavailable or too thin.
"""
from __future__ import annotations

import math
import os
import re
from collections import defaultdict
from typing import Any

import httpx
from fastapi import HTTPException

API_URL = "https://v3.football.api-sports.io"
MAX_GOALS = 10
MIN_MATCHES = 3


def _norm(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.casefold())


def _poisson(lam: float, goals: int) -> float:
    return math.exp(-lam) * (lam ** goals) / math.factorial(goals)


def _score_matrix(home_xg: float, away_xg: float) -> list[list[float]]:
    return [
        [_poisson(home_xg, h) * _poisson(away_xg, a) for a in range(MAX_GOALS + 1)]
        for h in range(MAX_GOALS + 1)
    ]


def _probabilities(matrix: list[list[float]]) -> dict[str, float]:
    home = draw = away = btts = 0.0
    over = {1.5: 0.0, 2.5: 0.0, 3.5: 0.0}
    total = sum(sum(row) for row in matrix) or 1.0
    for h, row in enumerate(matrix):
        for a, raw in enumerate(row):
            p = raw / total
            if h > a:
                home += p
            elif h == a:
                draw += p
            else:
                away += p
            if h > 0 and a > 0:
                btts += p
            for line in over:
                if h + a > line:
                    over[line] += p
    return {
        "home_win": home, "draw": draw, "away_win": away,
        "btts_yes": btts,
        "over_1_5": over[1.5], "over_2_5": over[2.5], "over_3_5": over[3.5],
    }


def _team_form(fixtures: list[dict[str, Any]], team_id: int) -> dict[str, float]:
    rows = []
    for item in fixtures:
        fixture = item.get("fixture", {})
        if fixture.get("status", {}).get("short") not in {"FT", "AET", "PEN"}:
            continue
        teams, goals = item.get("teams", {}), item.get("goals", {})
        home, away = teams.get("home", {}), teams.get("away", {})
        hg, ag = goals.get("home"), goals.get("away")
        if hg is None or ag is None:
            continue
        if home.get("id") == team_id:
            rows.append((True, float(hg), float(ag)))
        elif away.get("id") == team_id:
            rows.append((False, float(ag), float(hg)))
    # API returns newest first; keep the ten most recent completed matches.
    rows = rows[:10]
    if not rows:
        raise ValueError("No completed recent matches were returned for a team")

    def avg(values: list[float]) -> float:
        return sum(values) / len(values) if values else 0.0

    home_rows = [r for r in rows if r[0]]
    away_rows = [r for r in rows if not r[0]]
    return {
        "matches": float(len(rows)),
        "scored_avg": avg([r[1] for r in rows]),
        "conceded_avg": avg([r[2] for r in rows]),
        "home_scored_avg": avg([r[1] for r in home_rows]) if home_rows else avg([r[1] for r in rows]),
        "home_conceded_avg": avg([r[2] for r in home_rows]) if home_rows else avg([r[2] for r in rows]),
        "away_scored_avg": avg([r[1] for r in away_rows]) if away_rows else avg([r[1] for r in rows]),
        "away_conceded_avg": avg([r[2] for r in away_rows]) if away_rows else avg([r[2] for r in rows]),
    }


async def _api_get(client: httpx.AsyncClient, path: str, params: dict[str, Any]) -> dict:
    key = os.getenv("FOOTBALL_API_KEY") or os.getenv("API_FOOTBALL_KEY")
    if not key:
        raise HTTPException(
            status_code=503,
            detail="Kataka AI needs FOOTBALL_API_KEY (or API_FOOTBALL_KEY) configured on the backend.",
        )
    response = await client.get(
        f"{API_URL}{path}",
        headers={"x-apisports-key": key},
        params=params,
    )
    if response.status_code != 200:
        raise HTTPException(status_code=502, detail=f"Football data provider returned HTTP {response.status_code}")
    payload = response.json()
    if payload.get("errors"):
        raise HTTPException(status_code=502, detail="Football data provider rejected the request: " + str(payload["errors"]))
    return payload


async def _find_team(client: httpx.AsyncClient, name: str) -> dict:
    payload = await _api_get(client, "/teams", {"search": name})
    candidates = payload.get("response", [])
    if not candidates:
        raise HTTPException(status_code=404, detail=f"Team not found by football data provider: {name}")
    exact = [x for x in candidates if _norm(x.get("team", {}).get("name", "")) == _norm(name)]
    if len(exact) == 1:
        selected = exact[0]
    elif not exact and len(candidates) == 1:
        selected = candidates[0]
    else:
        raise HTTPException(
            status_code=409,
            detail=(
                f"Team name '{name}' is ambiguous in the football data provider. "
                "Use the full official team name so the model does not select the wrong club."
            ),
        )
    return selected.get("team", {})


async def predict_match(home_team: str, away_team: str, market: str) -> dict:
    if _norm(home_team) == _norm(away_team):
        raise HTTPException(status_code=422, detail="Home and away teams must be different.")
    market_key = market.strip().upper().replace(" ", "")
    allowed = {"1X2", "BTTS", "OVER1.5", "OVER2.5", "OVER3.5", "DOUBLECHANCE"}
    if market_key not in allowed:
        raise HTTPException(status_code=422, detail="Supported markets: 1X2, BTTS, OVER 1.5, OVER 2.5, OVER 3.5, DOUBLE CHANCE.")

    async with httpx.AsyncClient(timeout=25) as client:
        home, away = await _find_team(client, home_team), await _find_team(client, away_team)
        if not home.get("id") or not away.get("id"):
            raise HTTPException(status_code=502, detail="Team lookup did not return valid team IDs.")
        home_data, away_data = await _api_get(client, "/fixtures", {"team": home["id"], "last": 10}), await _api_get(client, "/fixtures", {"team": away["id"], "last": 10})

    try:
        hf = _team_form(home_data.get("response", []), int(home["id"]))
        af = _team_form(away_data.get("response", []), int(away["id"]))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=f"Insufficient recent results for this prediction: {exc}") from exc
    if hf["matches"] < MIN_MATCHES or af["matches"] < MIN_MATCHES:
        raise HTTPException(status_code=422, detail=f"At least {MIN_MATCHES} completed matches per team are required.")

    # League-neutral shrinkage limits extreme rates when only a small recent sample exists.
    home_attack = (hf["home_scored_avg"] * 0.65 + hf["scored_avg"] * 0.35)
    home_defence = (hf["home_conceded_avg"] * 0.65 + hf["conceded_avg"] * 0.35)
    away_attack = (af["away_scored_avg"] * 0.65 + af["scored_avg"] * 0.35)
    away_defence = (af["away_conceded_avg"] * 0.65 + af["conceded_avg"] * 0.35)
    home_xg = min(3.5, max(0.25, 0.55 * home_attack + 0.45 * away_defence + 0.15))
    away_xg = min(3.5, max(0.25, 0.55 * away_attack + 0.45 * home_defence - 0.05))
    matrix = _score_matrix(home_xg, away_xg)
    probs = _probabilities(matrix)

    if market_key == "1X2":
        options = {"Home": probs["home_win"], "Draw": probs["draw"], "Away": probs["away_win"]}
    elif market_key == "BTTS":
        options = {"Yes": probs["btts_yes"], "No": 1.0 - probs["btts_yes"]}
    elif market_key.startswith("OVER"):
        line = market_key.replace("OVER", "").replace(".", "_")
        options = {"Over " + market_key.replace("OVER", ""): probs["over_" + line]}
    else:
        options = {
            "Home or Draw (1X)": probs["home_win"] + probs["draw"],
            "Draw or Away (X2)": probs["draw"] + probs["away_win"],
            "Home or Away (12)": probs["home_win"] + probs["away_win"],
        }
    selection, probability = max(options.items(), key=lambda item: item[1])
    most_likely = max(
        ((h, a, matrix[h][a]) for h in range(MAX_GOALS + 1) for a in range(MAX_GOALS + 1)),
        key=lambda item: item[2],
    )
    return {
        "source": "kataka_ai",
        "model": "kataka-poisson-form-v1",
        "selection": selection,
        "confidence": round(probability * 100, 1),
        "probabilities": {key: round(value * 100, 2) for key, value in probs.items()},
        "expected_goals": {"home": round(home_xg, 2), "away": round(away_xg, 2)},
        "most_likely_score": f"{most_likely[0]}-{most_likely[1]}",
        "sample": {"home_team_matches": int(hf["matches"]), "away_team_matches": int(af["matches"])},
        "data_provider": "API-Football",
        "limitations": [
            "Statistical Poisson model, not a trained machine-learning model.",
            "Recent team results only; injuries, lineups, weather and odds are not included.",
            "Confidence is a model probability estimate and has not been calibrated by historical backtesting.",
        ],
    }
