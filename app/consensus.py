"""Consensus scoring for normalized football-provider probabilities.

Provider adapters must convert their responses into the normalized shape accepted
by this module. Never treat missing provider data as a negative prediction.
"""
from collections import Counter
from typing import Literal

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
