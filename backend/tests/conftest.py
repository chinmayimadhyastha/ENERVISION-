"""Shared pytest fixtures. One real application is loaded per test session."""

from __future__ import annotations

import sys
import warnings
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

warnings.filterwarnings("ignore")

from backend.app_factory import create_app  # noqa: E402
from backend.tests.helpers import ObservedWeatherProvider  # noqa: E402


@pytest.fixture(scope="session")
def app():
    application = create_app({"TESTING": True})
    yield application


@pytest.fixture(scope="session")
def client(app):
    return app.test_client()


@pytest.fixture(scope="session")
def container(app):
    return app.extensions["enervision"]


@pytest.fixture()
def observed_weather(container):
    return ObservedWeatherProvider(container)
