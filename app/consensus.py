from collections import Counter
from typing import Literal, Optional

from fastapi import APIRouter
from pydantic import BaseModel, Field

router = APIRouter(prefix="/consensus", tags=["Prediction Consensus"])

SourceName = Literal["forebet", "sports_mole", "soccervista", "goalwise_ai"]


class SourcePick(BaseModel):
    source: SourceName
    selection: str = Field(min_length=1, max_length=100)
    confidence: Optional[float] = Field(default=None, ge=0, le=100)
    source_url: Optional[str] = None
    retrieved_at: Optional[str] = None


class ConsensusRequest(BaseModel):
    fixture_id: str
    home_team: str
    away_team: str
    market: str
    predictions: list[SourcePick] = Field(default_factory=list)


def evaluate_consensus(predictions: list[SourcePick]) -> dict:
    # A source counts only once, and only when it supplied a real selection.
    by_source = {}
    for item in predictions:
        by_source[item.source] = item

    valid = list(by_source.values())
    counts = Counter(item.selection.strip().casefold() for item in valid)
    if not valid:
        return {
            "agreement": "0/4",
            "support_count": 0,
            "available_sources": 0,
            "selection": None,
            "status": "no_verified_predictions",
            "confidence": None,
            "source_picks": [],
        }

    winner, votes = counts.most_common(1)[0]
    # In a tie there is no consensus selection.
    tied = sum(1 for count in counts.values() if count == votes) > 1
    selection = None if tied else next(
        item.selection.strip() for item in valid
        if item.selection.strip().casefold() == winner
    )
    agreement = f"{votes}/4"
    if tied:
        status = "mixed_opinions"
    elif votes == 4:
        status = "very_strong_agreement"
    elif votes == 3:
        status = "strong_agreement"
    elif votes == 2:
        status = "mixed_opinions"
    else:
        status = "weak_agreement"

    # Confidence is the mean confidence of sources backing the winning pick.
    # It is not a calibrated probability of the match outcome.
    supporters = [
        item for item in valid
        if selection is not None
        and item.selection.strip().casefold() == winner
        and item.confidence is not None
    ]
    confidence = (
        round(sum(item.confidence for item in supporters) / len(supporters), 1)
        if supporters else None
    )

    return {
        "agreement": agreement,
        "support_count": votes,
        "available_sources": len(valid),
        "selection": selection,
        "status": status,
        "confidence": confidence,
        "source_picks": [
            {
                "source": item.source,
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
    result = evaluate_consensus(request.predictions)
    return {
        "fixture_id": request.fixture_id,
        "fixture": f"{request.home_team} vs {request.away_team}",
        "market": request.market,
        "consensus": result,
        "disclaimer": (
            "Agreement measures source alignment, not certainty. "
            "Missing sources do not count as votes; ties produce no selection."
        ),
    }
