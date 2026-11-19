from collections import Counter
from typing import Literal, Optional

from fastapi import APIRouter, HTTPException
from app.ai_model import predict_match
from pydantic import BaseModel, Field

router = APIRouter(prefix="/consensus", tags=["Prediction Consensus"])

SourceName = Literal["forebet", "sports_mole", "soccervista", "kataka_ai"]
SOURCE_ORDER = ("forebet", "sports_mole", "soccervista", "kataka_ai")

SOURCE_INFO = {
    "forebet": {
        "name": "Forebet",
        "url": "https://www.forebet.com/",
        "method": "external_prediction",
    },
    "sports_mole": {
        "name": "Sports Mole",
        "url": "https://www.sportsmole.co.uk/football/preview/",
        "method": "editorial_preview",
    },
    "soccervista": {
        "name": "SoccerVista",
        "url": "https://www.soccervista.com/",
        "method": "published_prediction",
    },
    "kataka_ai": {
        "name": "Kataka AI statistical model",
        "url": None,
        "method": "internal_model",
    },
}


class SourcePick(BaseModel):
    source: SourceName
    selection: str = Field(min_length=1, max_length=100)
    confidence: Optional[float] = Field(default=None, ge=0, le=100)
    source_url: Optional[str] = Field(default=None, max_length=2048)
    retrieved_at: Optional[str] = None


class ConsensusRequest(BaseModel):
    fixture_id: str
    home_team: str
    away_team: str
    market: str
    predictions: list[SourcePick] = Field(default_factory=list)


@router.get("/sources")
def list_consensus_sources():
    """List the four distinct sources used by the consensus engine."""
    return {
        "sources": [
            {"id": source, **SOURCE_INFO[source]}
            for source in SOURCE_ORDER
        ],
        "note": (
            "A source is counted only after a real, fixture-specific pick is "
            "submitted. A source link or missing prediction is never a vote."
        ),
    }


def evaluate_consensus(predictions: list[SourcePick]) -> dict:
    # Reject duplicate source votes rather than silently letting the last one win.
    source_ids = [item.source for item in predictions]
    duplicates = sorted({source for source in source_ids if source_ids.count(source) > 1})
    if duplicates:
        raise ValueError("Duplicate source predictions: " + ", ".join(duplicates))

    by_source = {item.source: item for item in predictions}
    valid = [by_source[source] for source in SOURCE_ORDER if source in by_source]
    counts = Counter(" ".join(item.selection.strip().casefold().split()) for item in valid)

    missing_sources = [source for source in SOURCE_ORDER if source not in by_source]
    if not valid:
        return {
            "agreement": "0/4",
            "support_count": 0,
            "available_sources": 0,
            "selection": None,
            "status": "no_verified_predictions",
            "confidence": None,
            "missing_sources": missing_sources,
            "source_picks": [],
        }

    winner, votes = counts.most_common(1)[0]
    tied = sum(1 for count in counts.values() if count == votes) > 1
    selection = None if tied else next(
        item.selection.strip() for item in valid
        if " ".join(item.selection.strip().casefold().split()) == winner
    )

    if tied:
        status = "mixed_opinions"
    elif votes == 4:
        status = "unanimous_4_of_4"
    elif votes == 3:
        status = "strong_consensus_3_of_4"
    elif votes == 2:
        status = "review_2_of_4"
    else:
        status = "exclude_1_of_4"

    supporters = [
        item for item in valid
        if selection is not None
        and " ".join(item.selection.strip().casefold().split()) == winner
        and item.confidence is not None
    ]
    confidence = (
        round(sum(item.confidence for item in supporters) / len(supporters), 1)
        if supporters else None
    )

    return {
        "agreement": f"{votes}/4",
        "support_count": votes,
        "available_sources": len(valid),
        "selection": selection,
        "status": status,
        "confidence": confidence,
        "missing_sources": missing_sources,
        "source_picks": [
            {
                "source": item.source,
                "source_name": SOURCE_INFO[item.source]["name"],
                "selection": item.selection,
                "confidence": item.confidence,
                "source_url": item.source_url,
                "retrieved_at": item.retrieved_at,
            }
            for item in valid
        ],
    }


@router.post("/evaluate")
def evaluate(request: ConsensusRequest):
    try:
        result = evaluate_consensus(request.predictions)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return {
        "fixture_id": request.fixture_id,
        "fixture": f"{request.home_team} vs {request.away_team}",
        "market": request.market,
        "consensus": result,
        "disclaimer": (
            "Agreement measures source alignment, not certainty or a calibrated "
            "match probability. Only fixture-specific predictions count. Missing "
            "sources do not count as opposing votes; ties produce no selection. "
            "2/4 requires review and 1/4 is excluded from the shortlist."
        ),
    }


class AIPredictionRequest(BaseModel):
    home_team: str = Field(min_length=2, max_length=150)
    away_team: str = Field(min_length=2, max_length=150)
    market: str = Field(default="1X2", min_length=2, max_length=30)


@router.post("/ai-predict")
async def kataka_ai_predict(request: AIPredictionRequest):
    """Generate an independent prediction from recent completed team results."""
    result = await predict_match(
        request.home_team,
        request.away_team,
        request.market,
    )
    return {
        "fixture": f"{request.home_team} vs {request.away_team}",
        "market": request.market,
        "prediction": result,
        "consensus_input": {
            "source": "kataka_ai",
            "selection": result["selection"],
            "confidence": result["confidence"],
            "source_url": None,
        },
        "message": (
            "This is Kataka's independent statistical prediction. "
            "Submit consensus_input with the other source picks to /consensus/evaluate."
        ),
    }
