"""GitLab MCP toolset.

Faultline talks to GitLab through the **official GitLab MCP server** (hosted
at ``<gitlab>/api/v4/mcp``) wired in via ADK's ``McpToolset``. This is the
load-bearing partner integration per the hackathon rules: commit/diff reads
AND issue/MR creation all flow through MCP.

Connection model
----------------
We default to the **Streamable HTTP** transport going straight at the GitLab
MCP endpoint, with a ``PRIVATE-TOKEN`` header carrying the user's GitLab
personal access token. This avoids needing a node runtime in Cloud Run.

If ``GITLAB_MCP_TRANSPORT=stdio`` is set, we fall back to launching
``npx mcp-remote`` as a child process (Claude Desktop's pattern). This is
useful for local dev environments where the streaming HTTP transport is
inconvenient.

Tool filtering
--------------
We only expose the tools the investigation policy actually uses. This keeps
the LLM's tool list focused and reduces the chance of stray actions:

  - ``search``                      : find recent commits/MRs touching a path
  - ``get_merge_request_commits``   : list commits for a given MR
  - ``get_merge_request_diffs``     : read the diff of an MR (step 4)
  - ``get_merge_request``           : MR metadata
  - ``create_issue``                : post the postmortem (step 7b)
  - ``create_merge_request``        : open the DRAFT rollback MR (step 7c)
"""

from __future__ import annotations

import logging
import os
from typing import Any


log = logging.getLogger(__name__)


# Tools we let the agent see. Keep narrow.
GITLAB_TOOL_ALLOWLIST: tuple[str, ...] = (
    "search",
    "get_merge_request_commits",
    "get_merge_request_diffs",
    "get_merge_request",
    "create_issue",
    "create_merge_request",
)


# Public so callers (tests, agent factory) can introspect what we'd send.
def gitlab_mcp_endpoint() -> str:
    """Resolve the MCP endpoint URL from env. Default: gitlab.com SaaS."""
    base = os.getenv("GITLAB_URL", "https://gitlab.com").rstrip("/")
    return f"{base}/api/v4/mcp"


def _require_token() -> str:
    token = os.getenv("GITLAB_TOKEN")
    if not token:
        raise RuntimeError(
            "GITLAB_TOKEN is not set. Put your GitLab personal access token "
            "in .env — never paste it in chat. Required scopes: api, "
            "read_repository, write_repository."
        )
    return token


def _http_connection_params() -> Any:
    """Build StreamableHTTPConnectionParams for the GitLab MCP endpoint."""
    from google.adk.tools.mcp_tool.mcp_session_manager import (
        StreamableHTTPConnectionParams,
    )

    return StreamableHTTPConnectionParams(
        url=gitlab_mcp_endpoint(),
        headers={"PRIVATE-TOKEN": _require_token()},
        timeout=10.0,
    )


def _stdio_connection_params() -> Any:
    """Build StdioConnectionParams launching `npx mcp-remote`.

    Used when GITLAB_MCP_TRANSPORT=stdio. mcp-remote bridges a stdio MCP
    client to a remote streamable-HTTP MCP server and supports passing
    custom headers via `--header`. We inject PRIVATE-TOKEN the same way.
    """
    from google.adk.tools.mcp_tool.mcp_session_manager import StdioConnectionParams
    from mcp import StdioServerParameters

    token = _require_token()
    endpoint = gitlab_mcp_endpoint()
    server_params = StdioServerParameters(
        command="npx",
        args=[
            "-y",
            "mcp-remote",
            endpoint,
            "--header",
            f"PRIVATE-TOKEN:{token}",
        ],
        env={**os.environ},
    )
    return StdioConnectionParams(server_params=server_params, timeout=15.0)


def build_gitlab_toolset() -> Any:
    """Return a configured ``McpToolset`` bound to the GitLab MCP server.

    Phase 4 plugs the return value into ``LlmAgent(tools=[...])`` alongside
    the telemetry function tools.
    """
    from google.adk.tools.mcp_tool import McpToolset

    transport = os.getenv("GITLAB_MCP_TRANSPORT", "http").strip().lower()
    if transport == "stdio":
        conn = _stdio_connection_params()
    elif transport in ("http", "streamable", "streamable_http"):
        conn = _http_connection_params()
    else:
        raise ValueError(
            f"Unknown GITLAB_MCP_TRANSPORT={transport!r}. Use 'http' or 'stdio'."
        )

    log.info(
        "GitLab MCP toolset configured (transport=%s, endpoint=%s, tools=%s)",
        transport,
        gitlab_mcp_endpoint(),
        ", ".join(GITLAB_TOOL_ALLOWLIST),
    )
    return McpToolset(
        connection_params=conn,
        tool_filter=list(GITLAB_TOOL_ALLOWLIST),
    )
