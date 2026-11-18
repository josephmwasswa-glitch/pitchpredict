
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from datetime import datetime
import os

from app.consensus import ConsensusRequest, calculate_consensus

from app.database import get_db
from app.models import Prediction as PredictionModel

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


class PredictionCreate(BaseModel):
    fixture_id: int
    market: str
    selection: str
    confidence: float = Field(ge=0, le=100)
    analysis: str = ""


@router.post("/")
def add_prediction(
    prediction: PredictionCreate,
    db: Session = Depends(get_db)
):
    if prediction.market not in ALLOWED_MARKETS:
        raise HTTPException(
            status_code=400,
            detail="Unsupported prediction market"
        )

    new_prediction = PredictionModel(
        **prediction.model_dump(),
        created_at=datetime.utcnow()
    )

    db.add(new_prediction)
    db.commit()
    db.refresh(new_prediction)

    return {
        "message": "Prediction saved successfully",
        "prediction_id": new_prediction.id
    }


@router.get("/providers")
def provider_status():
    """Show which prediction-provider credentials are configured; never expose keys."""
    return {
        "providers": {
            "api_football": bool(os.getenv("FOOTBALL_API_KEY")),
            "sportmonks": bool(os.getenv("SPORTMONKS_API_TOKEN")),
            "foresportia": bool(os.getenv("FORESPORTIA_API_KEY")),
        },
        "status": "credentials_only_not_live_feed_verification",
    }


@router.post("/consensus")
def preview_consensus(request: ConsensusRequest):
    """Calculate consensus from normalized provider probabilities."""
    return calculate_consensus(request)


@router.get("/")
def get_predictions(db: Session = Depends(get_db)):
    return db.query(PredictionModel).order_by(
        PredictionModel.created_at.desc()
    ).all()


@router.get("/count")
def prediction_count(db: Session = Depends(get_db)):
    return {
        "total_predictions": db.query(PredictionModel).count()
    }


@router.delete("/{prediction_id}")
def delete_prediction(
    prediction_id: int,
    db: Session = Depends(get_db)
):
    prediction = db.query(PredictionModel).filter(
        PredictionModel.id == prediction_id
    ).first()

    if not prediction:
        raise HTTPException(
            status_code=404,
            detail="Prediction not found"
        )

    db.delete(prediction)
    db.commit()

    return {"message": "Prediction deleted successfully"}
