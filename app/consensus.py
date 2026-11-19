"""Consensus scoring for normalized football-provider probabilities.

Provider adapters must convert their responses into the normalized shape accepted
by this module. Never treat missing provider data as a negative prediction.
"""
from collections import Counter
from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, model_validator


Market = Literal["1X2", "BTTS", "OVER_2_5"]
OUTCOMES = {
    "1X2": ("HOME", "DRAW", "AWAY"),
    "BTTS": ("YES", "NO"),
    "OVER_2_5": ("OVER", "UNDER"),
}


class ProviderProbabilities(BaseModel):
    provider: str = Field(min_length=2, max_length=40)
    market: Market
    probabilities: dict[str, float]

    @model_validator(mode="after")
    def validate_probabilities(self):
        expected = set(OUTCOMES[self.market])
        supplied = set(self.probabilities)
        if supplied != expected:
            raise ValueError(
                f"{self.market} requires exactly these outcomes: "
                f"{', '.join(OUTCOMES[self.market])}"
            )
        if any(value < 0 or value > 100 for value in self.probabilities.values()):
            raise ValueError("Probabilities must be between 0 and 100")
        total = sum(self.probabilities.values())
        if not 98 <= total <= 102:
            raise ValueError("Probabilities for a market must total approximately 100")
        return self


class ConsensusRequest(BaseModel):
    predictions: list[ProviderProbabilities] = Field(min_length=2)


def calculate_consensus(request: ConsensusRequest) -> dict:
    """Average independent provider probabilities and measure pick agreement."""
    results = []
    for market, outcomes in OUTCOMES.items():
        rows = [p for p in request.predictions if p.market == market]
        # Require two independent sources for each market before publishing it.
        unique = {row.provider.lower() for row in rows}
        if len(unique) < 2:
            continue

        averages = {
            outcome: sum(row.probabilities[outcome] for row in rows) / len(rows)
            for outcome in outcomes
        }
        selection = max(averages, key=averages.get)
        votes = Counter(
            max(row.probabilities, key=row.probabilities.get) for row in rows
        )
        agreement = round(votes[selection] / len(rows) * 100, 1)
        confidence = round(averages[selection], 1)

        results.append({
            "market": market,
            "selection": selection,
            "probability": confidence,
            "provider_count": len(rows),
            "agreement": agreement,
            "provider_probabilities": averages,
            "publish_recommended": confidence >= 55 and agreement >= 66.7,
        })

    return {
        "sources_received": len({p.provider.lower() for p in request.predictions}),
        "markets": results,
        "note": (
            "Consensus is an average of supplied provider probabilities, not a "
            "guarantee. Only publish markets with at least two independent sources."
        ),
    }


# Source-alignment consensus (separate from the probability-averaging API above).
from app.ai_model import predict_match

router = APIRouter(prefix="/consensus", tags=["Four-source consensus"])
SourceId = Literal["forebet", "sports_mole", "soccervista", "kataka_ai"]
SOURCE_IDS = ("forebet", "sports_mole", "soccervista", "kataka_ai")
SOURCE_LABELS = {
    "forebet": "Forebet",
    "sports_mole": "Sports Mole",
    "soccervista": "SoccerVista",
    "kataka_ai": "Kataka AI",
}


class SourceVote(BaseModel):
    source: SourceId
    selection: str = Field(min_length=1, max_length=100)
    source_url: str | None = Field(default=None, max_length=2048)
    confidence: float | None = Field(default=None, ge=0, le=100)
    retrieved_at: str | None = None


class SourceAgreementRequest(BaseModel):
    fixture_id: str
    home_team: str = Field(min_length=2, max_length=150)
    away_team: str = Field(min_length=2, max_length=150)
    market: str = Field(min_length=2, max_length=30)
    predictions: list[SourceVote] = Field(default_factory=list)


def _source_agreement(predictions: list[SourceVote]) -> dict:
    ids = [item.source for item in predictions]
    duplicates = sorted({source for source in ids if ids.count(source) > 1})
    if duplicates:
        raise ValueError("Duplicate source votes: " + ", ".join(duplicates))
    by_source = {item.source: item for item in predictions}
    valid = [by_source[source] for source in SOURCE_IDS if source in by_source]
    normalized = lambda value: " ".join(value.strip().casefold().split())
    votes = Counter(normalized(item.selection) for item in valid)
    missing = [source for source in SOURCE_IDS if source not in by_source]
    if not valid:
        return {"agreement": "0/4", "support_count": 0, "available_sources": 0,
                "selection": None, "status": "no_verified_predictions",
                "missing_sources": missing, "source_picks": []}
    winner, count = votes.most_common(1)[0]
    tied = sum(1 for value in votes.values() if value == count) > 1
    selection = None if tied else next(item.selection.strip() for item in valid
                                       if normalized(item.selection) == winner)
    status = ("mixed_opinions" if tied else
              "unanimous_4_of_4" if count == 4 else
              "strong_consensus_3_of_4" if count == 3 else
              "review_2_of_4" if count == 2 else "exclude_1_of_4")
    supporting = [item for item in valid if selection is not None
                  and normalized(item.selection) == winner
                  and item.confidence is not None]
    return {
        "agreement": f"{count}/4", "support_count": count,
        "available_sources": len(valid), "selection": selection,
        "status": status, "confidence": (
            round(sum(x.confidence for x in supporting) / len(supporting), 1)
            if supporting else None),
        "missing_sources": missing,
        "source_picks": [{"source": x.source, "source_name": SOURCE_LABELS[x.source],
            "selection": x.selection, "confidence": x.confidence,
            "source_url": x.source_url, "retrieved_at": x.retrieved_at}
            for x in valid],
    }


@router.get("/sources")
def list_sources():
    return {"sources": [
        {"id": source, "name": SOURCE_LABELS[source],
         "url": {"forebet": "https://www.forebet.com/",
                 "sports_mole": "https://www.sportsmole.co.uk/football/preview/",
                 "soccervista": "https://www.soccervista.com/",
                 "kataka_ai": None}[source]}
        for source in SOURCE_IDS
    ], "note": "A source counts only when a real fixture-specific pick is supplied."}


@router.post("/evaluate-sources")
def evaluate_sources(request: SourceAgreementRequest):
    try:
        result = _source_agreement(request.predictions)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"fixture_id": request.fixture_id,
            "fixture": f"{request.home_team} vs {request.away_team}",
            "market": request.market, "consensus": result,
            "note": "Source agreement is not certainty. Missing sources are not treated as votes."}


class AIPredictRequest(BaseModel):
    home_team: str = Field(min_length=2, max_length=150)
    away_team: str = Field(min_length=2, max_length=150)
    market: str = Field(default="1X2", min_length=2, max_length=30)


@router.post("/ai-predict")
async def ai_predict(request: AIPredictRequest):
    prediction = await predict_match(request.home_team, request.away_team, request.market)
    return {"fixture": f"{request.home_team} vs {request.away_team}",
            "market": request.market, "prediction": prediction,
            "consensus_input": {"source": "kataka_ai",
                "selection": prediction["selection"],
                "confidence": prediction["confidence"]}}


@router.post("/evaluate-with-ai")
async def evaluate_with_ai(request: SourceAgreementRequest):
    if any(item.source == "kataka_ai" for item in request.predictions):
        raise HTTPException(status_code=422,
            detail="Kataka AI is generated independently by this endpoint; do not submit it as an external pick.")
    prediction = await predict_match(request.home_team, request.away_team, request.market)
    combined = list(request.predictions) + [
        SourceVote(source="kataka_ai", selection=prediction["selection"],
                   confidence=prediction["confidence"])
    ]
    try:
        result = _source_agreement(combined)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"fixture_id": request.fixture_id,
            "fixture": f"{request.home_team} vs {request.away_team}",
            "market": request.market, "ai_prediction": prediction,
            "consensus": result,
            "note": "Kataka AI is calculated from recent completed results. External picks must be verified against the exact fixture."}
