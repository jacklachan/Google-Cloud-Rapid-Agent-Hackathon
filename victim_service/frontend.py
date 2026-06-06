"""Victim frontend service.

Entry point for the load generator (and any human poking the demo). Calls
auth, then data, then composes the response. Auth and data URLs are passed
in via env vars so the same image can wire into three Cloud Run services.
"""

from __future__ import annotations

import os

import httpx
from fastapi import FastAPI, HTTPException

from .telemetry import init_telemetry, instrument_app


# Defaults are localhost so `pytest` works without env config; in Cloud Run
# we set these to the auth/data Cloud Run URLs.
def _auth_url() -> str:
    return os.getenv("AUTH_URL", "http://127.0.0.1:8082")


def _data_url() -> str:
    return os.getenv("DATA_URL", "http://127.0.0.1:8083")


def create_app() -> FastAPI:
    init_telemetry("faultline-victim-frontend")
    app = FastAPI(title="victim-frontend")

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "service": "frontend"}

    @app.get("/")
    async def root() -> dict[str, object]:
        timeout = httpx.Timeout(5.0)
        async with httpx.AsyncClient(timeout=timeout) as client:
            auth_resp = await client.get(
                f"{_auth_url()}/verify",
                headers={"x-auth-token": "demo-token"},
            )
            if auth_resp.status_code != 200:
                raise HTTPException(status_code=502, detail="auth failed")

            data_resp = await client.get(f"{_data_url()}/items")
            if data_resp.status_code >= 500:
                raise HTTPException(status_code=502, detail="data failed")

        return {
            "ok": True,
            "auth": auth_resp.json(),
            "data": data_resp.json(),
        }

    instrument_app(app)
    return app


app = create_app()
