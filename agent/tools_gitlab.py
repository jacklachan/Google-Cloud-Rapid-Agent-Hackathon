"""GitLab MCP toolset configuration.

We do NOT reimplement GitLab API calls. We connect to the official GitLab MCP
server through ADK's MCP toolset support so commit reads, issue creation, and
merge-request creation are all load-bearing through MCP — per hackathon rules.

Filled in phase 3 after verifying current ADK MCP API from live Google docs.
"""

from __future__ import annotations

import os


def gitlab_mcp_config() -> dict[str, str]:
    """Return the env config needed to launch the GitLab MCP server.

    Phase 3 will turn this into an actual ADK MCPToolset instance. For now we
    only validate that the operator filled in the required env vars.
    """
    required = ("GITLAB_URL", "GITLAB_PROJECT_PATH", "GITLAB_TOKEN", "GITLAB_MCP_COMMAND")
    missing = [k for k in required if not os.getenv(k)]
    if missing:
        raise RuntimeError(
            f"GitLab MCP not configured. Missing env vars: {', '.join(missing)}. "
            "See .env.example."
        )
    return {k: os.environ[k] for k in required}
