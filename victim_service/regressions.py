"""Planted-regression toggles.

The agent's whole demo is "find the bug a recent commit caused." Rather than
patching code at demo time, we keep a small library of regressions selected
by the REGRESSION_MODE env var. In a real demo, the suspect commit is the
GitLab commit that *sets* REGRESSION_MODE in the Cloud Run config or that
imports a new dependency that triggers a path here.

Each regression simulates one of the symptom classes Faultline's policy
checks for:

    n_plus_one  -> latency creep (data service does many sequential queries)
    slow_query  -> latency creep (one slow operation)
    bad_dep     -> sudden 5xx spike (raises on every request)
    leaky       -> memory growth / crashloop (allocates and never frees)

Default is "off" so tests + clean deploys behave normally.
"""

from __future__ import annotations

import asyncio
import os
import time


_LEAK: list[bytes] = []  # noqa: F841 — intentional retained reference for `leaky` mode


def current_mode() -> str:
    return os.getenv("REGRESSION_MODE", "").strip().lower()


async def apply_data_regression() -> None:
    """Inject the configured regression into the data service request path."""
    mode = current_mode()
    if not mode:
        return

    if mode == "n_plus_one":
        # 25 sequential 8ms "queries" => ~200ms latency creep
        for _ in range(25):
            await asyncio.sleep(0.008)
        return

    if mode == "slow_query":
        # One blocking 600ms call — looks like a missing index
        time.sleep(0.6)
        return

    if mode == "bad_dep":
        # Simulate a new dependency that crashes on every request
        raise RuntimeError("bad_dep regression: new client lib raised on init")

    if mode == "leaky":
        # 1 MiB retained per request — Cloud Run will OOM after a few thousand
        _LEAK.append(b"x" * (1024 * 1024))
        return

    # Unknown mode => behave as off so a typo doesn't break the demo silently.
