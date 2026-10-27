"""WSGI entrypoint for production servers.

Example::

    waitress-serve --listen=0.0.0.0:5000 backend.wsgi:app
"""

from __future__ import annotations

from backend.app_factory import create_app

app = create_app()
