"""Run the ENERVISION backend.

From the repository root::

    python backend/app.py

For the Flask CLI::

    flask --app backend.app_factory:create_app run --host 0.0.0.0 --port 5000
"""

from __future__ import annotations

import sys
from pathlib import Path

if __package__ in (None, ""):  # executed as ``python backend/app.py``
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.app_factory import create_app  # noqa: E402
from backend.utils.errors import ArtifactError  # noqa: E402


def main() -> int:
    try:
        app = create_app()
    except ArtifactError as exc:
        print(f"ENERVISION backend startup failed: {exc}", file=sys.stderr)
        return 1

    config = app.extensions["enervision"].config
    app.run(
        host=config.HOST,
        port=config.PORT,
        debug=config.DEBUG,
        threaded=True,
        use_reloader=False,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
