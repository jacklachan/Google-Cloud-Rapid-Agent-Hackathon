"""Tests for the agent telemetry tools (fake mode only).

These exercise the fixture path so we know:
  - the shape returned is what the agent will see, and
  - fixtures match the regression modes the agent's policy reasons about.
Real-mode (GCP) paths are not exercised here; phase 8 covers end-to-end.
"""

from __future__ import annotations

import os

import pytest


os.environ["FAULTLINE_FAKE_TELEMETRY"] = "1"
os.environ.pop("GOOGLE_CLOUD_PROJECT", None)


def _set_scenario(name: str) -> None:
    os.environ["FAULTLINE_FAKE_SCENARIO"] = name


def test_dependency_graph_shape() -> None:
    from agent.tools_telemetry import list_dependency_edges

    front = list_dependency_edges("faultline-victim-frontend")
    assert front["calls"] == ["faultline-victim-auth", "faultline-victim-data"]
    leaf = list_dependency_edges("faultline-victim-data")
    assert leaf["calls"] == []


def test_metric_anomaly_latency_creep() -> None:
    _set_scenario("n_plus_one")
    from agent.tools_telemetry import read_metric

    m = read_metric("faultline-victim-data", "p95_latency_ms")
    points = m["points"]
    head = sum(p["v"] for p in points[:5]) / 5
    tail = sum(p["v"] for p in points[-5:]) / 5
    assert tail > head * 2, f"expected latency creep (head={head}, tail={tail})"


def test_metric_anomaly_5xx_spike() -> None:
    _set_scenario("bad_dep")
    from agent.tools_telemetry import read_metric

    m = read_metric("faultline-victim-data", "error_rate")
    tail = sum(p["v"] for p in m["points"][-5:]) / 5
    assert tail > 0.5


def test_metric_anomaly_memory_growth() -> None:
    _set_scenario("leaky")
    from agent.tools_telemetry import read_metric

    m = read_metric("faultline-victim-data", "mem_usage_mb")
    tail = sum(p["v"] for p in m["points"][-5:]) / 5
    assert tail > 300


def test_error_logs_present_for_bad_dep() -> None:
    _set_scenario("bad_dep")
    from agent.tools_telemetry import query_error_logs

    logs = query_error_logs("faultline-victim-data")
    assert len(logs["entries"]) > 0
    assert "bad_dep" in logs["entries"][0]["msg"]


def test_error_logs_empty_for_clean_path() -> None:
    _set_scenario("n_plus_one")
    from agent.tools_telemetry import query_error_logs

    # Auth/frontend are never the source of the planted regression.
    assert query_error_logs("faultline-victim-auth")["entries"] == []


def test_traces_show_slow_data_span() -> None:
    _set_scenario("slow_query")
    from agent.tools_telemetry import fetch_recent_traces

    res = fetch_recent_traces("faultline-victim-frontend")
    assert res["traces"], "expected fake traces"
    # The slowest span should be on data, not frontend.
    for tr in res["traces"]:
        slowest = max(tr["spans"], key=lambda s: s["ms"])
        assert slowest["service"] == "faultline-victim-data"


def test_unknown_metric_raises() -> None:
    from agent.tools_telemetry import read_metric

    with pytest.raises(ValueError):
        read_metric("faultline-victim-data", "not_a_real_metric")
