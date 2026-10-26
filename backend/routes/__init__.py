"""API route registration."""

from __future__ import annotations

from flask import Flask

from backend.routes import (
    analytics,
    dashboard,
    forecasts,
    health,
    history,
    models,
    plants,
    weather,
)

BLUEPRINTS = (
    health.bp,
    plants.bp,
    history.bp,
    weather.bp,
    forecasts.bp,
    models.bp,
    dashboard.bp,
    analytics.bp,
)


def register_blueprints(app: Flask) -> None:
    for blueprint in BLUEPRINTS:
        app.register_blueprint(blueprint)
