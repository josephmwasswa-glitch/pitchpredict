
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from datetime import datetime

router = APIRouter(
    prefix="/predictions",
    tags=["Football Predictions"]
)

ALLOWED_MARKETS = [
    "1X2",
    "BTTS",
    "OVER 2.5",
    "DOUBLE CHANCE",
    "COMBO",
    "ACCUMULATOR"
]

class Prediction(BaseModel):
    fixture_id: int
    home_team: str
    away_team: str
    market: str
    selection: str
    confidence: float = Field(ge=0, le=100)
    analysis: str = ""

predictions = []

@router.post("/")
def add_prediction(prediction: Prediction):
    if prediction.market not in ALLOWED_MARKETS:
        raise HTTPException(
            status_code=400,
            detail="Unsupported prediction market"
        )

    result = prediction.model_dump()
    result["created_at"] = datetime.utcnow().isoformat()

    predictions.append(result)

    return {
        "message": "Prediction added successfully",
        "prediction": result
    }

@router.get("/")
def get_predictions():
    return predictions

@router.get("/count")
def prediction_count():
    return {"total_predictions": len(predictions)}

@router.delete("/")
def clear_predictions():
    predictions.clear()
    return {"message": "Predictions cleared"}
