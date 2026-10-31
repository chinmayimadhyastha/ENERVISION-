"""SQLAlchemy ORM models for ENERVISION relational database."""

from __future__ import annotations

from datetime import date, datetime
from typing import List, Optional

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.db.database import Base


class PlantModel(Base):
    __tablename__ = "plants"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    plant_id: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    plant_name: Mapped[str] = mapped_column(String(200), index=True, nullable=False)
    type: Mapped[str] = mapped_column(String(20), index=True, nullable=False)  # Solar / Wind
    district: Mapped[Optional[str]] = mapped_column(String(100), index=True, nullable=True)
    state: Mapped[str] = mapped_column(String(50), default="Karnataka", nullable=False)
    owner: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    capacity_mw: Mapped[float] = mapped_column(Float, nullable=False)
    latitude: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    longitude: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    has_coordinates: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    first_observed_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    last_observed_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    observations_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    latest_generation_mu: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    latest_generation_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    weather_records: Mapped[List[WeatherObservationModel]] = relationship(
        "WeatherObservationModel", back_populates="plant", cascade="all, delete-orphan"
    )
    generation_records: Mapped[List[GenerationRecordModel]] = relationship(
        "GenerationRecordModel", back_populates="plant", cascade="all, delete-orphan"
    )
    forecast_records: Mapped[List[ForecastRecordModel]] = relationship(
        "ForecastRecordModel", back_populates="plant", cascade="all, delete-orphan"
    )


class WeatherObservationModel(Base):
    __tablename__ = "weather_observations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    plant_id: Mapped[str] = mapped_column(
        String(100), ForeignKey("plants.plant_id", ondelete="CASCADE"), index=True, nullable=False
    )
    date: Mapped[date] = mapped_column(Date, index=True, nullable=False)
    temperature: Mapped[float] = mapped_column(Float, nullable=False)
    humidity: Mapped[float] = mapped_column(Float, nullable=False)
    wind_speed: Mapped[float] = mapped_column(Float, nullable=False)
    ghi: Mapped[float] = mapped_column(Float, nullable=False)
    pressure: Mapped[float] = mapped_column(Float, nullable=False)
    is_forecast: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    weather_imputed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    source_sentinel_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    source: Mapped[str] = mapped_column(String(100), default="NASA POWER", nullable=False)

    plant: Mapped[PlantModel] = relationship("PlantModel", back_populates="weather_records")

    __table_args__ = (
        Index("idx_weather_plant_date", "plant_id", "date", unique=True),
    )


class GenerationRecordModel(Base):
    __tablename__ = "generation_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    plant_id: Mapped[str] = mapped_column(
        String(100), ForeignKey("plants.plant_id", ondelete="CASCADE"), index=True, nullable=False
    )
    date: Mapped[date] = mapped_column(Date, index=True, nullable=False)
    generation_mu: Mapped[float] = mapped_column(Float, nullable=False)
    capacity_mw: Mapped[float] = mapped_column(Float, nullable=False)
    unit: Mapped[str] = mapped_column(String(20), default="MU/day", nullable=False)

    plant: Mapped[PlantModel] = relationship("PlantModel", back_populates="generation_records")

    __table_args__ = (
        Index("idx_generation_plant_date", "plant_id", "date", unique=True),
    )


class ModelRegistryModel(Base):
    __tablename__ = "models_registry"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    model_id: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    algorithm: Mapped[str] = mapped_column(String(100), nullable=False)
    family: Mapped[str] = mapped_column(String(50), nullable=False)
    target: Mapped[str] = mapped_column(String(50), default="DailyGeneration_MU", nullable=False)
    unit: Mapped[str] = mapped_column(String(20), default="MU/day", nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False)  # production_candidate, committed_actual
    feature_count: Mapped[int] = mapped_column(Integer, nullable=False)
    sequence_length: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    mae: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    rmse: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    r2: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    artifact_path: Mapped[str] = mapped_column(String(255), nullable=False)
    last_verified: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class ForecastRecordModel(Base):
    __tablename__ = "forecast_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    forecast_id: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    plant_id: Mapped[str] = mapped_column(
        String(100), ForeignKey("plants.plant_id", ondelete="CASCADE"), index=True, nullable=False
    )
    model_id: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    model_family: Mapped[str] = mapped_column(String(50), nullable=False)
    horizon_days: Mapped[int] = mapped_column(Integer, nullable=False)
    base_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False)  # ok, weather_required, etc.
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)

    plant: Mapped[PlantModel] = relationship("PlantModel", back_populates="forecast_records")
    predictions: Mapped[List[PredictionItemModel]] = relationship(
        "PredictionItemModel", back_populates="forecast", cascade="all, delete-orphan"
    )


class PredictionItemModel(Base):
    __tablename__ = "prediction_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    forecast_id: Mapped[str] = mapped_column(
        String(100), ForeignKey("forecast_records.forecast_id", ondelete="CASCADE"), index=True, nullable=False
    )
    horizon_day: Mapped[int] = mapped_column(Integer, nullable=False)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    prediction: Mapped[float] = mapped_column(Float, nullable=False)
    raw_prediction: Mapped[float] = mapped_column(Float, nullable=False)
    clamp_applied: Mapped[bool] = mapped_column(Boolean, default=False)
    unit: Mapped[str] = mapped_column(String(20), default="MU/day", nullable=False)
    confidence_lower: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    confidence_upper: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    confidence_method: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    forecast: Mapped[ForecastRecordModel] = relationship("ForecastRecordModel", back_populates="predictions")
    explanations: Mapped[List[PredictionExplanationModel]] = relationship(
        "PredictionExplanationModel", back_populates="prediction_item", cascade="all, delete-orphan"
    )


class PredictionExplanationModel(Base):
    __tablename__ = "prediction_explanations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    prediction_item_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("prediction_items.id", ondelete="CASCADE"), index=True, nullable=False
    )
    feature: Mapped[str] = mapped_column(String(100), nullable=False)
    feature_value: Mapped[float] = mapped_column(Float, nullable=False)
    contribution: Mapped[float] = mapped_column(Float, nullable=False)
    direction: Mapped[str] = mapped_column(String(20), nullable=False)  # positive / negative
    rank: Mapped[int] = mapped_column(Integer, nullable=False)

    prediction_item: Mapped[PredictionItemModel] = relationship("PredictionItemModel", back_populates="explanations")
