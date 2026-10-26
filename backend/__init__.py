"""ENERVISION daily-forecasting REST API.

The package intentionally exposes only a factory.  Importing :mod:`backend`
must not load the 550 MB Random Forest artifact or TensorFlow; tests and the
Flask CLI create an application through :func:`backend.app.create_app`.
"""

__version__ = "1.0.0"
