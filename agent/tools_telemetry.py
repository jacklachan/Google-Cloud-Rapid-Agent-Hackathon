"""Telemetry read tools.

These wrap Cloud Logging, Cloud Trace and Cloud Monitoring as ADK function
tools the agent can call during an investigation. A fake-mode toggle returns
canned data so pytest and local development never touch live GCP.

Filled with real implementations in phase 2.
"""

from __future__ import annotations

import os
from typing import Any


def _fake_mode() -> bool:
    return os.getenv("FAULTLINE_FAKE_TELEMETRY", "1") == "1"


def query_error_logs(service: str, window_minutes: int = 15) -> dict[str, Any]:
    """Return recent error logs for ``service`` over the last ``window_minutes``.

    Real implementation will hit Cloud Logging. Phase 2.
    """
    raise NotImplementedError("query_error_logs: implemented in phase 2")


def fetch_recent_traces(service: str, window_minutes: int = 15) -> dict[str, Any]:
    """Return a sample of recent traces touching ``service``.

    Real implementation will hit Cloud Trace. Phase 2.
    """
    raise NotImplementedError("fetch_recent_traces: implemented in phase 2")


def read_metric(service: str, metric: str, window_minutes: int = 15) -> dict[str, Any]:
    """Read a named metric series (error_rate, p95_latency_ms, mem_usage_mb).

    Real implementation will hit Cloud Monitoring. Phase 2.
    """
    raise NotImplementedError("read_metric: implemented in phase 2")


def list_dependency_edges(service: str) -> dict[str, Any]:
    """Return downstream services ``service`` calls, derived from trace data.

    Used by the agent to walk from the alerting service toward the root cause.
    Phase 2.
    """
    raise NotImplementedError("list_dependency_edges: implemented in phase 2")
