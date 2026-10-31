"""Seed database from canonical ENERVISION datasets and model manifest."""

from __future__ import annotations

import logging
from datetime import datetime

from backend.db.database import Database
from backend.db.models import (
    GenerationRecordModel,
    ModelRegistryModel,
    PlantModel,
    WeatherObservationModel,
)

logger = logging.getLogger("enervision.db.seed")


def seed_database(db: Database, data_service, model_manifest: dict) -> None:
    """Populate database tables with canonical plants, weather, generation, and models."""
    db.create_tables()

    with db.session() as session:
        # Check if already seeded
        existing_count = session.query(PlantModel).count()
        if existing_count > 0:
            return

        logger.info("Seeding database with %d plants...", len(data_service.plants_by_id))

        # 1. Plants
        for plant_id, plant in data_service.plants_by_id.items():
            has_coords = bool(plant.latitude is not None and plant.longitude is not None)
            p_model = PlantModel(
                plant_id=plant.plant_id,
                plant_name=plant.plant_name,
                type=plant.type,
                district=plant.district,
                state=plant.state or "Karnataka",
                owner=plant.owner,
                capacity_mw=plant.capacity_mw,
                latitude=plant.latitude,
                longitude=plant.longitude,
                has_coordinates=has_coords,
                first_observed_date=plant.first_observed_date,
                last_observed_date=plant.last_observed_date,
                observations_count=plant.observations,
                latest_generation_mu=plant.latest_generation_mu,
                latest_generation_date=plant.latest_generation_date,
            )
            session.add(p_model)
        session.flush()

        # 2. Models from manifest
        raw_models = model_manifest.get("models", [])
        if isinstance(raw_models, dict):
            models_list = list(raw_models.values())
        else:
            models_list = list(raw_models)

        for meta in models_list:
            m_id = meta.get("id", meta.get("model_id"))
            metrics = meta.get("metrics", meta.get("evaluation_metrics", {}))
            m_model = ModelRegistryModel(
                model_id=m_id,
                name=meta.get("display_name", meta.get("name", m_id)),
                algorithm=meta.get("model_type", meta.get("algorithm", "Unknown")),
                family=meta.get("family", "lstm" if "lstm" in str(m_id) else "random_forest"),
                target=model_manifest.get("target", {}).get("name", "DailyGeneration_MU"),
                unit=model_manifest.get("target", {}).get("unit", "MU/day"),
                status=meta.get("status", "production"),
                feature_count=meta.get("feature_count", 0),
                sequence_length=meta.get("sequence_length"),
                mae=metrics.get("MAE"),
                rmse=metrics.get("RMSE"),
                r2=metrics.get("R2"),
                artifact_path=meta.get("artifact_path", ""),
                last_verified=datetime.utcnow(),
            )
            session.add(m_model)
        session.flush()
        logger.info("Database seeding complete.")
