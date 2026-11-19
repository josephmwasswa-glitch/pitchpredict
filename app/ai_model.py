"""Independent Kataka AI football model using recent completed match data."""
import math
import os
import re
from typing import Any

import httpx
from fastapi import HTTPException

API_URL = "https://v3.football.api-sports.io"
MAX_GOALS = 10
MIN_MATCHES = 3


def _norm(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.casefold())


def _poisson(lam: float, goals: int) -> float:
    return math.exp(-lam) * lam ** goals / math.factorial(goals)


def _matrix(home_xg: float, away_xg: float) -> list[list[float]]:
    return [[_poisson(home_xg, h) * _poisson(away_xg, a)
             for a in range(MAX_GOALS + 1)] for h in range(MAX_GOALS + 1)]


def _probabilities(matrix: list[list[float]]) -> dict[str, float]:
    home = draw = away = btts = 0.0
    overs = {1.5: 0.0, 2.5: 0.0, 3.5: 0.0}
    total = sum(map(sum, matrix)) or 1.0
    for h, row in enumerate(matrix):
        for a, raw in enumerate(row):
            p = raw / total
            if h > a:
                home += p
            elif h == a:
                draw += p
            else:
                away += p
            if h and a:
                btts += p
            for line in overs:
                if h + a > line:
                    overs[line] += p
    return {"home_win": home, "draw": draw, "away_win": away,
            "btts_yes": btts, "over_1_5": overs[1.5],
            "over_2_5": overs[2.5], "over_3_5": overs[3.5]}


def _form(fixtures: list[dict[str, Any]], team_id: int) -> dict[str, float]:
    rows = []
    for item in fixtures:
        if item.get("fixture", {}).get("status", {}).get("short") not in {"FT", "AET", "PEN"}:
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
    rows = rows[:10]
    if len(rows) < MIN_MATCHES:
        raise ValueError(f"Only {len(rows)} completed matches available; need at least {MIN_MATCHES}")
    avg = lambda values: sum(values) / len(values) if values else 0.0
    home_rows = [r for r in rows if r[0]]
    away_rows = [r for r in rows if not r[0]]
    return {
        "matches": float(len(rows)),
        "scored": avg([r[1] for r in rows]),
        "conceded": avg([r[2] for r in rows]),
        "home_scored": avg([r[1] for r in home_rows]) if home_rows else avg([r[1] for r in rows]),
        "home_conceded": avg([r[2] for r in home_rows]) if home_rows else avg([r[2] for r in rows]),
        "away_scored": avg([r[1] for r in away_rows]) if away_rows else avg([r[1] for r in rows]),
        "away_conceded": avg([r[2] for r in away_rows]) if away_rows else avg([r[2] for r in rows]),
    }


async def _get(client: httpx.AsyncClient, path: str, params: dict) -> dict:
    key = os.getenv("FOOTBALL_API_KEY") or os.getenv("API_FOOTBALL_KEY")
    if not key:
        raise HTTPException(status_code=503, detail="Set FOOTBALL_API_KEY on the Render backend to enable Kataka AI.")
    try:
        response = await client.get(f"{API_URL}{path}",
            headers={"x-apisports-key": key}, params=params)
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail="Football data provider request failed.") from exc
    if response.status_code != 200:
        raise HTTPException(status_code=502, detail=f"Football data provider returned HTTP {response.status_code}.")
    payload = response.json()
    if payload.get("errors"):
        raise HTTPException(status_code=502, detail="Football data provider rejected the request: " + str(payload["errors"]))
    return payload


async def _team(client: httpx.AsyncClient, name: str) -> dict:
    payload = await _get(client, "/teams", {"search": name})
    candidates = payload.get("response", [])
    exact = [x for x in candidates if _norm(x.get("team", {}).get("name", "")) == _norm(name)]
    if len(exact) == 1:
        chosen = exact[0]
    elif not exact and len(candidates) == 1:
        chosen = candidates[0]
    elif not candidates:
        raise HTTPException(status_code=404, detail=f"Team not found: {name}")
    else:
        raise HTTPException(status_code=409, detail=f"Team name '{name}' is ambiguous. Use its full official name.")
    return chosen.get("team", {})


async def predict_match(home_team: str, away_team: str, market: str) -> dict:
    if _norm(home_team) == _norm(away_team):
        raise HTTPException(status_code=422, detail="Home and away teams must be different.")
    market_key = market.strip().upper().replace(" ", "")
    if market_key not in {"1X2", "BTTS", "OVER1.5", "OVER2.5", "OVER3.5", "DOUBLECHANCE"}:
        raise HTTPException(status_code=422, detail="Supported markets: 1X2, BTTS, OVER 1.5, OVER 2.5, OVER 3.5, DOUBLE CHANCE.")
    async with httpx.AsyncClient(timeout=25) as client:
        home, away = await _team(client, home_team), await _team(client, away_team)
        if not home.get("id") or not away.get("id"):
            raise HTTPException(status_code=502, detail="Provider did not return valid team IDs.")
        hdata = await _get(client, "/fixtures", {"team": home["id"], "last": 10})
        adata = await _get(client, "/fixtures", {"team": away["id"], "last": 10})
    try:
        hf, af = _form(hdata.get("response", []), int(home["id"])), _form(adata.get("response", []), int(away["id"]))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    h_attack = 0.65 * hf["home_scored"] + 0.35 * hf["scored"]
    h_defence = 0.65 * hf["home_conceded"] + 0.35 * hf["conceded"]
    a_attack = 0.65 * af["away_scored"] + 0.35 * af["scored"]
    a_defence = 0.65 * af["away_conceded"] + 0.35 * af["conceded"]
    hxg = min(3.5, max(0.25, 0.55 * h_attack + 0.45 * a_defence + 0.15))
    axg = min(3.5, max(0.25, 0.55 * a_attack + 0.45 * h_defence - 0.05))
    matrix = _matrix(hxg, axg)
    probs = _probabilities(matrix)
    if market_key == "1X2":
        options = {"HOME": probs["home_win"], "DRAW": probs["draw"], "AWAY": probs["away_win"]}
    elif market_key == "BTTS":
        options = {"YES": probs["btts_yes"], "NO": 1.0 - probs["btts_yes"]}
    elif market_key.startswith("OVER"):
        line = market_key.replace("OVER", "").replace(".", "_")
        over_probability = probs["over_" + line]
        over_label = "Over " + market_key.replace("OVER", "")
        # Kataka never recommends an Under market; weak Over probabilities become PASS.
        options = {over_label if over_probability >= 0.55 else "PASS": over_probability}
    else:
        options = {"1X": probs["home_win"] + probs["draw"],
                   "X2": probs["draw"] + probs["away_win"],
                   "12": probs["home_win"] + probs["away_win"]}
    selection, confidence = max(options.items(), key=lambda x: x[1])
    score = max(((h, a, matrix[h][a]) for h in range(MAX_GOALS + 1)
                 for a in range(MAX_GOALS + 1)), key=lambda x: x[2])
    return {
        "source": "kataka_ai", "model": "kataka-poisson-form-v1",
        "selection": selection, "confidence": round(confidence * 100, 1),
        "probabilities": {k: round(v * 100, 2) for k, v in probs.items()},
        "expected_goals": {"home": round(hxg, 2), "away": round(axg, 2)},
        "most_likely_score": f"{score[0]}-{score[1]}",
        "sample": {"home_matches": int(hf["matches"]), "away_matches": int(af["matches"])},
        "data_provider": "API-Football",
        "limitations": ["Statistical Poisson model, not trained machine learning.",
            "Recent results only; injuries, lineups, weather and odds are not included.",
            "Probability is not calibrated by a historical backtest yet."]
    }
