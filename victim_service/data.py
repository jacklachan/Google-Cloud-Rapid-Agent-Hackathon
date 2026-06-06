"""Victim data service.

Returns a tiny JSON payload. This is the leaf of the chain and the most
common place we plant regressions (see regressions.py).
"""

from __future__ import annotations

from fastapi import FastAPI

from . import regressions
from .telemetry import init_telemetry, instrument_app


def create_app() -> FastAPI:
    init_telemetry("faultline-victim-data")
    app = FastAPI(title="victim-data")

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "service": "data"}

    @app.get("/items")
    async def items() -> dict[str, object]:
        await regressions.apply_data_regression()
        return {
            "items": [
                {"id": 1, "name": "alpha"},
                {"id": 2, "name": "beta"},
                {"id": 3, "name": "gamma"},
            ],
            "regression_mode": regressions.current_mode() or None,
        }

    instrument_app(app)
    return app


app = create_app()
