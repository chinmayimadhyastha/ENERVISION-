"""Unit tests for SQLAlchemy database and seed operations."""

from __future__ import annotations

from backend.db.models import ModelRegistryModel, PlantModel
from backend.db.seed import seed_database


def test_database_initialization_and_seeding(container):
    assert container.db is not None
    container.db.create_tables()
    seed_database(container.db, container.data, container.manifest)

    with container.db.session() as session:
        plant_count = session.query(PlantModel).count()
        assert plant_count == 37

        koppal = session.query(PlantModel).filter_by(plant_id="koppal-tpsaurya-s").first()
        assert koppal is not None
        assert koppal.plant_name == "KOPPAL_TPSAURYA_S"
        assert koppal.type == "Solar"
        assert koppal.capacity_mw == 131.0
        assert koppal.has_coordinates is True
        assert koppal.latitude is not None

        models = session.query(ModelRegistryModel).all()
        assert len(models) >= 3
        model_ids = {m.model_id for m in models}
        assert "random_forest_daily" in model_ids
        assert "solar_lstm_daily" in model_ids
        assert "wind_lstm_daily" in model_ids
