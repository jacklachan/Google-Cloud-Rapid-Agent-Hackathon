"""Faultline ADK agent factory.

Phase 4 will:
  - construct a google-adk Agent
  - configure Vertex AI backend with the model id from VERTEX_AI_MODEL
  - register telemetry tools from tools_telemetry as function tools
  - register the GitLab MCP toolset from tools_gitlab
  - set the system prompt to INVESTIGATION_POLICY from prompt.py

The exact ADK API surface will be verified against live Google docs before
implementation — model class names, MCPToolset signature, and Vertex backend
config have changed across ADK releases.
"""

from __future__ import annotations

import os

from .prompt import INVESTIGATION_POLICY


def build_agent():
    """Return a configured ADK agent. Implemented in phase 4."""
    model = os.getenv("VERTEX_AI_MODEL")
    if not model:
        raise RuntimeError(
            "VERTEX_AI_MODEL is not set. Pick the current Gemini model id from "
            "Vertex AI docs and put it in .env (see .env.example)."
        )
    _ = INVESTIGATION_POLICY  # will be used as system_instruction in phase 4
    raise NotImplementedError("build_agent: implemented in phase 4")
