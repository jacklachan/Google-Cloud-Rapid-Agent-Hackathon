"""Phase-0 smoke tests.

These do not import anything that touches GCP, Vertex AI, or GitLab. They
only assert that the package layout is importable and the FastAPI app
exposes a working /health endpoint. Heavier tests arrive in phase 2+.
"""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_packages_importable() -> None:
    import agent  # noqa: F401
    import server  # noqa: F401
    import victim_service  # noqa: F401


def test_health_endpoint() -> None:
    from server.main import app

    client = TestClient(app)
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok", "phase": "0"}


def test_investigation_policy_loaded() -> None:
    from agent.prompt import INVESTIGATION_POLICY

    # Sanity-check the 8 numbered steps are baked into the prompt verbatim.
    for step in ("1. READ THE INCIDENT SIGNAL", "8. STOP."):
        assert step in INVESTIGATION_POLICY
