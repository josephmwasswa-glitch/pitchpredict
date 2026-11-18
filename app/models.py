
from sqlalchemy import (
    Column, Integer, String, Float,
    DateTime, Text, ForeignKey
)
from app.database import Base


class Fixture(Base):
    __tablename__ = "fixtures"

    external_id = Column(Integer, unique=True, index=True, nullable=True)
    id = Column(Integer, primary_key=True, index=True)
    home_team = Column(String(150), nullable=False)
    away_team = Column(String(150), nullable=False)
    league = Column(String(150))
    country = Column(String(100))
    kickoff = Column(DateTime, nullable=False)
    status = Column(String(50), default="scheduled")


class Prediction(Base):
    __tablename__ = "predictions"

    id = Column(Integer, primary_key=True, index=True)
    fixture_id = Column(
        Integer,
        ForeignKey("fixtures.id"),
        nullable=False
    )
    market = Column(String(50), nullable=False)
    selection = Column(String(100), nullable=False)
    confidence = Column(Float, nullable=False)
    analysis = Column(Text)
    created_at = Column(DateTime)
