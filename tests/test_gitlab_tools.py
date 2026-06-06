"""Tests for tools_gitlab.py (no live GitLab calls).

These verify the toolset wiring — endpoint URL, header injection, transport
selection, and the tool allowlist — by patching the ADK MCPToolset / connection
classes. The actual MCP round-trip is exercised by scripts/gitlab_smoke.py
(which the user runs once a real token lives in .env).
"""

from __future__ import annotations

import importlib
import os
import sys
import types
from unittest.mock import MagicMock

import pytest


# We need to stub the google.adk + mcp modules before importing tools_gitlab,
# because Python 3.14 may not have the full ADK stack installed in this venv.
# The stubs let us assert on the parameters tools_gitlab passes through.


def _install_stubs() -> dict[str, MagicMock]:
    """Install minimal google.adk + mcp stubs. Return the mock objects."""
    captured: dict[str, MagicMock] = {}

    # mcp.StdioServerParameters
    mcp_mod = types.ModuleType("mcp")
    mcp_mod.StdioServerParameters = MagicMock(name="StdioServerParameters")
    captured["StdioServerParameters"] = mcp_mod.StdioServerParameters

    # google.adk.tools.mcp_tool.mcp_session_manager.{StreamableHTTPConnectionParams,StdioConnectionParams}
    g = types.ModuleType("google")
    g_adk = types.ModuleType("google.adk")
    g_adk_tools = types.ModuleType("google.adk.tools")
    g_adk_tools_mcp = types.ModuleType("google.adk.tools.mcp_tool")
    g_adk_tools_mcp_mgr = types.ModuleType(
        "google.adk.tools.mcp_tool.mcp_session_manager"
    )
    g_adk_tools_mcp_mgr.StreamableHTTPConnectionParams = MagicMock(
        name="StreamableHTTPConnectionParams"
    )
    g_adk_tools_mcp_mgr.StdioConnectionParams = MagicMock(name="StdioConnectionParams")
    g_adk_tools_mcp.McpToolset = MagicMock(name="McpToolset")
    captured["StreamableHTTPConnectionParams"] = (
        g_adk_tools_mcp_mgr.StreamableHTTPConnectionParams
    )
    captured["StdioConnectionParams"] = g_adk_tools_mcp_mgr.StdioConnectionParams
    captured["McpToolset"] = g_adk_tools_mcp.McpToolset

    sys.modules["mcp"] = mcp_mod
    sys.modules["google"] = g
    sys.modules["google.adk"] = g_adk
    sys.modules["google.adk.tools"] = g_adk_tools
    sys.modules["google.adk.tools.mcp_tool"] = g_adk_tools_mcp
    sys.modules["google.adk.tools.mcp_tool.mcp_session_manager"] = g_adk_tools_mcp_mgr
    return captured


@pytest.fixture(autouse=True)
def _isolate_env(monkeypatch):
    monkeypatch.setenv("GITLAB_TOKEN", "glpat-test-fake")
    monkeypatch.delenv("GITLAB_URL", raising=False)
    monkeypatch.delenv("GITLAB_MCP_TRANSPORT", raising=False)
    # Force a fresh import of tools_gitlab each test.
    sys.modules.pop("agent.tools_gitlab", None)
    yield


def _fresh_import():
    return importlib.import_module("agent.tools_gitlab")


def test_endpoint_defaults_to_gitlab_com(monkeypatch):
    _install_stubs()
    mod = _fresh_import()
    assert mod.gitlab_mcp_endpoint() == "https://gitlab.com/api/v4/mcp"


def test_endpoint_respects_custom_gitlab_url(monkeypatch):
    monkeypatch.setenv("GITLAB_URL", "https://gitlab.example.com/")
    _install_stubs()
    mod = _fresh_import()
    assert mod.gitlab_mcp_endpoint() == "https://gitlab.example.com/api/v4/mcp"


def test_missing_token_raises(monkeypatch):
    monkeypatch.delenv("GITLAB_TOKEN", raising=False)
    _install_stubs()
    mod = _fresh_import()
    with pytest.raises(RuntimeError, match="GITLAB_TOKEN"):
        mod.build_gitlab_toolset()


def test_http_transport_passes_private_token_header():
    captured = _install_stubs()
    mod = _fresh_import()
    mod.build_gitlab_toolset()

    captured["StreamableHTTPConnectionParams"].assert_called_once()
    kwargs = captured["StreamableHTTPConnectionParams"].call_args.kwargs
    assert kwargs["url"] == "https://gitlab.com/api/v4/mcp"
    assert kwargs["headers"] == {"PRIVATE-TOKEN": "glpat-test-fake"}


def test_http_transport_filters_to_allowlist():
    captured = _install_stubs()
    mod = _fresh_import()
    mod.build_gitlab_toolset()

    captured["McpToolset"].assert_called_once()
    kwargs = captured["McpToolset"].call_args.kwargs
    assert kwargs["tool_filter"] == list(mod.GITLAB_TOOL_ALLOWLIST)
    # Sanity: allowlist contains the four critical ops + the diff reader.
    assert "create_issue" in kwargs["tool_filter"]
    assert "create_merge_request" in kwargs["tool_filter"]
    assert "get_merge_request_diffs" in kwargs["tool_filter"]
    assert "search" in kwargs["tool_filter"]


def test_stdio_transport_uses_mcp_remote(monkeypatch):
    monkeypatch.setenv("GITLAB_MCP_TRANSPORT", "stdio")
    captured = _install_stubs()
    mod = _fresh_import()
    mod.build_gitlab_toolset()

    captured["StdioServerParameters"].assert_called_once()
    kwargs = captured["StdioServerParameters"].call_args.kwargs
    assert kwargs["command"] == "npx"
    assert "mcp-remote" in kwargs["args"]
    assert "https://gitlab.com/api/v4/mcp" in kwargs["args"]
    # PRIVATE-TOKEN passed via --header for mcp-remote
    header_idx = kwargs["args"].index("--header")
    assert kwargs["args"][header_idx + 1] == "PRIVATE-TOKEN:glpat-test-fake"


def test_unknown_transport_raises(monkeypatch):
    monkeypatch.setenv("GITLAB_MCP_TRANSPORT", "smoke-signals")
    _install_stubs()
    mod = _fresh_import()
    with pytest.raises(ValueError, match="GITLAB_MCP_TRANSPORT"):
        mod.build_gitlab_toolset()
