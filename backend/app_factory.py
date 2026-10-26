"""Flask application factory for the ENERVISION daily forecasting API."""

from __future__ import annotations

import logging
import os

from flask import Flask
from flask_cors import CORS

from backend.config import Config
from backend.container import ServiceContainer
from backend.routes import register_blueprints
from backend.utils.errors import register_error_handlers

os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "2")


def configure_logging(config: Config) -> None:
    level = getattr(logging, str(config.LOG_LEVEL).upper(), logging.INFO)
    root = logging.getLogger()
    if not root.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(
            logging.Formatter(
                "%(asctime)s %(levelname)s %(name)s: %(message)s",
                datefmt="%Y-%m-%dT%H:%M:%S",
            )
        )
        root.addHandler(handler)
    root.setLevel(level)
    for noisy in ("tensorflow", "keras", "absl"):
        logging.getLogger(noisy).setLevel(logging.ERROR)


def create_app(overrides: dict | None = None) -> Flask:
    """Build and fully initialize the API.

    All datasets, the Random Forest, both LSTMs and the four scalers are loaded
    before the first request.  If any required artifact is missing or contracts
    do not match, this function raises
    :class:`backend.utils.errors.ArtifactError` and the process refuses to start.
    """

    config = Config(overrides)
    configure_logging(config)

    app = Flask(__name__)
    app.config.update(
        ENERVISION_CONFIG=config,
        TESTING=bool(config.TESTING),
        PROPAGATE_EXCEPTIONS=False,
        JSON_SORT_KEYS=False,
        MAX_CONTENT_LENGTH=1024 * 1024,
    )
    app.json.ensure_ascii = False
    app.json.sort_keys = False

    CORS(
        app,
        resources={
            r"/api/*": {
                "origins": list(config.CORS_ORIGINS),
                "methods": ["GET", "OPTIONS"],
                "allow_headers": ["Content-Type"],
            }
        },
    )

    register_error_handlers(app)

    container = ServiceContainer(config)
    container.load()
    app.extensions["enervision"] = container

    register_blueprints(app)

    @app.after_request
    def _security_headers(response):
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        if response.content_type and "application/json" in response.content_type:
            response.headers.setdefault("Cache-Control", "no-store")
        return response

    logging.getLogger("enervision").info(
        "Flask application created with CORS origins %s", config.CORS_ORIGINS
    )
    return app
