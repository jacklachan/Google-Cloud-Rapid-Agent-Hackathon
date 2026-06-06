"""Victim service entrypoint.

The same Docker image runs all three roles. Cloud Run sets SERVICE_NAME
(frontend | auth | data) per service. We import the matching FastAPI app
and let uvicorn serve it.

We expose ``app`` as a module attribute so the Dockerfile CMD can be a flat
``uvicorn victim_service.main:app --host 0.0.0.0 --port $PORT``.
"""

from __future__ import annotations

import os


def _select_app():
    role = os.getenv("SERVICE_NAME", "frontend").strip().lower()
    if role == "frontend":
        from .frontend import app as a
        return a
    if role == "auth":
        from .auth import app as a
        return a
    if role == "data":
        from .data import app as a
        return a
    raise RuntimeError(
        f"Unknown SERVICE_NAME={role!r}. Expected one of: frontend, auth, data."
    )


app = _select_app()
