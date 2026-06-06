"""Victim service tests — fake-mode, no network.

Each test exercises one role's app via FastAPI's TestClient. The frontend
test patches httpx so we never actually open a socket; it just verifies the
frontend correctly chains auth then data and proxies the responses up.
"""

from __future__ import annotations

import asyncio
import os
import time
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from fastapi.testclient import TestClient


# Force console-only OTel for the whole test module.
os.environ.setdefault("FAULTLINE_FAKE_TELEMETRY", "1")
os.environ.pop("GOOGLE_CLOUD_PROJECT", None)


def test_data_clean_path() -> None:
    os.environ.pop("REGRESSION_MODE", None)
    from victim_service.data import create_app

    client = TestClient(create_app())
    r = client.get("/items")
    assert r.status_code == 200
    payload = r.json()
    assert len(payload["items"]) == 3
    assert payload["regression_mode"] is None


def test_data_n_plus_one_adds_latency() -> None:
    os.environ["REGRESSION_MODE"] = "n_plus_one"
    try:
        from victim_service.data import create_app

        client = TestClient(create_app())
        t0 = time.monotonic()
        r = client.get("/items")
        elapsed = time.monotonic() - t0
        assert r.status_code == 200
        # 25 * 8ms = 200ms minimum. Generous lower bound for CI jitter.
        assert elapsed > 0.15, f"expected n_plus_one to add latency, got {elapsed:.3f}s"
    finally:
        del os.environ["REGRESSION_MODE"]


def test_data_bad_dep_returns_500() -> None:
    os.environ["REGRESSION_MODE"] = "bad_dep"
    try:
        from victim_service.data import create_app

        client = TestClient(create_app(), raise_server_exceptions=False)
        r = client.get("/items")
        assert r.status_code == 500
    finally:
        del os.environ["REGRESSION_MODE"]


def test_auth_rejects_bad_token() -> None:
    from victim_service.auth import create_app

    client = TestClient(create_app())
    assert client.get("/verify").status_code == 401
    assert client.get("/verify", headers={"x-auth-token": "wrong"}).status_code == 401
    assert client.get("/verify", headers={"x-auth-token": "demo-token"}).status_code == 200


def test_frontend_chains_auth_then_data() -> None:
    """Frontend should call auth, then data, then return both payloads."""
    calls: list[str] = []

    async def fake_get(self, url, *args, **kwargs):  # noqa: ANN001
        calls.append(url)
        if "/verify" in url:
            return httpx.Response(200, json={"ok": True}, request=httpx.Request("GET", url))
        if "/items" in url:
            return httpx.Response(
                200,
                json={"items": [{"id": 1, "name": "alpha"}], "regression_mode": None},
                request=httpx.Request("GET", url),
            )
        return httpx.Response(404, request=httpx.Request("GET", url))

    with patch.object(httpx.AsyncClient, "get", new=fake_get):
        from victim_service.frontend import create_app

        client = TestClient(create_app())
        r = client.get("/")

    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["auth"] == {"ok": True}
    assert body["data"]["items"][0]["name"] == "alpha"
    # Auth must be called before data.
    assert any("/verify" in c for c in calls)
    assert any("/items" in c for c in calls)
    assert calls.index(next(c for c in calls if "/verify" in c)) < calls.index(
        next(c for c in calls if "/items" in c)
    )


def test_main_dispatches_by_service_name() -> None:
    """The entrypoint module picks the right app based on SERVICE_NAME."""
    import importlib
    import sys

    for role, title in (("frontend", "victim-frontend"), ("auth", "victim-auth"), ("data", "victim-data")):
        os.environ["SERVICE_NAME"] = role
        # Force a re-import so _select_app() runs again.
        sys.modules.pop("victim_service.main", None)
        mod = importlib.import_module("victim_service.main")
        assert mod.app.title == title
    os.environ.pop("SERVICE_NAME", None)
