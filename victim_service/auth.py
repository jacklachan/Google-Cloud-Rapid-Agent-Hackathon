"""Victim auth service.

Trivial token check. Sits between frontend and data so Faultline has at least
one intermediate hop to walk past when it's looking for the true root cause.
"""

from __future__ import annotations

from fastapi import FastAPI, Header, HTTPException

from .telemetry import init_telemetry, instrument_app


_VALID_TOKEN = "demo-token"  # not a real secret — intentional demo placeholder


def create_app() -> FastAPI:
    init_telemetry("faultline-victim-auth")
    app = FastAPI(title="victim-auth")

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "service": "auth"}

    @app.get("/verify")
    def verify(x_auth_token: str | None = Header(default=None)) -> dict[str, bool]:
        if x_auth_token != _VALID_TOKEN:
            raise HTTPException(status_code=401, detail="bad token")
        return {"ok": True}

    instrument_app(app)
    return app


app = create_app()
