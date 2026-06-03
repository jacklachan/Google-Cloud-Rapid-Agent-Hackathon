"""FastAPI server wrapping the Faultline ADK agent.

Phase 5 wires the live agent and SSE streaming. Phase 6 mounts the web console
at /. Phase 7 adds the /approve endpoint that auto-merges the rollback MR via
GitLab MCP and triggers victim redeploy.

For phase 0 we expose a /health endpoint so the scaffold can be smoke-tested.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

app = FastAPI(title="Faultline", version="0.0.1-phase0")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "phase": "0"}


# Mount the web console at /. Phase 6 fills the static assets with real UI.
_WEB_DIR = Path(__file__).resolve().parent.parent / "web"
if _WEB_DIR.is_dir():
    app.mount("/", StaticFiles(directory=str(_WEB_DIR), html=True), name="web")
